#!/usr/bin/env python3
# names.py - скрипт для добавления данных Username, FirstName и LastName существующим пользователям

import asyncio
import aiosqlite
from config import DB_PATH, API_TOKEN, logger
from aiogram import Bot

async def update_users_data():
    """
    Функция обновляет данные пользователей (Username, FirstName, LastName) 
    для всех существующих пользователей в базе данных.
    """
    logger.info("Запуск обновления данных пользователей")
    bot = Bot(token=API_TOKEN)
    
    # Получаем всех пользователей без данных
    async with aiosqlite.connect(DB_PATH) as db:
        # Получаем список UserID всех пользователей
        cursor = await db.execute("""
            SELECT UserID FROM Users
        """)
        users = await cursor.fetchall()
        
        if not users:
            logger.info("Пользователи в базе не найдены")
            return
            
        logger.info(f"Найдено {len(users)} пользователей в базе")
        
        update_count = 0
        error_count = 0
        
        # Обновляем данные для каждого пользователя
        for user_row in users:
            user_id = user_row[0]
            
            try:
                # Получаем информацию о пользователе из Telegram
                user = await bot.get_chat(user_id)
                
                # Обновляем запись в базе данных
                await db.execute("""
                    UPDATE Users 
                    SET Username = ?, FirstName = ?, LastName = ? 
                    WHERE UserID = ?
                """, (user.username, user.first_name, user.last_name, user_id))
                
                update_count += 1
                logger.info(f"Обновлены данные пользователя {user_id}: username={user.username}, first_name={user.first_name}, last_name={user.last_name}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"Ошибка при получении данных пользователя {user_id}: {e}")
                
        await db.commit()
        logger.info(f"Обновление завершено. Успешно: {update_count}, с ошибками: {error_count}")

async def main():
    try:
        await update_users_data()
    except Exception as e:
        logger.error(f"Ошибка при выполнении скрипта: {e}")
    finally:
        logger.info("Скрипт завершен")

if __name__ == "__main__":
    asyncio.run(main()) 