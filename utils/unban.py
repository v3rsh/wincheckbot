# utils/unban.py
import aiosqlite
from aiogram import Bot
from config import logger, API_TOKEN, DB_PATH

async def unban_user(user_id: int, bot: Bot = None):
    """
    Проверяет, стоит ли у пользователя Banned=TRUE.
    Если да — снимает бан в группах, где у бота есть права.
    Затем проставляет Banned=FALSE.
    """
    logger.info(f"[unban_user] Начинаем разбан для {user_id}. bot: {bot.token}")
    if bot is None:
        logger.info(f"bot is None, creating new bot")
        bot = Bot(token=API_TOKEN)
        should_close_session = True
    else:
        should_close_session = False

    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем, был ли пользователь забанен
        cursor = await db.execute("""
            SELECT Banned FROM Users WHERE UserID=?
        """, (user_id,))
        row = await cursor.fetchone()

        if not row:
            logger.warning(f"[unban_user] User {user_id} не найден в базе.")
            return
        
        banned = row[0]
        if not banned:
            logger.info(f"[unban_user] User {user_id} не был забанен, разбан не требуется.")
            return

        # Получаем список чатов, где бот может управлять пользователями
        cursor = await db.execute("""
            SELECT ChatID FROM Groups WHERE can_restrict_members=TRUE
        """)
        eligible_groups = await cursor.fetchall()

        if not eligible_groups:
            logger.info("[unban_user] Нет групп с правами can_restrict_members, разбан невозможен.")
            return

        # Разбаниваем пользователя во всех подходящих группах
        unbanned_count = 0
        for (chat_id,) in eligible_groups:
            try:
                await bot.unban_chat_member(chat_id, user_id)
                logger.info(f"[unban_user] Пользователь {user_id} разбанен в чате {chat_id}")
                unbanned_count += 1
            except Exception as e:
                logger.warning(f"[unban_user] Не удалось разбанить user_id={user_id} в {chat_id}: {e}")

        if unbanned_count > 0:
            # Обновляем статус Banned в базе
            await db.execute("""
                UPDATE Users SET Banned=FALSE WHERE UserID=?
            """, (user_id,))
            await db.commit()
            logger.info(f"[unban_user] Пользователь {user_id} теперь Banned=FALSE.")

    if should_close_session:
        await bot.session.close()

