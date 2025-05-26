import sys
import os
import asyncio

# Добавляем родительскую директорию в sys.path, чтобы модуль utils был доступен
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.email_sender import send_test
from utils.mask import mask_email

try:
    from config import logger
except ImportError:
    # Если не можем импортировать logger из config, создаем простой logger
    import logging
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

def main():
    email = input("Введите email для отправки тестового письма: ").strip()
    code = "111111"
    print(f"Пробуем отправить письмо на {email}...")
    result = send_test(email, code)
    if result:
        print(f"Письмо успешно отправлено на {email}")
        logger.info(f"Письмо успешно отправлено на {mask_email(email)}")
    else:
        print(f"Ошибка при отправке письма на {email}")
        logger.error(f"Ошибка при отправке письма на {mask_email(email)}")

if __name__ == "__main__":
    main() 