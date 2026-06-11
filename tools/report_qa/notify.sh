#!/bin/bash
# Telegram-уведомление от QA-агента «Кусь». Usage: ./notify.sh "сообщение"
# HTML: <b>bold</b>, <code>code</code>. Токен из .env (BOT_TOKEN), чат — ADMIN.
# Образец: /opt/avito-agents/notify.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BOT_TOKEN="$(grep -E '^BOT_TOKEN=' "$ROOT/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'"' ')"
CHAT_ID="${ADMIN_TELEGRAM_ID:-856877325}"
MSG="${1:-}"
[ -z "$MSG" ] && { echo "Usage: $0 \"message\""; exit 1; }
[ -z "$BOT_TOKEN" ] && { echo "нет BOT_TOKEN в $ROOT/.env"; exit 1; }
curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/sendMessage" \
  -d chat_id="$CHAT_ID" -d parse_mode="HTML" --data-urlencode text="$MSG" >/dev/null
