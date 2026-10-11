#!/usr/bin/env bash
# Start all Rankings Bot components in order: network → API → nginx → tunnel.
# Logs to rankings-bot-start.log; on failure logs ERROR and exits.
# Usage: cd /home/ansible/rankings-bot/Rankings-Bot && ./scripts/start_rankings_bot_all.sh
# Use sudo if Docker commands fail: sudo ./scripts/start_rankings_bot_all.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG="$APP_ROOT/rankings-bot-start.log"
NGINX_CONTAINER="probilliards-nginx"
# Tunnel container for this repository (cf-probilliards only)
TUNNEL_CONTAINER="cf-probilliards"
NETWORK="tunnel_network"
API_PORT="${API_PORT:-8003}"

# Always use sudo for Docker so the script works without the user being in the docker group
DOCKER="sudo docker"

log() { echo "$(date '+%Y-%m-%d %H:%T') $*" | tee -a "$LOG"; }
err() { echo "$(date '+%Y-%m-%d %H:%T') ERROR: $*" | tee -a "$LOG"; }

cd "$APP_ROOT"
: > "$LOG"
log "=== Starting Rankings Bot (network, API, nginx, tunnel) ==="
log ""

# Step 1: Ensure tunnel_network exists
log "Step 1: Docker network $NETWORK"
if $DOCKER network inspect "$NETWORK" &>/dev/null; then
  log "Step 1: OK (network exists)."
else
  if $DOCKER network create "$NETWORK" >> "$LOG" 2>&1; then
    log "Step 1: OK (network created)."
  else
    err "Step 1: Failed to create network $NETWORK."
    exit 1
  fi
fi
log ""

# Step 1.5: Start Postgres (and Redis) so API has a DB
log "Step 1.5: Postgres (and Redis)"
# Prefer Docker Compose V2 (see docs/UPGRADE_AND_VERSIONS.md)
COMPOSE_CMD=""
if $DOCKER compose version &>/dev/null 2>&1; then
  COMPOSE_CMD="$DOCKER compose"
elif command -v docker-compose &>/dev/null; then
  COMPOSE_CMD="sudo docker-compose"
fi
if [ -n "$COMPOSE_CMD" ] && [ -f "$APP_ROOT/docker-compose.yml" ]; then
  (cd "$APP_ROOT" && $COMPOSE_CMD up -d postgres redis) >> "$LOG" 2>&1 || true
  log "   Waiting for Postgres to be ready..."
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if $DOCKER exec rankings-bot-postgres pg_isready -U rankings -d rankings &>/dev/null 2>&1; then
      log "Step 1.5: OK (Postgres ready)."
      break
    fi
    sleep 2
    [ "$i" -eq 10 ] && { err "Step 1.5: Postgres did not become ready."; exit 1; }
  done
else
  log "Step 1.5: Skip (no 'docker compose' / docker-compose or docker-compose.yml). Ensure Postgres is running and DATABASE_URL is set."
fi
log ""

# Step 2: Start host API on 8003
log "Step 2: Host API (port $API_PORT)"
if ! [ -d "venv" ]; then
  err "Step 2: venv not found. Run from project root after setup (e.g. start_website_server.sh once)."
  exit 1
fi
./scripts/restart_api.sh >> "$LOG" 2>&1
log "   Waiting for API health..."
for i in 1 2 3 4 5 6 7 8 9 10; do
  sleep 3
  CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://127.0.0.1:$API_PORT/api/health" 2>/dev/null || echo "000")
  if [ "$CODE" = "200" ]; then
    log "Step 2: OK (API health 200)."
    break
  fi
  [ "$i" -eq 10 ] && { err "Step 2: API health check failed (got $CODE). Check rankings-api.log."; exit 1; }
done
log ""

