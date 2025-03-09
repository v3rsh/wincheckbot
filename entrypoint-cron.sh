#!/usr/bin/env bash
set -e

# 1) Если нужно явно считать .env (если ENV_FILE не подхватывается по умолчанию)
# source /app/.env

# 2) Пробросить все переменные окружения в /etc/environment
printenv | sed 's/^\(.*\)$/export \1/g' > /etc/profile.d/envvars.sh
chmod +x /etc/profile.d/envvars.sh

# 3) Запустить cron в форграунде
exec cron -f
