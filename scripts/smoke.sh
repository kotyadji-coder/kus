#!/usr/bin/env bash
set -euo pipefail

URL="${1:-}"

if [ -z "$URL" ]; then
  echo "Usage: ./scripts/smoke.sh https://example.com"
  exit 1
fi

curl -fsS "$URL" >/dev/null
echo "Smoke OK: $URL"

