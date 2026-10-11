#!/usr/bin/env bash
# ARCHIVED: legacy incremental starter (deps-only, app-only, dev, tunnel).
# Invoked automatically by ../start.sh for those flags only.
# Full stack → use ../full_deploy.sh or ../start.sh with no specialty flags.
#
# Intelligent start: single entry point for Rankings Bot.
# Detects context (Docker, dev, production) and starts the right components.
#
# Re-exec with clean bash (no BASH_ENV / profile hooks) — same pattern as full_deploy.sh; avoids
# broken completion or rc snippets interfering with deploys.
# Disk/Docker: ./scripts/cleanup_docker_disk.sh (df + builder prune; optional hook in full_deploy.sh).
if [ -z "${START_SH_CLEAN_RUN:-}" ]; then
  export BASH_ENV=
  export ENV=
  export START_SH_CLEAN_RUN=1
  exec /usr/bin/env bash --norc --noprofile "$0" "$@"
fi
#
# Usage:
#   ./scripts/start.sh              # Full stack (production Docker + nginx)
#   ./scripts/start.sh --dev        # Development Docker flow via start_web.sh
#   ./scripts/start.sh --deps-only  # Postgres + Redis only
#   ./scripts/start.sh --app-only   # API + Celery + Frontend (deps must be running)
#   ./scripts/start.sh --tunnel     # Cloudflare tunnel only
#   ./scripts/start.sh --no-cache   # Force rebuild (with --app-only)
#   ./scripts/start.sh --production # Full stack, set www to live app (no prompt)
#   ./scripts/start.sh --maintenance # Full stack, set www to maintenance page (no prompt)
#
# Use sudo if Docker needs it: sudo ./scripts/start.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
NGINX_CONTAINER="probilliards-nginx"
TUNNEL_CONTAINER="cf-probilliards"
NETWORK="tunnel_network"

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
MODE="full"
DEPS_ONLY=
APP_ONLY=
DEV=
TUNNEL_ONLY=
NO_CACHE=
SITE_MODE=
for arg in "$@"; do
  case "$arg" in
    --deps-only)    DEPS_ONLY=1 ;;
    --app-only)     APP_ONLY=1 ;;
    --dev)          DEV=1 ;;
    --tunnel)       TUNNEL_ONLY=1 ;;
    --no-cache)     NO_CACHE=1 ;;
    --production)   SITE_MODE=production ;;
    --maintenance)  SITE_MODE=maintenance ;;
    -h|--help)
      echo "Usage: ./scripts/start.sh [OPTIONS]"
      echo "  (no args)     Full stack (Docker + nginx); prompts maintenance vs production"
      echo "  --dev         Development: Docker flow (same as web)"
      echo "  --deps-only   Postgres + Redis only"
      echo "  --app-only    API + Celery + Frontend (deps must run first)"
      echo "  --tunnel      Cloudflare tunnel only"
      echo "  --no-cache    Force rebuild (with --app-only or full stack)"
      echo "  --production  Full stack, set www to live app (no prompt)"
      echo "  --maintenance Full stack, set www to maintenance page (no prompt)"
      echo ""
      echo "Web/mobile: use start_web.sh, start_mobile.sh"
      exit 0
      ;;
  esac
done

cd "$APP_ROOT"

# --- Development mode: Docker flow (same as production, no host API) ---
if [ -n "$DEV" ]; then
  if [ -x "$SCRIPT_DIR/start_web.sh" ]; then
    exec "$SCRIPT_DIR/start_web.sh"
  else
    echo "ERROR: start_web.sh not found or not executable."
    exit 1
  fi
fi

# --- Tunnel only ---
if [ -n "$TUNNEL_ONLY" ]; then
  if [ -x "$SCRIPT_DIR/start_cf_probilliards.sh" ]; then
    exec "$SCRIPT_DIR/start_cf_probilliards.sh"
  else
    echo "ERROR: start_cf_probilliards.sh not found."
    exit 1
  fi
fi

