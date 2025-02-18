# handlers/callback_handler.py
from aiogram import Router, types, F
from aiogram.filters.callback_data import CallbackData
from config import logger
from utils.email_sender import send_email
import aiosqlite
from datetime import datetime, timedelta
import random
from combine.answer import not_registered, block_time
from combine.reply import remove_keyboard
from utils.mask import mask_email


router = Router()

@router.callback_query()
async def handle_callback(callback_query: types.CallbackQuery):
    logger.info(f"Хэндлер /callback вызван для пользователя {callback_query.from_user.id}.")
    user_id = callback_query.from_user.id
    data = callback_query.data  # Данные колбэка
    now = datetime.now()

    logger.info(f"Пользователь {user_id} вызвал callback с данными: {data}")

    async with aiosqlite.connect("pulse.db") as db:
        # Проверяем, есть ли пользователь в базе
        cursor = await db.execute("SELECT Email, Code, Approve, BlockedUntil FROM Users WHERE UserID = ?", (user_id,))
        user = await cursor.fetchone()

        if not user:
            logger.warning(f"Пользователь {user_id} не найден в базе данных.")
            await callback_query.message.answer(not_registered, reply_markup=remove_keyboard())
            await callback_query.answer()  # Просто подтверждаем обработку колбэка без текста
            return

        email, code, approve, blocked_until = user

        # Проверяем тип данных колбэка
        if data == "retry_code":
            # Логика повторной отправки кода
            logger.info(f"Пользователь {user_id} запросил повторную отправку кода.")
            if blocked_until and datetime.fromisoformat(blocked_until) > now:
                remaining_time = int((datetime.fromisoformat(blocked_until) - now).total_seconds() // 60)
                await callback_query.answer(block_time(remaining_time), reply_markup=remove_keyboard())
                return

            if email and approve is False:
                new_code = str(random.randint(100000, 999999))
                await db.execute(
                    "UPDATE Users SET Code = ?, LastRetry = ?, CodeAttempts = 0 WHERE UserID = ?",
                    (new_code, now.isoformat(), user_id)
                )
                await db.commit()

                if await send_email(email, new_code):
                    logger.info(f"Код подтверждения повторно отправлен на {mask_email(email)}.")
                    await callback_query.answer(f"Код отправлен повторно на {email}. Проверьте почту.")
                else:
                    logger.error(f"Не удалось отправить код на {mask_email(email)}.")
                    await callback_query.answer(f"Ошибка отправки кода. Попробуйте позже.")
            else:
                await callback_query.answer("Ваш email уже подтверждён или отсутствует.")

        elif data == "change_email":
            # Логика изменения email
            logger.info(f"Пользователь {user_id} запросил изменение email.")
            await db.execute(
                "UPDATE Users SET WaitingForEmail = TRUE, Email = NULL, Code = NULL, WaitingForCode = FALSE WHERE UserID = ?",
                (user_id,)
            )
            await db.commit()
            await set_flag(user_id, "WAITING_EMAIL", db)
            await callback_query.answer("Введите новый email для изменения текущего адреса.")
            await callback_query.message.answer("Введите ваш новый рабочий email.")
        else:
            # Обработка неизвестного колбэка
            logger.warning(f"Неизвестный тип callback: {data}")
            await callback_query.answer("Неизвестная команда. Попробуйте ещё раз.")

        # Отвечаем Telegram, что колбэк обработан
        await callback_query.answer()
