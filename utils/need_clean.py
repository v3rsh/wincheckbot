# need_clean.py

import os
import aiosqlite
from datetime import datetime, timedelta
from typing import Tuple

from config import logger, MAINTENANCE_MODE

from os import listdir
from os.path import isfile, join

# Здесь идут твои функции:
# 1) ensure_comment_column(db)
# 2) check_if_need_to_skip(db)
# 3) check_export_dir()
# 4) write_skip_history(db, reason)
# 5) get_eligible_groups(db)

async def ensure_comment_column(db: aiosqlite.Connection):
    """
    Проверяем, есть ли колонка Comment в SyncHistory.
    Если нет — добавляем.
    """
    try:
        await db.execute("ALTER TABLE SyncHistory ADD COLUMN Comment TEXT")
        await db.commit()
        logger.info("[ensure_comment_column] Добавлена колонка Comment в SyncHistory.")
    except aiosqlite.OperationalError as e:
        # Если ошибка "duplicate column name", то всё ок, колонка уже есть.
        if "duplicate column name" in str(e).lower():
            logger.info("[ensure_comment_column] Колонка Comment уже существует, пропускаем.")
        else:
            logger.warning(f"[ensure_comment_column] Ошибка при добавлении Comment: {e}")


async def check_if_need_to_skip(db: aiosqlite.Connection) -> Tuple[bool, str]:
    """
    Возвращает (True, reason), если нужно пропустить работу cleaner.
    Возвращает (False, "") - если продолжать можно.
    
    Условия (пример):
      1. Нет удачного импорта за вчера? (в SyncHistory нет записи import c yesterday)
      2. В папке /export лежат не забранные файлы? (Сценарий, где logика не позволяет чистить)
      3. Groups вообще нет (частично проверим тут — или в основном коде)
      ... и т.д.
      
    MAINTENANCE_MODE больше не останавливает выполнение скрипта полностью,
    а только блокирует фактические операции ban_chat_member.
    """

    # (1) Нет удачного импорта за прошедший день
    # Предположим, мы считаем "удачным" любой import с RecordCount >= 0
    # (или можно искать конкретный FileName != '-skipped' и т.п.)
    yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
    cursor = await db.execute("""
        SELECT COUNT(*)
          FROM SyncHistory
         WHERE SyncType='import'
           AND date(SyncDate, 'localtime') = ?
    """, (yesterday,))
    (import_count,) = await cursor.fetchone()

    if import_count == 0:
        return (True, f"No import for {yesterday}")

    # (3) Проверяем /export
    export_files = check_export_dir()
    if export_files:
        return (True, f"Export folder not empty: {export_files}")

    # Если всё ок — не пропускаем
    return (False, "")


def check_export_dir() -> list:
    """
    Проверяет, есть ли файлы в /export.
    Возвращает список файлов, если есть, иначе пустой список.
    """
    from os import listdir
    from os.path import isfile, join

    EXPORT_DIR = "./export"
    files = [f for f in listdir(EXPORT_DIR) if isfile(join(EXPORT_DIR, f))]
    return files


async def write_skip_history(db: aiosqlite.Connection, comment: str):
    """
    Пишет запись в SyncHistory о пропуске cleaner.
    """
    await db.execute("""
        INSERT INTO SyncHistory (SyncType, FileName, RecordCount, SyncDate, Comment)
        VALUES (?, ?, ?, DATETIME('now', 'localtime'), ?)
    """, ("cleaner-skip", "-", 0, comment))
    await db.commit()


async def get_eligible_groups(db: aiosqlite.Connection) -> list:
    """
    Возвращает список chat_id, где can_restrict_members=TRUE.
    """
    cursor = await db.execute("""
        SELECT ChatID
          FROM Groups
         WHERE can_restrict_members=TRUE
    """)
    rows = await cursor.fetchall()
    return [r[0] for r in rows]
