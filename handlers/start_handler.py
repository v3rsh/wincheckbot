# handlers/start_handler.py
import aiosqlite
from aiogram import Router, types
from datetime import datetime
from combine.answer import (
    email_request, email_verified, code_request, email_actions,
    email_fired, email_not_verified
)
from combine.reply import verified_keyboard, remove_keyboard, email_keyboard
from config import logger, DB_PATH
from aiogram.filters.command import Command
from states import Verification
from aiogram.fsm.context import FSMContext
import os

router = Router()

@router.message(Command("start"))
async def handle_start(message: types.Message, state: FSMContext):
    logger.info(f"Хэндлер /start вызван для пользователя {message.from_user.id}.")
    user_id = message.from_user.id
    now = datetime.now()
    logger.info(f"Пользователь {user_id} отправил команду /start в {now.isoformat()}")

    async with aiosqlite.connect(DB_PATH) as db:
        logger.info(f"Абсолютный путь к базе: {os.path.abspath(DB_PATH)}")
        try:
            # Проверяем наличие пользователя в базе
            cursor = await db.execute("""
                SELECT Approve, WasApproved
                FROM Users WHERE UserID = ?
            """, (user_id,))
            user = await cursor.fetchone()

            if not user:
                # Пользователь отсутствует в базе
                logger.info(f"Пользователь {user_id} отсутствует в базе. Добавляем запись.")
                # Получаем данные пользователя из Telegram
                username = message.from_user.username
                first_name = message.from_user.first_name
                last_name = message.from_user.last_name
                
                logger.info(f"Данные пользователя: username={username}, first_name={first_name}, last_name={last_name}")
                
                await db.execute("""
                    INSERT INTO Users (UserID, Username, FirstName, LastName, Approve, WasApproved, Synced, Notified, Banned)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, username, first_name, last_name, False, False, False, False, False))
                await db.commit()
                logger.info(f"Пользователь {user_id} добавлен в базу")
                await state.set_state(Verification.waiting_email)  # Устанавливаем состояние ожидания email
                await message.answer(email_request, reply_markup=remove_keyboard())
                return

            Approve, WasApproved = user
            current_state = await state.get_state()

            if Approve:
                # Пользователь верифицирован
                logger.info(f"Пользователь {user_id} верифицирован.")
                await state.set_state(Verification.verified)
                await message.answer(email_verified, reply_markup=verified_keyboard())

            elif not Approve and WasApproved:
                # Пользователь утратил статус верифицированного (уволен)
                logger.info(f"Пользователь {user_id} имеет признаки уволенного и нажал /start.")
                await state.set_state(Verification.waiting_email)
                await message.answer(email_fired, reply_markup=remove_keyboard())

            elif current_state == Verification.waiting_email:
                # Уже в состоянии ожидания email
                logger.info(f"Пользователь {user_id} находится в waiting_email при /start.")
                data = await state.get_data()
                saved_email = data.get("email")

                if saved_email:
                    # Если email уже есть в FSM data, переводим в waiting_confirm
                    logger.info(f"У пользователя {user_id} уже есть email={saved_email} в data. Переводим в waiting_confirm.")
                    await state.set_state(Verification.waiting_confirm)
                    await message.answer(
                        email_not_verified(saved_email),
                        reply_markup=email_keyboard()
                    )
                else:
                    # Email нет, просим ввести
                    logger.info(f"У пользователя {user_id} нет email в data. Просим ввести заново.")
                    await message.answer(email_request, reply_markup=remove_keyboard())

            elif current_state == Verification.waiting_confirm:
                # Ожидание подтверждения email
                logger.info(f"Пользователь {user_id} в состоянии waiting_confirm и нажал /start.")
                await message.answer(email_actions, reply_markup=email_keyboard())

            elif current_state == Verification.waiting_code:
                # Ожидание ввода кода
                logger.info(f"Пользователь {user_id} ожидает ввода кода.")
                await message.answer(code_request, reply_markup=remove_keyboard())

            else:
                # Предложить пройти верификацию
                logger.info(f"Пользователю {user_id} предложена повторная верификация (неизвестное состояние).")
                await state.set_state(Verification.waiting_email)
                await message.answer(email_request, reply_markup=remove_keyboard())

        except Exception as e:
            logger.error(f"Ошибка при обработке команды /start для пользователя {user_id}: {e}")
