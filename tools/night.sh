#!/usr/bin/env bash
# Ночной ОРКЕСТРАТОР дайджеста (запускается НА АМСТЕРДАМЕ, без AI-токенов).
# Гоняет детерминированные проверки НА 5.42 по ssh (там живут код+venv), а
# Telegram-дайджест шлёт С АМСТЕРДАМА — у 5.42 заблокирован egress на
# api.telegram.org (проверено: -4 timeout, -6 no route; monitor.sh давно молча
# не доходил). Так разнесены роли: тяжёлое — на сервере, доставка — где есть сеть.
#
#   bash tools/night.sh
#
# Тишина утром = джоб не отработал (watchdog: «нет письма — смотри сервер»).
set -u
REMOTE="${KUS_REMOTE:-root@5.42.101.215}"
REPO="${KUS_REMOTE_REPO:-/opt/kus}"
SSH="ssh -o BatchMode=yes -o ConnectTimeout=15"

# 1. Проверки на 5.42: дайджест → stdout, общий код → exit
digest="$($SSH "$REMOTE" "cd $REPO && FUZZ_N=${FUZZ_N:-500} bash tools/nightly.sh 2>/dev/null")"
rc=$?
if [ -z "$digest" ]; then
  digest="🌙 Кусь ночной контроль — НЕТ ОТВЕТА от 5.42 (ssh упал или джоб умер). Проверьте сервер."
  rc=1
fi

# 2. Токены из .env на 5.42 (Амстердам их не хранит)
creds="$($SSH "$REMOTE" "grep -E '^(BOT_TOKEN|ADMIN_TELEGRAM_ID)=' $REPO/.env" 2>/dev/null)"
TG_TOKEN="$(printf '%s\n' "$creds" | sed -n 's/^BOT_TOKEN=//p' | tr -d '\r')"
TG_CHAT="$(printf '%s\n' "$creds" | sed -n 's/^ADMIN_TELEGRAM_ID=//p' | tr -d '\r')"

# 3. Отправка С АМСТЕРДАМА (здесь Telegram доступен)
if [ -n "$TG_TOKEN" ] && [ -n "$TG_CHAT" ]; then
  curl -s --max-time 25 "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TG_CHAT}" --data-urlencode "text=${digest}" >/dev/null \
    && echo "[night] дайджест отправлен в Telegram" \
    || echo "[night] отправка в Telegram не удалась"
else
  echo "[night] токены не получены — дайджест в лог:"; printf '%s\n' "$digest"
fi
exit $rc
