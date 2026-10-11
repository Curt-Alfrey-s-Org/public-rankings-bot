#!/usr/bin/env bash
# Start dependencies only: Postgres and Redis
# Apps (api, celery, frontend) are assumed to be already running or stopped.
# Use this to bring up deps after a stop_deps call without restarting the app stack.
#
# Usage: ./scripts/start_deps.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Prefer Docker Compose V2
COMPOSE_CMD=""
if docker compose version &>/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null 2>&1; then
  COMPOSE_CMD="sudo docker-compose"
else
  echo "❌ Docker Compose not found"
  exit 1
fi

cd "$APP_ROOT"

ENV_FILE="$APP_ROOT/.env"
COMPOSE_ENV_ARGS=""
[ -f "$ENV_FILE" ] && COMPOSE_ENV_ARGS="--env-file $ENV_FILE"

echo "Starting dependencies (Postgres, Redis)..."

# Use sudo for Docker if needed
if ! docker ps &>/dev/null 2>&1; then
  COMPOSE_CMD="sudo $COMPOSE_CMD"
fi

# Start only postgres and redis
$COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$APP_ROOT/docker-compose.yml" up -d postgres redis

# Wait for postgres and redis to be healthy
echo "Waiting for Postgres to be healthy..."
for i in {1..30}; do
  if $COMPOSE_CMD -f "$APP_ROOT/docker-compose.yml" exec -T postgres pg_isready -U postgres &>/dev/null; then
    echo "✅ Postgres is healthy"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "❌ Postgres failed to start"
    exit 1
  fi
  sleep 1
done

echo "Waiting for Redis to be healthy..."
for i in {1..30}; do
  if $COMPOSE_CMD -f "$APP_ROOT/docker-compose.yml" exec -T redis redis-cli ping &>/dev/null; then
    echo "✅ Redis is healthy"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "❌ Redis failed to start"
    exit 1
  fi
  sleep 1
done

echo "✅ Dependencies started successfully"
