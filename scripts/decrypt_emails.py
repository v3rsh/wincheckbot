#!/usr/bin/env python3
"""
Скрипт для расшифровки email'ов в базе данных.
Заменяет зашифрованные email'ы на расшифрованные.
"""

import asyncio
import aiosqlite
import sys
import os

# Добавляем корневую директорию в путь для импорта модулей
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import logger, DB_PATH
from utils.crypto import decrypt_email
from utils.mask import mask_email

async def decrypt_all_emails():
    """
    Расшифровывает все email'ы в базе данных и заменяет их на расшифрованные.
    """
    logger.info("=== Начало расшифровки email'ов в базе данных ===")
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем всех пользователей с email'ами
        cursor = await db.execute("SELECT UserID, Email FROM Users WHERE Email IS NOT NULL AND Email != ''")
        users = await cursor.fetchall()
        
        if not users:
            logger.info("Нет пользователей с email'ами для расшифровки.")
            return
        
        logger.info(f"Найдено {len(users)} пользователей с email'ами.")
        
        decrypted_count = 0
        error_count = 0
        
        for user_id, encrypted_email in users:
            try:
                # Пытаемся расшифровать email
                decrypted_email = decrypt_email(encrypted_email)
                
                if decrypted_email:
                    # Обновляем email в базе данных
                    await db.execute(
                        "UPDATE Users SET Email = ? WHERE UserID = ?",
                        (decrypted_email, user_id)
                    )
                    decrypted_count += 1
                    
                    # Логируем с маской для безопасности
                    masked_email = mask_email(decrypted_email)
                    logger.info(f"Расшифрован email для пользователя {user_id}: {masked_email}")
                else:
                    logger.warning(f"Не удалось расшифровать email для пользователя {user_id}")
                    error_count += 1
                    
            except Exception as e:
                logger.error(f"Ошибка при расшифровке email для пользователя {user_id}: {e}")
                error_count += 1
        
        # Фиксируем изменения
        await db.commit()
        
        logger.info(f"=== Расшифровка завершена ===")
        logger.info(f"Успешно расшифровано: {decrypted_count}")
        logger.info(f"Ошибок: {error_count}")
        
        # Записываем в историю синхронизации
        await db.execute("""
            INSERT INTO SyncHistory (SyncType, FileName, RecordCount, SyncDate, Comment)
            VALUES (?, ?, ?, DATETIME('now', 'localtime'), ?)
        """, ("decrypt_emails", "-", decrypted_count, f"Расшифровка email'ов (ошибок: {error_count})"))
        await db.commit()

async def verify_decryption():
    """
    Проверяет, что все email'ы успешно расшифрованы.
    """
    logger.info("=== Проверка расшифровки email'ов ===")
    
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT UserID, Email FROM Users WHERE Email IS NOT NULL AND Email != ''")
        users = await cursor.fetchall()
        
        if not users:
            logger.info("Нет пользователей с email'ами для проверки.")
            return
        
        encrypted_count = 0
        decrypted_count = 0
        
        for user_id, email in users:
            # Проверяем, является ли email зашифрованным (hex строка)
            try:
                # Если это hex строка, пытаемся расшифровать
                if len(email) > 32 and all(c in '0123456789abcdefABCDEF' for c in email):
                    # Пытаемся расшифровать
                    decrypted = decrypt_email(email)
                    if decrypted and decrypted != email:
                        encrypted_count += 1
                        masked_email = mask_email(email)
                        logger.warning(f"Найден зашифрованный email для пользователя {user_id}: {masked_email}")
                    else:
                        decrypted_count += 1
                else:
                    decrypted_count += 1
            except:
                decrypted_count += 1
        
        logger.info(f"Проверка завершена:")
        logger.info(f"Расшифрованных email'ов: {decrypted_count}")
        logger.info(f"Зашифрованных email'ов: {encrypted_count}")
        
        if encrypted_count == 0:
            logger.info("✅ Все email'ы успешно расшифрованы!")
        else:
            logger.warning(f"⚠️ Найдено {encrypted_count} зашифрованных email'ов")

async def main():
    """
    Основная функция скрипта.
    """
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        await verify_decryption()
    else:
        await decrypt_all_emails()
        # После расшифровки проверяем результат
        await verify_decryption()

if __name__ == "__main__":
    asyncio.run(main()) 