#!/usr/bin/env bash
# Intelligent start: single entry point for Rankings Bot.
# Detects context (Docker, dev, production) and starts the right components.
#
# Doc refs (AI / maintainers — nginx/tunnel/API wiring): docs/NETWORKING_DOC_HOOKS.md;
#   docs/PORT_MANAGEMENT.md; docs/MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md
#
# Usage:
#   ./scripts/start.sh              # Full stack (production Docker + nginx)
#   ./scripts/start.sh --dev        # Development: host API + frontend (start_gui.sh)
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

# The main Dockerfile (api + celery-worker) does FROM rankings-bot-base:${BASE_TAG}.
# Route every build through a buildx builder whose BuildKit instance
# persistently stores cache mount data. On this host the dockerd-integrated
# BuildKit does NOT persist `--mount=type=cache` blobs between builds (verified
# empirically: a marker file written to id=bots-pip is gone on the next build).
# The `docker-container` driver stores cache mount blobs in the builder
# container's volume, so `bots-pip` / `bots-apt` / `bots-npm` actually survive
# across builds and across `--no-cache` invocations. See
# /srv/dep-cache/README.md and docs/DOCKER_BASE_AND_SMALL_EDITS.md.
#
# Pick the first available docker-container builder; fall back to whichever
# builder is active. Override with DEP_CACHE_BUILDER=<name>.
pick_builder() {
  local override="${DEP_CACHE_BUILDER:-}"
  if [ -n "$override" ]; then
    printf '%s' "$override"
    return
  fi
  if ! command -v docker >/dev/null 2>&1 || ! docker buildx version >/dev/null 2>&1; then
    printf '%s' "default"
    return
  fi
  # Prefer any docker-container driver builder (persistent cache mounts).
  local name
  name=$(docker buildx ls 2>/dev/null \
    | awk '/docker-container/ { sub(/\*$/, "", $1); print $1; exit }')
  if [ -n "$name" ]; then
    printf '%s' "$name"
    return
  fi
  printf '%s' "default"
}
BUILDX_BUILDER="$(pick_builder)"
export BUILDX_BUILDER
# Compose 2.22+: route `docker compose build` through buildx/bake so it
# respects BUILDX_BUILDER. Without this, compose invokes the classic docker
# builder regardless of `docker buildx use`.
export COMPOSE_BAKE=true
echo "🔧 Build routed through buildx builder: $BUILDX_BUILDER (persistent cache mounts via /srv/dep-cache)"

# buildx_build: drop-in for `docker build`, but routed through BUILDX_BUILDER
# and with `--load` so the docker-container driver exports the image into the
# local docker image store (otherwise `docker compose up` can't find it).
buildx_build() {
  docker buildx build --builder "$BUILDX_BUILDER" --load "$@"
}

# When BASE_TAG=local (default) and the base image doesn't exist, Docker tries to
# pull it from a registry and fails. Build it locally from Dockerfile.base first.
# See Dockerfile and docs/DOCKER_BASE_AND_SMALL_EDITS.md.
BASE_IMAGE="${RANKINGS_BOT_BASE_IMAGE:-rankings-bot-base:local}"
ensure_base_image() {
  local force="${1:-}"
  if [ -z "$force" ] && $DOCKER image inspect "$BASE_IMAGE" &>/dev/null; then
    return 0
  fi
  echo "Building base image ($BASE_IMAGE) from Dockerfile.base via $BUILDX_BUILDER..."
  # hub hub: refresh build-contexts/wheels-bots before the wheel-consuming build (non-fatal).
  ALFA_AI_ROOT="${ALFA_AI_ROOT:-$APP_ROOT/../alfa-ai}"
  [ -f "$ALFA_AI_ROOT/scripts/sync-bot-wheels-preflight.sh" ] && \
    bash "$ALFA_AI_ROOT/scripts/sync-bot-wheels-preflight.sh" || true
  local cache_arg=""
  [ -n "$force" ] && cache_arg="--no-cache"
  (cd "$APP_ROOT" && buildx_build $cache_arg \
       -f Dockerfile.base -t "$BASE_IMAGE" .) \
    || { echo "❌ Base image build failed (Dockerfile.base)."; exit 1; }
  echo "   ✅ Base image built: $BASE_IMAGE"
}

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
      echo "  --no-cache    Force rebuild (with --app-only or full stack)."
      echo "                NOTE: wipes BuildKit cache mounts too (moby/moby#41715)"
      echo "                so pip/apt/npm all re-download. Avoid for routine rebuilds."
      echo "  --production  Full stack, set www to live app (no prompt)"
      echo "  --maintenance Full stack, set www to maintenance page (no prompt)"
      echo ""
      echo "Web/mobile: use start_web.sh, start_mobile.sh"
      exit 0
      ;;
  esac
