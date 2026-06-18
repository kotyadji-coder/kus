#!/usr/bin/env bash
# Ночной CLAUDE-АГЕНТ-ЧИНИТ (НА АМСТЕРДАМЕ, на подписке Claude — не тратит Gemini).
# Работает в ЛОКАЛЬНОМ клоне (НЕ в проде/не в sshfs-монтаже). Логика:
#   1. синхронизируется с origin/main;
#   2. фаззингом ищет нарушение инварианта; если чисто — выходит (подписку не жжёт);
#   3. отдаёт repro Claude, тот чинит корень + добавляет регресс-профиль на ВЕТКЕ;
#   4. ВОРОТА (tools/check.sh) прогоняет САМ СКРИПТ — Claude физически не может влить
#      регресс: зелено → push + PR; красно → ветка удаляется, алерт админу.
# Прод не трогается никогда: ни рестарта, ни мержа. Мержит человек.
set -u
cd "$(dirname "$0")/.." || exit 2
PY=./venv/bin/python; [ -x "$PY" ] || PY=python3
LOG="${KUS_AGENT_LOG:-/tmp/kus-night-agent.log}"
SEEDS="${KUS_AGENT_SEEDS:-201 202 203}"
FUZZ_N="${KUS_AGENT_FUZZ_N:-500}"

note() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

tg() {  # отправка админу (Амстердам имеет egress); токены из .env клона
  set -a; [ -f .env ] && . ./.env; set +a
  local tok="${BOT_TOKEN:-}" chat="${ADMIN_TELEGRAM_ID:-}"
  [ -n "$tok" ] && [ -n "$chat" ] && curl -s --max-time 25 \
    "https://api.telegram.org/bot${tok}/sendMessage" \
    --data-urlencode "chat_id=${chat}" --data-urlencode "text=$1" >/dev/null 2>&1
}

note "=== ночной агент старт ==="
git fetch -q origin main && git checkout -q main && git reset -q --hard origin/main || { note "git sync failed"; exit 1; }

# Не плодим PR: если уже есть открытый auto/* — выходим
if gh pr list --state open --json headRefName -q '.[].headRefName' 2>/dev/null | grep -q '^auto/'; then
  note "уже есть открытый auto/* PR — жду мержа человеком, выхожу"; exit 0
fi

# 1. Ищем нарушение
repro=""; viol=""
for s in $SEEDS; do
  out="$($PY tools/fuzz.py "$FUZZ_N" "$s" 2>&1)"
  if echo "$out" | grep -q "repro:"; then
    viol="$(echo "$out" | grep -A4 '^✗' | head -6)"
    repro="$(echo "$out" | grep -m1 'repro:' | sed 's/^[[:space:]]*repro:[[:space:]]*//')"
    note "нарушение на seed=$s"; break
  fi
done
if [ -z "$repro" ]; then
  note "нарушений не найдено — чинить нечего, выхожу (подписку не трогаю)"; exit 0
fi

# 2. Ветка + Claude чинит
BR="auto/fix-$(date +%Y%m%d-%H%M)"
git checkout -q -b "$BR"
PROMPT="Ты чинишь баг в калькуляторе рациона для собак (проект kus). Ночной фаззер нашёл нарушение инварианта согласования (reconcile.py).

НАРУШЕНИЕ:
$viol

ВОСПРОИЗВЕДЕНИЕ (профиль): $repro

ЗАДАЧА:
1. Найди КОРНЕВУЮ причину в calculator.py / pdf_generator.py (не маскируй симптом).
2. Почини так, чтобы рацион оставался ветеринарно-корректным.
3. По принципу ХРАПОВИКА добавь этот кейс как регрессионный профиль в список PROFILES в evals.py (с label, описывающим баг).
4. Если изменился рендер отчётов — обнови эталон: $PY tools/snapshot.py --update (только если изменения ОЖИДАЕМЫ и корректны).
5. Прогони ворота: bash tools/check.sh — добейся, чтобы было зелено (канарейка+снапшот+согласование).
6. Сделай git commit с понятным сообщением (НЕ делай git push и НЕ открывай PR — это сделает скрипт).
ПРОД НЕ ТРОГАЙ: никаких рестартов сервиса, никаких правок вне репозитория."

note "запускаю Claude (subscription)…"
claude -p "$PROMPT" --permission-mode acceptEdits >>"$LOG" 2>&1
note "Claude завершил, прогоняю ворота независимо…"

# 3. Ворота решает скрипт — Claude не может влить регресс
if bash tools/check.sh >>"$LOG" 2>&1; then
  if git diff --quiet HEAD -- && [ -z "$(git log origin/main..HEAD --oneline)" ]; then
    note "Claude не внёс изменений — нечего пушить"; git checkout -q main; git branch -qD "$BR"
    tg "🌙🤖 Ночной агент: нашёл нарушение, но Claude не смог починить (нет коммита). repro: $repro"
    exit 1
  fi
  git push -q origin "$BR"
  body="$(printf 'Автофикс ночного агента. Ворота (канарейка+снапшот+согласование) ЗЕЛЁНЫЕ.\n\nНарушение:\n%s\n\nrepro: %s\n\n⚠️ Мерж — вручную после ревью. Прод не тронут.' "$viol" "$repro")"
  url="$(gh pr create --base main --head "$BR" --title "auto: фикс ночного фаззера ($BR)" --body "$body" 2>>"$LOG")"
  note "PR создан: $url"
  tg "🌙🤖 Ночной агент починил баг и открыл PR (ворота зелёные, ждёт твоего ревью):
$url

repro: $repro"
else
  note "ворота КРАСНЫЕ после Claude — откатываю ветку, прод чист"
  git checkout -q main; git branch -qD "$BR" 2>/dev/null
  tg "🌙🤖 Ночной агент: нашёл баг, но автофикс НЕ прошёл ворота — откатил, ничего не влил. Нужен человек.
repro: $repro"
  exit 1
fi
note "=== ночной агент конец ==="
