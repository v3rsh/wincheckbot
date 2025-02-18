from aiogram import Router, types
from aiogram.filters.command import Command  # Обновлён импорт
from config import WORK_MAIL, logger  # Добавлен импорт логгера при необходимости

router = Router()

@router.message(Command("instruction"))
async def send_instruction(message: types.Message):
    logger.info(f"Пользователь {message.from_user.id} вызвал команду /instruction")
    instruction_text = (
        f"Здравствуйте! Для доступа к корпоративному каналу необходимо пройти верификацию.\n\n"
        f"**Зачем это нужно?**\n"
        f"Верификация подтверждает, что вы являетесь сотрудником компании, что позволяет обеспечить безопасность и доступ к внутренним ресурсам.\n\n"
        f"**Как её провести?**\n"
        f"1. Введите ваш рабочий email в формате `имя@{WORK_MAIL}`.\n"
        f"2. На указанный email будет отправлен код подтверждения.\n"
        f"3. Введите полученный код в боте для завершения верификации.\n\n"
        f"**Что это даёт пользователю?**\n"
        f"После успешной верификации вы получите доступ к корпоративному каналу, где сможете получать актуальные новости, объявления и участвовать в обсуждениях."
    )
    await message.answer(instruction_text, parse_mode='Markdown')
