#!/bin/bash
# Telegram-уведомление QA-агента «Кусь». Usage: ./notify.sh "сообщение" (HTML).
# ЗАПУСКАТЬ НА AMS: сервер 5.42 (РФ) не достаёт api.telegram.org. Токен kus-бота
# тянем с 5.42 по ssh, curl делаем локально на AMS. Чат — ADMIN (Анастасия).
set -uo pipefail
MSG="${1:-}"
[ -z "$MSG" ] && { echo "Usage: $0 \"message\""; exit 1; }
SRV="ssh -o StrictHostKeyChecking=no root@5.42.101.215"
TOKEN="$($SRV 'grep -E "^BOT_TOKEN=" /opt/kus/.env | head -1 | cut -d= -f2-' | tr -d ' "'"'"'\r')"
CHAT_ID="${ADMIN_TELEGRAM_ID:-856877325}"
[ -z "$TOKEN" ] && { echo "не получил BOT_TOKEN с 5.42"; exit 1; }
curl -s -m 20 -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
  -d chat_id="$CHAT_ID" -d parse_mode="HTML" --data-urlencode text="$MSG" >/dev/null \
  && echo "отправлено" || { echo "ошибка отправки (telegram недоступен?)"; exit 1; }
