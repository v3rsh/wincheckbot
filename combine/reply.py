from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from config import logger
from datetime import timedelta

# Основные клавиатуры
def email_keyboard():
    """Клавиатура с действиями: Отправить код, Изменить email."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отправить код")],
            [KeyboardButton(text="Изменить email")]
        ],
        resize_keyboard=True
    )

def verified_keyboard():
    """Клавиатура для верифицированного пользователя."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Перейти в канал")]
        ],
        resize_keyboard=True
    )

def change_email_keyboard():
    """Клавиатура с действием: Изменить email."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Изменить email")]
        ],
        resize_keyboard=True
    )

def remove_keyboard():
    """Удаление клавиатуры."""
    return ReplyKeyboardRemove()

# Inline-кнопки

async def get_invite_link(bot, chat_id):
    """Генерация одноразовой ссылки на канал."""
    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=chat_id, expire_date=timedelta(minutes=10), member_limit=1
        )
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Присоединиться", url=invite_link.invite_link)]
            ]
        )
    except Exception as e:
        logger.error(f"Ошибка при создании ссылки: {e}")
        return None

async def get_restoration_invite_link(bot, chat_id):
    """Генерация ссылки для восстановления статуса (24 часа, 1 пользователь)."""
    try:
        invite_link = await bot.create_chat_invite_link(
            chat_id=chat_id, expire_date=timedelta(hours=24), member_limit=1
        )
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Присоединиться к Winline Team", url=invite_link.invite_link)]
            ]
        )
    except Exception as e:
        logger.error(f"Ошибка при создании ссылки восстановления: {e}")
        return None
