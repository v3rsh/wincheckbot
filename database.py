# database.py
import aiosqlite
from config import logger
from utils.crypto import encrypt_email, decrypt_email
import os
from config import DB_PATH

async def initialize_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Создание таблицы Users (если её ещё нет)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS Users (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                UserID INTEGER UNIQUE,
                Email TEXT,
                Approve BOOLEAN DEFAULT FALSE,
                WasApproved BOOLEAN DEFAULT FALSE,
                InviteCount INTEGER DEFAULT 0,
                Synced BOOLEAN DEFAULT FALSE
            )
        ''')
        # Создание таблицы Groups (если её ещё нет)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS Groups (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                ChatID INTEGER UNIQUE,
                Rights BOOLEAN DEFAULT FALSE
            )
        ''')
        await db.commit()
    logger.info("База данных инициализирована.")

async def set_user_email(user_id: int, plain_email: str):
    """
    Шифрует plain_email и записывает в поле Email для данного user_id.
    """
    enc_email = encrypt_email(plain_email)  # зашифровываем
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE Users SET Approve = TRUE, WasApproved = TRUE, Banned = FALSE, Email=? WHERE UserID=?",
            (enc_email, user_id)
        )
        await db.commit()
    logger.info(f"set_user_email: user_id={user_id}, email=ЗАШИФРОВАНО")


async def get_user_email(user_id: int) -> str:
    """
    Читает поле Email (в зашифрованном виде) и расшифровывает.
    Возвращает plain_email (или пустую строку).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT Email FROM Users WHERE UserID=?", (user_id,))
        row = await cursor.fetchone()
        if row and row[0]:
            dec_email = decrypt_email(row[0])
            return dec_email
        return ""