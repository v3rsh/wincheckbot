FROM python:3.10.16-slim-bullseye
RUN apt-get update && apt-get install -y tzdata
ENV TZ=Europe/Moscow
RUN apt-get update && apt-get install -y sqlite3
RUN apt-get update && apt-get install -y cron
RUN apt-get update && apt-get install -y nano && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
COPY crontab /etc/cron.d/mycron
RUN chmod 0644 /etc/cron.d/mycron && crontab /etc/cron.d/mycron
CMD ["python3", "main.py"]