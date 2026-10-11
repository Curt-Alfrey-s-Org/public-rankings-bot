#!/bin/bash
# Restart API. Uses Docker when containers are running (single flow).
# No host API - everything via Docker network.
#
# Usage: ./scripts/restart_api.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_ROOT"

DOCKER="sudo docker"
COMPOSE_CMD=""
if $DOCKER compose version &>/dev/null 2>&1; then
  COMPOSE_CMD="$DOCKER compose"
elif command -v docker-compose &>/dev/null 2>&1; then
  COMPOSE_CMD="sudo docker-compose"
fi

# Check if API container exists and is running
if $DOCKER ps --format '{{.Names}}' 2>/dev/null | grep -q "^rankings-bot-api$"; then
  echo "Restarting API container (Docker flow)..."
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
  $COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$APP_ROOT/docker-compose.yml" restart rankings-bot-api
  echo "API restarted. Logs: $DOCKER logs -f rankings-bot-api"
  exit 0
fi

# No Docker API - exit with instructions
echo "ERROR: rankings-bot-api container not running. Use Docker flow:" >&2
echo "  ./scripts/start.sh --deps-only" >&2
echo "  ./scripts/start.sh --app-only" >&2
echo "Or: ./scripts/start_web.sh" >&2
exit 1
