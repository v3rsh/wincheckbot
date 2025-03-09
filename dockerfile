ARG DEBIAN_FRONTEND=noninteractive
FROM python:3.10.16-slim-bullseye

# Устанавливаем необходимые пакеты
RUN apt-get update && apt-get install -y tzdata sqlite3 cron nano --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

ENV TZ=Europe/Moscow

WORKDIR /app

RUN pip install --upgrade pip

# Устанавливаем Python-зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем проект
COPY . /app

# Копируем crontab и регистрируем её в системе
COPY crontab /etc/cron.d/mycron
RUN chmod 0644 /etc/cron.d/mycron && crontab /etc/cron.d/mycron
COPY entrypoint-cron.sh /app/
RUN chmod +x /app/entrypoint-cron.sh

# Управляем запуском через переменную ROLE:
# - ROLE=cron   -> запускаем entrypoint-cron.sh
# - ROLE=simulation -> запускаем simulation.py
# - Иначе         -> запускаем main.py (бот)
CMD ["sh", "-c", "if [ \"$ROLE\" = 'cron' ]; then /app/entrypoint-cron.sh; elif [ \"$ROLE\" = 'simulation' ]; then python3 simulate.py; else python3 main.py; fi"]