from datetime import datetime, date
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
