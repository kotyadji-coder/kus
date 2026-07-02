#!/usr/bin/env bash
set -euo pipefail

echo "== Local verification without live deploy =="

failed=0
warned=0

run_required() {
  echo
  echo "== $1 =="
  shift
  if "$@"; then
    echo "OK: $*"
  else
    echo "FAILED: $*"
    failed=1
  fi
}

run_optional() {
  echo
  echo "== $1 =="
  shift
  if "$@"; then
    echo "OK: $*"
  else
    echo "SKIPPED_OR_FAILED: $*"
    warned=1
  fi
}

echo
echo "== Project markers =="
[ -f package.json ] && echo "Detected: Node/web project"
[ -f pyproject.toml ] && echo "Detected: Python project"
[ -f requirements.txt ] && echo "Detected: Python requirements"
[ -f docker-compose.yml ] && echo "Detected: docker-compose.yml"
[ -f compose.yml ] && echo "Detected: compose.yml"
[ -d tests ] && echo "Detected: tests/"
[ -d sim ] && echo "Detected: sim/"

if [ -x ./scripts/check.sh ]; then
  run_required "Project code checks" ./scripts/check.sh
else
  echo "WARNING: no ./scripts/check.sh"
  warned=1
fi

if [ -f package.json ]; then
  if npm run | grep -q "test:e2e"; then
    run_optional "Browser e2e checks" npm run test:e2e
  elif [ -x ./scripts/browser-check.sh ]; then
    run_optional "Browser checks" ./scripts/browser-check.sh
  else
    echo "WARNING: web/browser checks are not configured"
    warned=1
  fi
fi

if [ -d sim ]; then
  if [ -x ./.venv/bin/python ] && [ -f sim/e2e.py ]; then
    run_optional "Bot/app simulator sim/e2e.py" ./.venv/bin/python sim/e2e.py
  elif [ -f sim/e2e.py ]; then
    run_optional "Bot/app simulator sim/e2e.py" python3 sim/e2e.py
  fi
fi

if [ -d scripts ]; then
  found_sim=0
  for sim_script in scripts/sim_*.py; do
    [ -f "$sim_script" ] || continue
    found_sim=1
    if [ -x ./.venv/bin/python ]; then
      run_optional "Bot simulator $sim_script" ./.venv/bin/python "$sim_script"
    else
      run_optional "Bot simulator $sim_script" python3 "$sim_script"
    fi
  done
  if [ "$found_sim" -eq 0 ]; then
    :
  fi
fi

if [ -f HARNESS.yaml ]; then
  if grep -qi "database:" HARNESS.yaml; then
    echo
    echo "== Database safety =="
    echo "Do not run live migrations from local verification."
    echo "Use test database or staging only."
  fi
fi

echo
echo "== Local verification summary =="
if [ "$failed" -ne 0 ]; then
  echo "VERDICT: Нельзя выкладывать: есть проблемы"
  exit 1
fi

if [ "$warned" -ne 0 ]; then
  echo "VERDICT: Нельзя уверенно выкладывать: часть проверок не настроена или не прошла"
  exit 2
fi

echo "VERDICT: Готово к выкладке на живой проект"

