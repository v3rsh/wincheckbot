import asyncio
import aiosqlite
from config import logger, DB_PATH, EXCLUDED_EMAILS, WORK_MAIL
from database import get_user_email

async def check_exclusions():
    logger.info("=== Начало проверки исключений при старте бота ===")
    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем всех пользователей с Approve = TRUE
        cursor = await db.execute("SELECT UserID FROM Users WHERE Approve = TRUE")
        users = await cursor.fetchall()

        # Приводим исключения к нижнему регистру для корректного сравнения
        excluded_emails_lower = [email.lower() for email in EXCLUDED_EMAILS]
        processed_count = 0

        # Проверяем каждого пользователя
        for (user_id,) in users:
            email = await get_user_email(user_id)
            if not email:
                continue

            email_lower = email.lower()
            if not email_lower.endswith(f"@{WORK_MAIL.lower()}") and email_lower not in excluded_emails_lower:
                # Email не соответствует домену и не в исключениях
                await db.execute("UPDATE Users SET Approve = FALSE WHERE UserID = ?", (user_id,))
                logger.info(f"Пользователь {user_id} с email {email} не соответствует домену и не в исключениях. Статус Approve обновлен на FALSE.")
                processed_count += 1

                # Дополнительно: оповещение в чат (если нужно)
                # await send_chat_notification(f"Пользователь {user_id} ({email}) исключен из активных.")

        # Фиксируем изменения в базе
        await db.commit()

        # Запись в SyncHistory
        if processed_count > 0:
            await db.execute("""
                INSERT INTO SyncHistory (SyncType, FileName, RecordCount, SyncDate, Comment)
                VALUES (?, ?, ?, DATETIME('now', 'localtime'), ?)
            """, ("exclusion_check", "-", processed_count, "Проверка исключений при старте"))
            await db.commit()
            logger.info(f"Обработано {processed_count} пользователей при проверке исключений.")