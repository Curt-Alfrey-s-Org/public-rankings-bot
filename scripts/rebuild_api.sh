#!/usr/bin/env bash
# Rebuild API image only, then restart rankings-bot-api and celery-worker.
# Use when only backend (api/, database/, scripts/, requirements) changed.
# Redis is not recreated. Run from Rankings-Bot app root.
#
# Usage:
#   ./scripts/rebuild_api.sh           # build with cache (faster)
#   ./scripts/rebuild_api.sh --no-cache   # clean build like full deploy

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_ROOT"

NO_CACHE=""
for arg in "$@"; do
  [ "$arg" = "--no-cache" ] && NO_CACHE="--no-cache"
done

echo "=========================================="
echo "  Rankings Bot — Rebuild API only"
echo "=========================================="
echo "App root: $APP_ROOT"
echo ""

if ! command -v docker &>/dev/null; then
  echo "Docker not found. For host API, use: ./scripts/restart_api.sh"
  exit 0
fi

# Always use sudo for Docker so the script works without the user being in the docker group
DOCKER="sudo docker"
COMPOSE_CMD=
if $DOCKER compose version &>/dev/null 2>&1; then
  COMPOSE_CMD="sudo docker compose"
elif command -v docker-compose &>/dev/null; then
  COMPOSE_CMD="sudo docker-compose"
else
  echo "docker-compose / docker compose not found."
  exit 1
fi

COMPOSE_FILE="$APP_ROOT/production/docker-compose.prod.yml"
if [ ! -f "$COMPOSE_FILE" ]; then
  echo "Production compose not found: $COMPOSE_FILE"
  exit 1
fi

# shellcheck disable=SC1091
. "$SCRIPT_DIR/export_compose_uid_gid.sh"
write_compose_host_user_env "$APP_ROOT"
COMPOSE_ENV_ARGS=(--env-file "$APP_ROOT/.env.compose-host-user")
[ -f "$APP_ROOT/.env" ] && COMPOSE_ENV_ARGS+=(--env-file "$APP_ROOT/.env")

echo "1. Rebuilding API image (celery uses same image)..."
# BuildKit: intelligent layering per Docker docs
(cd "$APP_ROOT" && DOCKER_BUILDKIT=1 $COMPOSE_CMD "${COMPOSE_ENV_ARGS[@]}" -f production/docker-compose.prod.yml build $NO_CACHE rankings-bot-api) || exit 1
echo "   ✅ API image built."
echo ""

echo "2. Restarting rankings-bot-api and celery-worker..."
(cd "$APP_ROOT" && $COMPOSE_CMD "${COMPOSE_ENV_ARGS[@]}" -f production/docker-compose.prod.yml up -d --force-recreate rankings-bot-api celery-worker) || exit 1
echo "   ✅ API and celery restarted (redis unchanged)."
echo ""

# rankings-bot-production.conf uses upstream keepalive to rankings-bot-api:8003. After --force-recreate
# the API container is new; nginx can reuse dead keepalive sockets and return 502 until reload/restart.
echo "3. Restarting probilliards-nginx (refresh upstream keepalive after API recreate)..."
if $DOCKER ps --format '{{.Names}}' 2>/dev/null | grep -qx 'probilliards-nginx'; then
  $DOCKER restart probilliards-nginx
  echo "   ✅ probilliards-nginx restarted."
else
  echo "   (probilliards-nginx not running; skipped)"
fi
echo ""

if [ "${SKIP_TOURNAMENT_SMOKE:-0}" != "1" ]; then
  echo "4. Tournament wizard smoke tests..."
  bash "$SCRIPT_DIR/smoke_test_tournament_wizard.sh"
fi

echo ""
echo "Done. Backend updates are live."
