import asyncio
import aiosqlite
from aiogram import Bot
from config import logger, DB_PATH, EXCLUDED_EMAILS, WORK_MAIL, COMPANY_CHANNEL_ID
from utils.unban import unban_user
from combine.reply import get_restoration_invite_link
from combine.answer import status_restored

async def process_excluded_users(db, excluded_emails_lower, bot):
    """Обрабатывает пользователей из EXCLUDED_EMAILS согласно их статусам."""
    restored_count = 0
    unbanned_count = 0
    approved_count = 0
    restored_users = []
    
    # Получаем всех пользователей с их email и статусами одним запросом
    cursor = await db.execute("""
        SELECT UserID, Email, Approve, Banned, WasApproved FROM Users 
        WHERE Email IS NOT NULL AND Email != ''
    """)
    all_users = await cursor.fetchall()
    
    logger.info(f"Проверяем {len(all_users)} пользователей для исключений...")
    
    for user_id, email, approve, banned, was_approved in all_users:
        logger.info(f"Обрабатываем пользователя {user_id}:{email}")
        if not email:
            logger.info(f"Пропускаем {user_id} - нет email")
            continue
            
        email_lower = email.strip().lower()
        if email_lower not in excluded_emails_lower:
            logger.info(f"Пропускаем {user_id} - email не в исключениях")
            continue
        
        logger.info(f"Пользователь {user_id} найден в исключениях, статус: approve={approve}, banned={banned}, was_approved={was_approved}")
        
        # Логика обработки по статусам:
        if approve and not banned:
            # Approve=TRUE, Banned=FALSE - ничего не делать
            continue
            
        elif approve and banned:
            # Approve=TRUE, Banned=TRUE - профилактический unban
            await unban_user(user_id, bot)
            await db.execute("UPDATE Users SET Banned = FALSE WHERE UserID = ?", (user_id,))
            logger.info(f"Профилактический unban для {user_id}:{email}")
            unbanned_count += 1
            
        elif not approve and banned and was_approved:
            # Approve=FALSE, Banned=TRUE, WasApproved=TRUE - полное восстановление
            await unban_user(user_id, bot)
            await db.execute("""
                UPDATE Users SET Approve = TRUE, Banned = FALSE WHERE UserID = ?
            """, (user_id,))
            
            # Отправляем уведомление о восстановлении
            logger.info(f"Начинаем отправку уведомления для {user_id}:{email}")
            try:
                logger.info(f"Создаем ссылку восстановления для {user_id}")
                invite_markup = await get_restoration_invite_link(bot, COMPANY_CHANNEL_ID)
                logger.info(f"Ссылка создана для {user_id}, markup: {invite_markup is not None}")
                
                if invite_markup:
                    logger.info(f"Отправляем сообщение пользователю {user_id}")
                    await bot.send_message(
                        chat_id=user_id,
                        text=status_restored,
                        parse_mode="Markdown",
                        reply_markup=invite_markup
                    )
                    logger.info(f"Полное восстановление {user_id}:{email} - отправлено уведомление")
                else:
                    logger.error(f"Не удалось создать ссылку восстановления для {user_id}:{email}")
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления {user_id}:{email}: {e}")
            
            restored_users.append(user_id)
            restored_count += 1
            
        elif not approve and banned and not was_approved:
            # Approve=FALSE, Banned=TRUE, WasApproved=FALSE - только unban
            await unban_user(user_id, bot)
            await db.execute("""
                UPDATE Users SET Approve = TRUE, Banned = FALSE WHERE UserID = ?
            """, (user_id,))
            logger.info(f"Unban и активация для {user_id}:{email}")
            unbanned_count += 1
            
        elif not approve and not banned:
            # Approve=FALSE, Banned=FALSE - установка Approve=TRUE
            await unban_user(user_id, bot)
            await db.execute("UPDATE Users SET Approve = TRUE WHERE UserID = ?", (user_id,))
            logger.info(f"Активация для {user_id}:{email}")
            approved_count += 1
    
    return restored_count, unbanned_count, approved_count, restored_users

