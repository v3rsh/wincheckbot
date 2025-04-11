import asyncio
from aiogram import Bot, Dispatcher
from config import API_TOKEN, logger
from database import initialize_db
from exclusions import check_exclusions
from handlers import (
    start_handler, check_handler, manual_handler, 
    email_handler, code_handler, confirm_handler, #callback_handler, 
    general_handler, group_handler, block_handler,
    chat_handler
)
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
from redis.asyncio import Redis

async def main():
    logger.info("Запуск бота.")
    await initialize_db()
    await check_exclusions()
    # Инициализация бота и диспетчера
    bot = Bot(token=API_TOKEN)
    redis = Redis(host='redis', port=6379, db=5)
    storage = RedisStorage(redis=redis, key_builder=DefaultKeyBuilder(prefix="pulse_fsm"))    
    dp = Dispatcher(storage=storage)

    # Регистрация хэндлеров
    dp.include_router(chat_handler)
    dp.include_router(group_handler)
    dp.include_router(block_handler)
    dp.include_router(start_handler)
    dp.include_router(check_handler)
    dp.include_router(manual_handler)
    dp.include_router(email_handler)
    dp.include_router(confirm_handler)
    dp.include_router(code_handler)
 #   dp.include_router(callback_handler)
    dp.include_router(general_handler)

    logger.info("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
