# entrypoint-cron.sh
#!/bin/bash
# Записываем всё текущее окружение в /etc/environment (кроме no_proxy)
printenv | grep -v "no_proxy" > /etc/environment

# Затем запускаем cron в форграунде
cron -f
