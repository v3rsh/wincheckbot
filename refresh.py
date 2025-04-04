import redis

def reset_fsm_state(user_id: int, chat_id: int = None, redis_url: str = "redis://localhost:6379/0"):
    # Подключаемся к Redis
    r = redis.Redis.from_url(redis_url)

    # Если chat_id не указан, предполагаем, что chat_id = user_id (личный чат)
    chat_id = chat_id or user_id

    # Шаблон ключа для поиска (например: "fsm:{user_id}:{chat_id}:*")
    key_pattern = f"fsm:{user_id}:{chat_id}:*"

    # Ищем и удаляем все ключи, связанные с состоянием пользователя
    for key in r.scan_iter(match=key_pattern):
        r.delete(key)
        print(f"Удален ключ: {key.decode()}")

if __name__ == "__main__":
    try:
        # Запрашиваем user_id у пользователя
        user_id = input("Введите user_id пользователя: ")
        # Проверяем, что введено число
        user_id = int(user_id)
        
        # Вызываем функцию с введенным user_id
        reset_fsm_state(
            user_id=user_id,
            redis_url="redis://redis:6379/5"  # URL для подключения к Redis в Docker
        )
        print(f"Состояние FSM для пользователя {user_id} успешно сброшено")
    except ValueError:
        print("Ошибка: Введите корректный числовой user_id")
    except Exception as e:
        print(f"Произошла ошибка: {e}")