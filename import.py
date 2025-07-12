#!/usr/bin/env python3
"""
import.py
Запускается раз в сутки в 20:00
"""
import os
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
from utils.import_logic import process_unapproved_in_db, restore_banned_users
from utils.notify import notify_newly_fired
import aiosqlite

os.getcwd()

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
    previous_user_ids = parse_csv_users(last_archived_file.name)

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

    filename = find_import_file()
    if filename:
        logger.info(f"Filename type: {type(filename)}, value: {filename}")
    
    # 0) Проверяем, пуста ли папка /export
    if not is_export_empty():
        # Значит, компания не забрала файлы из /export => пропускаем этот импорт
        if filename:
            skip_import_file(filename)
            await write_sync_history("import-skipped", filename, 0, comment="Файлы в папке export не обработаны")
        else:
            logger.info("Нет файла для импорта (или неверное имя), пропускаем.")
        return

    # 1) Проверяем наличие файла
    if not filename:
        logger.warning("Файл импортa не найден или неправильно назван. Выходим.")
        await write_sync_history("import-skipped", "no file found", 0, comment="Файл импортa не найден или неправильно назван")
        return

    # 2) Парсим CSV — получаем user_ids
    # Используем filename напрямую, без relative_to
    user_ids = parse_csv_users(filename)
    if not user_ids:
        logger.error(f"Не удалось прочесть {filename}, возможно файл пуст или поврежден.")
        await write_sync_history("import-skipped", filename, 0, comment=f"Не удалось прочесть {filename}, возможно файл пуст или поврежден")
        archive_import_file(filename, success=False)
        return

    logger.info(f"Прочитано {len(user_ids)} актуальных user_id из {filename}.")

    # Сравниваем с предыдущим
    if not await compare_with_previous_import(user_ids):
        logger.critical("Обнаружены аномальные различия. Обработка прервана.")
        await write_sync_history("import-skipped", filename, 0, comment="Обнаружены аномальные различия. Обработка прервана.")
        return
    # Если все ок, продолжаем
    logger.info("Обработка продолжается...")
    
    # 3) Снимаем Approve=TRUE тем, кто не в списке (и не в EXCLUDED_EMAILS)
    changed_users = await process_unapproved_in_db(user_ids, filename)
    if changed_users:
        changed_ids_str = ", ".join(map(str, changed_users))
        logger.info(f"Уволено {len(changed_users)} пользователей: {changed_ids_str}")
    else:
        changed_ids_str = ""
        logger.info("Нет пользователей для увольнения.")
    
    # 3.1) Восстанавливаем доступ пользователям, которые ранее были забанены, но теперь в списке
    restored_users = await restore_banned_users(user_ids)
    if restored_users:
        restored_ids_str = ", ".join(map(str, restored_users))
        logger.info(f"Восстановлен доступ для {len(restored_users)} пользователей: {restored_ids_str}")
    else:
        restored_ids_str = ""
        logger.info("Нет пользователей для восстановления доступа.")
    
    # 4) Отправляем уведомления только тем, кому ещё не отправляли
    notified_users = []
    if changed_users:
        logger.info(f"Формирование уведомлений для {len(changed_users)} уволенных.")
        notified_users = await notify_newly_fired(changed_users)
        if notified_users:
            notified_ids_str = ", ".join(map(str, notified_users))
            logger.info(f"Отправлены уведомления {len(notified_users)} пользователям: {notified_ids_str}")
        else:
            logger.info("Уведомления не были отправлены.")
    else:
        logger.info("Никому не нужно отправлять уведомления.")

    # Формируем комментарий для SyncHistory
    comment_parts = []
    if restored_users:
        comment_parts.append(f"восстановлено: {len(restored_users)} ({restored_ids_str})")
    if changed_users:
        comment_parts.append(f"уволено: {len(changed_users)} ({changed_ids_str})")
    if notified_users:
        comment_parts.append(f"уведомлено: {len(notified_users)} ({', '.join(map(str, notified_users))})")
    
    comment = f"success ({'; '.join(comment_parts)})" if comment_parts else "success"
    await write_sync_history("import", filename, len(user_ids), comment=comment)

    # 5) Переносим обработанный файл в ./import/archived
    archive_import_file(filename, success=True)
    
    logger.info("=== Импорт завершён ===")


async def write_sync_history(sync_type: str, filename: str, count: int, comment: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO SyncHistory (SyncType, FileName, RecordCount, SyncDate, Comment)
            VALUES (?, ?, ?, DATETIME('now', 'localtime'), ?)
        """, (sync_type, filename, count, comment))
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
