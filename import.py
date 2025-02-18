#!/usr/bin/env python3
"""
import.py
Запускается раз в сутки в 20:00
1) Ищет файл в папке ./import вида: active_users_YYYYmmDD.csv
2) Читает UserID
3) Ставим Approve=FALSE всем, у кого Approve=TRUE, но они не в списке, за исключением
   тех пользователей, у кого Email в EXCLUDED_EMAILS (не трогаем их).
4) Рассылаем уведомления об утрате статуса.
5) Пишем SyncHistory
"""

import asyncio
import csv
import datetime
from pathlib import Path
import aiosqlite
from config import logger, EXCLUDED_EMAILS
from database import DB_PATH, get_user_email
from aiogram import Bot
from config import API_TOKEN
# from states import Verification  # Если нужно
# from combine.answer import ...
# from config import ...
# from main import bot  # Можно, но лучше создавать новый Bot

IMPORT_DIR = "./import"

NOTIFICATION_TEXT = (
    "Здравствуйте! \n"
    "Компания обновила список активных сотрудников, и ваш статус был сброшен. "
    "Чтобы продолжить пользоваться рабочими группами, необходимо вновь пройти верификацию."
)

async def main():
    logger.info("=== [import.py] Начинаем обработку файла от компании ===")

    # 1) Определяем имя файла: active_users_YYYYmmDD.csv
    today_str = datetime.date.today().strftime("%Y%m%d")
    in_filename = f"active_users_{today_str}.csv"
    inpath = Path(IMPORT_DIR) / in_filename

    if not inpath.exists():
        logger.error(f"Файл {inpath} не найден. Предполагается что компания кладёт его.")
        return

    # 2) Собираем user_id из CSV
    active_user_ids = set()
    with inpath.open("r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        for row in reader:
            if not row:
                continue
            try:
                uid = int(row[0])
                active_user_ids.add(uid)
            except ValueError:
                logger.warning(f"Некорректная строка в CSV: {row}")

    logger.info(f"Прочитано {len(active_user_ids)} актуальных user_id из {inpath}.")

    # 3) Ставим Approve=FALSE всем, кто Approve=TRUE и не в active_user_ids.
    #    Но пропускаем (не трогаем) тех, у кого email в EXCLUDED_EMAILS.
    #    => Нужно SELECT-ить всех Approve=TRUE, а затем фильтровать.

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
          SELECT ID, UserID, Email
            FROM Users
           WHERE Approve=TRUE
        """)
        rows = await cursor.fetchall()

        changed_users = []
        for row_id, user_id, enc_email in rows:
            # Если user_id не в списке => надо сбросить Approve=FALSE
            if user_id not in active_user_ids:
                # Проверим email
                plain_email = await get_user_email(user_id)
                if plain_email.strip().lower() in [ex.strip().lower() for ex in EXCLUDED_EMAILS if ex.strip()]:
                    # Не трогаем
                    continue
                # Иначе снимаем Approve=TRUE
                changed_users.append((row_id, user_id))

        if not changed_users:
            logger.info("Никого не перевели на Approve=FALSE (либо EXCLUDED, либо все присутствуют).")
        else:
            ids_list = [r[0] for r in changed_users]
            placeholders = ",".join("?" * len(ids_list))
            await db.execute(f"""
                UPDATE Users
                   SET Approve=FALSE, WasApproved=TRUE
                 WHERE ID IN ({placeholders})
            """, tuple(ids_list))
            await db.commit()

            logger.info(f"Approve=FALSE выставлен для {len(changed_users)} пользователей.")
            # Записываем историю
            await db.execute("""
                INSERT INTO SyncHistory (SyncType, FileName, RecordCount, SyncDate)
                VALUES (?, ?, ?, DATETIME('now'))
            """, ("import", in_filename, len(changed_users)))
            await db.commit()

    # 4) Рассылаем уведомления по Telegram-боту
    if changed_users:
        async with Bot(token=API_TOKEN) as bot:
            # Для каждого user_id шлём сообщение:
            for _, user_id in changed_users:
                try:
                    await bot.send_message(user_id, NOTIFICATION_TEXT)
                    logger.info(f"Пользователю {user_id} отправлено уведомление о необходимости повторной верификации.")
                except Exception as e:
                    logger.warning(f"Не удалось отправить сообщение user_id={user_id}: {e}")

    logger.info("=== Импорт завершён ===")

if __name__ == "__main__":
    asyncio.run(main())
