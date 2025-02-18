# utils/crypto.py

import os
import binascii
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from config import logger, ENCRYPTION_KEY 

# Превращаем hex-строку в байты
try:
    KEY_BYTES = binascii.unhexlify(ENCRYPTION_KEY)
    # Проверим длину: AES может быть 16, 24, 32 байта
    if len(KEY_BYTES) not in (16, 24, 32):
        raise ValueError("Длина ключа должна быть 16/24/32 байта (AES-128/192/256).")
except binascii.Error as e:
    raise ValueError("Неверный формат ENCRYPTION_KEY (не hex)") from e

def encrypt_email(plain_email: str) -> str:
    """
    Шифрует email с помощью AES (CBC).
    Возвращает hex-строку: IV + зашифрованные данные.
    """
    if not plain_email:
        return ""  # или None

    # Генерируем случайный IV (16 байт)
    from os import urandom
    iv = urandom(16)

    cipher = AES.new(KEY_BYTES, AES.MODE_CBC, iv)
    # Паддим исходную строку до размера блока
    ciphertext = cipher.encrypt(pad(plain_email.encode('utf-8'), AES.block_size))

    # Склеиваем iv + ciphertext и кодируем в hex
    full_data = iv + ciphertext
    return binascii.hexlify(full_data).decode('utf-8')

def decrypt_email(enc_hex: str) -> str:
    """
    Расшифровывает email из hex-строки.
    Возвращает исходную строку (plain_email).
    Если enc_hex пуст, возвращаем "".
    """
    if not enc_hex:
        return ""
    full_data = binascii.unhexlify(enc_hex)
    iv = full_data[:16]
    ciphertext = full_data[16:]

    cipher = AES.new(KEY_BYTES, AES.MODE_CBC, iv)
    plain = unpad(cipher.decrypt(ciphertext), AES.block_size)
    return plain.decode('utf-8')
