#!/usr/bin/env python3
"""
cleaner.py
Запускается раз в сутки в 07:30.

Изменения:
1) Проверяем все записи из Groups (ChatID):
   - Используем новые колонки для определения прав.
   - Не удаляем записи из базы при ошибках, а просто логируем.
2) Ищем всех, у кого Approve=FALSE
3) Удаляем их из групп, где у бота есть необходимые права (используем новые колонки)
4) Пишем запись в SyncHistory
"""

import asyncio
import aiosqlite

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from config import logger, API_TOKEN, DB_PATH

async def main():
    logger.info("=== [cleaner.py] Проверяем права в группах и удаляем unapproved-пользователей ===")

    bot = Bot(token=API_TOKEN)
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # 1) Читаем все чаты из Groups с их административными правами
            cursor = await db.execute("""
                SELECT ChatID, can_restrict_members
                FROM Groups
            """)
            all_groups = await cursor.fetchall()
            if not all_groups:
                logger.info("Таблица Groups пуста. Выходим.")
                return

            # Список групп, где бот может ограничивать участников
            eligible_groups = []
            for (chat_id, can_restrict_members) in all_groups:
                if can_restrict_members:
                    eligible_groups.append(chat_id)
                else:
                    logger.info(f"Чат {chat_id} не имеет необходимых прав (can_restrict_members=False). Пропускаем.")

            if not eligible_groups:
                logger.info("Нет групп с необходимыми правами. Выходим.")
                return

            # 2) Ищем всех, кто Approve=FALSE
            cursor = await db.execute("""
                SELECT UserID
                FROM Users
                WHERE Approve=FALSE
            """)
            unapproved_users = await cursor.fetchall()
            if not unapproved_users:
                logger.info("Нет пользователей Approve=FALSE. Выходим.")
                return

            logger.info(f"Найдено {len(unapproved_users)} пользователей для удаления из групп.")

            # 3) Удаляем unapproved пользователей из eligible_groups
            removed_count = 0
            for (user_id,) in unapproved_users:
                for (chat_id,) in eligible_groups:
                    try:
                        # ban + unban (aiogram 3.x)
                        await bot.ban_chat_member(chat_id, user_id)
                        await bot.unban_chat_member(chat_id, user_id)
                        logger.info(f"Удалён user_id={user_id} из чата={chat_id}")
                        removed_count += 1
                    except Exception as e:
                        logger.warning(f"Не удалось удалить user_id={user_id} из {chat_id}: {e}")

            # 4) Пишем в SyncHistory
            await db.execute("""
                INSERT INTO SyncHistory (SyncType, FileName, RecordCount, SyncDate)
                VALUES (?, ?, ?, DATETIME('now'))
            """, ("cleaner", "-", removed_count))
            await db.commit()

        logger.info(f"=== Удалено {removed_count} записей (ban+unban) ===")

    except Exception as e:
        logger.exception(f"Неожиданная ошибка в cleaner.py: {e}")

    finally:
        await bot.session.close()
        logger.info("Сессия бота закрыта.")

if __name__ == "__main__":
    asyncio.run(main())
