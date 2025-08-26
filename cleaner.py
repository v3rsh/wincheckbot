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
from config import logger, API_TOKEN, DB_PATH, EXCLUDED_EMAILS, MAINTENANCE_MODE
from database import get_emails_by_user_ids, get_group_titles_by_chat_ids, get_user_email 

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
        AND Comment LIKE 'success%'
        AND SyncDate >= DATETIME('now', 'localtime', '-12 hours')
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

async def clean_new_groups(db: aiosqlite.Connection, bot: Bot):
    """
    Очищает все группы с пометкой New=TRUE от пользователей с Approve=FALSE
    Возвращает (количество_удаленных, список_забаненных_user_id)
    """
    # Получаем список новых групп
    cursor = await db.execute("""
        SELECT ChatID
        FROM Groups
        WHERE New=TRUE AND can_restrict_members=TRUE
    """)
    new_groups = [row[0] for row in await cursor.fetchall()]
    
    if not new_groups:
        logger.info("Нет новых групп для полной очистки")
        return 0, []

    # Получаем всех пользователей с Approve=FALSE
    cursor = await db.execute("""
        SELECT UserID
        FROM Users
        WHERE Approve=FALSE
    """)
    unapproved_users = [row[0] for row in await cursor.fetchall()]
    
    if not unapproved_users:
        logger.info("Нет пользователей с Approve=FALSE для очистки новых групп")
        return 0, []
    
    # Фильтруем пользователей: исключаем тех, кто в EXCLUDED_EMAILS
    filtered_users = []
    for user_id in unapproved_users:
        plain_email = await get_user_email(user_id)
        if plain_email:
            email_lower = plain_email.strip().lower()
            if email_lower in [ex.strip().lower() for ex in EXCLUDED_EMAILS if ex.strip()]:
                logger.info(f"[clean_new_groups] Пользователь {user_id}:{plain_email} пропущен - в EXCLUDED_EMAILS")
                continue
        filtered_users.append(user_id)
    
    if not filtered_users:
        logger.info("После фильтрации EXCLUDED_EMAILS не осталось пользователей для очистки новых групп")
        return 0, []

    # Получаем email пользователей и названия групп пакетно
    user_emails = await get_emails_by_user_ids(filtered_users)
    group_titles = await get_group_titles_by_chat_ids(new_groups)
    
    removed_count = 0
    banned_users = []
    
    for chat_id in new_groups:
        group_name = group_titles.get(chat_id, f"Group_{chat_id}")
        for user_id in filtered_users:
            try:
                user_email = user_emails.get(user_id, "")
                if MAINTENANCE_MODE == "1":
                    # Симуляция удаления в режиме отладки
                    logger.info(f"[cleaner:new_groups] [SIMULATION] Удалён user_id={user_id}:{user_email} из нового чата={chat_id}:{group_name}")
                else:
                    # Реальное удаление в рабочем режиме
                    await bot.ban_chat_member(chat_id, user_id)
                    logger.info(f"[cleaner:new_groups] Удалён user_id={user_id}:{user_email} из нового чата={chat_id}:{group_name}")
                removed_count += 1
                if user_id not in banned_users:
                    banned_users.append(user_id)
            except Exception as e:
                user_email = user_emails.get(user_id, "")
                if MAINTENANCE_MODE == "1":
                    logger.warning(f"[cleaner:new_groups] [SIMULATION] Не удалось удалить user_id={user_id}:{user_email} из {chat_id}:{group_name}: {e}")
                else:
                    logger.warning(f"[cleaner:new_groups] Не удалось удалить user_id={user_id}:{user_email} из {chat_id}:{group_name}: {e}")

        # Снимаем пометку New с группы
        await db.execute("""
            UPDATE Groups
            SET New=FALSE
            WHERE ChatID=?
        """, (chat_id,))
        await db.commit()
        logger.info(f"Группа {chat_id}:{group_name} очищена и помечена как не новая")

    return removed_count, banned_users

