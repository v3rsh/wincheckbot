import asyncio
import aiosqlite
from config import logger, DB_PATH, EXCLUDED_EMAILS, WORK_MAIL
from database import get_user_email

async def check_exclusions():
    logger.info("=== Начало проверки исключений при старте бота ===")
    async with aiosqlite.connect(DB_PATH) as db:
        # Приводим исключения к нижнему регистру для корректного сравнения
        excluded_emails_lower = [email.strip().lower() for email in EXCLUDED_EMAILS if email.strip()]
        
        if not excluded_emails_lower:
            logger.info("EXCLUDED_EMAILS пуст, проверка исключений пропущена.")
            return

        logger.info(f"Список исключений: {excluded_emails_lower}")
        
        # 1. Сначала устанавливаем Approve=TRUE, Banned=FALSE для всех пользователей из EXCLUDED_EMAILS
        cursor = await db.execute("SELECT UserID FROM Users")
        all_users = await cursor.fetchall()
        
        approved_count = 0
        unapproved_count = 0

        for (user_id,) in all_users:
            email = await get_user_email(user_id)
            if not email:
                continue

            email_lower = email.strip().lower()
            
            if email_lower in excluded_emails_lower:
                # Пользователь в исключениях - устанавливаем Approve=TRUE, Banned=FALSE
                await db.execute("""
                    UPDATE Users 
                    SET Approve = TRUE, Banned = FALSE 
                    WHERE UserID = ?
                """, (user_id,))
                logger.info(f"Пользователь {user_id}:{email} из EXCLUDED_EMAILS - установлен Approve=TRUE, Banned=FALSE")
                approved_count += 1
                
            elif not email_lower.endswith(f"@{WORK_MAIL.lower()}"):
                # Email не корпоративный и не в исключениях - снимаем доступ
                cursor_check = await db.execute("SELECT Approve FROM Users WHERE UserID = ?", (user_id,))
                current_status = await cursor_check.fetchone()
                
                if current_status and current_status[0] == 1:  # Если был Approve=TRUE
                    await db.execute("UPDATE Users SET Approve = FALSE WHERE UserID = ?", (user_id,))
                    logger.info(f"Пользователь {user_id}:{email} не соответствует домену и не в исключениях - установлен Approve=FALSE")
                    unapproved_count += 1

        # Фиксируем изменения в базе
        await db.commit()

        # Запись в SyncHistory
        total_processed = approved_count + unapproved_count
        if total_processed > 0:
            await db.execute("""
                INSERT INTO SyncHistory (SyncType, FileName, RecordCount, SyncDate, Comment)
                VALUES (?, ?, ?, DATETIME('now', 'localtime'), ?)
            """, ("exclusion_check", "-", total_processed, f"Approved: {approved_count}, Unapproved: {unapproved_count}"))
            await db.commit()
            logger.info(f"Проверка исключений завершена. Approved: {approved_count}, Unapproved: {unapproved_count}, Всего: {total_processed}")
        else:
            logger.info("Изменений при проверке исключений не требовалось.")