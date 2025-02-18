# handlers/group_message_handler.py

from aiogram import Router, types, Bot, F
from aiogram.enums import ChatMemberStatus, ChatType # Обновлён импорт
from config import logger

router = Router()

@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL}))
async def handle_group_message(message: types.Message):
    """
    Хэндлер для сообщений из групп, супергрупп и каналов.
    Теперь бот полностью игнорирует эти сообщения.
    """
    logger.debug(f"Получено сообщение из группы/канала {message.chat.id}, игнорируем.")
    # Не выполняем никаких действий, чтобы не расходовать память
    pass