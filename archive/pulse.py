import os
import aiosqlite
import random
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BotCommand, ChatInviteLink, ReplyKeyboardRemove
from aiogram import Router
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from datetime import datetime, timedelta
import requests
import asyncio
import logging
import re
import signal
from aiogram.filters.command import Command
import answer

def handle_exit_signal(signum, frame):
    logger.warning(f"Получен сигнал завершения: {signum}")
    loop = asyncio.get_event_loop()
    loop.stop()
    logger.info("Завершение работы бота.")

signal.signal(signal.SIGTERM, handle_exit_signal)
signal.signal(signal.SIGINT, handle_exit_signal)

# Настройка логирования
logging.basicConfig(
    filename='pulse.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
WORK_MAIL = os.getenv("WORK_MAIL")
UNI_API_KEY = os.getenv("UNI_API_KEY")
UNI_EMAIL = os.getenv("UNI_EMAIL")
COMPANY_CHANNEL_ID = int(os.getenv("COMPANY_CHANNEL_ID"))
EXCLUDED_EMAILS = os.getenv("EXCLUDED_EMAILS", "").split(",")

required_env_vars = ["TELEGRAM_API_TOKEN", "WORK_MAIL", "UNI_API_KEY", "UNI_EMAIL", "COMPANY_CHANNEL_ID"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]

if missing_vars:
    logger.critical(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
    raise EnvironmentError("Не все переменные окружения заданы.")

bot = Bot(token=API_TOKEN)
router = Router()  # Создаем Router глобально
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)  # Router прикрепляется здесь, и больше не нужно повторять


# Регулярное выражение для проверки email
email_regex = re.compile(rf"^[a-zA-Z0-9._%+-]+@{WORK_MAIL}$")

# Инициализация базы данных
async def initialize_db():
    async with aiosqlite.connect("/root/pulse/pulse.db") as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS Users (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                UserID INTEGER UNIQUE,
                Email TEXT,
                Code TEXT,
                Approve BOOLEAN DEFAULT FALSE,
                WasApproved BOOLEAN DEFAULT FALSE,
                EmailAttempts INTEGER DEFAULT 0,
                CodeAttempts INTEGER DEFAULT 0,
                BlockedUntil TIMESTAMP,
                WaitingForCode BOOLEAN DEFAULT FALSE,
                WaitingForEmail BOOLEAN DEFAULT FALSE,
                LastRetry TIMESTAMP
            )
        ''')
        await db.commit()
    logger.info("База данных инициализирована.")

# Кнопки "Отправить снова" и "Изменить адрес"
action_buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Отправить снова", callback_data="retry_code"),
            InlineKeyboardButton(text="Изменить адрес", callback_data="change_email")
        ]
    ]
)

async def ensure_user_in_channel(user_id):
    logger.debug("Начало функции ensure_user_in_channel")
    try:
        member = await bot.get_chat_member(COMPANY_CHANNEL_ID, user_id)
        if member.status in ["member", "creator", "administrator"]:
            # Пользователь уже в канале
            logger.info(f"Пользователь {user_id} уже в канале.")
            return None  # Не требуется создавать ссылку
        else:
            # Пользователь не в канале, создаем новую ссылку
            logger.info(f"Пользователь {user_id} не найден в канале. Создаем новую ссылку.")
            return await create_invite_link()
    except Exception as e:
        logger.error(f"Ошибка при проверке пользователя в канале: {e}")
        # Если возникла ошибка (например, пользователь не найден), создаем новую ссылку
        return await create_invite_link()

async def create_invite_link():
    try:
        # Создаем одноразовую ссылку-приглашение, действующую 1 час
        invite_link = await bot.create_chat_invite_link(
            chat_id=COMPANY_CHANNEL_ID,
            expire_date=datetime.now() + timedelta(hours=1),
            member_limit=1
        )
        return invite_link.invite_link
    except Exception as e:
        logger.error(f"Ошибка при создании ссылки-приглашения: {e}")
        return None


@router.message(Command(commands=["start"]))
async def handle_start(message: types.Message):
    user_id = message.from_user.id
    now = datetime.now()

    async with aiosqlite.connect("/root/pulse/pulse.db") as db:
        cursor = await db.execute("SELECT Email, Code, Approve, WasApproved, CodeAttempts, BlockedUntil, LastRetry FROM Users WHERE UserID = ?", (user_id,))
        user = await cursor.fetchone()

        if not user:
            # Новый пользователь
            await db.execute("INSERT INTO Users (UserID) VALUES (?)", (user_id,))
            await db.commit()
            await message.answer(f"Привет! Чтобы попасть в telegram-канал сотрудников Winline необходимо пройти верификацию. Введи свой рабочий email полностью. ")
            return

        email, code, approve, was_approved, code_attempts, blocked_until, last_retry = user

        # Если пользователь заблокирован
        if blocked_until:
            blocked_until_time = datetime.fromisoformat(blocked_until)
            if now >= blocked_until_time:
                # Блокировка истекла, сбрасываем счетчики и данные
                await db.execute("UPDATE Users SET BlockedUntil = NULL, CodeAttempts = 0, EmailAttempts = 0, Email = NULL, Code = NULL, WaitingForCode = FALSE, WaitingForEmail = FALSE WHERE UserID = ?", (user_id,))
                await db.commit()
                blocked_until = None
                code_attempts = 0
                email = None
                code = None
                await message.answer("Блокировка снята. Попробуй начать верификацию заново. Введи свой рабочий email полностью.")
                return
            else:
                remaining_time = int((blocked_until_time - now).total_seconds() // 60)
                await message.answer(f"Упс! Из-за большого количества неверных попыток ввода, ты заблокирован на {remaining_time} минут. Повтори попытку верификации позже.")
                return

        # Проверка, если Approve = FALSE, но WasApproved = TRUE (пользователь был верифицирован ранее)
        if not approve and was_approved:
            # Сбрасываем данные и предлагаем пройти верификацию заново
            await db.execute("UPDATE Users SET Email = NULL, Code = NULL, WaitingForCode = FALSE, WaitingForEmail = FALSE, WasApproved = FALSE WHERE UserID = ?", (user_id,))
            await db.commit()
            await message.answer(f"По какой-то причине твой статус верификации был сброшен ☹. Введи свой рабочий email полностью для повторной верификации.")
            return

        # Состояние: Верифицирован
        if approve:
            await message.answer("Твой email верифицирован! Добро пожаловать в telegram-канал Winline! ") #тут ссылка тоже должна быть
            return

        # Состояние: Не верифицирован и не ввёл email
        if not email:
            await message.answer(f"Ты пока не указал свой email. Введи свой рабочий email полностью для повторной верификации.  ")
            return

        # Состояние: Не верифицирован, email введён, но код не отправлен
        if email and not code:
            await message.answer(f"Твой email: {email}.Код подтверждения пока не был отправлен. Отправить код? ", reply_markup=action_buttons)
            return

        # Состояние: Код отправлен, но не прошло 3 минуты
        if code and last_retry:
            last_retry_time = datetime.fromisoformat(last_retry)
            if (now - last_retry_time).total_seconds() < 180:  # 3 минуты
                await message.answer(
                    f"Код подтверждения был отправлен на email {email}.\n"
                    f"Проверь папку «Входящие» и «Спам» ",
                    reply_markup=action_buttons,
                )
                return

        # Состояние: Код отправлен, прошло больше 3 минут, но пользователь не ввёл код
        if code and last_retry and (now - datetime.fromisoformat(last_retry)).total_seconds() >= 180:
            await db.execute("UPDATE Users SET Code = NULL, LastRetry = NULL WHERE UserID = ?", (user_id,))
            await db.commit()
            await message.answer(
                f"Код подтверждения истек. Отправить новый код? ",
                reply_markup=action_buttons
            )
            return

        # Состояние: Любое другое состояние
        await message.answer("Что-то не так, я не могу определить твой статус пользователя. Попробуй отправить /start для новой попытки верификации.")

# Хэндлер команды /instruction для отправки инструкции по верификации

@router.message(Command("instruction"))
async def send_instruction(message: types.Message):
    instruction_text = (
        f"Привет! Чтобы попасть в telegram-канал сотрудников Winline, необходимо пройти верификацию. \n\n"
        f"**Зачем это нужно?**\n"
        f"Верификация подтвердит, что ты – сотрудник Winline и позволит ограничить доступ к информации, которая адресована здесь исключительно сотрудникам нашей команды. \n\n"
        f"**Как её провести?**\n"
        f"1. Введите ваш рабочий email в формате `имя@{WORK_MAIL}`.\n"
        f"2. На указанный email будет отправлен код подтверждения.\n"
        f"3. Введите полученный код в боте для завершения верификации.\n\n"
        f"**Что это даёт пользователю?**\n"
        f"После успешной верификации ты получишь доступ к корпоративному telegram-каналу, где сможешь получать все актуальные новости и важные объявления, а также участвовать в обсуждениях команды."
    )
    await message.answer(instruction_text, parse_mode=ParseMode.MARKDOWN_V2)

# Функция проверки email
def is_valid_email(email: str) -> bool:
    """Проверяет email на соответствие шаблону ИЛИ наличие в списке исключений."""
    return email_regex.match(email) or email in EXCLUDED_EMAILS

@router.message(F.text & F.chat.type == "private")
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()
    now = datetime.now()

    async with aiosqlite.connect("/root/pulse/pulse.db") as db:
        cursor = await db.execute(
            "SELECT Email, Code, Approve, WasApproved, WaitingForCode, WaitingForEmail, CodeAttempts, EmailAttempts, BlockedUntil FROM Users WHERE UserID = ?",
            (user_id,)
        )
        user = await cursor.fetchone()

        if not user:
            await message.answer("Пожалуйста, отправь /start для начала работы бота.")
            return

        email, code, approve, was_approved, waiting_for_code, waiting_for_email, code_attempts, email_attempts, blocked_until = user

        # Если пользователь заблокирован
        if blocked_until:
            blocked_until_time = datetime.fromisoformat(blocked_until)
            if now >= blocked_until_time:
                # Сброс состояния после блокировки
                await db.execute(
                    "UPDATE Users SET BlockedUntil = NULL, CodeAttempts = 0, EmailAttempts = 0, Email = NULL, Code = NULL, WaitingForCode = FALSE, WaitingForEmail = FALSE WHERE UserID = ?",
                    (user_id,)
                )
                await db.commit()
                await message.answer("Блокировка снята. Попробуй начать верификацию заново. Введи свой рабочий email полностью.")
                return
            else:
                remaining_time = int((blocked_until_time - now).total_seconds() // 60)
                await message.answer(f"Ввод временно заблокирован. Подожди еще {remaining_time} минут.")
                return

        # Если бот ожидает email или email отсутствует
        if waiting_for_email or not email:
            if not is_valid_email(text):
                email_attempts += 1
                if email_attempts >= 3:
                    block_time = now + timedelta(minutes=5)
                    await db.execute(
                        "UPDATE Users SET EmailAttempts = ?, BlockedUntil = ?, Email = NULL, Code = NULL, WaitingForCode = FALSE, WaitingForEmail = FALSE WHERE UserID = ?",
                        (email_attempts, block_time.isoformat(), user_id)
                    )
                    await db.commit()
                    await message.answer("Упс! Из-за большого количества неверных попыток ввода, ты заблокирован на 5 минут. Повтори попытку верификации позже.")
                    return
                else:
                    await db.execute("UPDATE Users SET EmailAttempts = ? WHERE UserID = ?", (email_attempts, user_id))
                    await db.commit()
                await message.answer(f"Ты ввел некорректный email. Рабочий email сотрудника должен содержать домен {WORK_MAIL}.")
                return

            new_code = str(random.randint(100000, 999999))
            await db.execute(
                "UPDATE Users SET Email = ?, Code = ?, WaitingForCode = TRUE, WaitingForEmail = FALSE, LastRetry = ?, CodeAttempts = 0, BlockedUntil = NULL WHERE UserID = ?",
                (text, new_code, now.isoformat(), user_id)
            )
            await db.commit()
            await send_email(text, new_code)
            await message.answer(
                "На указанную почту был отправлен код подтверждения. Проверь папки «Входящие» и «Спам», код придет в течение 10 минут.\n"
                "Введи, полученный код, в строке для ввода.\n"
                "Если код не пришел, то выбери команду /start и начни сначала"
            )
            return

        # Если бот ожидает код подтверждения
        if waiting_for_code:
            if text.isdigit() and code and text == code:  # Успешное совпадение кода
                await db.execute(   
                    "UPDATE Users SET Approve = TRUE, WasApproved = TRUE, WaitingForCode = FALSE, Code = NULL, CodeAttempts = 0 WHERE UserID = ?",
                    (user_id,)
                )
                await db.commit()

                try:
                    # Создаем одноразовую ссылку-приглашение
                    invite_link = await bot.create_chat_invite_link(
                        chat_id=COMPANY_CHANNEL_ID,
                        expire_date=datetime.now() + timedelta(hours=1),
                        member_limit=1
                    )

                    invite_keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="Перейти в канал компании", url=invite_link.invite_link)]
                        ]
                    )
                    await message.answer(
                        "Код подтвержден! Добро пожаловать в telegram-канал сотрудников Winline!",
                        reply_markup=invite_keyboard
                    )
                except Exception as e:
                    logger.error(f"Ошибка при создании ссылки-приглашения: {e}")
                    await message.answer("Код подтверждён, но возникла ошибка при создании ссылки. Свяжись с администратором через команду /help.")
                return
            else:
                # Неверный код
                code_attempts += 1
                if code_attempts >= 3:  # Блокируем пользователя после 3 попыток
                    block_time = now + timedelta(minutes=5)
                    await db.execute(
                        "UPDATE Users SET BlockedUntil = ?, WaitingForCode = FALSE, Code = NULL, CodeAttempts = 0 WHERE UserID = ?",
                        (block_time.isoformat(), user_id)
                    )
                    await db.commit()
                    await message.answer(
                        "Упс! Ты ввел неверный код 3 раза. Ты временно заблокирован на 5 минут. Попробуй позже."
                    )
                else:
                    await db.execute("UPDATE Users SET CodeAttempts = ? WHERE UserID = ?", (code_attempts, user_id))
                    await db.commit()
                    await message.answer(f"Неверный код. У тебя осталось {3 - code_attempts} попытки. Попробуй снова.")
                return

        # Любой другой случай
        if not approve:
            await message.answer("Пожалуйста, введи свой рабочий email для верификации.")
        else:
            await message.answer("Твой email уже верифицирован!")

@router.callback_query(F.data == "retry_code")
async def handle_retry_code(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    now = datetime.now()

    async with aiosqlite.connect("/root/pulse/pulse.db") as db:
        cursor = await db.execute("SELECT Email, Approve, BlockedUntil FROM Users WHERE UserID = ?", (user_id,))
        user = await cursor.fetchone()

        if not user:
            await callback_query.message.answer("Ты еще не запускал процесс верификации. Отправь /start для начала работы.")
            await callback_query.answer()
            return

        email, approve, blocked_until = user

        if blocked_until:
            blocked_until_time = datetime.fromisoformat(blocked_until)
            if now < blocked_until_time:
                remaining_time = int((blocked_until_time - now).total_seconds() // 60)
                await callback_query.message.answer(f"Ввод временно заблокирован. Подожди еще {remaining_time} минут.")
                await callback_query.answer()
                return

        if approve:
            await callback_query.message.answer("Твой email уже верифицирован! Добро пожаловать в telegram-канал Winline!") # Добавить генерацию ссылки
            await callback_query.answer()
            return

        if not email:
            await callback_query.message.answer("Введи свой рабочий email.")
            await callback_query.answer()
            return

        new_code = str(random.randint(100000, 999999))
        await db.execute("UPDATE Users SET Code = ?, WaitingForCode = TRUE, LastRetry = ?, CodeAttempts = 0 WHERE UserID = ?", (new_code, now.isoformat(), user_id))
        await db.commit()
        await send_email(email, new_code)
        await callback_query.message.answer(f"Код подтверждения был повторно отправлен на {email}. Проверьте почту.")
        await callback_query.answer()

# Обработчик inline кнопки "Изменить адрес"
@dp.callback_query(F.data == "change_email")
async def handle_change_email(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    async with aiosqlite.connect("/root/pulse/pulse.db") as db:
        cursor = await db.execute("SELECT Email FROM Users WHERE UserID = ?", (user_id,))
        user = await cursor.fetchone()
        if not user:
            await callback_query.message.answer("Вы не зарегистрированы. Отправьте /start для начала работы.")
            await callback_query.answer()
            return

        await db.execute("UPDATE Users SET WaitingForEmail = TRUE, Email = NULL, Code = NULL, WaitingForCode = FALSE WHERE UserID = ?", (user_id,))
        await db.commit()

        await callback_query.message.answer("Введите новый email для изменения текущего адреса.")
        await callback_query.answer()

# Хэндлер команды /check для проверки статуса

@router.message(Command(commands=["check"]))
async def check_status(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect("/root/pulse/pulse.db") as db:
        cursor = await db.execute("SELECT Email, Approve FROM Users WHERE UserID = ?", (user_id,))
        user = await cursor.fetchone()
        if not user:
            await message.answer("Ты еще не запускал процесс верификации. Отправь /start для начала работы.")
            return

        email, approve = user
        if approve:
            invite_link = await ensure_user_in_channel(user_id)
            if invite_link:
                # Если пользователь не в канале, отправляем новую ссылку
                invite_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="Перейти в канал компании", url=invite_link)]
                    ]
                )
                await message.answer(
                    "Твой email уже верифицирован! Добро пожаловать в telegram-канал Winline!",
                    reply_markup=invite_keyboard
                )
            else:
                # Если пользователь уже в канале
                await message.answer("Твой email уже верифицирован, и ты уже в канале компании! Добро пожаловать!")

        else:
            await message.answer(
                f"Твой email пока не верифицирован! Отправить код повторно или изменить адрес рабочей почты?",
                reply_markup=action_buttons
            )


# Функция отправки email через UniSender
async def send_email(to_email, code):
    try:
        url = "https://api.unisender.com/ru/api/sendEmail"
        email_body = f"""
        <html>
        <body>
            <h1>Подтверждение регистрации</h1>
            <p>Твой код подтверждения: <strong>{code}</strong></p>
            <p>Введи его в боте для завершения верификации.</p>
        </body>
        </html>
        """
        payload = {
            "api_key": UNI_API_KEY,
            "sender_name": "HR отдел Winline",
            "sender_email": UNI_EMAIL,
            "subject": "Код подтверждения",
            "body": email_body,
            "list_id": "8",  # ID списка
            "email": to_email
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        response = requests.post(url, data=payload, headers=headers)
        response.raise_for_status()  # Поднимает исключение при HTTP-ошибке
        response_data = response.json()

        if response.status_code == 200 and 'result' in response_data:
            logger.info(f"Письмо успешно отправлено на {to_email}. ID письма: {response_data['result']['email_id']}")
            return True
        else:
            logger.error(f"Ошибка при отправке письма: {response_data}")
            return False
    except requests.exceptions.RequestException as e:
        logger.exception(f"Сетевая ошибка при отправке письма на {to_email}: {e}")
        return False


async def main():
    await initialize_db()  # Инициализация базы данных
    logger.info("Бот успешно запущен.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
