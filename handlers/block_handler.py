from aiogram import Router
from datetime import datetime
import combine.answer 
from aiogram.types import Message
from combine.reply import remove_keyboard
from config import logger
from states import Verification
from aiogram.fsm.context import FSMContext

router = Router()

@router.message(Verification.blocked)
async def handle_blocked_user(message: Message, state: FSMContext):
    # Извлекаем время окончания блокировки из данных состояния
    data = await state.get_data()
    if "blocked_until" in data:
        blocked_until = datetime.fromisoformat(data["blocked_until"])

    if blocked_until:
        try:
            now = datetime.now()

            if now < blocked_until:
                remaining_time = int((blocked_until- now).total_seconds() // 60)
                logger.warning(f"Пользователь {message.from_user.id} заблокирован. Осталось {remaining_time} минут.")
                await message.answer(combine.answer.block_time(remaining_time), reply_markup=remove_keyboard())
            else:
                # Если срок блокировки истёк, очищаем состояние
                logger.info(f"Срок блокировки для пользователя {message.from_user.id} истёк.")
                await message.answer(combine.answer.block_released, reply_markup=remove_keyboard())
                await state.update_data(blocked_until=None)
                await state.set_state(Verification.waiting_email)

        except ValueError:
                # Обрабатываем некорректные данные в поле BlockedUntil
                logger.error(f"Некорректный формат даты BlockedUntil для пользователя {message.from_user.id} Состояния сброшены.")
                await state.update_data(blocked_until=None)
                await state.clear
                await message.answer(combine.answer.not_registered, reply_markup=remove_keyboard())
    else:
        # Пользователь не заблокирован
        logger.info(f"Пользователь {message.from_user.id} ошибочно попал в block_handler.Состояния сброшены")
        await state.update_data(blocked_until=None)
        await state.clear
        await message.answer(combine.answer.not_registered, reply_markup=remove_keyboard())
