#!/usr/bin/env python3
"""
import.py
Запускается раз в сутки в 20:00
"""
import asyncio
from pathlib import Path
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

async def compare_with_previous_import(current_user_ids: set[int]) -> bool:
    """
    Сравнивает текущий список user_id с последним успешным импортом.
    Возвращает True, если различия допустимы, и False, если они слишком велики.
    """
    archived_dir = Path("./import/archived")
    archived_files = sorted(
        archived_dir.glob("active_users_*.csv"),
        key=lambda x: x.stem.split('_')[-1],
        reverse=True
    )

    if not archived_files:
        logger.info("Нет предыдущих файлов для сравнения. Продолжаем.")
        return True

    last_archived_file = archived_files[0]
    previous_user_ids = parse_csv_users(str(last_archived_file))

    if not previous_user_ids:
        logger.warning(f"Не удалось прочитать {last_archived_file}. Продолжаем.")
        return True

    # Вычисляем различия
    added = len(current_user_ids - previous_user_ids)
    removed = len(previous_user_ids - current_user_ids)
    total_changes = added + removed
    previous_count = len(previous_user_ids)

    # Порог: 50% изменений
    if previous_count > 0 and (total_changes / previous_count) > 0.5:
        logger.error(f"Слишком большие изменения: добавлено {added}, удалено {removed} из {previous_count}.")
        return False
    else:
        logger.info(f"Изменения в норме: добавлено {added}, удалено {removed}.")
        return True


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

    # Сравниваем с предыдущим
    if not await compare_with_previous_import(user_ids):
        logger.critical("Обнаружены аномальные различия. Обработка прервана.")
        return
    # Если все ок, продолжаем
    logger.info("Обработка продолжается...")
    
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
