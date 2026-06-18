#!/usr/bin/env bash
# Ворота прода: прогнать качество и перезапустить kus.service ТОЛЬКО если зелено.
# Это настоящий гейт «регресс не доезжает до прода» — на уровне деплоя, а не git
# (авто-backup-крон коммитит всё подряд, поэтому гейт на коммите ломал бы бэкапы).
#
#   bash tools/deploy.sh            # гейт + рестарт
#   bash tools/deploy.sh --check    # только гейт, без рестарта
set -u
cd "$(dirname "$0")/.." || exit 2

echo "▶ Проверка качества перед деплоем…"
if ! bash tools/check.sh; then
  echo "✗ ДЕПЛОЙ ОТМЕНЁН — есть регресс. Прод не тронут."
  exit 1
fi

if [ "${1:-}" = "--check" ]; then
  echo "✓ Гейт пройден (рестарт пропущен по --check)."
  exit 0
fi

echo "▶ Рестарт kus.service…"
if systemctl restart kus.service && sleep 2 && systemctl is-active --quiet kus.service; then
  echo "✓ Деплой выполнен: kus.service активен."
else
  echo "✗ Сервис не поднялся после рестарта — проверьте: journalctl -u kus.service -n 30"
  exit 1
fi
