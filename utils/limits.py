from datetime import datetime, date, timedelta
from aiogram.fsm.context import FSMContext

async def get_daily_email_changes(state: FSMContext):
    data = await state.get_data()
    saved_date_str = data.get("daily_email_changes_date")
    saved_count = data.get("daily_email_changes_count", 0)

    today_str = date.today().isoformat()
    if saved_date_str != today_str:
        # Сбрасываем, если день поменялся
        saved_date_str = today_str
        saved_count = 0
        await state.update_data(
            daily_email_changes_date=saved_date_str,
            daily_email_changes_count=saved_count
        )
    return saved_count

async def increment_email_changes(state: FSMContext):
    """Увеличивает счётчик изменений почты и возвращает новое значение."""
    changes_count = await get_daily_email_changes(state)  # эта функция уже актуализирует счётчик, если день сменился
    changes_count += 1
    await state.update_data(daily_email_changes_count=changes_count)
    return changes_count

async def get_email_send_count(state: FSMContext):
    """
    Получает текущее количество отправок кода.
    """
    data = await state.get_data()
    return data.get("email_send_count", 0)

async def increment_email_send_count(state: FSMContext):
    """
    Увеличивает счетчик отправок кода и возвращает новое значение.
    """
    current_count = await get_email_send_count(state)
    new_count = current_count + 1
    await state.update_data(email_send_count=new_count)
    return new_count

async def reset_email_send_count(state: FSMContext):
    """
    Сбрасывает счетчик отправок кода.
    """
    await state.update_data(email_send_count=0)
    return 0

async def reset_code_attempts(state: FSMContext):
    """
    Сбрасывает счетчик попыток ввода кода.
    """
    await state.update_data(code_attempts=0)
    return 0
