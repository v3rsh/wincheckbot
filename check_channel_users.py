#!/usr/bin/env python3
"""
Вспомогательный скрипт для проверки наличия пользователей в канале
Использует переменные окружения TELEGRAM_API_TOKEN и COMPANY_CHANNEL_ID
Работает с файлом data/list_to_clean.csv
"""
import os
import asyncio
import csv
from pathlib import Path
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

# Отладка: проверяем загрузку переменных до импорта config
print(f"До импорта config - TELEGRAM_API_TOKEN из os.environ: {os.environ.get('TELEGRAM_API_TOKEN', 'НЕ НАЙДЕН')}")

from config import logger, API_TOKEN, COMPANY_CHANNEL_ID

print(f"После импорта config - API_TOKEN: {API_TOKEN}")
print(f"После импорта config - COMPANY_CHANNEL_ID: {COMPANY_CHANNEL_ID}")


async def check_bot_permissions(bot: Bot, channel_id: str) -> bool:
    """Проверяет права бота в канале"""
    try:
        # Получаем информацию о боте в канале
        bot_member = await bot.get_chat_member(channel_id, bot.id)
        
        logger.info(f"Статус бота в канале: {bot_member.status}")
        
        if bot_member.status not in ['administrator', 'creator']:
            logger.error("Бот не является администратором канала")
            return False
        
        # Проверяем конкретные права (если бот администратор)
        if hasattr(bot_member, 'can_restrict_members'):
            logger.info(f"Может просматривать участников: {getattr(bot_member, 'can_restrict_members', 'Неизвестно')}")
        
        # Пробуем получить количество участников (тест функциональности)
        try:
            member_count = await bot.get_chat_member_count(channel_id)
            logger.info(f"Тест: количество участников канала: {member_count}")
        except TelegramAPIError as e:
            logger.error(f"Бот не может получить информацию об участниках: {e}")
            return False
        
        logger.info("✓ Права бота проверены успешно")
        return True
        
    except TelegramAPIError as e:
        logger.error(f"Ошибка при проверке прав бота: {e}")
        return False

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

def read_users_from_csv(filename: str) -> list[dict]:
    """Читает пользователей из CSV файла с разделителем ;"""
    users = []
    with open(filename, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file, delimiter=';')
        for row in reader:
            # Очищаем пробелы в значениях
            cleaned_row = {key.strip(): value.strip() for key, value in row.items()}
            users.append(cleaned_row)
    logger.info(f"Прочитано {len(users)} пользователей из {filename}")
    return users

def write_users_to_csv(users: list[dict], filename: str):
    """Записывает пользователей в CSV файл с разделителем ;"""
    if not users:
        logger.warning("Нет данных для записи")
        return
    
    fieldnames = list(users[0].keys())
    
    with open(filename, 'w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        writer.writerows(users)
    
    logger.info(f"Результат сохранен в {filename}")

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
    logger.info(f"COMPANY_CHANNEL_ID: {COMPANY_CHANNEL_ID}, API_TOKEN: {API_TOKEN}")
    # Инициализируем бота
    bot = Bot(token=API_TOKEN)
    
    try:
        # Проверяем права бота в канале
        logger.info("Проверка прав бота в канале...")
        if not await check_bot_permissions(bot, COMPANY_CHANNEL_ID):
            logger.error("Недостаточно прав для работы с каналом. Завершение работы.")
            return
        
        # Работаем с фиксированным файлом
        users_file = "data/list_to_clean.csv"
        
        if not Path(users_file).exists():
            logger.error(f"Файл {users_file} не найден")
            return
        
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
            user['in channel'] = str(in_channel)
            
            processed_count += 1
            
            if processed_count % 10 == 0:
                logger.info(f"Обработано {processed_count} пользователей...")
            
            # Небольшая задержка чтобы не превысить лимиты API
            await asyncio.sleep(0.1)
        
        # Записываем результат обратно в тот же файл
        write_users_to_csv(users, users_file)
        
        # Статистика
        total_users = len(users)
        in_channel_count = sum(1 for u in users if u['in channel'] == 'True')
        
        logger.info(f"=== Статистика ===")
        logger.info(f"Всего пользователей: {total_users}")
        logger.info(f"В канале: {in_channel_count}")
        logger.info(f"Не в канале: {total_users - in_channel_count}")
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении: {e}")
    finally:
        # Закрываем сессию бота
        await bot.session.close()
        logger.info("Сессия бота закрыта")

if __name__ == "__main__":
    asyncio.run(main()) 