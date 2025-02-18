# utils/invite.py
from datetime import datetime, timedelta
from aiogram import types
from aiogram.fsm.context import FSMContext

from config import logger, COMPANY_CHANNEL_ID
from combine.reply import get_invite_link, remove_keyboard
from combine.answer import (
    link_exists,         # "Твоя ссылка-приглашение уже была сгенерирована..."
    invite_link_error,   # "Не удалось создать ссылку..."
    user_not_in_channel  # "Ты верифицирован, но ещё не вступил..."
)


async def generate_and_send_invite(
    message: types.Message,
    state: FSMContext
):
    """
    Генерирует одноразовую ссылку (inline-кнопку) на канал с защитой от
    повторной генерации в течение 10 минут. Хранит 'link_time' и 'members'
    в FSM data.
    """

    user_id = message.from_user.id
    now = datetime.now()

    logger.info(f"[invite] Начинаем generate_and_send_invite для user_id={user_id}")

    # 1. Проверяем, не генерировали ли мы ссылку недавно
    data = await state.get_data()
    link_time_str = data.get("link_time")
    if link_time_str:
        old_link_time = datetime.fromisoformat(link_time_str)
        diff_sec = (now - old_link_time).total_seconds()
        if diff_sec < 600:  # 10 минут = 600 секунд
            logger.info(
                f"[invite] user_id={user_id}: ссылка уже была сгенерирована "
                f"{diff_sec:.0f} сек назад. Повторная генерация запрещена."
            )
            await message.answer(link_exists, reply_markup=remove_keyboard())
            return

    # 2. Обновляем время генерации ссылки в FSM
    await state.update_data(link_time=now.isoformat())

    # 3. Узнаём кол-во участников в канале (если нужно логировать/сохранять)
    try:
        members_count = await message.bot.get_chat_member_count(COMPANY_CHANNEL_ID)
        logger.info(
            f"[invite] user_id={user_id}: в канале {members_count} участников. Генерируем ссылку на 10 минут."
        )
        # Сохраняем members_count, вдруг вам пригодится в будущем
        await state.update_data(members=members_count)
    except Exception as e:
        logger.error(f"[invite] Не удалось получить кол-во участников канала: {e}")
        members_count = None  # или -1, если хотите

    # 4. Генерируем ссылку с expire_date = 10 минут
    expire_10 = timedelta(minutes=10)
    invite_markup = await get_invite_link(message.bot, COMPANY_CHANNEL_ID)
    if not invite_markup:
        logger.error(f"[invite] Не удалось создать одноразовую ссылку user_id={user_id}")
        await message.answer(invite_link_error, reply_markup=remove_keyboard())
        return

    # 5. Отправляем сообщение пользователю
    logger.info(f"[invite] Ссылка сгенерирована для user_id={user_id}, отправляем InlineKeyboard.")
    await message.answer(
        user_not_in_channel,  # содержит предупреждение о 10 мин / 1 юзера
        parse_mode="Markdown",
        reply_markup=invite_markup
    )
