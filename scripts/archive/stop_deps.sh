#!/usr/bin/env bash
# Stop dependencies only: Postgres and Redis
# Apps (api, celery, frontend) continue running.
# Use this when you want to pause database/cache without stopping the application.
# ⚠️ WARNING: App will lose database/cache connectivity if still running!
#
# Usage: ./scripts/stop_deps.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

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

echo "Stopping dependencies (Postgres, Redis)..."

# Use sudo for Docker if needed
if ! docker ps &>/dev/null 2>&1; then
  COMPOSE_CMD="sudo $COMPOSE_CMD"
fi

# Stop only postgres and redis
$COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$APP_ROOT/docker-compose.yml" stop postgres redis -t 5 || true

echo "✅ Dependencies stopped"
