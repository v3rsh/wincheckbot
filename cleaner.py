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
from config import logger, API_TOKEN, DB_PATH 

# Импортируем из need_clean.py
from utils.need_clean import (
    check_if_need_to_skip,
    ensure_comment_column,
    write_skip_history,
    get_eligible_groups,
)

async def main():
    logger.info("=== [cleaner.py] Запущен сценарий очистки ===")

    async with aiosqlite.connect(DB_PATH) as db:
        # Убедимся, что в таблице SyncHistory есть колонка Comment
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
