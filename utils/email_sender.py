# utils/email_sender.py
import requests
import smtplib
from config import UNI_API_KEY, UNI_EMAIL, logger  # Импорт логгера из config.py
from utils.mask import mask_email
from email.mime.text import MIMEText
from email.header import Header

async def send_email(to_email, code):
    try:
        url = "https://api.unisender.com/ru/api/sendEmail"
        email_body = f"""
        <html>
        <body>
            <h1>Подтверждение регистрации</h1>
            <p>Ваш код подтверждения: <strong>{code}</strong></p>
            <p>Введите его в приложении для завершения регистрации.</p>
        </body>
        </html>
        """
        payload = {
            "api_key": UNI_API_KEY,
            "sender_name": "HR отдел Winline",
            "sender_email": UNI_EMAIL,
            "subject": "Код подтверждения",
            "body": email_body,
            "list_id": "8",
            "email": to_email
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }

        response = requests.post(url, data=payload, headers=headers)
        response.raise_for_status()
        response_data = response.json()

        logger.info(f"UniSender raw response: {response_data}")

        if response.status_code == 200 and "result" in response_data:
            result_value = response_data["result"]
            
            # 1) Если result - это массив (список)
            if isinstance(result_value, list):
                if not result_value:
                    logger.error(f"Неверный формат result: пустой список")
                    return False
                
                first_item = result_value[0]
                errors = first_item.get("errors")
                if errors:
                    logger.error(f"UniSender вернул ошибку при отправке письма {mask_email(to_email)}: {errors}")
                    return False
                
                logger.info(f"Письмо успешно отправлено на {mask_email(to_email)}. (list format)")
                return True

            # 2) Если result - это словарь (dict)
            elif isinstance(result_value, dict):
                # Примерно так:
                # {"result": {"email_id": "35269310002"}}
                # Проверим, нет ли всё-таки поля "errors"
                if "errors" in result_value:
                    errors = result_value["errors"]
                    logger.error(f"UniSender вернул ошибку при отправке письма {mask_email(to_email)}: {errors}")
                    return False

                # Иначе считаем, что письмо отправлено успешно
                logger.info(f"Письмо успешно отправлено на {mask_email(to_email)}. (dict format: {result_value})")
                return True

            else:
                # Ни список, ни словарь — неожиданный формат
                logger.error(f"Неподдерживаемый формат result: {type(result_value)} => {result_value}")
                return False

        else:
            logger.error(f"Ошибка при отправке письма (код {response.status_code}): {response_data}")
            return False

    except requests.exceptions.RequestException as e:
        logger.exception(f"Сетевая ошибка при отправке письма на {mask_email(to_email)}: {e}")
        return False

def send_test(to_email, code):
    """
    Отправляет email с кодом через SMTP mail.winline.ru:25 (без SSL).
    """
    try:
        smtp_server = "mail.winline.ru"
        smtp_port = 25
        sender_name = "HR отдел Winline"
        sender_email = UNI_EMAIL
        subject = "Код подтверждения"
        email_body = f"""
        <html>
        <body>
            <h1>Подтверждение регистрации</h1>
            <p>Ваш код подтверждения: <strong>{code}</strong></p>
            <p>Введите его в приложении для завершения регистрации.</p>
        </body>
        </html>
        """
        msg = MIMEText(email_body, "html", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = f"{sender_name} <{sender_email}>"
        msg["To"] = to_email

        with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
            server.sendmail(sender_email, [to_email], msg.as_string())
        logger.info(f"Письмо успешно отправлено через SMTP на {mask_email(to_email)}.")
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке письма через SMTP на {mask_email(to_email)}: {e}")
        return False