# --- Deps only: Postgres + Redis ---
if [ -n "$DEPS_ONLY" ]; then
  [ -z "$COMPOSE_CMD" ] && { echo "ERROR: Docker Compose not found."; exit 1; }
  echo "Starting dependencies (Postgres, Redis)..."
  (cd "$APP_ROOT" && $COMPOSE_CMD $COMPOSE_ENV_ARGS -f docker-compose.yml up -d postgres redis) || exit 1
  echo "Waiting for Postgres..."
  for i in $(seq 1 30); do
    if $DOCKER exec rankings-bot-postgres pg_isready -U postgres &>/dev/null 2>&1; then
      echo "✅ Postgres healthy"
      break
    fi
    [ "$i" -eq 30 ] && { echo "❌ Postgres failed to start"; exit 1; }
    sleep 1
  done
  echo "Waiting for Redis..."
  for i in $(seq 1 30); do
    if $DOCKER exec rankings-bot-redis redis-cli ping &>/dev/null 2>&1; then
      echo "✅ Redis healthy"
      break
    fi
    [ "$i" -eq 30 ] && { echo "❌ Redis failed to start"; exit 1; }
    sleep 1
  done
  echo "✅ Dependencies started."
  exit 0
fi

# --- App only: API + Celery + Frontend (deps must be running) ---
if [ -n "$APP_ONLY" ]; then
  [ -z "$COMPOSE_CMD" ] && { echo "ERROR: Docker Compose not found."; exit 1; }
  echo "Checking dependencies..."
  if ! $DOCKER exec rankings-bot-postgres pg_isready -U postgres &>/dev/null 2>&1; then
    echo "❌ Postgres not running. Run: ./scripts/start.sh --deps-only"
    exit 1
  fi
  if ! $DOCKER exec rankings-bot-redis redis-cli ping &>/dev/null 2>&1; then
    echo "❌ Redis not running. Run: ./scripts/start.sh --deps-only"
    exit 1
  fi
  echo "Building and starting app containers..."
  CACHE_ARG=""
  [ -n "$NO_CACHE" ] && CACHE_ARG="--no-cache"
  # BuildKit: intelligent layering, cache mounts (Docker docs)
  DOCKER_BUILDKIT=1 $DOCKER build -t rankings-bot_rankings-bot-frontend $CACHE_ARG frontend/ &>/dev/null || { echo "❌ Frontend build failed"; exit 1; }
  DOCKER_BUILDKIT=1 $COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$APP_ROOT/docker-compose.yml" build $CACHE_ARG rankings-bot-api celery-worker &>/dev/null || { echo "❌ App build failed"; exit 1; }
  $COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$APP_ROOT/docker-compose.yml" up -d rankings-bot-api celery-worker rankings-bot-frontend
  echo "Waiting for API (container health endpoint)..."
  for i in $(seq 1 60); do
    if $DOCKER exec rankings-bot-api curl -fsS http://localhost:8003/api/health &>/dev/null 2>&1; then
      echo "✅ API healthy"
      break
    fi
    [ "$i" -eq 60 ] && echo "⚠️ API may still be starting (check: docker logs rankings-bot-api)"
    sleep 1
  done
  echo "✅ Application started."
  exit 0
fi

# --- Full stack (production) ---
[ -z "$COMPOSE_CMD" ] && { echo "ERROR: Docker Compose not found."; exit 1; }

# Ensure network
$DOCKER network inspect "$NETWORK" &>/dev/null || $DOCKER network create "$NETWORK" 2>/dev/null || true

# Choose compose file
COMPOSE_FILE="$APP_ROOT/docker-compose.yml"
PROD_COMPOSE_FILE="$APP_ROOT/production/docker-compose.prod.yml"
[ -f "$PROD_COMPOSE_FILE" ] && COMPOSE_FILE="$PROD_COMPOSE_FILE"

echo "🚀 Starting Rankings Bot (full stack)..."

# 1. Build frontend via Docker Node when using production compose (API mounts frontend/dist)
if [[ "$COMPOSE_FILE" == "$PROD_COMPOSE_FILE" ]]; then
  if [ -d "$APP_ROOT/frontend" ] && [ -f "$APP_ROOT/frontend/package.json" ]; then
    echo "Building frontend (Docker Node, for API mount)..."
    if [ -x "$SCRIPT_DIR/clean_frontend_dist.sh" ]; then
      "$SCRIPT_DIR/clean_frontend_dist.sh"
    fi
    "$SCRIPT_DIR/build_frontend_with_docker.sh" "$APP_ROOT" || { echo "❌ Frontend build failed"; exit 1; }
    echo "   ✅ frontend/dist ready."
  fi
