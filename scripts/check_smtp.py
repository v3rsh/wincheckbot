import smtplib
import sys
import os

# Добавляем родительскую директорию в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from config import logger
except ImportError:
    import logging
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

def check_smtp_server(server="mail.winline.ru", port=25):
    """Проверяет доступность SMTP-сервера и поддержку TLS"""
    print(f"Проверка SMTP сервера {server}:{port}...")
    
    try:
        # Устанавливаем соединение с SMTP-сервером
        print("Подключение к серверу...")
        smtp = smtplib.SMTP(server, port, timeout=10)
        print("Соединение установлено.")
        
        # Получаем приветствие
        print("Приветствие сервера:", smtp.ehlo_resp.decode() if hasattr(smtp, 'ehlo_resp') else "Нет данных")
        
        # Проверяем поддерживаемые расширения
        print("\nПоддерживаемые расширения:")
        for ext in smtp.esmtp_features:
            print(f"- {ext.decode()}")
        
        # Проверяем поддержку STARTTLS
        has_tls = smtp.has_extn('STARTTLS')
        print(f"\nПоддержка STARTTLS: {'ДА' if has_tls else 'НЕТ'}")
        
        if has_tls:
            try:
                print("Попытка установить TLS соединение...")
                smtp.starttls()
                print("TLS соединение успешно установлено!")
                
                # После TLS соединения выполняем новый EHLO
                smtp.ehlo()
                print("Новые поддерживаемые расширения после TLS:")
                for ext in smtp.esmtp_features:
                    print(f"- {ext.decode()}")
            except Exception as e:
                print(f"Ошибка при установке TLS соединения: {e}")
        
        # Закрываем соединение
        print("\nЗакрытие соединения...")
        smtp.quit()
        print("Соединение закрыто.")
        
    except Exception as e:
        print(f"Ошибка при проверке SMTP-сервера: {e}")

if __name__ == "__main__":
    server = "mail.winline.ru"
    port = 25
    
    # Проверяем, есть ли аргументы командной строки
    if len(sys.argv) > 1:
        server = sys.argv[1]
    if len(sys.argv) > 2:
        port = int(sys.argv[2])
    
    check_smtp_server(server, port) 