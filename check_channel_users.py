#!/usr/bin/env python3
"""
Вспомогательный скрипт для проверки наличия пользователей в канале
Использует переменные окружения TELEGRAM_API_TOKEN и COMPANY_CHANNEL_ID
"""
import os
import asyncio
import csv
import glob
from pathlib import Path
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from config import logger, API_TOKEN, COMPANY_CHANNEL_ID

# Список уволенных ID (можно вынести в отдельный файл или переменную среды)
FIRED_IDS = {190998836, 1508750069, 1800297798, 7995910481}

async def check_user_in_channel(bot: Bot, channel_id: str, user_id: int) -> bool:
    """Проверяет, является ли пользователь участником канала"""
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        return member.status not in ['left', 'kicked']
    except TelegramAPIError as e:
        if "user not found" in str(e).lower() or "chat not found" in str(e).lower():
            return False
        logger.warning(f"Ошибка при проверке пользователя {user_id}: {e}")
        return False

def find_latest_users_file() -> str:
    """Находит самый свежий файл all_users в папке data"""
    pattern = "data/all_users_*.csv"
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError("Не найдены файлы all_users_*.csv в папке data")
    
    # Сортируем по дате в имени файла и берем самый свежий
    latest_file = max(files, key=lambda x: Path(x).stem.split('_')[-1])
    logger.info(f"Найден файл: {latest_file}")
    return latest_file

def read_users_from_csv(filename: str) -> list[dict]:
    """Читает пользователей из CSV файла"""
    users = []
    with open(filename, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            users.append(row)
    logger.info(f"Прочитано {len(users)} пользователей из {filename}")
    return users

def write_users_to_csv(users: list[dict], filename: str):
    """Записывает пользователей в CSV файл с новыми колонками"""
    if not users:
        logger.warning("Нет данных для записи")
        return
    
    # Добавляем новые колонки если их нет
    fieldnames = list(users[0].keys())
    if 'InChannel' not in fieldnames:
        fieldnames.append('InChannel')
    if 'Match' not in fieldnames:
        fieldnames.append('Match')
    if 'Fired' not in fieldnames:
        fieldnames.append('Fired')
    
    # Создаем новый файл с суффиксом _checked
    base_name = Path(filename).stem
    new_filename = f"data/{base_name}_checked.csv"
    
    with open(new_filename, 'w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(users)
    
    logger.info(f"Результат сохранен в {new_filename}")

async def main():
    """Основная функция"""
    logger.info("=== Начало проверки пользователей в канале ===")
    
    # Проверяем переменные окружения
    if not API_TOKEN:
        logger.error("Не задан TELEGRAM_API_TOKEN")
        return
    
    if not COMPANY_CHANNEL_ID:
        logger.error("Не задан COMPANY_CHANNEL_ID")
        return
    
    # Инициализируем бота
    bot = Bot(token=API_TOKEN)
    
    try:
        # Находим и читаем файл с пользователями
        users_file = find_latest_users_file()
        users = read_users_from_csv(users_file)
        
        # Получаем общее количество участников канала для справки
        try:
            member_count = await bot.get_chat_member_count(COMPANY_CHANNEL_ID)
            logger.info(f"Общее количество участников канала: {member_count}")
        except TelegramAPIError as e:
            logger.warning(f"Не удалось получить количество участников: {e}")
        
        # Проверяем каждого пользователя
        processed_count = 0
        for user in users:
            user_id = int(user['UserID'])
            
            # Проверяем наличие в канале
            in_channel = await check_user_in_channel(bot, COMPANY_CHANNEL_ID, user_id)
            user['InChannel'] = 'Да' if in_channel else 'Нет'
            
            # Проверяем совпадение Approve и InChannel
            approve_status = user.get('Approve', 'Нет')
            match = (approve_status == 'Да' and in_channel) or (approve_status == 'Нет' and not in_channel)
            user['Match'] = 'Да' if match else 'Нет'
            
            # Fired
            user['Fired'] = 'Да' if user_id in FIRED_IDS else 'Нет'
            
            processed_count += 1
            
            if processed_count % 10 == 0:
                logger.info(f"Обработано {processed_count} пользователей...")
            
            # Небольшая задержка чтобы не превысить лимиты API
            await asyncio.sleep(0.1)
        
        # Записываем результат
        write_users_to_csv(users, users_file)
        
        # Статистика
        total_users = len(users)
        in_channel_count = sum(1 for u in users if u['InChannel'] == 'Да')
        match_count = sum(1 for u in users if u['Match'] == 'Да')
        
        logger.info(f"=== Статистика ===")
        logger.info(f"Всего пользователей: {total_users}")
        logger.info(f"В канале: {in_channel_count}")
        logger.info(f"Не в канале: {total_users - in_channel_count}")
        logger.info(f"Совпадения: {match_count}")
        logger.info(f"Несовпадения: {total_users - match_count}")
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении: {e}")
    finally:
        # Закрываем сессию бота
        await bot.session.close()
        logger.info("Сессия бота закрыта")

if __name__ == "__main__":
    asyncio.run(main()) 