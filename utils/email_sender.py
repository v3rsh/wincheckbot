# utils/email_sender.py
import requests
import smtplib
from config import UNI_EMAIL, logger  # Импорт логгера из config.py
from utils.mask import mask_email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formatdate, make_msgid
import socket

async def send_email(to_email, code):
    """
    Отправляет email с кодом через SMTP mail.winline.ru:25 с использованием TLS и добавлением
    заголовков для предотвращения попадания в спам.
    """
    # Проверка входных параметров
    if not to_email or not code:
        logger.error("Не указан email или код для отправки")
        return False
    
    if not UNI_EMAIL:
        logger.error("Не указан UNI_EMAIL в переменных окружения")
        return False
        
    try:
        smtp_server = "mail.winline.ru"
        smtp_port = 25
        sender_name = "HR отдел Winline"
        sender_email = UNI_EMAIL
        subject = "Код подтверждения"
        
        # Создаем multipart/alternative сообщение (HTML + текстовая версия)
        message = MIMEMultipart('alternative')
        
        # Текстовая версия сообщения (без HTML)
        plain_text = f"""
Подтверждение регистрации

Ваш код подтверждения: {code}

Введите его в приложении для завершения регистрации.
        """
        
        # HTML версия сообщения
        html_body = f"""
        <html>
        <body>
            <h1>Подтверждение регистрации</h1>
            <p>Ваш код подтверждения: <strong>{code}</strong></p>
            <p>Введите его в приложении для завершения регистрации.</p>
        </body>
        </html>
        """
        
        # Добавляем обе версии сообщения
        message.attach(MIMEText(plain_text, 'plain', 'utf-8'))
        message.attach(MIMEText(html_body, 'html', 'utf-8'))
        
        # Добавляем стандартные заголовки
        message["Subject"] = Header(subject, "utf-8")
        message["From"] = f"{sender_name} <{sender_email}>"
        message["To"] = to_email
        
        # Добавляем дополнительные заголовки для снижения вероятности попадания в спам
        message["Date"] = formatdate(localtime=True)
        message["Message-ID"] = make_msgid(domain="winline.ru")
        message["X-Priority"] = "3"  # Нормальный приоритет
        
        # Устанавливаем таймаут для DNS-запросов
        socket.setdefaulttimeout(15)
        
        logger.info(f"Попытка подключения к SMTP-серверу {smtp_server}:{smtp_port}")
        
        with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
            # Используем TLS если сервер поддерживает
            server.ehlo()
            try:
                if server.has_extn('STARTTLS'):
                    server.starttls()
                    server.ehlo()
                    logger.info("Установлено TLS-соединение с SMTP-сервером")
            except Exception as e:
                logger.warning(f"Не удалось установить TLS-соединение: {e}. Продолжаем без шифрования.")
            
            # Проверяем аутентификацию (если необходимо)
            try:
                # Попытка отправки без аутентификации
                server.sendmail(sender_email, [to_email], message.as_string())
            except smtplib.SMTPAuthenticationError:
                logger.error("Требуется аутентификация SMTP. Проверьте настройки.")
                return False
            except smtplib.SMTPSenderRefused:
                logger.error("Сервер отклонил отправителя. Проверьте адрес отправителя.")
                return False
            except smtplib.SMTPRecipientsRefused:
                logger.error(f"Сервер отклонил получателя {mask_email(to_email)}.")
                return False
            except smtplib.SMTPDataError as e:
                logger.error(f"Ошибка SMTP при отправке данных: {e}")
                return False
            except smtplib.SMTPServerDisconnected:
                logger.error("Соединение с SMTP-сервером было неожиданно закрыто.")
                return False
            
        logger.info(f"Письмо успешно отправлено через SMTP на {mask_email(to_email)}.")
        return True
    
    except socket.gaierror as e:
        logger.error(f"Ошибка DNS при подключении к SMTP-серверу: {e}")
        return False
    except socket.timeout:
        logger.error("Превышено время ожидания при подключении к SMTP-серверу")
        return False
    except ConnectionRefusedError:
        logger.error(f"Соединение с SMTP-сервером {smtp_server}:{smtp_port} отклонено")
        return False
    except Exception as e:
        logger.error(f"Ошибка при отправке письма через SMTP на {mask_email(to_email)}: {e}")
        return False