done

cd "$APP_ROOT"

# Single compose file for all Docker Compose invocations (avoids duplicate project / name conflicts).
COMPOSE_FILE="$APP_ROOT/docker-compose.yml"
[ -f "$APP_ROOT/production/docker-compose.prod.yml" ] && COMPOSE_FILE="$APP_ROOT/production/docker-compose.prod.yml"

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
  (cd "$APP_ROOT" && $COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$COMPOSE_FILE" up -d --wait postgres redis) || exit 1
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
  # Base image must exist before building api/celery (they do FROM rankings-bot-base).
  ensure_base_image "$NO_CACHE"
  # BuildKit: intelligent layering + persistent cache mounts (Docker docs).
  # All builds go through $BUILDX_BUILDER so id=bots-pip / bots-npm / bots-apt
  # cache mounts reuse blobs across invocations.
  buildx_build -t rankings-bot_rankings-bot-frontend $CACHE_ARG frontend/ &>/dev/null || { echo "❌ Frontend build failed"; exit 1; }
  $COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$COMPOSE_FILE" build $CACHE_ARG rankings-bot-api celery-worker &>/dev/null || { echo "❌ App build failed"; exit 1; }
  $COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$COMPOSE_FILE" up -d rankings-bot-api celery-worker rankings-bot-frontend
  echo "Waiting for API..."
  for i in $(seq 1 60); do
    if curl -s http://127.0.0.1:8003/api/health &>/dev/null; then
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

# Ensure networks (postgres/redis live only on rankings-bot-network; see production compose)
$DOCKER network inspect "$NETWORK" &>/dev/null || $DOCKER network create "$NETWORK" 2>/dev/null || true
$DOCKER network inspect rankings-bot-network &>/dev/null || $DOCKER network create rankings-bot-network 2>/dev/null || true

echo "🚀 Starting Rankings Bot (full stack)..."

# 1. Build frontend when using production compose (API mounts frontend/dist)
if [ "$COMPOSE_FILE" = "$APP_ROOT/production/docker-compose.prod.yml" ]; then
  if [ -d "$APP_ROOT/frontend" ] && [ -f "$APP_ROOT/frontend/package.json" ]; then
    echo "Building frontend (for API mount) via Docker Node image..."
    if [ ! -f "$SCRIPT_DIR/build_frontend_with_docker.sh" ]; then
      echo "❌ Missing scripts/build_frontend_with_docker.sh (Docker-only frontend build)."
      exit 1
    fi
    if ! command -v docker &>/dev/null; then
      echo "❌ Docker is required to build the frontend (no host npm fallback)."
      exit 1
    fi
    bash "$SCRIPT_DIR/build_frontend_with_docker.sh" "$APP_ROOT" || { echo "❌ Frontend build failed"; exit 1; }
    echo "   ✅ frontend/dist ready."
  fi
fi

# 2. Build Docker images (API, celery, frontend container) so code changes are picked up
echo "Building app images..."
CACHE_ARG=""
[ -n "$NO_CACHE" ] && CACHE_ARG="--no-cache"
# Base image must exist before building api/celery (they do FROM rankings-bot-base).
ensure_base_image "$NO_CACHE"
(cd "$APP_ROOT" && $COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$COMPOSE_FILE" build $CACHE_ARG) || { echo "❌ Image build failed"; exit 1; }
echo "   ✅ Images built."

# When using production compose, ensure Postgres is up before the full stack.
# Use the same compose file as the main "up" below: root docker-compose.yml uses
# "include:" and can yield a different Compose project name than -f production/...
# alone, which caused "container name already in use" for rankings-bot-postgres.
if [ "$COMPOSE_FILE" = "$APP_ROOT/production/docker-compose.prod.yml" ]; then
  echo "Starting Postgres..."
  if $DOCKER exec rankings-bot-postgres pg_isready -U postgres &>/dev/null 2>&1; then
    echo "   ✅ Postgres already running (rankings-bot-postgres)."
  else
    (cd "$APP_ROOT" && $COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$COMPOSE_FILE" up -d postgres) || exit 1
  fi
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
(cd "$APP_ROOT" && $COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$COMPOSE_FILE" up -d --wait) || { echo "ERROR: Compose up failed."; exit 1; }

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
