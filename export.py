#!/usr/bin/env python3
"""
export.py
Запускается раз в сутки в 08:00 (cron).
1) Выбирает пользователей: Approve=TRUE и Synced=FALSE,
2) Пропускает, если email в EXCLUDED_EMAILS,
3) Выгружает (UserID;расшифрованный_email) в ./export/export_YYYYmmDD_HHMMSS.csv,
4) Ставит Synced=TRUE,
5) Пишет запись в SyncHistory (или лог).
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
    logger.info("=== [export.py] Начинаем экспорт пользователей для компании ===")
    logger.info(f"Current working directory: {os.getcwd()}")
    
    today_str = datetime.date.today().strftime("%Y%m%d")
    # Добавляем время в формате HHMM для уникальности имени файла
    time_str = datetime.datetime.now().strftime("%H%M")
    out_filename = f"export_{today_str}_{time_str}.csv"
    outpath = Path(OUTPUT_DIR) / out_filename
    
    logger.info(f"Attempting to create file: {outpath.absolute()}")  # Добавляем эту строку
    
    async with aiosqlite.connect(DB_PATH) as db:
        # 1) Находим всех, кто Approve=TRUE, Synced=FALSE
        #    и не входит в EXCLUDED_EMAILS
        cursor = await db.execute("""
            SELECT ID, UserID, Email
              FROM Users
             WHERE Approve=TRUE
               AND Synced=FALSE
        """)
        rows = await cursor.fetchall()

        if not rows:
            logger.info("Нет пользователей для экспорта (Approve=TRUE, Synced=FALSE).")
            return

        to_update_ids = []
        exported_count = 0

        # 2) Пишем CSV
        with outpath.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["UserID", "Email"])  # заголовок

            for row_id, user_id, enc_email in rows:
                # Расшифровываем email
                plain_email = await get_user_email(user_id)

                # Пропускаем, если email в EXCLUDED_EMAILS
                if plain_email.strip().lower() in [ex.strip().lower() for ex in EXCLUDED_EMAILS if ex.strip()]:
                    continue

                writer.writerow([user_id, plain_email])
                to_update_ids.append(row_id)
                exported_count += 1

        logger.info(f"Создан файл: {outpath}. Экспортировано {exported_count} пользователей.")

        if exported_count == 0:
            logger.info("Фактически никто не попал в выгрузку (из-за EXCLUDED_EMAILS). Прерываем.")
            return

        # 3) Обновляем Synced=TRUE
        placeholders = ",".join("?" * len(to_update_ids))
        query = f"UPDATE Users SET Synced=TRUE WHERE ID IN ({placeholders})"
        await db.execute(query, tuple(to_update_ids))
        await db.commit()

        await db.execute("""
            INSERT INTO SyncHistory (SyncType, FileName, RecordCount, SyncDate)
            VALUES (?, ?, ?, DATETIME('now', 'localtime'))
        """, ("export", out_filename, exported_count))
        await db.commit()
    
    logger.info("=== Экспорт завершён. ===\n")

if __name__ == "__main__":
    asyncio.run(main())
