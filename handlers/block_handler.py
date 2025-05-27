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
    blocked_until = None
    
    if "blocked_until" in data:
        try:
            blocked_until = datetime.fromisoformat(data["blocked_until"])
        except ValueError:
            # Обрабатываем некорректные данные в поле blocked_until
            logger.error(f"Некорректный формат даты blocked_until для пользователя {message.from_user.id}. Состояния сброшены.")
            await state.update_data(blocked_until=None)
            await state.clear()
            await message.answer(combine.answer.not_registered, reply_markup=remove_keyboard())
            return

    if blocked_until:
        now = datetime.now()

        if now < blocked_until:
            # Пользователь всё ещё заблокирован
            remaining_time = int((blocked_until - now).total_seconds() // 60)
            logger.warning(f"Пользователь {message.from_user.id} заблокирован. Осталось {remaining_time} минут.")
            await message.answer(combine.answer.block_time(remaining_time), reply_markup=remove_keyboard())
        else:
            # Если срок блокировки истёк, очищаем состояние
            logger.info(f"Срок блокировки для пользователя {message.from_user.id} истёк.")
            await message.answer(combine.answer.block_released, reply_markup=remove_keyboard())
            # Сбрасываем счетчики и блокировку
            await state.update_data(
                blocked_until=None, 
                daily_email_changes_count=0,
                daily_email_changes_date=None,
                email_change_count=0
            )
            await state.set_state(Verification.waiting_email)
    else:
        # Пользователь не заблокирован или данные отсутствуют
        logger.info(f"Пользователь {message.from_user.id} ошибочно попал в block_handler. Состояния сброшены.")
        await state.update_data(blocked_until=None)
        await state.clear()
        await message.answer(combine.answer.not_registered, reply_markup=remove_keyboard())

# Вспомогательная функция для проверки статуса блокировки
async def check_if_still_blocked(state: FSMContext):
    """
    Проверяет, истек ли срок блокировки пользователя.
    Если срок истек, сбрасывает состояние блокировки.
    Возвращает True, если пользователь всё ещё заблокирован, иначе False.
    """
    data = await state.get_data()
    if "blocked_until" in data and data["blocked_until"]:
        try:
            blocked_until = datetime.fromisoformat(data["blocked_until"])
            now = datetime.now()
            
            if now >= blocked_until:
                # Блокировка истекла, сбрасываем состояние
                logger.info(f"Автоматическая разблокировка пользователя (check_if_still_blocked)")
                await state.update_data(
                    blocked_until=None, 
                    daily_email_changes_count=0,
                    daily_email_changes_date=None,
                    email_change_count=0
                )
                return False
            else:
                # Пользователь всё ещё заблокирован
                return True
        except ValueError:
            # Некорректный формат даты
            await state.update_data(blocked_until=None)
            return False
    
    return False