async def main():
    logger.info("=== [cleaner.py] Запущен сценарий очистки ===")
    if MAINTENANCE_MODE == "1":
        logger.info("🔧 РЕЖИМ ОТЛАДКИ: Все операции ban_chat_member будут симулированы")
    else:
        logger.info("⚡ РАБОЧИЙ РЕЖИМ: Будут выполнены реальные операции удаления")

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
        regular_removed_count = 0
        new_groups_removed_count = 0

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
            unapproved_users = [row[0] for row in await cursor.fetchall()]
            if not unapproved_users:
                logger.info("Нет пользователей Approve=FALSE и Banned=FALSE. Выходим.")
                await db.execute("""
                    INSERT INTO SyncHistory (SyncType, FileName, RecordCount, SyncDate, Comment)
                    VALUES (?, ?, ?, DATETIME('now', 'localtime'), ?)
                """, ("cleaner", "-", 0, "no unapproved users"))
                await db.commit()
                return

            logger.info(f"Найдено {len(unapproved_users)} пользователей для проверки и удаления из групп.")

            # Фильтруем пользователей: исключаем тех, кто в EXCLUDED_EMAILS
            filtered_users = []
            excluded_users = []
            
            for user_id in unapproved_users:
                plain_email = await get_user_email(user_id)
                if plain_email:
                    email_lower = plain_email.strip().lower()
                    if email_lower in [ex.strip().lower() for ex in EXCLUDED_EMAILS if ex.strip()]:
                        excluded_users.append(user_id)
                        logger.info(f"Пользователь {user_id}:{plain_email} пропущен - в EXCLUDED_EMAILS")
                        continue
                filtered_users.append(user_id)
            
            if excluded_users:
                logger.info(f"Исключено из очистки {len(excluded_users)} пользователей из EXCLUDED_EMAILS.")
            
            if not filtered_users:
                logger.info("После фильтрации EXCLUDED_EMAILS не осталось пользователей для удаления.")
                await db.execute("""
                    INSERT INTO SyncHistory (SyncType, FileName, RecordCount, SyncDate, Comment)
                    VALUES (?, ?, ?, DATETIME('now', 'localtime'), ?)
                """, ("cleaner", "-", 0, "no users after EXCLUDED_EMAILS filter"))
                await db.commit()
                return

            logger.info(f"После фильтрации осталось {len(filtered_users)} пользователей для удаления из групп.")

            # Получаем email пользователей и названия групп пакетно
            user_emails = await get_emails_by_user_ids(filtered_users)
            group_titles = await get_group_titles_by_chat_ids(eligible_groups)

            # 3) Удаляем отфильтрованных пользователей из групп
            regular_removed_count = 0
            regular_banned_users = []
            
            for user_id in filtered_users:
                user_email = user_emails.get(user_id, "")
                for chat_id in eligible_groups:
                    group_name = group_titles.get(chat_id, f"Group_{chat_id}")
                    try:
                        if MAINTENANCE_MODE == "1":
                            # Симуляция удаления в режиме отладки
                            logger.info(f"[cleaner] [SIMULATION] Удалён user_id={user_id}:{user_email} из чата={chat_id}:{group_name}")
                        else:
                            # Реальное удаление в рабочем режиме
                            await bot.ban_chat_member(chat_id, user_id)
                            logger.info(f"[cleaner] Удалён user_id={user_id}:{user_email} из чата={chat_id}:{group_name}")
                    except Exception as e:
                        if MAINTENANCE_MODE == "1":
                            logger.warning(f"[cleaner] [SIMULATION] Не удалось удалить user_id={user_id}:{user_email} из {chat_id}:{group_name}: {e}")
                        else:
                            logger.warning(f"[cleaner] Не удалось удалить user_id={user_id}:{user_email} из {chat_id}:{group_name}: {e}")

                # Ставим Banned=TRUE
                await db.execute("""
                    UPDATE Users
                       SET Banned=TRUE
                     WHERE UserID=?
                """, (user_id,))
                regular_removed_count += 1
                regular_banned_users.append(user_id)

            await db.commit()

            # 4) Очистка новых групп
            new_groups_removed_count, new_groups_banned_users = await clean_new_groups(db, bot)
            
            # 5) Формируем комментарий для SyncHistory
            all_banned_users = list(set(regular_banned_users + new_groups_banned_users))
            total_removed = regular_removed_count + new_groups_removed_count
            
            # Формируем комментарий с указанием режима работы
            mode_prefix = "[SIMULATION] " if MAINTENANCE_MODE == "1" else ""
            
            if all_banned_users:
                banned_emails = await get_emails_by_user_ids(all_banned_users)
                banned_list = ", ".join(f"{uid}:{banned_emails.get(uid, '')}" for uid in all_banned_users)
                comment = f"{mode_prefix}regular:{regular_removed_count}, new_groups:{new_groups_removed_count}; banned: {len(all_banned_users)} ({banned_list})"
            else:
                comment = f"{mode_prefix}regular:{regular_removed_count}, new_groups:{new_groups_removed_count}"
            
            # Пишем в SyncHistory общий результат
            await db.execute("""
                INSERT INTO SyncHistory (SyncType, FileName, RecordCount, SyncDate, Comment)
                VALUES (?, ?, ?, DATETIME('now', 'localtime'), ?)
            """, ("cleaner", "-", total_removed, comment))
            await db.commit()

        except Exception as e:
            logger.exception(f"Неожиданная ошибка в cleaner.py: {e}")
        finally:
            await bot.session.close()
            mode_text = "симулировано" if MAINTENANCE_MODE == "1" else "выполнено"
            if 'all_banned_users' in locals() and all_banned_users:
                logger.info(f"Сессия бота закрыта. {mode_text.capitalize()} всего {total_removed} удалений (regular:{regular_removed_count}, new_groups:{new_groups_removed_count}). Забанено пользователей: {len(all_banned_users)}")
            else:
                logger.info(f"Сессия бота закрыта. {mode_text.capitalize()} всего удалений: 0")

if __name__ == "__main__":
    asyncio.run(main())
