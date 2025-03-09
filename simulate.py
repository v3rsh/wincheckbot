#!/usr/bin/env python3
import os
import aiosqlite
import asyncio
import random
import datetime
import csv
from pathlib import Path
import time

# Путь к базе данных бота (совпадает с DB_PATH в основном проекте)
DB_PATH = "./data/pulse.db"

# Папки export/import из проекта
EXPORT_DIR = "./export"
IMPORT_DIR = "./import"

# -------------------------
#   Создадим таблицу Company
# -------------------------
async def ensure_company_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS Company (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                TelegramID INTEGER,
                Email TEXT
            )
        """)
        await db.commit()

# -------------------------
#   Каждую минуту добавляем фейкового пользователя
# -------------------------
async def add_fake_user():
    """Раз в минуту добавляет фейкового пользователя в таблицу Users проекта."""
    user_id = random.randint(1000000, 9999999)
    email = f"test_{user_id}@winline.ru"

    # 80% сразу прошли "верификацию"
    approve = random.random() < 0.8
    was_approved = approve

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO Users (UserID, Email, Approve, WasApproved, Synced, Notified, Banned)
            VALUES (?, ?, ?, ?, 0, 0, 0)
        """, (user_id, email, approve, was_approved))
        await db.commit()

    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] "
          f"Added fake user_id={user_id}, approve={approve}")

# -------------------------
#   Эмулируем "действия компании" раз в 8 минут
# -------------------------
async def simulate_company_actions():
    """
    - Забираем все export_*.csv из ./export,
    - Заполняем таблицу Company,
    - Пытаемся уволить (удалить) некую часть сотрудников,
      но если она > 30%, то НЕ удаляем,
      а лишь «на экспорт» выдаём (total - n) случайных сотрудников.
    - Генерируем ./import/active_users_YYYYmmDD.csv
    """
    exports = sorted(Path(EXPORT_DIR).glob("export_*.csv"))
    if not exports:
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] No export files found.")
        return

    # Обновляем таблицу Company из всех файлов export
    async with aiosqlite.connect(DB_PATH) as db:
        await ensure_company_table()

        for file in exports:
            with file.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=";")
                # Ожидаем поля: UserID, Email
                for row in reader:
                    uid = int(row["UserID"])
                    email = row["Email"]
                    # Сначала удаляем, если уже есть такой ID (чтобы обновить)
                    await db.execute("DELETE FROM Company WHERE TelegramID=?", (uid,))
                    await db.execute("""
                        INSERT INTO Company (TelegramID, Email) VALUES (?, ?)
                    """, (uid, email))
            # При желании можно переименовать/переместить обработанный файл
            # file.rename(file.with_suffix(".done"))
            print(f"[simulate_company_actions] Processed export file: {file.name}")

        await db.commit()

    # Теперь берём всех сотрудников из Company => увольняем некоторую часть
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT ID, TelegramID, Email FROM Company")
        all_emps = await cursor.fetchall()

        total_count = len(all_emps)
        if total_count == 0:
            print("Company table is empty, nothing to do.")
            return

        # выберем n = random.randint(0, total_count)
        n = random.randint(0, total_count)
        percent = n / total_count

        print(f"[simulate_company_actions] Attempting to fire {n} out of {total_count}"
              f" ({percent*100:.1f}%)")

        if percent <= 0.3:
            # <= 30%, значит реально удаляем
            to_fire = random.sample(all_emps, n)
            fired_ids = [x[0] for x in to_fire]
            for fid in fired_ids:
                await db.execute("DELETE FROM Company WHERE ID=?", (fid,))
            await db.commit()
            print(f"Fired {n} employees from Company (<=30% scenario).")

            # Оставшиеся = все в таблице Company
            cursor = await db.execute("SELECT TelegramID FROM Company")
            rows = await cursor.fetchall()
            active_uids = [r[0] for r in rows]

        else:
            # > 30%, трактуем как ошибку, НЕ удаляем.
            # Но в итоговый файл пойдёт только (total_count - n) случайных
            # (т. е. будто "HR решил выдать укороченный список")
            keep_count = total_count - n
            keep_count = max(keep_count, 0)  # на случай если n=total_count
            remain = random.sample(all_emps, keep_count)
            active_uids = [x[1] for x in remain]  # [TelegramID]

            print(f"[simulate_company_actions] Firing attempt >30%. "
                  f"No changes in DB. We only export {keep_count} random employees.")
            # DB не трогаем

    # Сохраняем active_users_YYYYmmDD.csv
    today = datetime.date.today().strftime("%Y%m%d")
    filename = f"active_users_{today}.csv"
    out_path = Path(IMPORT_DIR) / filename

    # Пишем в CSV
    out_path.parent.mkdir(exist_ok=True, parents=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        for uid in active_uids:
            writer.writerow([uid])

    print(f"[simulate_company_actions] Wrote {len(active_uids)} records to {out_path}")

# -------------------------
#   Основной цикл
# -------------------------
async def main_loop():
    await ensure_company_table()

    minute_counter = 0
    while True:
        # Каждую минуту добавляем одного пользователя
        await add_fake_user()

        # Каждые 8 минут — симуляция «действий компании»
        if minute_counter % 8 == 0:
            await simulate_company_actions()

        minute_counter += 1
        await asyncio.sleep(60)

def main():
    print("[simulation] Start simulation script.")
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("Stopped by user Ctrl+C")

if __name__ == "__main__":
    main()