async def process_non_corporate_emails(db):
    """Снимает доступ у пользователей с некорпоративными email."""
    excluded_emails_lower = [email.strip().lower() for email in EXCLUDED_EMAILS if email.strip()]
    unapproved_count = 0
    
    # Получаем всех пользователей с их email и статусом одним запросом
    cursor = await db.execute("SELECT UserID, Email, Approve FROM Users WHERE Email IS NOT NULL AND Email != ''")
    all_users = await cursor.fetchall()
    
    logger.info(f"Проверяем {len(all_users)} пользователей с email...")
    
    for user_id, email, approve in all_users:
        if not email:
            continue
            
        email_lower = email.strip().lower()
        
        # Проверяем только некорпоративные email, не входящие в исключения
        if (not email_lower.endswith(f"@{WORK_MAIL.lower()}") and 
            email_lower not in excluded_emails_lower):
            
            if approve == 1:  # Если был Approve=TRUE
                await db.execute("UPDATE Users SET Approve = FALSE WHERE UserID = ?", (user_id,))
                logger.info(f"Снят доступ у {user_id}:{email} - некорпоративный email")
                unapproved_count += 1
    
    return unapproved_count

async def check_exclusions(bot: Bot):
    logger.info("=== Начало проверки исключений при старте бота ===")
    async with aiosqlite.connect(DB_PATH) as db:
        # Приводим исключения к нижнему регистру для корректного сравнения
        excluded_emails_lower = [email.strip().lower() for email in EXCLUDED_EMAILS if email.strip()]
        
        if not excluded_emails_lower:
            logger.info("EXCLUDED_EMAILS пуст, выполняем только проверку некорпоративных email.")
        else:
            logger.info(f"Список исключений: {excluded_emails_lower}")

        # 1. Обрабатываем исключенных пользователей
        if excluded_emails_lower:
            restored_count, unbanned_count, approved_count, restored_users = await process_excluded_users(
                db, excluded_emails_lower, bot
            )
        else:
            restored_count = unbanned_count = approved_count = 0
            restored_users = []
        
        # 2. Обрабатываем некорпоративные email
        logger.info("Начинаем обработку некорпоративных email...")
        unapproved_count = await process_non_corporate_emails(db)
        logger.info(f"Обработка некорпоративных email завершена. Результат: {unapproved_count}")
        
        # Фиксируем изменения в базе
        logger.info("Фиксируем изменения в базе данных...")
        await db.commit()
        logger.info("Изменения в БД зафиксированы")
        logger.info("=== Обработка исключений полностью завершена ===")

        # Запись в SyncHistory
        total_excluded_processed = restored_count + unbanned_count + approved_count
        total_processed = total_excluded_processed + unapproved_count
        
        if total_processed > 0:
            comment_parts = []
            if restored_count > 0:
                comment_parts.append(f"Restored: {restored_count}")
            if unbanned_count > 0:
                comment_parts.append(f"Unbanned: {unbanned_count}")
            if approved_count > 0:
                comment_parts.append(f"Approved: {approved_count}")
            if unapproved_count > 0:
                comment_parts.append(f"Unapproved: {unapproved_count}")
            
            comment = "; ".join(comment_parts)
            
            await db.execute("""
                INSERT INTO SyncHistory (SyncType, FileName, RecordCount, SyncDate, Comment)
                VALUES (?, ?, ?, DATETIME('now', 'localtime'), ?)
            """, ("exclusion_check", "-", total_processed, comment))
            await db.commit()
            
            if restored_users:
                logger.info(f"Восстановлено {len(restored_users)} пользователей: {restored_users}")
            
            logger.info(f"Проверка исключений завершена. {comment}, Всего: {total_processed}")
        else:
            logger.info("Изменений при проверке исключений не требовалось.")