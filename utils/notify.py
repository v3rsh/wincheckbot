# utils/notify.py

from aiogram import Bot
import aiosqlite
from config import logger, API_TOKEN, DB_PATH

NOTIFICATION_TEXT = (
    "Здравствуйте! \n"
    "Компания обновила список активных сотрудников, и ваш статус был сброшен. "
    "Чтобы продолжить пользоваться рабочими группами, необходимо вновь пройти верификацию."
)

async def notify_newly_fired(user_ids: list[int]):
    """
    Отправляет уведомления тем, у кого Notified=FALSE, 
    и затем проставляет Notified=TRUE.
    """
    if not user_ids:
        return

    async with aiosqlite.connect(DB_PATH) as db:
        # Выбираем только тех, у кого Notified=FALSE
        placeholders = ",".join("?" * len(user_ids))
        cursor = await db.execute(
            f"SELECT UserID FROM Users WHERE UserID IN ({placeholders}) AND Notified=FALSE",
            tuple(user_ids)
        )
        rows = await cursor.fetchall()
        to_notify = [r[0] for r in rows]

    if not to_notify:
        logger.info("Все пользователи из списка уже получили уведомление (Notified=TRUE).")
        return

    bot = Bot(token=API_TOKEN)
    notified_count = 0
    try:
        for uid in to_notify:
            try:
                await bot.send_message(uid, NOTIFICATION_TEXT)
                logger.info(f"[notify_newly_fired] Отправлено уведомление user_id={uid}")
                notified_count += 1
            except Exception as e:
                logger.warning(f"[notify_newly_fired] Не удалось отправить сообщение user_id={uid}: {e}")

        # Проставляем Notified=TRUE тем, кому отправляли
        async with aiosqlite.connect(DB_PATH) as db:
            placeholders = ",".join("?" * len(to_notify))
            await db.execute(
                f"UPDATE Users SET Notified=TRUE WHERE UserID IN ({placeholders})",
                tuple(to_notify)
            )
            await db.commit()
        logger.info(f"[notify_newly_fired] Установлен Notified=TRUE для {notified_count} пользователей.")

    finally:
        await bot.session.close()
