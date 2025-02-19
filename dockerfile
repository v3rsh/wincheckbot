FROM python:3.10.16-slim-bullseye
RUN apt-get update && apt-get install -y sqlite3
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app
CMD ["python3", "main.py"]