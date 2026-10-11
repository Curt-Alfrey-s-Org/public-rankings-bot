#!/usr/bin/env bash
# Post-deploy smoke check. Run from Rankings-Bot project root.
# Usage:
#   ./scripts/smoke_check.sh
#   BASE_URL=https://www.probilliardssoftware.com ./scripts/smoke_check.sh
# Optional: ADMIN_USERNAME=admin ADMIN_PASSWORD=secret for login check.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_ROOT"

BASE_URL="${BASE_URL:-http://127.0.0.1:8003}"
BASE_URL="${BASE_URL%/}"
FAIL=0

check() {
  local label="$1"
  local url="$2"
  local method="${3:-GET}"
  local code
  if [[ "$method" == "GET" ]]; then
    code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 "$url" || echo "000")
  else
    code=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" --connect-timeout 10 "$url" || echo "000")
  fi
  if [[ "$code" == "200" ]]; then
    echo "[PASS] $label ($code)"
    return 0
  fi
  echo "[FAIL] $label ($code) $url"
  FAIL=1
  return 1
}

echo "=== Rankings Bot smoke check ==="
echo "BASE_URL=$BASE_URL"
echo "---"
check "Health" "$BASE_URL/api/health"
check "System health" "$BASE_URL/api/system/health"
check "Frontend /" "$BASE_URL/"
check "Rankings WPA" "$BASE_URL/api/rankings/wpa?limit=5"
check "Rankings WPBA" "$BASE_URL/api/rankings/wpba?limit=5"

if [[ -n "${ADMIN_USERNAME:-}" && -n "${ADMIN_PASSWORD:-}" ]]; then
  resp=$(curl -s -w "\n%{http_code}" -X POST -H "Content-Type: application/json" \
    -d "{\"username\":\"$ADMIN_USERNAME\",\"password\":\"$ADMIN_PASSWORD\"}" \
    "$BASE_URL/api/auth/login" || true)
  status=$(echo "$resp" | tail -n1)
  if [[ "$status" == "200" ]]; then
    token=$(echo "$resp" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
    if [[ -n "$token" ]]; then
      code=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $token" "$BASE_URL/api/auth/me" || echo "000")
      if [[ "$code" == "200" ]]; then
        echo "[PASS] Admin login + /api/auth/me (200)"
      else
        echo "[FAIL] Admin /api/auth/me ($code)"
        FAIL=1
      fi
    else
      echo "[FAIL] Admin login (no token)"
      FAIL=1
    fi
  else
    echo "[FAIL] Admin login ($status)"
    FAIL=1
  fi
else
  echo "[SKIP] Admin login (set ADMIN_USERNAME and ADMIN_PASSWORD to test)"
fi

echo "---"
if [[ $FAIL -eq 0 ]]; then
  echo "Smoke check passed."
  exit 0
fi
echo "Smoke check had failures. See docs/SMOKE_CHECK.md and docs/DEPLOY_DEBUG_HTTP.md"
exit 1
