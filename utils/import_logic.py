# utils/import_logic.py

import aiosqlite
from config import logger, DB_PATH, EXCLUDED_EMAILS
from database import get_user_email

async def process_unapproved_in_db(active_user_ids: set[int], in_filename: str) -> list[int]:
    """
    Ставим Approve=FALSE тем, у кого Approve=TRUE и Synced=TRUE но кто не в active_user_ids.
    Пропускаем (не трогаем) тех, у кого email в EXCLUDED_EMAILS.
    Возвращаем список user_id, кому сброшен Approve.
    """
    changed_users = []
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT UserID, Email FROM Users
             WHERE Approve=TRUE
              AND Synced=TRUE
        """)
        rows = await cursor.fetchall()

        for user_id, enc_email in rows:
            if user_id not in active_user_ids:
                # Проверяем email
                plain_email = await get_user_email(user_id)
                email_lower = plain_email.strip().lower()
                if email_lower in [ex.strip().lower() for ex in EXCLUDED_EMAILS if ex.strip()]:
                    continue
                # Иначе снимаем Approve
                changed_users.append(user_id)

        if changed_users:
            placeholders = ",".join("?" * len(changed_users))
            query = f"""
                UPDATE Users
                   SET Approve=FALSE,
                       WasApproved=TRUE,
                       Banned=FALSE
                 WHERE UserID IN ({placeholders})
            """
            await db.execute(query, tuple(changed_users))
            await db.commit()
            logger.info(f"Approve=FALSE выставлен для {len(changed_users)} пользователей.")
        else:
            logger.info("Никого не перевели на Approve=FALSE.")

    return changed_users

async def restore_banned_users(active_user_ids: set[int]) -> list[int]:
    """
    Восстанавливаем доступ пользователям, которые ранее были забанены или потеряли доступ, 
    но присутствуют в новом списке активных пользователей.
    
    Для таких пользователей устанавливаем:
    - Approve = TRUE (разрешаем доступ)
    - Synced = TRUE (помечаем как синхронизированных)
    - Banned = FALSE (снимаем бан)
    
    Возвращает список ID пользователей, которым восстановлен доступ.
    """
    restored_users = []
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем всех пользователей, которым нужно восстановить доступ
        # (они есть в списке активных, но у них Approve=FALSE)
        cursor = await db.execute("""
            SELECT UserID FROM Users
            WHERE Approve=FALSE 
              AND UserID IN ({})
        """.format(','.join('?' * len(active_user_ids))), tuple(active_user_ids))
        
        rows = await cursor.fetchall()
        
        if rows:
            # Извлекаем ID пользователей из результатов запроса
            users_to_restore = [row[0] for row in rows]
            
            # Восстанавливаем доступ пользователям
            query = """
                UPDATE Users
                SET Approve=TRUE,
                    Synced=TRUE,
                    Banned=FALSE
                WHERE UserID IN ({})
            """.format(','.join('?' * len(users_to_restore)))
            
            await db.execute(query, tuple(users_to_restore))
            await db.commit()
            
            logger.info(f"Восстановлен доступ для {len(users_to_restore)} пользователей.")
            restored_users = users_to_restore
        else:
            logger.info("Нет пользователей для восстановления доступа.")
    
    return restored_users
