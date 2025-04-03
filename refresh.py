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
    # Пример использования
    reset_fsm_state(
        user_id=123123131,  # Замените на нужный user_id
        redis_url="redis://your-redis-host:6379/0"  # Укажите ваш Redis URL
    )