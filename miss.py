# import_missing_users.py

import aiosqlite
import asyncio
import csv

CSV_FILE = "users_export.csv"
PULSE_DB = "data/pulse.db"

async def import_missing_users():
    async with aiosqlite.connect(PULSE_DB) as db:
        # Получаем существующие UserID
        cursor = await db.execute("SELECT UserID FROM Users")
        existing_ids = set(row[0] for row in await cursor.fetchall())

        # Загружаем из CSV
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            new_users = []

            for row in reader:
                try:
                    uid = int(row["UserID"])
                    if uid not in existing_ids:
                        # Добавляем в список для вставки
                        new_users.append((
                            uid,
                            row["Email"],
                            int(row["Approve"]),
                            int(row["WasApproved"]),
                            int(row["InviteCount"]),
                            int(row["Synced"]),
                            int(row["Notified"]) if row["Notified"] != "" else 0,
                            int(row["Banned"]),
                        ))
                except Exception as e:
                    print(f"[!] Ошибка в строке: {row} — {e}")

        if not new_users:
            print("[✓] Новых пользователей не найдено.")
            return

        await db.executemany("""
            INSERT INTO Users (
                UserID, Email, Approve, WasApproved, InviteCount, Synced, Notified, Banned
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, new_users)
        await db.commit()

        print(f"[✓] Добавлено {len(new_users)} новых пользователей в базу {PULSE_DB}")

if __name__ == "__main__":
    asyncio.run(import_missing_users())
