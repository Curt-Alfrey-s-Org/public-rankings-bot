#!/usr/bin/env bash
# Start Rankings Bot: main stack (postgres, redis, api, celery) then nginx.
# Removes any existing probilliards-nginx container before bringing up nginx
# so "container name already in use" never occurs.
#
# Usage: ./scripts/start-rankings-bot.sh
#   Or from home: /path/to/Rankings-Bot/scripts/start-rankings-bot.sh
# Use sudo if Docker needs it: sudo ./scripts/start-rankings-bot.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
NGINX_CONTAINER="probilliards-nginx"
# Tunnel container for this repository (cf-probilliards only)
TUNNEL_CONTAINER="cf-probilliards"
NETWORK="tunnel_network"

# Always use sudo for Docker so the script works without the user being in the docker group
DOCKER="sudo docker"

# Prefer Docker Compose V2 (see docs/UPGRADE_AND_VERSIONS.md)
COMPOSE_CMD=""
if $DOCKER compose version &>/dev/null 2>&1; then
  COMPOSE_CMD="$DOCKER compose"
elif command -v docker-compose &>/dev/null 2>&1; then
  COMPOSE_CMD="sudo docker-compose"
fi

if [ -z "$COMPOSE_CMD" ]; then
  echo "ERROR: 'docker compose' (V2) or docker-compose not found. See docs/UPGRADE_AND_VERSIONS.md."
  exit 1
fi

cd "$APP_ROOT"

# Ensure tunnel_network exists (required by main compose and nginx)
if ! $DOCKER network inspect "$NETWORK" &>/dev/null; then
  echo "Creating network $NETWORK..."
  $DOCKER network create "$NETWORK" || true
fi

# If build context (Dockerfile, requirements) changed since last build, prompt to rebuild
BUILD_HASH_FILE="$APP_ROOT/.docker-build-hash"
REBUILD_BEFORE_START=0
if [ -x "$APP_ROOT/scripts/docker_build_hash.sh" ]; then
  CURRENT_HASH="$("$APP_ROOT/scripts/docker_build_hash.sh" 2>/dev/null || true)"
  if [ -n "$CURRENT_HASH" ] && [ "$CURRENT_HASH" != "unknown" ]; then
    if [ -f "$BUILD_HASH_FILE" ]; then
      STORED_HASH="$(cat "$BUILD_HASH_FILE" 2>/dev/null)"
      if [ "$CURRENT_HASH" != "$STORED_HASH" ]; then
        if [ -t 0 ]; then
          echo "Image definition has changed (Dockerfile or requirements). Rebuild before start? (y/n)"
          read -r REPLY
          case "$REPLY" in
            y|Y|yes|YES) REBUILD_BEFORE_START=1 ;;
            *) echo "Starting without rebuild (image may be outdated)." ;;
          esac
        else
          echo "NOTE: Image definition changed; run ./scripts/full_deploy.sh or rebuild manually to pick up changes."
        fi
      fi
    fi
  fi
fi
COMPOSE_FILE="$APP_ROOT/docker-compose.yml"
[ -f "$APP_ROOT/production/docker-compose.prod.yml" ] && COMPOSE_FILE="$APP_ROOT/production/docker-compose.prod.yml"
ENV_FILE="$APP_ROOT/.env"
COMPOSE_ENV_ARGS=""
[ -f "$ENV_FILE" ] && COMPOSE_ENV_ARGS="--env-file $ENV_FILE"

if [ "$REBUILD_BEFORE_START" -eq 1 ]; then
  echo "Rebuilding API image..."
  (cd "$APP_ROOT" && $COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$COMPOSE_FILE" build rankings-bot-api) || true
  [ -n "$CURRENT_HASH" ] && echo "$CURRENT_HASH" > "$BUILD_HASH_FILE"
  echo "Image rebuilt. Starting containers..."
fi

echo "🚀 Starting Rankings Bot..."
echo "Starting main services..."
(cd "$APP_ROOT" && $COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$COMPOSE_FILE" up -d) || { echo "ERROR: Main services failed."; exit 1; }
echo ""

echo "Starting nginx reverse proxy..."
# Remove any existing nginx container so compose can create it (avoids "name already in use")
$DOCKER stop "$NGINX_CONTAINER" 2>/dev/null || true
$DOCKER rm "$NGINX_CONTAINER" 2>/dev/null || true
if [ -f "$APP_ROOT/nginx-config/docker-compose.nginx.yml" ]; then
  (cd "$APP_ROOT/nginx-config" && $COMPOSE_CMD -f docker-compose.nginx.yml up -d) || { echo "ERROR: Nginx failed."; exit 1; }
else
  echo "WARN: nginx-config/docker-compose.nginx.yml not found; skipping nginx."
fi

# Optional: start tunnel if it exists (so public URL works)
if $DOCKER ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${TUNNEL_CONTAINER}$"; then
  STATE=$($DOCKER inspect -f '{{.State.Status}}' "$TUNNEL_CONTAINER" 2>/dev/null || true)
  if [ "$STATE" != "running" ]; then
    $DOCKER start "$TUNNEL_CONTAINER" 2>/dev/null || true
  fi
  if ! $DOCKER inspect "$TUNNEL_CONTAINER" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null | grep -q "$NETWORK"; then
    $DOCKER network connect "$NETWORK" "$TUNNEL_CONTAINER" 2>/dev/null || true
  fi
fi

echo "✅ Rankings Bot started (main services + nginx)."
