#!/usr/bin/env python3
"""
Скрипт для восстановления Approve=TRUE:
- Всем UserID из последнего файла импорта (import/archived/active_users_YYYYMMDD.csv)
- Всем, чей email в EXCLUDED_EMAILS
"""
import os
import sys
import asyncio
import aiosqlite
import csv
from pathlib import Path

# Добавляем корень проекта в sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import logger, DB_PATH, EXCLUDED_EMAILS

ARCHIVE_DIR = "import/archived"


def find_latest_import_file() -> Path:
    """
    Находит последний по дате файл active_users_YYYYMMDD.csv в архиве импорта.
    """
    archive = Path(ARCHIVE_DIR)
    files = list(archive.glob("active_users_*.csv"))
    if not files:
        return None
    # Сортируем по дате в имени файла
    files.sort(key=lambda f: f.stem.split('_')[-1], reverse=True)
    return files[0]


def read_user_ids_from_csv(csv_path: Path) -> set:
    """
    Читает все UserID из файла импорта.
    """
    user_ids = set()
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            try:
                user_ids.add(int(row["UserID"]))
            except Exception:
                continue
    return user_ids

async def recover_approve():
    logger.info("=== [recover.py] Восстановление Approve=TRUE по последнему импорту и EXCLUDED_EMAILS ===")
    latest_file = find_latest_import_file()
    if not latest_file:
        logger.error(f"Не найден файл active_users_*.csv в {ARCHIVE_DIR}")
        return
    logger.info(f"Используется файл: {latest_file}")
    user_ids = read_user_ids_from_csv(latest_file)
    logger.info(f"UserID из файла: {len(user_ids)}")

    # Приводим EXCLUDED_EMAILS к нижнему регистру и убираем пустые
    excluded_emails = [e.strip().lower() for e in EXCLUDED_EMAILS if e.strip()]
    logger.info(f"EXCLUDED_EMAILS: {excluded_emails}")

    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Approve=TRUE для UserID из файла
        if user_ids:
            placeholders = ",".join(["?"] * len(user_ids))
            await db.execute(f"UPDATE Users SET Approve=TRUE WHERE UserID IN ({placeholders})", tuple(user_ids))
            logger.info(f"Approve=TRUE выставлен {len(user_ids)} пользователям из файла.")
        else:
            logger.info("Нет UserID для восстановления из файла.")

        # 2. Approve=TRUE для email в EXCLUDED_EMAILS
        if excluded_emails:
            placeholders = ",".join(["?"] * len(excluded_emails))
            await db.execute(f"UPDATE Users SET Approve=TRUE WHERE lower(Email) IN ({placeholders})", tuple(excluded_emails))
            logger.info(f"Approve=TRUE выставлен пользователям с email из EXCLUDED_EMAILS.")
        else:
            logger.info("EXCLUDED_EMAILS пуст.")

        await db.commit()
    logger.info("=== Восстановление Approve завершено ===")

if __name__ == "__main__":
    asyncio.run(recover_approve()) 