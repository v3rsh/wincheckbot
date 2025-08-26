import aiosqlite
from aiogram import Router, types
from datetime import datetime, timedelta
from combine.answer import (
    code_success, code_invalid, code_blocked
)
from combine.reply import remove_keyboard
from config import logger
from states import Verification
from aiogram.fsm.context import FSMContext
from database import set_user_email
from utils.unban import unban_user

# Импортируем нашу «универсальную» функцию генерации ссылки
from utils.invite import generate_and_send_invite
from utils.limits import reset_email_send_count

router = Router()

@router.message(Verification.waiting_code)
async def handle_code_input(message: types.Message, state: FSMContext):
    """
    Хэндлер, который полностью использует FSM для проверки кода
    и, в случае успеха, генерирует ссылку через функцию generate_and_send_invite.
    """
    user_id = message.from_user.id
    code_entered = message.text.strip()
    now = datetime.now()

    logger.info(f"[code_handler] Пользователь {user_id} ввёл код: {code_entered}")

    # 1. Получаем из FSM хранимый код и счётчик неудач
    data = await state.get_data()
    stored_code = data.get("code")
    code_attempts = data.get("code_attempts", 0)

    # Добавляем логирование типов для отладки
    logger.info(f"[code_handler] user_id={user_id}, stored_code={stored_code} ({type(stored_code)}), code_entered={code_entered} ({type(code_entered)})")
    
    # Преобразуем оба значения в строки для гарантированного сравнения
    code_entered_str = str(code_entered)
    stored_code_str = str(stored_code) if stored_code is not None else None
    
    logger.info(f"[code_handler] После преобразования: stored_code_str={stored_code_str}, code_entered_str={code_entered_str}")

    # 2. Сравниваем коды как строки
    if stored_code is not None and code_entered_str == stored_code_str:
        logger.info(f"[code_handler] Пользователь {user_id} ввёл верный код.")
        email = data.get("email")
        
        # 1) Записываем email в базу данных
        await set_user_email(user_id, email)
        await state.set_state(Verification.verified)
        
        # Очищаем временные данные и сбрасываем все счетчики
        await state.update_data(code=None, code_attempts=0, email=None)
        await reset_email_send_count(state)  # Сбрасываем счетчик отправки email
        await unban_user(user_id, message.bot)

        # 3. Отправляем сообщение о том, что код подтверждён
        logger.info(f"[code_handler] user_id={user_id} -> передаём invite_count=0 в generate_and_send_invite")

        await message.answer(code_success, reply_markup=remove_keyboard())

        # Генерируем и отправляем ссылку (если функция внутри сама проверяет «10 мин» и т.п.)
        await generate_and_send_invite(message, state)
        
    else:
        # Код неверный, увеличиваем счётчик неудач
        code_attempts += 1
        logger.info(f"[code_handler] Неверный код от пользователя {user_id}. code_attempts={code_attempts}")

        # Если 3 и более попыток => блокируем на 10 мин
        if code_attempts >= 3:
            block_time = now + timedelta(minutes=10)
            # Важно: сбрасываем только счетчик попыток ввода кода, но НЕ счетчик отправки email
            await state.update_data(blocked_until=block_time.isoformat(), code_attempts=0, code=None)
            await state.set_state(Verification.blocked)
            logger.warning(f"[code_handler] Пользователь {user_id} заблокирован на 10 минут (3 неверных кода).")
            await message.answer(code_blocked(10), reply_markup=remove_keyboard())
        else:
            # Просто записываем обновлённый счётчик
            await state.update_data(code_attempts=code_attempts)
            remaining = 3 - code_attempts
            logger.info(f"[code_handler] user_id={user_id}, осталось попыток={remaining}")
            await message.answer(
                code_invalid(remaining),
                reply_markup=remove_keyboard()
            )
