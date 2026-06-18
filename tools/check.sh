#!/usr/bin/env bash
# Ворота качества: канарейка + golden-снапшот + инварианты согласования.
# Вызывается pre-commit хуком и вручную (`bash tools/check.sh`). Exit != 0 — регресс.
set -u
cd "$(dirname "$0")/.." || exit 2
PY=./venv/bin/python
[ -x "$PY" ] || PY=python3
fail=0

echo "── [1/3] Канарейка (детектор живой?) ──────────────"
$PY tools/canary.py        || fail=1
echo "── [2/3] Golden-снапшот (дизайн/числа заморожены?) ─"
$PY tools/snapshot.py      || fail=1
echo "── [3/3] Согласование сводка↔меню↔покупки (эталоны) ─"
$PY tools/gate_reconcile.py || fail=1

echo "───────────────────────────────────────────────────"
if [ $fail -eq 0 ]; then
  echo "✓ ВОРОТА ОТКРЫТЫ — регрессов нет"
else
  echo "✗ ВОРОТА ЗАКРЫТЫ — есть регресс (см. выше). Если изменения ОЖИДАЕМЫ:"
  echo "    ./venv/bin/python tools/snapshot.py --update   # одобрить новый эталон"
fi
exit $fail
