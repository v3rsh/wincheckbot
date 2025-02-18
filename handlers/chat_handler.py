# handlers/chat_handler.py

from aiogram import Router
from aiogram.types import ChatMemberUpdated, ChatMemberAdministrator, ChatMemberMember, ChatMemberOwner
from aiogram.enums import ChatMemberStatus
import aiosqlite
from config import logger
from database import DB_PATH

router = Router()

@router.my_chat_member()
async def handle_my_chat_member(update: ChatMemberUpdated):
    """
    Хэндлер вызывается при добавлении/удалении/изменении статуса бота в чате.
    Сохраняем в таблицу Groups только нужные поля.
    """

    chat = update.chat
    new_status = update.new_chat_member.status   # например "administrator"/"member"/"creator"...

    chat_id = chat.id
    chat_title = chat.title or "Без названия"
    chat_type = chat.type  # "group","supergroup","channel"...

    logger.info(f"[my_chat_member] chat_id={chat_id}, status={new_status}, title={chat_title}")

    try:
        # 1) Получаем статус бота в чате
        chat_member = await update.bot.get_chat_member(chat_id, update.bot.id)
        # Может быть ChatMemberAdministrator, ChatMemberMember, ChatMemberOwner, ChatMemberLeft и т.д.

        # 2) Готовим поля для записи
        fields = {
            "Title": chat_title,
            "Type": chat_type,
            "Status": chat_member.status,  # "administrator","creator","member","left","kicked"...
            "can_manage_chat": False,
            "can_restrict_members": False,
            "can_promote_members": False,
            "can_invite_users": False
        }

        # 3) Если бот - админ, копируем нужные поля
        if isinstance(chat_member, ChatMemberAdministrator):
            # Ставим Status="administrator"
            fields["Status"] = "administrator"
            fields["can_manage_chat"] = chat_member.can_manage_chat
            fields["can_restrict_members"] = chat_member.can_restrict_members
            fields["can_promote_members"] = chat_member.can_promote_members
            fields["can_invite_users"] = chat_member.can_invite_users

        elif isinstance(chat_member, ChatMemberOwner):
            # Владелец (creator). В aiogram 3.x ChatMemberOwner не даёт can_..., 
            # но логично, что владелец может всё.
            fields["Status"] = "creator"
            fields["can_manage_chat"] = True
            fields["can_restrict_members"] = True
            fields["can_promote_members"] = True
            fields["can_invite_users"] = True

        elif isinstance(chat_member, ChatMemberMember):
            # Рядовой участник
            fields["Status"] = "member"
            # Остальные поля False

        else:
            # Возможно ChatMemberLeft / ChatMemberBanned
            fields["Status"] = chat_member.status
            # Остальные поля остаются False

        # 4) INSERT или UPDATE в таблицу Groups
        col_names = list(fields.keys())  
        # ["Title","Type","Status","can_manage_chat","can_restrict_members","can_promote_members","can_invite_users"]
        placeholders = ", ".join("?" for _ in col_names)         # "?,?,?,...?"
        update_expr = ", ".join(f"{c}=?" for c in col_names)     # "Title=?,Type=?,Status=?,..."
        values_list = [fields[c] for c in col_names]             # Собираем значения по порядку

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT ChatID FROM Groups WHERE ChatID=?", (chat_id,))
            row = await cursor.fetchone()

            if not row:
                # Вставляем новую запись
                sql_insert = f"""
                    INSERT INTO Groups (ChatID, {",".join(col_names)})
                    VALUES (?, {placeholders})
                """
                await db.execute(sql_insert, [chat_id] + values_list)
                logger.info(f"[my_chat_member] INSERT new chat {chat_id}, status={fields['Status']}")
            else:
                # Обновляем существующую
                sql_update = f"UPDATE Groups SET {update_expr} WHERE ChatID=?"
                await db.execute(sql_update, values_list + [chat_id])
                logger.info(f"[my_chat_member] UPDATE chat {chat_id}, status={fields['Status']}")

            await db.commit()

        logger.info(f"[my_chat_member] Запись в Groups для чата {chat_id} завершена.")

    except Exception as e:
        logger.exception(f"Ошибка при обработке chat_id={chat_id}: {e}")
