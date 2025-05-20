import sys
import asyncio
from utils.email_sender import send_test

def main():
    email = input("Введите email для отправки тестового письма: ").strip()
    code = "111111"
    print(f"Пробуем отправить письмо на {email}...")
    result = send_test(email, code)
    if result:
        print(f"Письмо успешно отправлено на {email}")
    else:
        print(f"Ошибка при отправке письма на {email}")

if __name__ == "__main__":
    main() 