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

# <-- NEW: импортируем функции из limits.py
from utils.limits import get_daily_email_changes, increment_email_changes

router = Router()

@router.message(Verification.waiting_confirm)
async def handle_confirm_state(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text.strip().lower()

    data = await state.get_data()
    email = data.get("email")
    email_change_count = data.get("email_change_count", 0)

    if text == "изменить email":
        # <-- NEW: Проверяем суточный лимит
        daily_count = await get_daily_email_changes(state)
        if daily_count >= 2:
            # Если уже 2 изменения в сутки, блокируем 10 минут (пример)
            now = datetime.now()
            block_expires = now + timedelta(minutes=10)
            await state.update_data(blocked_until=block_expires.isoformat(),
                                    email_change_count=0)  # сбрасываем счётчик
            await state.set_state(Verification.blocked)
            logger.info(f"[confirm_handler] user {user_id} достиг суточного лимита. Блокируем на 10 мин.")
            await message.answer(email_too_often, reply_markup=remove_keyboard())
            return

        # Иначе — инкрементируем суточный счётчик
        new_count = await increment_email_changes(state)  
        logger.info(f"[confirm_handler] user {user_id} daily_email_changes_count => {new_count}")

        # Плюс локальный счётчик email_change_count (как раньше)
        email_change_count += 1
        if email_change_count >= 3:
            # Пример: если локальный счётчик ≥3, тоже блокируем (или можно убрать этот блок)
            now = datetime.now()
            block_expires = now + timedelta(minutes=10)
            await state.update_data(blocked_until=block_expires.isoformat(),
                                    email_change_count=0)
            await state.set_state(Verification.blocked)
            logger.info(f"[confirm_handler] user {user_id} превысил локальный лимит (3). Блокируем на 10 мин.")
            await message.answer(email_too_often, reply_markup=remove_keyboard())
            return
        
        # Разрешаем ввод нового email
        logger.info(f"[confirm_handler] user {user_id} меняет email (лок. count={email_change_count}).")
        await state.update_data(email=None, code=None, email_change_count=email_change_count)
        await state.set_state(Verification.waiting_email)
        await message.answer(email_change, reply_markup=remove_keyboard())

    elif text == "отправить код":
        # Отправляем код
        verification_code = str(random.randint(100000, 999999))
        now = datetime.now()
        if not email:
            logger.warning(f"[confirm_handler] user {user_id} нет email в FSM, но запросил отправку кода.")
            await message.answer(email_request, reply_markup=remove_keyboard())
            return

        success = await send_email(email, verification_code)
        if success:
            logger.info(f"[confirm_handler] Код подтверждения отправлен на {mask_email(email)} (user {user_id}).")
            await state.set_state(Verification.waiting_code)
            await state.update_data(code=verification_code, code_sent_time=now.isoformat())
            await message.answer(code_sent, reply_markup=remove_keyboard())
        else:
            logger.error(f"[confirm_handler] Ошибка при отправке кода на {mask_email(email)} (user {user_id}).")
            await message.answer(code_send_error)

    else:
        logger.info(f"[confirm_handler] user {user_id} неподходящая команда: {text}")
        await message.answer(confirm_wrong_command, reply_markup=remove_keyboard())
