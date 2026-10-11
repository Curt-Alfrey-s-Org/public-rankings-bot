#!/usr/bin/env bash
# Tournament wizard smoke: manager core + deferred paths + production HTTP E2E.
# Runs inside rankings-bot-api container (creates/deletes throwaway data only).
#
# Usage (from app root on server):
#   ./scripts/smoke_test_tournament_wizard.sh
#   SKIP_TOURNAMENT_SMOKE=1 ./scripts/deploy_website.sh   # skip in deploy
#
# Env:
#   CONTAINER_API (default rankings-bot-api)
#   API_PORT (default 8003)
#   E2E_USER / E2E_ROLE (default tornybotca1 / super_admin for create permission)
#   SKIP_TOURNAMENT_SMOKE=1  skip entirely (exit 0)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONTAINER_API="${CONTAINER_API:-rankings-bot-api}"
API_PORT="${API_PORT:-8003}"
HEALTH_URL="http://127.0.0.1:${API_PORT}/api/health"
E2E_USER="${E2E_USER:-tornybotca1}"
E2E_ROLE="${E2E_ROLE:-super_admin}"

if [ "${SKIP_TOURNAMENT_SMOKE:-0}" = "1" ]; then
  echo "SKIP_TOURNAMENT_SMOKE=1 — tournament wizard smoke skipped."
  exit 0
fi

DOCKER="${DOCKER:-docker}"
if ! $DOCKER info &>/dev/null; then
  DOCKER="sudo docker"
fi

if ! $DOCKER ps --format '{{.Names}}' 2>/dev/null | grep -qx "$CONTAINER_API"; then
  echo "ERROR: container $CONTAINER_API not running." >&2
  exit 1
fi

echo "=== Tournament wizard smoke ($CONTAINER_API) ==="

echo "Waiting for $HEALTH_URL ..."
elapsed=0
timeout=90
while [ "$elapsed" -lt "$timeout" ]; do
  if $DOCKER exec "$CONTAINER_API" curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
    echo "[PASS] API health"
    break
  fi
  sleep 2
  elapsed=$((elapsed + 2))
done
if [ "$elapsed" -ge "$timeout" ]; then
  echo "[FAIL] API health timeout after ${timeout}s" >&2
  exit 1
fi

run_py() {
  local label="$1"
  local script="$2"
  echo "--- $label ---"
  if ! $DOCKER exec -i "$CONTAINER_API" python3 "/app/scripts/$script"; then
    echo "[FAIL] $label" >&2
    exit 1
  fi
}

run_py "Core tournament_manager smoke" "smoke_test_tournament_manager.py"
run_py "Deferred tournament paths smoke" "smoke_test_tournament_deferred.py"

echo "--- Production wizard HTTP E2E ---"
if ! $DOCKER exec -i \
  -e "E2E_USER=$E2E_USER" \
  -e "E2E_ROLE=$E2E_ROLE" \
  "$CONTAINER_API" python3 /app/scripts/e2e_production_wizard_http.py; then
  echo "[FAIL] Production wizard HTTP E2E" >&2
  exit 1
fi

echo "=== ALL TOURNAMENT WIZARD SMOKE PASSED ==="
