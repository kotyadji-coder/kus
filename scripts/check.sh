#!/usr/bin/env bash
set -euo pipefail

echo "== Git status =="
git status --short || true

if [ -f package.json ]; then
  echo "== Node project checks =="
  if npm run | grep -q "lint"; then npm run lint; fi
  if npm run | grep -q "typecheck"; then npm run typecheck; fi
  if npm run | grep -q "test"; then npm run test; fi
  if npm run | grep -q "build"; then npm run build; fi
fi

if [ -f pyproject.toml ] || [ -f pytest.ini ] || [ -d tests ]; then
  echo "== Python project checks =="
  export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}."
  if [ -x ./.venv/bin/python ] && ./.venv/bin/python -m pytest --version >/dev/null 2>&1; then
    ./.venv/bin/python -m pytest -q
  elif [ -x ./venv/bin/python ] && ./venv/bin/python -m pytest --version >/dev/null 2>&1; then
    ./venv/bin/python -m pytest -q
  elif command -v pytest >/dev/null 2>&1; then
    pytest -q
  else
    echo "pytest not found; skipping Python tests"
  fi
fi

if [ -x ./tools/check.sh ]; then
  echo "== Project tools/check.sh =="
  ./tools/check.sh
fi

echo "== Check finished =="
