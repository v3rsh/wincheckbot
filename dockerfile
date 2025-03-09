# dockerfile
ARG DEBIAN_FRONTEND=noninteractive
FROM python:3.10.16-slim-bullseye

# Устанавливаем часовой пояс
RUN apt-get update && apt-get install -y tzdata
ENV TZ=Europe/Moscow

# Не даём apt-у запускать демоны через policy-rc.d
RUN echo 'exit 101' > /usr/sbin/policy-rc.d && chmod +x /usr/sbin/policy-rc.d

# Устанавливаем необходимые пакеты, включая cron
RUN apt-get update && apt-get install -y \
    tzdata sqlite3 cron nano \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Ставим Python-зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем проект
COPY . /app
COPY .env /app/.env
# Делаем скрипт исполняемым
RUN chmod +x /app/entrypoint-cron.sh

# Копируем crontab и регистрируем её в системе
COPY crontab /etc/cron.d/mycron
RUN chmod 0644 /etc/cron.d/mycron && crontab /etc/cron.d/mycron

# По умолчанию будем запускать бота
# (если хотим, можем убрать CMD вообще, но оставим для удобства
#  одиночного запуска образа без docker-compose)
CMD ["python3", "main.py"]
