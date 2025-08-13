import asyncio
import aiosqlite
from aiogram import Bot
from config import logger, DB_PATH, EXCLUDED_EMAILS, WORK_MAIL, API_TOKEN, COMPANY_CHANNEL_ID
from database import get_user_email
from utils.unban import unban_user
from combine.reply import get_restoration_invite_link
from combine.answer import status_restored

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
        restored_users = []

        # Создаем бота для отправки сообщений
        bot = Bot(token=API_TOKEN)

        try:
            for (user_id,) in all_users:
                email = await get_user_email(user_id)
                if not email:
                    continue

                email_lower = email.strip().lower()
                
                if email_lower in excluded_emails_lower:
                    # Пользователь в исключениях - проверяем нужно ли восстановление
                    cursor_check = await db.execute("""
                        SELECT Approve, Banned, WasApproved FROM Users WHERE UserID = ?
                    """, (user_id,))
                    current_status = await cursor_check.fetchone()
                    
                    if current_status:
                        approve, banned, was_approved = current_status
                        
                        # Условие для восстановления: Approve=FALSE, WasApproved=TRUE, Banned=TRUE
                        if not approve and was_approved and banned:
                            logger.info(f"Найден пользователь для восстановления: {user_id}:{email}")
                            
                            # 1. Разбаниваем пользователя во всех группах
                            await unban_user(user_id)
                            
                            # 2. Устанавливаем Approve=TRUE, Banned=FALSE
                            await db.execute("""
                                UPDATE Users 
                                SET Approve = TRUE, Banned = FALSE 
                                WHERE UserID = ?
                            """, (user_id,))
                            
                            # 3. Отправляем уведомление и приглашение
                            try:
                                invite_markup = await get_restoration_invite_link(bot, COMPANY_CHANNEL_ID)
                                if invite_markup:
                                    await bot.send_message(
                                        chat_id=user_id,
                                        text=status_restored,
                                        parse_mode="Markdown",
                                        reply_markup=invite_markup
                                    )
                                    logger.info(f"Отправлено уведомление о восстановлении пользователю {user_id}:{email}")
                                else:
                                    logger.error(f"Не удалось создать ссылку восстановления для {user_id}:{email}")
                            except Exception as e:
                                logger.error(f"Ошибка при отправке уведомления пользователю {user_id}:{email}: {e}")
                            
                            restored_users.append(user_id)
                            approved_count += 1
                        else:
                            # Обычное обновление для исключенных пользователей
                            await unban_user(user_id)
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
        finally:
            await bot.session.close()

        # Фиксируем изменения в базе
        await db.commit()

        # Запись в SyncHistory
        total_processed = approved_count + unapproved_count
        if total_processed > 0 or restored_users:
            comment_parts = []
            if approved_count > 0:
                comment_parts.append(f"Approved: {approved_count}")
            if unapproved_count > 0:
                comment_parts.append(f"Unapproved: {unapproved_count}")
            if restored_users:
                comment_parts.append(f"Restored: {len(restored_users)}")
            
            comment = "; ".join(comment_parts)
            
            await db.execute("""
                INSERT INTO SyncHistory (SyncType, FileName, RecordCount, SyncDate, Comment)
                VALUES (?, ?, ?, DATETIME('now', 'localtime'), ?)
            """, ("exclusion_check", "-", total_processed, comment))
            await db.commit()
            
            if restored_users:
                logger.info(f"Восстановлено {len(restored_users)} забаненных исключенных пользователей: {restored_users}")
            logger.info(f"Проверка исключений завершена. {comment}, Всего: {total_processed}")
        else:
            logger.info("Изменений при проверке исключений не требовалось.")