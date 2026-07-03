#!/usr/bin/env bash
set -euo pipefail

if [ -f package.json ] && npm run | grep -q "test:e2e"; then
  npm run test:e2e
  exit 0
fi

if [ -f package.json ] && [ -d tests/e2e ]; then
  npx playwright test
  exit 0
fi

echo "No browser checks configured yet."
echo "For web projects, add Playwright tests in tests/e2e."
exit 2
