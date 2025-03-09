#!/usr/bin/env python3
"""
import.py
Запускается раз в сутки в 20:00
"""

import asyncio
from dotenv import load_dotenv

load_dotenv()
from config import logger, DB_PATH
from utils.file_ops import (
    is_export_empty,
    find_import_file,
    skip_import_file,
    archive_import_file,
    parse_csv_users
)
from utils.import_logic import process_unapproved_in_db
from utils.notify import notify_newly_fired
import aiosqlite

async def main():
    logger.info("=== [import.py] Начинаем обработку файла от компании ===")

    # 0) Проверяем, пуста ли папка /export
    if not is_export_empty():
        # Значит, компания не забрала файлы из /export => пропускаем этот импорт
        skip_filename = find_import_file()
        if skip_filename:
            skip_import_file(skip_filename)
            await write_sync_history("import-skipped", skip_filename, 0)
        else:
            logger.info("Нет файла для импорта (или неверное имя), пропускаем.")
        return

    # 1) Ищем файл active_users_YYYYmmDD.csv
    in_filename = find_import_file()
    if not in_filename:
        logger.warning("Файл импортa не найден или неправильно назван. Выходим.")
        return

    # 2) Парсим CSV — получаем user_ids
    user_ids = parse_csv_users(in_filename)
    if not user_ids:
        logger.error(f"Не удалось прочесть {in_filename}, возможно файл пуст или поврежден.")
        archive_import_file(in_filename, success=False)
        return

    logger.info(f"Прочитано {len(user_ids)} актуальных user_id из {in_filename}.")

    # 3) Снимаем Approve=TRUE тем, кто не в списке (и не в EXCLUDED_EMAILS)
    changed_users = await process_unapproved_in_db(user_ids, in_filename)
    
    # 4) Отправляем уведомления только тем, кому ещё не отправляли
    if changed_users:
        logger.info(f"Формирование уведомлений для {len(changed_users)} уволенных.")
        await notify_newly_fired(changed_users)
    else:
        logger.info("Никому не нужно отправлять уведомления.")

    # 5) Переносим обработанный файл в ./import/archived
    archive_import_file(in_filename, success=True)

    logger.info("=== Импорт завершён ===")


async def write_sync_history(sync_type: str, filename: str, count: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO SyncHistory (SyncType, FileName, RecordCount, SyncDate)
            VALUES (?, ?, ?, DATETIME('now'))
        """, (sync_type, filename, count))
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
