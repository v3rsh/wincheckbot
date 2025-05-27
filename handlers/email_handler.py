# email_handler.py
import re
from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
from utils.mask import mask_email
from combine.answer import email_confirm, email_invalid, email_limit_change, block_released
from combine.reply import remove_keyboard, email_keyboard
from config import logger, EXCLUDED_EMAILS, WORK_MAIL
from states import Verification
from utils.limits import get_daily_email_changes, increment_email_changes
from handlers.block_handler import check_if_still_blocked

router = Router()

# Регулярное выражение для проверки email
email_regex = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

def is_valid_email(email: str) -> bool:
    """Проверяет email на соответствие базовому шаблону."""
    return email_regex.match(email)

def is_valid_work_email(email: str) -> bool:
    """
    Проверяем, что email валидный и заканчивается на @WORK_MAIL (если он не входит в EXCLUDED_EMAILS).
    """
    if not is_valid_email(email):
        return False

    # Если email входит в EXCLUDED_EMAILS, считаем тоже валидным (по условию, возможно, HR почты или что-то ещё)
    if any(email.strip().lower() == ex.strip().lower() for ex in EXCLUDED_EMAILS if ex.strip()):
        return True

    domain = WORK_MAIL.lower()
    return email.lower().endswith("@" + domain)

@router.message(Verification.waiting_email)
async def handle_email_input(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    logger.info(f"[email_handler] Пользователь {user_id} вводит email в waiting_email.")
    email_text = message.text.strip()

    # Сначала проверяем, был ли пользователь заблокирован и истек ли срок блокировки
    data = await state.get_data()
    if "blocked_until" in data and data["blocked_until"]:
        try:
            blocked_until = datetime.fromisoformat(data["blocked_until"])
            now = datetime.now()
            
            if now < blocked_until:
                # Пользователь всё ещё должен быть заблокирован
                logger.warning(f"[email_handler] Пользователь {user_id} пытается ввести email, но должен быть заблокирован")
                await state.set_state(Verification.blocked)
                return
            else:
                # Блокировка истекла, сбрасываем счетчики и уведомляем
                logger.info(f"[email_handler] Блокировка для пользователя {user_id} истекла. Сбрасываем счетчики.")
                await state.update_data(
                    blocked_until=None,
                    daily_email_changes_count=0,
                    daily_email_changes_date=None,
                    email_change_count=0
                )
                await message.answer(block_released, reply_markup=remove_keyboard())
        except ValueError:
            # Ошибка формата даты, сбрасываем данные блокировки
            await state.update_data(blocked_until=None)

    # <-- NEW: проверяем суточный лимит (например, если считаем "ввод email" = смена)
    daily_count = await get_daily_email_changes(state)
    if daily_count >= 2:
        # Пример: блокируем на 10 минут
        now = datetime.now()
        block_expires = now + timedelta(minutes=10)
        await state.update_data(
            blocked_until=block_expires.isoformat(),
            # Не сбрасываем счетчики, чтобы после разблокировки пользователь не мог снова использовать лимит
        )
        await state.set_state(Verification.blocked)
        logger.info(f"[email_handler] user {user_id} достиг суточного лимита смен email. Блокируем на 10 мин.")
        await message.answer(email_limit_change, reply_markup=remove_keyboard())
        return

    if is_valid_work_email(email_text):
        # Разрешаем "смену" и инкрементируем счётчик
        new_count = await increment_email_changes(state)
        logger.info(f"[email_handler] user {user_id} daily changes => {new_count}")
        
        # Переходим в waiting_confirm
        logger.info(f"[email_handler] Пользователь {user_id} ввёл корректный email: {mask_email(email_text)}.")
        await state.set_state(Verification.waiting_confirm)
        await state.update_data(email=email_text)
        await message.answer(email_confirm(email_text), parse_mode='Markdown', reply_markup=email_keyboard())
    else:
        logger.warning(f"[email_handler] Пользователь {user_id} ввёл некорректный email: {email_text}")
        await message.answer(email_invalid, reply_markup=remove_keyboard())