fi

# 2. Build Docker images (API, celery, frontend container) so code changes are picked up
echo "Building app images..."
CACHE_ARG=""
[ -n "$NO_CACHE" ] && CACHE_ARG="--no-cache"
(cd "$APP_ROOT" && DOCKER_BUILDKIT=1 $COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$COMPOSE_FILE" build $CACHE_ARG) || { echo "❌ Image build failed"; exit 1; }
echo "   ✅ Images built."

# When using production compose, start Postgres from main compose first
if [[ "$COMPOSE_FILE" == "$PROD_COMPOSE_FILE" ]]; then
  echo "Starting Postgres..."
  (cd "$APP_ROOT" && $COMPOSE_CMD $COMPOSE_ENV_ARGS -f docker-compose.yml up -d postgres) || exit 1
  echo "Waiting for Postgres..."
  for i in $(seq 1 30); do
    if $DOCKER exec rankings-bot-postgres pg_isready -U postgres &>/dev/null 2>&1; then
      break
    fi
    [ "$i" -eq 30 ] && { echo "❌ Postgres failed"; exit 1; }
    sleep 1
  done
fi

# 3. Start main services
echo "Starting main services..."
(cd "$APP_ROOT" && $COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$COMPOSE_FILE" up -d) || { echo "ERROR: Compose up failed."; exit 1; }

# Nginx
echo "Starting nginx..."
$DOCKER stop "$NGINX_CONTAINER" 2>/dev/null || true
$DOCKER rm "$NGINX_CONTAINER" 2>/dev/null || true
if [ -f "$APP_ROOT/nginx-config/docker-compose.nginx.yml" ]; then
  (cd "$APP_ROOT/nginx-config" && $COMPOSE_CMD -f docker-compose.nginx.yml up -d) || { echo "WARN: Nginx failed."; }
else
  echo "WARN: nginx-config/docker-compose.nginx.yml not found."
fi

# Prompt for maintenance vs production (when nginx is up and full stack)
if $DOCKER ps --format '{{.Names}}' 2>/dev/null | grep -q "^${NGINX_CONTAINER}$"; then
  if [ -z "${SITE_MODE:-}" ] && [ -n "${DEPLOY_SITE_MODE:-}" ]; then
    SITE_MODE="$DEPLOY_SITE_MODE"
  fi
  if [ -z "${SITE_MODE:-}" ]; then
    if [ -t 0 ]; then
      echo ""
      echo "Run www.probilliardssoftware.com in [p]roduction (live app) or [m]aintenance (static page)?"
      printf "  (p/m) [default: p]: "
      read -r choice
      case "${choice:-p}" in
        p|production)  SITE_MODE=production ;;
        m|maintenance) SITE_MODE=maintenance ;;
        *) echo "Invalid choice. Using production."; SITE_MODE=production ;;
      esac
    else
      SITE_MODE=production
    fi
  fi
  case "$SITE_MODE" in
    production|demo) SITE_MODE=production ;;
    maintenance) ;;
    *) SITE_MODE=production ;;
  esac
  [ -n "${SITE_MODE:-}" ] && "$SCRIPT_DIR/switch-site.sh" "$SITE_MODE"
  if [ "$SITE_MODE" = "maintenance" ]; then
    echo ""
    echo "Maintenance mode is active for public www."
    echo "Local development ingress remains available through nginx only:"
    echo "  - http://localhost:8088"
  fi
fi

# Optional: start tunnel if it exists
if $DOCKER ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${TUNNEL_CONTAINER}$"; then
  STATE=$($DOCKER inspect -f '{{.State.Status}}' "$TUNNEL_CONTAINER" 2>/dev/null || true)
  if [ "$STATE" != "running" ]; then
    $DOCKER start "$TUNNEL_CONTAINER" 2>/dev/null || true
  fi
  $DOCKER network connect "$NETWORK" "$TUNNEL_CONTAINER" 2>/dev/null || true
fi

echo "✅ Rankings Bot started (main services + nginx)."
