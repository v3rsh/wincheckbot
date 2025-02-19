# handlers/general_handler.py

from aiogram import Router, types, F
from combine.answer import bot_commands
from combine.reply import remove_keyboard
from aiogram.fsm.context import FSMContext
from utils.invite import generate_and_send_invite
import aiosqlite
from config import logger, COMPANY_CHANNEL_ID, DB_PATH

router = Router()

@router.message(F.text)
async def handle_text(message: types.Message, state: FSMContext):
    user_input = message.text.strip()

    if user_input == "Перейти в канал":
        user_id = message.from_user.id

        # Шаг 1: Проверяем, есть ли пользователь в базе и верифицирован ли он
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("""
                SELECT Approve
                FROM Users
                WHERE UserID = ?
            """, (user_id,))
            row = await cursor.fetchone()

        if not row:
            # Пользователь не найден в базе
            logger.info(f"[general_handler] User {user_id} not in DB, can't generate invite.")
            await message.answer(
                "Вы ещё не верифицированы. Отправьте /start для начала верификации.",
                reply_markup=remove_keyboard()
            )
            return

        approve = row[0]
        if not approve:
            # Пользователь есть в базе, но не верифицирован
            logger.info(f"[general_handler] User {user_id} is not approved => deny invite.")
            await message.answer(
                "Ваш email ещё не подтверждён. Для получения доступа отправьте /start.",
                reply_markup=remove_keyboard()
            )
            return

        # Шаг 2: Проверяем членство в канале
        try:
            chat_member = await message.bot.get_chat_member(COMPANY_CHANNEL_ID, user_id)
            # Если пользователь в канале, не генерируем новую ссылку
            if chat_member.status in ["member", "administrator", "creator"]:
                logger.info(f"[general_handler] User {user_id} already in channel => no new link.")
                await message.answer(
                    "Вы уже состоите в корпоративном канале!",
                    reply_markup=remove_keyboard()
                )
                return
            else:
                # Пользователя нет в канале → генерируем ссылку
                logger.info(f"[general_handler] User {user_id} not in channel => generate invite.")
                await generate_and_send_invite(message, state)

        except Exception as e:
            logger.error(f"[general_handler] Ошибка при проверке статуса в канале: {e}")
            await message.answer(
                "Произошла ошибка при проверке статуса в канале. Попробуйте позже.",
                reply_markup=remove_keyboard()
            )
    else:
        # Любые другие тексты
        await message.answer(
            bot_commands, 
            parse_mode='Markdown', 
            reply_markup=remove_keyboard()
        )
