# mask.py 

def mask_email(email: str) -> str:
    """
    Маскирует email, оставляя первые 2 символа локальной части
    и расширение (после последней точки в домене).
    Пример: "username@domain.com" -> "us**@**.com"
    """
    if '@' not in email:
        # На всякий случай, если email некорректный
        return email  # или вернуть "??"

    local, domain = email.split('@', 1)
    local_part = local[:2]  # первые два символа

    # Находим расширение после последней точки
    dot_pos = domain.rfind('.')
    if dot_pos == -1:
        # Если в домене нет точки, просто убираем всё, кроме local_part
        return f"{local_part}**@**"

    extension = domain[dot_pos + 1:]
    # Формируем маску
    return f"{local_part}**@**.{extension}"
