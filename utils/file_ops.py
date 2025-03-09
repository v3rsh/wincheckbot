# utils/file_ops.py

import os
import csv
import datetime
import shutil
from pathlib import Path
from config import logger

IMPORT_DIR = "./import"
ARCHIVE_SKIPPED = "./import/skipped"
ARCHIVE_DONE = "./import/archived"
EXPORT_DIR = "./export"

def is_export_empty() -> bool:
    """Возвращает True, если папка /export пустая (нет файлов), иначе False."""
    exports = [f for f in os.listdir(EXPORT_DIR) 
               if os.path.isfile(os.path.join(EXPORT_DIR, f))]
    return len(exports) == 0

def find_import_file() -> str | None:
    """
    Ищем файл вида active_users_YYYYmmDD.csv
    за текущую дату (или можно расширить логику, искать самый свежий).
    """
    today_str = datetime.date.today().strftime("%Y%m%d")
    expected_name = f"active_users_{today_str}.csv"
    full_path = os.path.join(IMPORT_DIR, expected_name)
    if os.path.exists(full_path):
        return expected_name
    return None

def skip_import_file(filename: str):
    """
    Переносит файл из ./import в ./import/skipped
    """
    src = os.path.join(IMPORT_DIR, filename)
    if not os.path.isfile(src):
        logger.warning(f"skip_import_file: Файл {src} не найден.")
        return

    os.makedirs(ARCHIVE_SKIPPED, exist_ok=True)
    dst = os.path.join(ARCHIVE_SKIPPED, filename)
    shutil.move(src, dst)
    logger.info(f"Файл {filename} перемещён в {ARCHIVE_SKIPPED} (SKIPPED).")

def archive_import_file(filename: str, success=True):
    """
    Переносит файл из ./import в ./import/archived
    Если success=False, можем в будущем разделять на 'archived/errors'
    """
    src = os.path.join(IMPORT_DIR, filename)
    if not os.path.isfile(src):
        logger.warning(f"archive_import_file: файл {src} не найден.")
        return

    os.makedirs(ARCHIVE_DONE, exist_ok=True)
    dst = os.path.join(ARCHIVE_DONE, filename)
    shutil.move(src, dst)
    logger.info(f"Файл {filename} перемещён в {ARCHIVE_DONE}.")


def parse_csv_users(filename: str) -> set[int]:
    """
    Читает CSV-файл, автоматически определяя разделитель, и собирает уникальные user_id (int) из колонки 'UserID'.
    Возвращает пустое множество, если файл пуст, не найден, или отсутствует колонка 'UserID'.

    Args:
        filename (str): Имя файла в директории IMPORT_DIR.

    Returns:
        set[int]: Множество user_id из файла.
    """
    filepath = Path(IMPORT_DIR) / filename
    if not filepath.is_file():
        logger.warning(f"parse_csv_users: файл {filepath} не найден.")
        return set()

    user_ids = set()
    try:
        with filepath.open("r", encoding="utf-8") as f:
            # Читаем первые 1024 байта для анализа разделителя
            sample = f.read(1024)
            if not sample:
                logger.warning(f"Файл {filename} пустой.")
                return set()
            f.seek(0)  # Возвращаемся в начало файла

            # Определяем диалект CSV с помощью Sniffer
            dialect = csv.Sniffer().sniff(sample)
            delimiter = dialect.delimiter
            logger.info(f"Определен разделитель: '{delimiter}' для файла {filename}")

            # Читаем файл как словарь с заголовками
            reader = csv.DictReader(f, delimiter=delimiter)
            if 'UserID' not in reader.fieldnames:
                logger.error(f"В файле {filename} отсутствует колонка 'UserID'.")
                return set()

            for row in reader:
                try:
                    uid = int(row['UserID'])
                    user_ids.add(uid)
                except (ValueError, KeyError):
                    logger.warning(f"Некорректная строка: {row}")
    except Exception as e:
        logger.error(f"Ошибка чтения файла {filepath}: {e}")
        return set()

    return user_ids
