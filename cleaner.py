#!/usr/bin/env python3
"""
cleaner.py
Запускается раз в сутки в 07:30.

Изменения:
 - В начале проверяем ряд условий (check_if_need_to_skip).
 - Если что-то не так, записываем в SyncHistory причину skip и выходим.
 - Иначе чистим тех, у кого Approve=FALSE, Banned=FALSE.
 - Пишем запись в SyncHistory.
"""
import asyncio
import aiosqlite
from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()
from config import logger, API_TOKEN, DB_PATH 

# Импортируем из need_clean.py
from utils.need_clean import (
    check_if_need_to_skip,
    ensure_comment_column,
    write_skip_history,
    get_eligible_groups,
)

import asyncio
import aiosqlite
from pathlib import Path
from config import logger, DB_PATH
from utils.file_ops import parse_csv_users  # Функция для чтения user_id из CSV-файла

async def check_import_users_in_db(db: aiosqlite.Connection):
    """
    Проверяет, все ли user_id из последнего импорта присутствуют в таблице Users.
    Возвращает True, если всё в порядке, и False, если есть расхождения.
    """
    # 1. Находим имя файла последнего импорта из SyncHistory
    cursor = await db.execute("""
        SELECT FileName
        FROM SyncHistory
        WHERE SyncType='import'
        AND Comment='success'
        AND SyncDate >= DATETIME('now', '-12 hours')
        ORDER BY SyncDate DESC
        LIMIT 1
    """)
    row = await cursor.fetchone()
    if not row:
        logger.warning("Нет записей об успешном импорте за 12 часов.")
        await write_skip_history(db, "Нет записей об успешном импорте за 12 часов.")
        return False  # Если импорта не было, продолжаем работу

    import_filename = row[0]
    archived_path = Path("./import/archived") / import_filename

    if not archived_path.is_file():
        logger.error(f"Файл {archived_path} не найден в архиве.")
        await write_skip_history(db, f"Файл {archived_path} не найден в архиве.")
        return False
    
    # 2. Читаем user_id из файла импорта
    # Превращаем «./import/archived/…» в путь относительно ./import:
    archived_rel = archived_path.relative_to("./import")
    import_user_ids = set(parse_csv_users(str(archived_rel)))
    if not import_user_ids:
        logger.warning("Не удалось прочитать user_id из файла импорта.")
        await write_skip_history(db, "Не удалось прочитать user_id из файла импорта.")
        return False

    # 3. Получаем user_id из таблицы Users
    cursor = await db.execute("SELECT UserID FROM Users")
    db_user_ids = set(row[0] for row in await cursor.fetchall())

    # 4. Проверяем, все ли user_id из импорта есть в базе
    missing_ids = import_user_ids - db_user_ids
    if missing_ids:
        logger.error(f"В базе отсутствуют user_id из импорта: {missing_ids}")
        await write_skip_history(db, f"В базе отсутствуют user_id из импорта: {missing_ids}")
        return False
    else:
        logger.info("Все user_id из импорта присутствуют в базе.")
        return True

async def main():
    logger.info("=== [cleaner.py] Запущен сценарий очистки ===")

    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем наличие всех user_id из импорта в базе
        if not await check_import_users_in_db(db):
            logger.error("Очистка прервана.")
            return
        
        await ensure_comment_column(db)

        # Проверяем, нужно ли пропускать cleaner.py
        skip, skip_reason = await check_if_need_to_skip(db)
        if skip:
            logger.info(f"SKIP cleaner: {skip_reason}")
            await write_skip_history(db, skip_reason)
            return

        # Если дошли сюда - значит, мы НЕ пропускаем чистку
        bot = Bot(token=API_TOKEN)
        removed_count = 0
        try:
            # 1) Список групп, где бот может ограничивать
            eligible_groups = await get_eligible_groups(db)
            if not eligible_groups:
                logger.info("Нет групп с необходимыми правами (can_restrict_members=TRUE). Выходим.")
                await write_skip_history(db, "No groups with restrict_members")
                return

            # 2) Ищем всех, кто Approve=FALSE AND Banned=FALSE
            cursor = await db.execute("""
                SELECT UserID
                  FROM Users
                 WHERE Approve=FALSE
                   AND Banned=FALSE
            """)
            unapproved_users = await cursor.fetchall()
            if not unapproved_users:
                logger.info("Нет пользователей Approve=FALSE и Banned=FALSE. Выходим.")
                await db.execute("""
                    INSERT INTO SyncHistory (SyncType, FileName, RecordCount, SyncDate, Comment)
                    VALUES (?, ?, ?, DATETIME('now'), ?)
                """, ("cleaner", "-", 0, "no unapproved users"))
                await db.commit()
                return

            logger.info(f"Найдено {len(unapproved_users)} пользователей для удаления из групп.")

            # 3) Удаляем этих пользователей из групп
            removed_count = 0
            for (user_id,) in unapproved_users:
                logger.info(f"[cleaner.py] Type of eligible_groups: {type(eligible_groups)}")
                logger.info(f"[cleaner.py] First 5 elements in eligible_groups: {eligible_groups[:5] if eligible_groups else 'EMPTY'}")
                for chat_id in eligible_groups:
                    try:
                        await bot.ban_chat_member(chat_id, user_id)
                        logger.info(f"[cleaner] Удалён user_id={user_id} из чата={chat_id}")
                        removed_count += 1
                    except Exception as e:
                        logger.warning(f"[cleaner] Не удалось удалить user_id={user_id} из {chat_id}: {e}")

                # Ставим Banned=TRUE
                await db.execute("""
                    UPDATE Users
                       SET Banned=TRUE
                     WHERE UserID=?
                """, (user_id,))

            await db.commit()

            # 4) Пишем в SyncHistory
            await db.execute("""
                INSERT INTO SyncHistory (SyncType, FileName, RecordCount, SyncDate, Comment)
                VALUES (?, ?, ?, DATETIME('now'), ?)
            """, ("cleaner", "-", removed_count, "ok"))
            await db.commit()

        except Exception as e:
            logger.exception(f"Неожиданная ошибка в cleaner.py: {e}")
        finally:
            await bot.session.close()
            logger.info(f"Сессия бота закрыта. Удалено {removed_count} записей (ban).")

if __name__ == "__main__":
    asyncio.run(main())
