#!/usr/bin/env bash
# Intelligent stop: single entry point for stopping Rankings Bot.
#
# Usage:
#   ./scripts/stop.sh              # Full stack (compose down + nginx)
#   ./scripts/stop.sh --app-only   # API + Celery + Frontend + Nginx (keep deps)
#   ./scripts/stop.sh --deps-only  # Postgres + Redis only
#   ./scripts/stop.sh --dev        # Host API + frontend + compose (dev environment)
#   ./scripts/stop.sh --tunnel     # Also stop Cloudflare tunnel (default: leave running)
#
# Use sudo if Docker needs it: sudo ./scripts/stop.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
NGINX_CONTAINER="probilliards-nginx"
TUNNEL_CONTAINER="cf-probilliards"

DOCKER="sudo docker"
COMPOSE_CMD=""
if $DOCKER compose version &>/dev/null 2>&1; then
  COMPOSE_CMD="$DOCKER compose"
elif command -v docker-compose &>/dev/null 2>&1; then
  COMPOSE_CMD="sudo docker-compose"
fi

ENV_FILE="$APP_ROOT/.env"
COMPOSE_ENV_ARGS=""
[ -f "$ENV_FILE" ] && COMPOSE_ENV_ARGS="--env-file $ENV_FILE"
# shellcheck disable=SC1091
. "$SCRIPT_DIR/export_compose_uid_gid.sh"
write_compose_host_user_env "$APP_ROOT"
if [ -n "$COMPOSE_ENV_ARGS" ]; then
  COMPOSE_ENV_ARGS="$COMPOSE_ENV_ARGS --env-file $APP_ROOT/.env.compose-host-user"
else
  COMPOSE_ENV_ARGS="--env-file $APP_ROOT/.env.compose-host-user"
fi

# Parse flags
APP_ONLY=
DEPS_ONLY=
DEV=
STOP_TUNNEL=
API_ONLY=
for arg in "$@"; do
  case "$arg" in
    --app-only)   APP_ONLY=1 ;;
    --deps-only)  DEPS_ONLY=1 ;;
    --dev)        DEV=1 ;;
    --tunnel)     STOP_TUNNEL=1 ;;
    --api-only)   API_ONLY=1 ;;
    -h|--help)
      echo "Usage: ./scripts/stop.sh [OPTIONS]"
      echo "  (no args)     Full stack (compose down + nginx)"
      echo "  --app-only   API + Celery + Frontend + Nginx (keep Postgres, Redis)"
      echo "  --deps-only  Postgres + Redis only"
      echo "  --dev        Host API + frontend + mobile + compose (development)"
      echo "  --api-only   Kill host API process on port 8003"
      echo "  --tunnel     Also stop Cloudflare tunnel"
      echo ""
      echo "Web/mobile: use stop_web.sh, stop_mobile.sh"
      exit 0
      ;;
  esac
done

cd "$APP_ROOT"

# --- API only: kill host process on port 8003 ---
if [ -n "$API_ONLY" ]; then
  PORT="${API_PORT:-8003}"
  pid=$(lsof -t -i ":$PORT" 2>/dev/null || true)
  if [ -z "$pid" ]; then
    echo "Nothing running on port $PORT."
  else
    kill "$pid" 2>/dev/null || true
    echo "Stopped API (PID $pid) on port $PORT."
  fi
  exit 0
fi

# --- Dev mode: kill host processes (web + mobile) + compose down ---
if [ -n "$DEV" ]; then
  echo "Stopping development environment (web + mobile)..."
  pkill -f "uvicorn.*api.main:app" 2>/dev/null || true
  pkill -f "vite" 2>/dev/null || true
  pkill -f "npm.*dev" 2>/dev/null || true
  pkill -f "python.*uvicorn" 2>/dev/null || true
  pkill -f "node.*vite" 2>/dev/null || true
  pkill -f "react-native start" 2>/dev/null || true
  pkill -f "metro" 2>/dev/null || true
  pkill -f "node.*react-native" 2>/dev/null || true
  pid=$(lsof -t -i ":8081" 2>/dev/null || true)
  [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  rm -f /tmp/rankings-bot-browser-open.lock 2>/dev/null || true
  if [ -n "$COMPOSE_CMD" ] && [ -f "$APP_ROOT/docker-compose.yml" ]; then
    (cd "$APP_ROOT" && $COMPOSE_CMD $COMPOSE_ENV_ARGS -f docker-compose.yml down --remove-orphans -t 5) || true
  fi
  echo "✅ Development environment stopped."
  exit 0
fi

# --- Deps only: Postgres + Redis ---
if [ -n "$DEPS_ONLY" ]; then
  [ -z "$COMPOSE_CMD" ] && { echo "ERROR: Docker Compose not found."; exit 1; }
  echo "Stopping dependencies (Postgres, Redis)..."
  $COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$APP_ROOT/docker-compose.yml" stop postgres redis -t 5 2>/dev/null || true
  echo "✅ Dependencies stopped."
  exit 0
fi

# --- App only: API + Celery + Frontend + Nginx ---
if [ -n "$APP_ONLY" ]; then
  echo "Stopping application containers..."
  if [ -n "$COMPOSE_CMD" ] && [ -f "$APP_ROOT/docker-compose.yml" ]; then
    $COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$APP_ROOT/docker-compose.yml" stop \
      rankings-bot-api celery-worker rankings-bot-frontend -t 5 2>/dev/null || true
  fi
  $DOCKER stop "$NGINX_CONTAINER" -t 5 2>/dev/null || true
  # Also try production compose
  if [ -f "$APP_ROOT/production/docker-compose.prod.yml" ]; then
    $COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$APP_ROOT/production/docker-compose.prod.yml" stop \
      rankings-bot-api celery-worker -t 5 2>/dev/null || true
  fi
  echo "✅ Application stopped (dependencies still running)."
  exit 0
fi

# --- Full stack (default) ---
echo "Stopping Rankings Bot..."

if [ -n "$COMPOSE_CMD" ]; then
  if [ -f "$APP_ROOT/production/docker-compose.prod.yml" ]; then
    echo "   Using production compose..."
    (cd "$APP_ROOT" && $COMPOSE_CMD $COMPOSE_ENV_ARGS -f production/docker-compose.prod.yml down --remove-orphans -t 10) || true
  fi
  if [ -f "$APP_ROOT/docker-compose.yml" ]; then
    (cd "$APP_ROOT" && $COMPOSE_CMD $COMPOSE_ENV_ARGS -f docker-compose.yml down --remove-orphans -t 10) || true
  fi
  # Explicitly stop/remove Redis and other rankings-bot containers in case compose down left orphans
  for c in rankings-bot-redis rankings-bot-postgres rankings-bot-api rankings-bot-celery-worker rankings-bot-frontend; do
    $DOCKER stop "$c" -t 5 2>/dev/null || true
    $DOCKER rm "$c" 2>/dev/null || true
  done
  echo "   ✓ All containers stopped (including Redis)."
else
  echo "   ⚠ Docker Compose not found."
fi

$DOCKER stop "$NGINX_CONTAINER" 2>/dev/null || true
$DOCKER rm "$NGINX_CONTAINER" 2>/dev/null || true
echo "   ✓ Nginx stopped."

if [ -n "$STOP_TUNNEL" ]; then
  $DOCKER stop "$TUNNEL_CONTAINER" 2>/dev/null || true
  echo "   ✓ Tunnel ($TUNNEL_CONTAINER) stopped."
fi

echo "✅ Rankings Bot stopped."
