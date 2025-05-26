import os
import sys

# Добавляем родительскую директорию в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from dotenv import load_dotenv
    # Загружаем переменные из .env файла, если он существует
    load_dotenv()
except ImportError:
    print("Пакет python-dotenv не установлен. Используются только системные переменные окружения.")

# Список переменных, которые нужны для отправки почты
required_vars = [
    "UNI_EMAIL",
    "UNI_API_KEY"
]

# Проверяем наличие переменных
missing_vars = []
for var in required_vars:
    value = os.getenv(var)
    if not value:
        missing_vars.append(var)
    else:
        # Скрываем значение для безопасности, показываем только первые 2 символа
        masked_value = value[:2] + "*" * (len(value) - 2) if len(value) > 2 else value
        print(f"{var}: {masked_value}")

if missing_vars:
    print(f"\nОТСУТСТВУЮТ переменные окружения: {', '.join(missing_vars)}")
    print("Для работы скрипта отправки почты необходимо задать эти переменные.")
    print("Создайте файл .env в корневой директории проекта со следующим содержимым:")
    for var in missing_vars:
        print(f"{var}=YOUR_{var}_VALUE")
else:
    print("\nВсе необходимые переменные окружения настроены.")
    print("Скрипт test_mail.py должен работать корректно.") 