#!/usr/bin/env bash
# Smoke test: verify API health and basic endpoints respond.
# Usage: ./scripts/smoke_test.sh [BASE_URL]
# Default: https://www.probilliardssoftware.com (or set API_URL env)
# Exit 0 if all pass, 1 if any fail.

set -euo pipefail
BASE_URL="${1:-${API_URL:-https://www.probilliardssoftware.com}}"
BASE_URL="${BASE_URL%/}"

echo "=== Smoke test: $BASE_URL ==="

FAIL=0

# Health
code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 "$BASE_URL/api/health" 2>/dev/null || echo "000")
if [[ "$code" == "200" ]]; then
  echo "[PASS] GET /api/health ($code)"
else
  echo "[FAIL] GET /api/health ($code) — expected 200"
  FAIL=1
fi

# App version (no auth)
code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$BASE_URL/api/app-version" 2>/dev/null || echo "000")
if [[ "$code" == "200" ]]; then
  echo "[PASS] GET /api/app-version ($code)"
else
  echo "[WARN] GET /api/app-version ($code)"
fi

# Privacy (App Store)
code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$BASE_URL/privacy" 2>/dev/null || echo "000")
if [[ "$code" == "200" ]]; then
  echo "[PASS] GET /privacy ($code)"
else
  echo "[WARN] GET /privacy ($code)"
fi

echo "---"
if [[ $FAIL -eq 0 ]]; then
  echo "Smoke test passed."
  exit 0
fi
echo "Smoke test failed. Fix health endpoint or network."
exit 1
