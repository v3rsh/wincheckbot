# database.py
import aiosqlite
from config import logger
from utils.mask import mask_email
import os
from config import DB_PATH

async def initialize_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Создание таблицы Users (если её ещё нет)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS Users (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                UserID INTEGER UNIQUE,
                Username TEXT,
                FirstName TEXT,
                LastName TEXT,
                Email TEXT,
                Approve BOOLEAN DEFAULT FALSE,
                WasApproved BOOLEAN DEFAULT FALSE,
                InviteCount INTEGER DEFAULT 0,
                Synced BOOLEAN DEFAULT FALSE,
                Notified BOOLEAN,
                Banned BOOLEAN DEFAULT FALSE
            )
        ''')
        # Создание таблицы Groups (если её ещё нет)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS Groups (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                ChatID INTEGER UNIQUE,
                Title TEXT,
                Type TEXT,
                Status TEXT,
                can_manage_chat BOOLEAN,  
                can_restrict_members BOOLEAN,  
                can_promote_members BOOLEAN,  
                can_invite_users BOOLEAN,
                New BOOLEAN DEFAULT TRUE
            )
        ''')
        # Создание таблицы Groups (если её ещё нет)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS SyncHistory (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                SyncType TEXT,  -- 'export' / 'import'
                FileName TEXT,
                RecordCount INTEGER,
                SyncDate DATETIME,
                Comment TEXT
            )
        ''')    

        await db.commit()
    logger.info("База данных инициализирована.")

async def set_user_email(user_id: int, plain_email: str):
    """
    Записывает plain_email в поле Email для данного user_id.
    """
    final_email = plain_email.strip().lower()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE Users SET Approve = TRUE, WasApproved = TRUE, Email=? WHERE UserID=?",
            (final_email, user_id)
        )
        await db.commit()
    logger.info(f"set_user_email: user_id={user_id}, email={final_email}")


async def get_user_email(user_id: int) -> str:
    """
    Читает поле Email и возвращает его значение.
    Возвращает email (или пустую строку).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT Email FROM Users WHERE UserID=?", (user_id,))
        row = await cursor.fetchone()
        if row and row[0]:
            return row[0]
        return ""

async def get_emails_by_user_ids(user_ids: list[int]) -> dict[int, str]:
    """
    Возвращает словарь {user_id: email} для списка user_ids одним SQL-запросом.
    """
    if not user_ids:
        return {}
    placeholders = ",".join(["?"] * len(user_ids))
    query = f"SELECT UserID, Email FROM Users WHERE UserID IN ({placeholders})"
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(query, tuple(user_ids))
        rows = await cursor.fetchall()
    return {user_id: email for user_id, email in rows}

async def get_group_titles_by_chat_ids(chat_ids: list[int]) -> dict[int, str]:
    """
    Возвращает словарь {chat_id: title} для списка chat_ids одним SQL-запросом.
    """
    if not chat_ids:
        return {}
    placeholders = ",".join(["?"] * len(chat_ids))
    query = f"SELECT ChatID, Title FROM Groups WHERE ChatID IN ({placeholders})"
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(query, tuple(chat_ids))
        rows = await cursor.fetchall()
    return {chat_id: title or f"Group_{chat_id}" for chat_id, title in rows}