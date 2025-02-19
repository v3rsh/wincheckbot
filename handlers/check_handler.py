# handlers/check_handler.py

import aiosqlite
from aiogram import Router, types
from aiogram.filters.command import Command
from config import logger, COMPANY_CHANNEL_ID, DB_PATH
from combine.reply import remove_keyboard
from combine.answer import (
    not_registered,
    check_error,
    was_approved_but_removed,
    never_verified_info,
    user_in_channel
)
from aiogram.enums import ChatMemberStatus
from utils.invite import generate_and_send_invite
from aiogram.fsm.context import FSMContext
from database import get_user_email
from utils.mask import mask_email

router = Router()

@router.message(Command("check"))
async def check_status(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    logger.info(f"[check_handler] Пользователь {user_id} вызвал команду /check")

    # 1) Ищем пользователя в базе
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT Approve, WasApproved, InviteCount
            FROM Users
            WHERE UserID = ?
        """, (user_id,))
        result = await cursor.fetchone()

    if not result:
        # Пользователь не найден
        logger.warning(f"[check_handler] Пользователь {user_id} не найден в базе при /check.")
        await message.answer(not_registered, reply_markup=remove_keyboard())
        return

    approve, was_approved, invite_count = result

    # 2) Разбираем логику
    if not approve:
        # Approve=False => проверим WasApproved
        if was_approved:
            # Ранее был верифицирован, но сейчас лишён статуса
            logger.info(f"[check_handler] User {user_id} was approved but now lost status => was_approved_but_removed.")
            await message.answer(was_approved_but_removed, reply_markup=remove_keyboard())
        else:
            # Никогда не был верифицирован
            logger.info(f"[check_handler] User {user_id} never was verified => never_verified_info.")
            await message.answer(never_verified_info, reply_markup=remove_keyboard())
        return

    # Если мы здесь, значит Approve=TRUE
    # Достаем email для наглядности
    dec_email = await get_user_email(user_id)
    masked_email = mask_email(dec_email)
    logger.info(f"[check_handler] Пользователь {user_id} имеет approve=TRUE, email={masked_email}.")

    # 3) Проверяем, состоит ли пользователь в канале
    try:
        chat_member = await message.bot.get_chat_member(COMPANY_CHANNEL_ID, user_id)
        if chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            # Уже в канале
            logger.info(f"[check_handler] Пользователь {user_id} уже в канале => no new link.")
            # Отправляем сообщение с «Вы уже в канале»
            # user_in_channel — это лямбда, передаем masked_email, если надо вывести
            await message.answer(
                user_in_channel(masked_email),
                reply_markup=remove_keyboard()
            )
        else:
            # Не в канале => генерируем ссылку (при желании можно проверять InviteCount)
            logger.info(f"[check_handler] Пользователь {user_id} не в канале => генерируем ссылку.")
            await generate_and_send_invite(message, state)

    except Exception as e:
        logger.error(f"[check_handler] Ошибка при проверке статуса в канале: {e}")
        await message.answer(check_error, reply_markup=remove_keyboard())
