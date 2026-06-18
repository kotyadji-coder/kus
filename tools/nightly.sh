#!/usr/bin/env bash
# Ночной самоконтроль на 5.42: ворота + фаззинг + дайджест в Telegram админу.
# Запуск из cron/systemd-timer. Токены не тратятся (всё детерминированно, без AI).
#
#   bash tools/nightly.sh
#
# Шлёт ОДНО сообщение-сводку. Если сообщение не пришло утром — job не отработал
# (это и есть алерт: «тишина = смотри сервер», как watchdog).
set -u
cd "$(dirname "$0")/.." || exit 2
PY=./venv/bin/python
[ -x "$PY" ] || PY=python3

# .env → BOT_TOKEN, ADMIN_TELEGRAM_ID (или ADMIN_ID)
set -a; [ -f .env ] && . ./.env; set +a
TG_TOKEN="${BOT_TOKEN:-}"
TG_CHAT="${ADMIN_TELEGRAM_ID:-${ADMIN_ID:-}}"

FUZZ_N="${FUZZ_N:-500}"
ts="$(date '+%Y-%m-%d %H:%M')"

canary_out="$($PY tools/canary.py 2>&1)";        canary_rc=$?
snap_out="$($PY tools/snapshot.py 2>&1)";         snap_rc=$?
gate_out="$($PY tools/gate_reconcile.py 2>&1)";   gate_rc=$?
fuzz_out="$($PY tools/fuzz.py "$FUZZ_N" "$(date +%j)" 2>&1)"; fuzz_rc=$?
fuzz_head="$(echo "$fuzz_out" | head -1 | sed 's/^Фаззинг: //')"

emoji() { [ "$1" -eq 0 ] && echo "✅" || echo "🔴"; }
overall=$(( canary_rc | snap_rc | gate_rc | fuzz_rc ))
title=$([ $overall -eq 0 ] && echo "🌙 Кусь ночной контроль — всё чисто" || echo "🌙 Кусь ночной контроль — ЕСТЬ ПРОБЛЕМЫ")

msg="$title
$ts

$(emoji $canary_rc) Канарейка (детектор живой)
$(emoji $snap_rc) Снапшот (дизайн не уехал)
$(emoji $gate_rc) Согласование эталонов
$(emoji $fuzz_rc) Фаззинг: $fuzz_head"

# При провале — прикладываем первые строки деталей (что именно сломалось).
if [ $overall -ne 0 ]; then
  details="$(printf '%s\n%s\n%s\n%s' "$canary_out" "$snap_out" "$gate_out" "$fuzz_out" \
            | grep -E '✗|repro|→|:' | head -25)"
  msg="$msg

— детали —
$details"
fi

# Дайджест — в stdout (его забирает оркестратор на Амстердаме и шлёт в Telegram,
# т.к. у 5.42 заблокирован egress на api.telegram.org). Попытку прямой отправки
# оставляем для случая запуска на хосте С доступом — статус идёт в stderr, чтобы
# не засорять «чистый» дайджест в stdout.
printf '%s\n' "$msg"
if [ -n "$TG_TOKEN" ] && [ -n "$TG_CHAT" ]; then
  if curl -s --max-time 20 "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
       --data-urlencode "chat_id=${TG_CHAT}" --data-urlencode "text=${msg}" >/dev/null 2>&1; then
    echo "[nightly] дайджест отправлен в Telegram напрямую" >&2
  else
    echo "[nightly] прямая отправка не удалась (ожидаемо на 5.42) — пусть шлёт оркестратор" >&2
  fi
fi
exit $overall
