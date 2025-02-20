# config.py

import os
import logging
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

LOG_DIR = "./logs"  # Путь к директории логов
LOG_FILENAME = os.path.join(LOG_DIR, "bot.log")

os.makedirs(LOG_DIR, exist_ok=True)
# Настройка логирования
logger = logging.getLogger()
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

# Обработчик для файла с ротацией
from logging.handlers import RotatingFileHandler

file_handler = RotatingFileHandler(
    LOG_FILENAME, maxBytes=5*1024*1024, backupCount=5  # 5 МБ и 5 резервных файлов
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Обработчик для консоли
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


API_TOKEN = os.getenv("TELEGRAM_API_TOKEN")
COMPANY_CHANNEL_ID = int(os.getenv("COMPANY_CHANNEL_ID"))
WORK_MAIL = os.getenv("WORK_MAIL")
UNI_API_KEY = os.getenv("UNI_API_KEY")
UNI_EMAIL = os.getenv("UNI_EMAIL")
EXCLUDED_EMAILS = os.getenv("EXCLUDED_EMAILS", "").split(",")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
DB_PATH = os.getenv("DB_PATH")
MAINTENANCE_MODE=os.getenv("MAINTENANCE_MODE")

# Проверка наличия обязательных переменных
required_env_vars = ["API_TOKEN", "WORK_MAIL", "UNI_API_KEY", "UNI_EMAIL", "COMPANY_CHANNEL_ID", "ENCRYPTION_KEY", "DB_PATH", "MAINTENANCE_MODE"]
missing_vars = [var for var in required_env_vars if not globals().get(var)]

if missing_vars:
    logger.critical(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
    raise EnvironmentError("Не все переменные окружения заданы.")
