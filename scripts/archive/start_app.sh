#!/usr/bin/env bash
# Start application containers only: API, Celery, Frontend
# Dependencies (Postgres, Redis) must be running before calling this.
# Rebuilds app images if code changed. Fast for code-only updates.
# Use this for quick app restarts without touching database/cache.
#
# Usage: ./scripts/start_app.sh [--no-cache]
# Options:
#   --no-cache    Force full rebuild without Docker cache (slow but clean)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

log() { echo "[$(date -u '+%H:%M:%S')] $*"; }

# Prefer Docker Compose V2
COMPOSE_CMD=""
if docker compose version &>/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null 2>&1; then
  COMPOSE_CMD="sudo docker-compose"
else
  log "❌ Docker Compose not found"
  exit 1
fi

cd "$APP_ROOT"

ENV_FILE="$APP_ROOT/.env"
COMPOSE_ENV_ARGS=""
[ -f "$ENV_FILE" ] && COMPOSE_ENV_ARGS="--env-file $ENV_FILE"

NO_CACHE=
for arg in "$@"; do
  [ "$arg" = "--no-cache" ] && NO_CACHE=1
done

# Check if deps are running
log "Checking if dependencies are healthy..."
if ! $COMPOSE_CMD -f "$APP_ROOT/docker-compose.yml" exec -T postgres pg_isready -U postgres &>/dev/null 2>&1; then
  log "❌ Postgres is not running. Run ./scripts/start_deps.sh first"
  exit 1
fi
if ! $COMPOSE_CMD -f "$APP_ROOT/docker-compose.yml" exec -T redis redis-cli ping &>/dev/null 2>&1; then
  log "❌ Redis is not running. Run ./scripts/start_deps.sh first"
  exit 1
fi

# Use sudo for Docker if needed
DOCKER_CMD="docker"
if ! docker ps &>/dev/null 2>&1; then
  DOCKER_CMD="sudo docker"
  COMPOSE_CMD="sudo $COMPOSE_CMD"
fi

log "Building frontend..."
$DOCKER_CMD build -t rankings-bot_rankings-bot-frontend frontend/ \
  $([ -z "$NO_CACHE" ] || echo "--no-cache") &>/dev/null || {
  log "❌ Frontend build failed"
  exit 1
}
log "✅ Frontend built"

log "Building app images (API, Celery)..."
$COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$APP_ROOT/docker-compose.yml" build \
  rankings-bot-api celery-worker \
  $([ -z "$NO_CACHE" ] || echo "--no-cache") &>/dev/null || {
  log "❌ App build failed"
  exit 1
}
log "✅ App images built"

log "Starting application containers..."
$COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$APP_ROOT/docker-compose.yml" up -d \
  rankings-bot-api celery-worker rankings-bot-frontend

# Wait for API to be healthy
log "Waiting for API to be healthy..."
for i in {1..60}; do
  if curl -s http://127.0.0.1:8003/health &>/dev/null; then
    log "✅ API is healthy"
    break
  fi
  if [ $i -eq 60 ]; then
    log "⚠️ API did not become healthy in 60s (may still be starting)"
  fi
  sleep 1
done

log "✅ Application started successfully"
