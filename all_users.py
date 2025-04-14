#!/usr/bin/env python3
# all_users.py - скрипт для экспорта данных пользователей в CSV

import asyncio
import aiosqlite
import csv
from config import DB_PATH, logger
from datetime import datetime

async def export_users_to_csv():
    """
    Функция экспортирует данные пользователей (UserID, Username, FirstName, LastName, Approve)
    в CSV файл для последующего анализа менеджером компании.
    """
    logger.info("Запуск экспорта данных пользователей в CSV")
    
    # Формируем имя файла с текущей датой
    current_date = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"all_users_{current_date}.csv"
    
    # Получаем данные пользователей из базы
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row  # Чтобы получать результаты в виде словаря
        
        cursor = await db.execute("""
            SELECT UserID, Username, FirstName, LastName, Approve 
            FROM Users
            ORDER BY Approve DESC, UserID
        """)
        
        users = await cursor.fetchall()
        
        if not users:
            logger.info("Пользователи в базе не найдены")
            return
            
        logger.info(f"Найдено {len(users)} пользователей в базе")
        
        # Записываем данные в CSV
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            # Определяем заголовки
            fieldnames = ['UserID', 'Username', 'FirstName', 'LastName', 'Approve']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # Записываем заголовок
            writer.writeheader()
            
            # Записываем данные пользователей
            for user in users:
                writer.writerow({
                    'UserID': user['UserID'],
                    'Username': user['Username'] or '',  # Защита от None
                    'FirstName': user['FirstName'] or '',
                    'LastName': user['LastName'] or '',
                    'Approve': 'Да' if user['Approve'] else 'Нет'
                })
        
        logger.info(f"Данные {len(users)} пользователей экспортированы в файл {csv_filename}")
        return csv_filename

async def main():
    try:
        filename = await export_users_to_csv()
        if filename:
            print(f"\nФайл успешно создан: {filename}")
            print("\nФайл содержит следующие данные:")
            print("- UserID: идентификатор пользователя в Telegram")
            print("- Username: никнейм пользователя")
            print("- FirstName: имя пользователя")
            print("- LastName: фамилия пользователя")
            print("- Approve: статус верификации (Да/Нет)")
            print("\nЭти данные можно использовать для удаления неактивных пользователей из чатов.")
    except Exception as e:
        logger.error(f"Ошибка при выполнении скрипта: {e}")
    finally:
        logger.info("Скрипт завершен")

if __name__ == "__main__":
    asyncio.run(main()) 