# ./handlers/confirm_handler.py
import random
from datetime import datetime, timedelta
from aiogram import Router, types
from aiogram.fsm.context import FSMContext

from states import Verification
from utils.email_sender import send_email
from utils.mask import mask_email
from config import logger

from combine.answer import (
    code_send_error, 
    email_too_often,
    email_change,  
    code_sent,
    email_request,
    confirm_wrong_command
)
from combine.reply import remove_keyboard

# Новые импорты для обновленной логики
from utils.limits import get_email_send_count, increment_email_send_count, reset_code_attempts

router = Router()

@router.message(Verification.waiting_confirm)
async def handle_confirm_state(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text.strip().lower()

    data = await state.get_data()
    email = data.get("email")

    if text == "изменить email":
        # Просто разрешаем ввод нового email без увеличения счетчика
        logger.info(f"[confirm_handler] user {user_id} меняет email.")
        await state.update_data(email=None, code=None)
        await state.set_state(Verification.waiting_email)
        await message.answer(email_change, reply_markup=remove_keyboard())

    elif text == "отправить код":
        # Проверяем количество отправленных кодов
        email_send_count = await get_email_send_count(state)
        
        # Если достигнут лимит 3 отправки кода - блокируем
        if email_send_count >= 3:
            # 4-я попытка отправить код - блокируем на 30 минут и сбрасываем счетчик
            now = datetime.now()
            block_expires = now + timedelta(minutes=30)
            await state.update_data(blocked_until=block_expires.isoformat(), email_send_count=0)
            await state.set_state(Verification.blocked)
            logger.info(f"[confirm_handler] user {user_id} достиг лимита отправки кодов (4-я попытка). Блокируем на 30 мин.")
            await message.answer(email_too_often, reply_markup=remove_keyboard())
            return
        
        # Увеличиваем счетчик отправки кодов
        new_count = await increment_email_send_count(state)
        logger.info(f"[confirm_handler] user {user_id} отправка кода {new_count}/3")
        
        # Генерируем и отправляем код
        verification_code = str(random.randint(100000, 999999))
        logger.info(f"[confirm_handler] Код подтверждения {verification_code}. Готовится отправка {mask_email(email)} (user {user_id}).")
        now = datetime.now()
        
        if not email:
            logger.warning(f"[confirm_handler] user {user_id} нет email в FSM, но запросил отправку кода.")
            await message.answer(email_request, reply_markup=remove_keyboard())
            return

        # Сбрасываем счетчик попыток ввода кода при отправке нового кода
        await reset_code_attempts(state)
        
        success = await send_email(email, verification_code)
        if success:
            logger.info(f"[confirm_handler] Код подтверждения {verification_code} отправлен на {mask_email(email)} (user {user_id}).")
            await state.set_state(Verification.waiting_code)
            await state.update_data(code=verification_code, code_sent_time=now.isoformat())
            await message.answer(code_sent, reply_markup=remove_keyboard())
        else:
            logger.error(f"[confirm_handler] Ошибка при отправке кода на {mask_email(email)} (user {user_id}).")
            await message.answer(code_send_error)

    else:
        logger.info(f"[confirm_handler] user {user_id} неподходящая команда: {text}")
        await message.answer(confirm_wrong_command, reply_markup=remove_keyboard())
