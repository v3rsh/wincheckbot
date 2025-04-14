#!/usr/bin/env python3
"""
export_all_emails.py
Экспортирует всех пользователей с непустым email,
независимо от статуса верификации.

1) Выбирает всех пользователей с непустым Email
2) Пропускает, если email в EXCLUDED_EMAILS
3) Выгружает (UserID;расшифрованный_email) в ./export/all_emails_YYYYmmDD_HHMMSS.csv
4) Пишет запись в SyncHistory
"""
import os
import asyncio
import csv
import aiosqlite
import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from database import get_user_email
from config import EXCLUDED_EMAILS, logger, DB_PATH

OUTPUT_DIR = "./export"

async def main():
    logger.info("=== [export_all_emails.py] Начинаем экспорт всех пользователей с email ===")
    logger.info(f"Current working directory: {os.getcwd()}")
    
    today_str = datetime.date.today().strftime("%Y%m%d")
    time_str = datetime.datetime.now().strftime("%H%M")
    out_filename = f"export_{today_str}_{time_str}.csv"
    outpath = Path(OUTPUT_DIR) / out_filename
    
    logger.info(f"Attempting to create file: {outpath.absolute()}")
    
    async with aiosqlite.connect(DB_PATH) as db:
        # Находим всех пользователей с непустым Email
        cursor = await db.execute("""
            SELECT ID, UserID, Email
              FROM Users
             WHERE Email IS NOT NULL
               AND Email != ''
        """)
        rows = await cursor.fetchall()

        if not rows:
            logger.info("Нет пользователей с email.")
            return

        exported_count = 0

        # Пишем CSV
        with outpath.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["UserID", "Email"])  # Только стандартные колонки

            for row_id, user_id, enc_email in rows:
                # Расшифровываем email
                plain_email = await get_user_email(user_id)
                
                # Пропускаем, если email в EXCLUDED_EMAILS
                if plain_email.strip().lower() in [ex.strip().lower() for ex in EXCLUDED_EMAILS if ex.strip()]:
                    continue

                writer.writerow([user_id, plain_email])
                exported_count += 1

        logger.info(f"Создан файл: {outpath}. Экспортировано {exported_count} пользователей.")

        if exported_count == 0:
            logger.info("Фактически никто не попал в выгрузку (из-за EXCLUDED_EMAILS). Прерываем.")
            return

        # Записываем в SyncHistory
        await db.execute("""
            INSERT INTO SyncHistory (SyncType, FileName, RecordCount, SyncDate, Comment)
            VALUES (?, ?, ?, DATETIME('now'), ?)
        """, ("export-all", out_filename, exported_count, "All users with email"))
        await db.commit()
    
    logger.info("=== Экспорт всех email завершён. ===\n")

if __name__ == "__main__":
    asyncio.run(main()) 