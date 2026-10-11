#!/usr/bin/env bash
# Stop application containers only: API, Celery, Frontend, Nginx
# Dependencies (Postgres, Redis) continue running.
# Use this for quick app restarts without database/cache downtime.
#
# Usage: ./scripts/stop_app.sh

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
fi

cd "$APP_ROOT"

ENV_FILE="$APP_ROOT/.env"
COMPOSE_ENV_ARGS=""
[ -f "$ENV_FILE" ] && COMPOSE_ENV_ARGS="--env-file $ENV_FILE"

# Use sudo for Docker if needed
DOCKER_CMD="docker"
if ! docker ps &>/dev/null 2>&1; then
  DOCKER_CMD="sudo docker"
  if [ -n "$COMPOSE_CMD" ]; then
    COMPOSE_CMD="sudo $COMPOSE_CMD"
  fi
fi

log "Stopping application containers..."

# Stop app containers via compose
if [ -n "$COMPOSE_CMD" ] && [ -f "$APP_ROOT/docker-compose.yml" ]; then
  $COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$APP_ROOT/docker-compose.yml" stop \
    rankings-bot-api celery-worker rankings-bot-frontend -t 5 || true
  log "✅ App containers stopped"
fi

# Stop nginx
NGINX_CONTAINER="probilliards-nginx"
if $DOCKER_CMD ps | grep -q "$NGINX_CONTAINER"; then
  $DOCKER_CMD stop "$NGINX_CONTAINER" -t 5 2>/dev/null || true
  log "✅ Nginx stopped"
fi

log "✅ Application stopped (dependencies still running)"