# Step 3: probilliards-nginx running and on tunnel_network
log "Step 3: Container $NGINX_CONTAINER"
if $DOCKER ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${NGINX_CONTAINER}$"; then
  STATE=$($DOCKER inspect -f '{{.State.Status}}' "$NGINX_CONTAINER" 2>/dev/null || true)
  if [ "$STATE" != "running" ]; then
    if $DOCKER start "$NGINX_CONTAINER" >> "$LOG" 2>&1; then
      log "Step 3: Started $NGINX_CONTAINER."
    else
      err "Step 3: Failed to start $NGINX_CONTAINER."
      exit 1
    fi
  fi
  if ! $DOCKER inspect "$NGINX_CONTAINER" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null | grep -q "$NETWORK"; then
    if $DOCKER network connect "$NETWORK" "$NGINX_CONTAINER" >> "$LOG" 2>&1; then
      log "Step 3: Connected $NGINX_CONTAINER to $NETWORK."
    else
      err "Step 3: Failed to connect $NGINX_CONTAINER to $NETWORK."
      exit 1
    fi
  fi
  log "Step 3: OK ($NGINX_CONTAINER running, on $NETWORK)."
else
  # Create via compose if available (prefer V2)
  if [ -f "$APP_ROOT/nginx-config/docker-compose.nginx.yml" ]; then
    if [ -z "$COMPOSE_CMD" ]; then
      if $DOCKER compose version &>/dev/null 2>&1; then
        COMPOSE_CMD="$DOCKER compose"
      elif command -v docker-compose &>/dev/null; then
        COMPOSE_CMD="sudo docker-compose"
      fi
    fi
    if [ -n "$COMPOSE_CMD" ]; then
    # Remove any existing nginx container so compose can create it (avoids "name already in use")
    $DOCKER stop "$NGINX_CONTAINER" 2>/dev/null || true
    $DOCKER rm "$NGINX_CONTAINER" 2>/dev/null || true
    (cd "$APP_ROOT/nginx-config" && $COMPOSE_CMD -f docker-compose.nginx.yml up -d) >> "$LOG" 2>&1 || true
    if $DOCKER ps --format '{{.Names}}' 2>/dev/null | grep -q "^${NGINX_CONTAINER}$"; then
      log "Step 3: OK (created and started via compose)."
    else
      err "Step 3: Container $NGINX_CONTAINER not found. Create it (see nginx-config/README.md)."
      exit 1
    fi
    else
      err "Step 3: Container $NGINX_CONTAINER not found (no docker compose?). See nginx-config/README.md."
      exit 1
    fi
  else
    err "Step 3: Container $NGINX_CONTAINER not found. Create it (see nginx-config/README.md)."
    exit 1
  fi
fi
log ""

# Step 4: Tunnel cf-probilliards running and on tunnel_network
log "Step 4: Tunnel $TUNNEL_CONTAINER"
if $DOCKER ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${TUNNEL_CONTAINER}$"; then
  STATE=$($DOCKER inspect -f '{{.State.Status}}' "$TUNNEL_CONTAINER" 2>/dev/null || true)
  if [ "$STATE" != "running" ]; then
    if $DOCKER start "$TUNNEL_CONTAINER" >> "$LOG" 2>&1; then
      log "Step 4: Started $TUNNEL_CONTAINER."
    else
      err "Step 4: Failed to start $TUNNEL_CONTAINER (tunnel may be managed elsewhere)."
      exit 1
    fi
  fi
  if ! $DOCKER inspect "$TUNNEL_CONTAINER" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null | grep -q "$NETWORK"; then
    if $DOCKER network connect "$NETWORK" "$TUNNEL_CONTAINER" >> "$LOG" 2>&1; then
      log "Step 4: Connected $TUNNEL_CONTAINER to $NETWORK."
    else
      err "Step 4: Failed to connect $TUNNEL_CONTAINER to $NETWORK."
      exit 1
    fi
  fi
  log "Step 4: OK ($TUNNEL_CONTAINER running, on $NETWORK)."
else
  err "Step 4: Tunnel container $TUNNEL_CONTAINER not found. Create/start it separately (e.g. Cloudflare tunnel)."
  exit 1
fi
log ""

log "=== All components started. Log: $LOG ==="
log "Site: https://www.probilliardssoftware.com/"
