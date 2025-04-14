import redis

def reset_fsm_state(user_id: int, chat_id: int = None, redis_url: str = "redis://localhost:6379/0"):
    # Подключаемся к Redis
    r = redis.Redis.from_url(redis_url)

    # Если chat_id не указан, предполагаем, что chat_id = user_id (личный чат)
    chat_id = chat_id or user_id

    # Шаблон ключа для поиска (например: "pulse_fsm:*:user_id:chat_id:*")
    key_pattern = f"pulse_fsm:*:{user_id}:{chat_id}:*"

    # Ищем и удаляем все ключи, связанные с состоянием пользователя
    deleted = False
    for key in r.scan_iter(match=key_pattern):
        r.delete(key)
        print(f"Удален ключ: {key.decode()}")
        deleted = True
    
    if not deleted:
        print(f"Не найдено ключей по шаблону: {key_pattern}")
        # Попробуем более широкий поиск
        alt_pattern = f"*:{user_id}:*"
        print(f"Пробуем поиск по альтернативному шаблону: {alt_pattern}")
        for key in r.scan_iter(match=alt_pattern):
            print(f"Найден ключ: {key.decode()}")
            if input(f"Удалить ключ {key.decode()}? (y/n): ").lower() == 'y':
                r.delete(key)
                print(f"Ключ удален.")
                deleted = True

    return deleted

def show_fsm_keys(user_id: int, chat_id: int = None, redis_url: str = "redis://localhost:6379/0"):
    """Показывает все ключи FSM для пользователя"""
    r = redis.Redis.from_url(redis_url)
    chat_id = chat_id or user_id
    
    # Пробуем разные шаблоны поиска
    patterns = [
        f"pulse_fsm:*:{user_id}:{chat_id}:*",
        f"pulse_fsm:*:{user_id}:*",
        f"*:{user_id}:{chat_id}:*"
    ]
    
    found = False
    for pattern in patterns:
        print(f"\nПоиск ключей по шаблону: {pattern}")
        for key in r.scan_iter(match=pattern):
            found = True
            try:
                value = r.get(key)
                print(f"Ключ: {key.decode()}")
                if value:
                    print(f"Значение: {value.decode()}")
                else:
                    print("Значение: None")
                print("-" * 50)
            except Exception as e:
                print(f"Ошибка при чтении ключа {key}: {e}")
    
    if not found:
        print(f"Ключи для пользователя {user_id} не найдены.")
    
    return found

if __name__ == "__main__":
    try:
        redis_url = "redis://redis:6379/5"  # URL для подключения к Redis в Docker
        
        # Запрашиваем user_id у пользователя
        user_id = input("Введите user_id пользователя: ")
        # Проверяем, что введено число
        user_id = int(user_id)
        
        # Меню выбора действия
        print("\nВыберите действие:")
        print("1. Показать ключи FSM")
        print("2. Сбросить состояние FSM")
        print("3. Показать и сбросить")
        
        choice = input("\nВаш выбор (1-3): ")
        
        if choice == "1" or choice == "3":
            found = show_fsm_keys(user_id, redis_url=redis_url)
            if not found and choice == "1":
                print("Ключи не найдены. Возможно пользователь не имеет активного состояния.")
        
        if choice == "2" or choice == "3":
            deleted = reset_fsm_state(user_id, redis_url=redis_url)
            if deleted:
                print(f"Состояние FSM для пользователя {user_id} успешно сброшено")
            else:
                print(f"Не найдено состояний для сброса у пользователя {user_id}")
        
    except ValueError:
        print("Ошибка: Введите корректный числовой user_id")
    except Exception as e:
        print(f"Произошла ошибка: {e}")