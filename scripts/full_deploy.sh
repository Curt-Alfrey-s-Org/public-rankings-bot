#!/bin/sh
# Full deploy: rebuild frontend + API (Docker Compose), then nginx, tunnel, UFW, and verification.
# Builds frontend via scripts/build_frontend_with_docker.sh (ephemeral Node image) so production bind-mount
# of frontend/dist serves the latest site,
# then rebuilds images and brings up the stack. When using Docker, ensures tunnel_network (and optionally
# rankings-bot-network) exist before compose up; when using production compose, ensures Postgres is up
# before starting the app stack. Waits for API health before proceeding to nginx.
# When REBUILD_WEBSITE_LOG is set (e.g. by the admin "Update Website" button), output is appended for live streaming.
#
# Modules brought online (Docker path):
#   - tunnel_network, rankings-bot-network (created if missing)
#   - Postgres (from docker-compose.yml when using production compose; Docker-network-only, no host port)
#   - Redis, rankings-bot-api, celery-worker (from production or main compose)
#   - probilliards-nginx (Part B)
#   - Cloudflare tunnel (Part B; default cf-probilliards, create if missing when TUNNEL_TOKEN set)
#
# Preconditions: Docker and compose available. Frontend is built only via scripts/build_frontend_with_docker.sh
# (Docker Node image). Host npm is not used.
# .env with JWT_SECRET, DATABASE_URL (see docs/PRODUCTION_READINESS.md).
# Optional: restore-docker-networks.sh for full network pattern; UFW active for step 5.
#
# Disk space (optional): ./scripts/cleanup_docker_disk.sh — df + Docker build-cache prune (see script for
# CLEANUP_DOCKER_AGGRESSIVE, CLEANUP_DOCKER_IMAGES, --all-images). Before compose image build, full_deploy can
# run it when RUN_DOCKER_CLEANUP_BEFORE_BUILD=1 (always) or =auto (only if / is ≥85% used or ≤2GiB free).
#
# Usage:
#   ./scripts/full_deploy.sh                      # Smart Docker deploy; prompts production or maintenance
#   ./scripts/full_deploy.sh --production         # Deploy and set www to live app (no prompt)
#   ./scripts/full_deploy.sh --maintenance       # Deploy and set www to maintenance page (no prompt)
#   ./scripts/full_deploy.sh --no-cache          # Force full rebuild (bypasses auto-detection)
#   ./scripts/full_deploy.sh --rollback-on-failure  # On failure, run stop.sh to avoid orphan containers
#   ./scripts/full_deploy.sh --force-docker         # No-op (kept for backward compatibility)
#   DEPLOY_SITE_MODE=production ./scripts/full_deploy.sh  # Non-interactive: use production (or maintenance)
#   ./scripts/full_deploy.sh --production --verbose 2>&1 | tee full_deploy.log  # Verbose + log to file (tail -f full_deploy.log)
#
# Intelligent Caching:
# - Automatically detects when dependencies change (Dockerfile, requirements-*.txt)
# - Uses cached builds for speed when safe (typically 20-30s)
# - Forces full rebuild when dependencies change (typically 7-8 minutes)
# - Override with --no-cache if you know better than auto-detection
#
# Environment: When using Docker, .env in APP_ROOT is loaded for compose (JWT_SECRET, BOT_API_KEY, XAI_API_KEY, etc.).
# If .env is missing you get "variable not set" warnings; copy .env.example to .env and set values. See docs/PRODUCTION_READINESS.md.
#
# Intended for nightly maintenance (run once per day); build is long so full verbose logs are shown.
#
# Start under sh then re-exec with clean bash (no BASH_ENV/rc/profile) so the script runs
# flawlessly from any terminal that has broken bash completion (e.g. _parse_usage syntax errors).
if [ -z "${FULL_DEPLOY_CLEAN_RUN:-}" ]; then
  export BASH_ENV=
  export ENV=
  export FULL_DEPLOY_CLEAN_RUN=1
  exec /bin/bash --norc --noprofile "$0" "$@"
fi

set -e
# Ensure PATH so docker/compose/curl/sudo are findable when run from clean bash
export PATH="${PATH:-/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_ROOT"

# When called from the admin "Update Website" button, stream output to the rebuild log
if [ -n "${REBUILD_WEBSITE_LOG:-}" ]; then
  exec >> "$REBUILD_WEBSITE_LOG" 2>&1
fi

log() { echo "[$(date -u '+%H:%M:%S')] $*"; }
err() { echo "[$(date -u '+%H:%M:%S')] ERROR: $*"; }

ENV_FILE="$APP_ROOT/.env"
# Load TUNNEL_TOKEN and API_PORT from .env (value may contain = or special chars; avoid tr -d which corrupts)
if [ -f "$ENV_FILE" ]; then
  _tline=$(grep -E '^TUNNEL_TOKEN=' "$ENV_FILE" 2>/dev/null | head -1)
  [ -n "${_tline}" ] && export TUNNEL_TOKEN="${_tline#TUNNEL_TOKEN=}"
  _pline=$(grep -E '^API_PORT=' "$ENV_FILE" 2>/dev/null | head -1)
  if [ -n "${_pline}" ]; then
    _pval="${_pline#API_PORT=}"
    _pval="${_pval//[^0-9]/}"
    [ -n "${_pval}" ] && export API_PORT="${_pval}"
  fi
fi

# Load full env for DATABASE_URL and other settings used in migrations
if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

echo ""
log "Full deploy (rebuild all images and startup)"
echo ""

NO_CACHE=
ROLLBACK_ON_FAILURE=
SITE_MODE=
VERBOSE=
for arg in "$@"; do
  if [ "$arg" = "--no-docker" ]; then
    err "Docker is required. --no-docker is deprecated (single Docker flow)."
    exit 1
  fi
  # Backward compatibility: older docs/scripts passed --force-docker; deploy is Docker-only by default.
  [ "$arg" = "--force-docker" ] && :
  [ "$arg" = "--no-cache" ] && NO_CACHE=1
  [ "$arg" = "--rollback-on-failure" ] && ROLLBACK_ON_FAILURE=1
  [ "$arg" = "--production" ] && SITE_MODE=production
  [ "$arg" = "--maintenance" ] && SITE_MODE=maintenance
  [ "$arg" = "--verbose" ] && VERBOSE=1
done
[ -n "$VERBOSE" ] && set -x

# Production or maintenance: prompt if not set by flag or env (non-interactive → default production)
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
      p|production) SITE_MODE=production ;;
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
log "Site mode: $SITE_MODE (will apply after nginx is up)"
# Docker-only deployment (Compose is the single orchestrator for the app stack).
# On failure, run stop.sh to avoid orphan containers (optional; industry practice: opt-in rollback)
rollback_on_err() {
  _code=${1:-1}
  if [ -n "${ROLLBACK_ON_FAILURE:-}" ]; then
    err "Deploy failed. Running stop script to clean up..."
    "$SCRIPT_DIR/stop.sh" || true
  fi
  exit "$_code"
}
trap 'e=$?; rollback_on_err $e' ERR
BUILD_HASH_FILE="$APP_ROOT/.docker-build-hash"

NGINX_CONTAINER="probilliards-nginx"
# Tunnel container for this repository (cf-probilliards only)
TUNNEL_CONTAINER="cf-probilliards"
NETWORK="tunnel_network"
API_PORT="${API_PORT:-8003}"

activate_venv() {
  if [ -d "$APP_ROOT/.venv" ]; then
    . "$APP_ROOT/.venv/bin/activate"
    return 0
  fi
  if [ -d "$APP_ROOT/venv" ]; then
    . "$APP_ROOT/venv/bin/activate"
    return 0
  fi
  return 1
}

# Wait for container health check (polls Docker health status, not guessing time)
# Usage: wait_for_container_health <container_name> <timeout_seconds>
# Returns 0 if healthy, 1 if timeout
wait_for_container_health() {
  local container=$1
  local timeout=${2:-60}
  local elapsed=0
  local interval=2
  
  log "   Waiting for $container health (max ${timeout}s)..."
  while [ $elapsed -lt $timeout ]; do
    local status=$(sudo docker inspect "$container" --format='{{.State.Health.Status}}' 2>/dev/null || echo "none")
    if [ "$status" = "healthy" ]; then
      log "   ✅ $container healthy."
      return 0
    elif [ "$status" = "unhealthy" ]; then
      err "$container unhealthy (check: sudo docker logs $container)"
      return 1
    fi
    sleep $interval
    elapsed=$((elapsed + interval))
  done
  err "$container did not become healthy after ${timeout}s"
  return 1
}

# Wait for HTTP endpoint health (for host-based services without Docker health checks)
# Usage: wait_for_http_health <url> <timeout_seconds>
# Returns 0 if 200 OK, 1 if timeout
wait_for_http_health() {
  local url=$1
  local timeout=${2:-60}
  local elapsed=0
  local interval=2
  
  log "   Waiting for $url health (max ${timeout}s)..."
  while [ $elapsed -lt $timeout ]; do
    local code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 "$url" 2>/dev/null || echo "000")
    if [ "$code" = "200" ]; then
      log "   ✅ Endpoint healthy (HTTP $code)."
      return 0
    fi
    sleep $interval
    elapsed=$((elapsed + interval))
  done
  err "Endpoint did not return 200 OK after ${timeout}s"
  return 1
}

# Always use sudo for Docker so the script works without the user being in the docker group.
# Set DOCKER to "sudo docker" so every $DOCKER and "sudo $COMPOSE_CMD" works the same for all users.
DOCKER="sudo docker"
# Leave swarm if active so docker-compose works (we don't use swarm; swarm causes ContainerConfig errors)
if $DOCKER info 2>/dev/null | grep -q "Swarm: active"; then
  log "Leaving Docker swarm (this script uses compose, not swarm)..."
  $DOCKER swarm leave --force 2>/dev/null || true
fi

# Clean up potential container name conflicts before starting
log "Cleaning up potential container name conflicts..."
$DOCKER stop rankings-bot-api rankings-bot-postgres rankings-bot-redis rankings-bot-celery-worker probilliards-nginx cf-probilliards 2>/dev/null || true
$DOCKER rm rankings-bot-api rankings-bot-postgres rankings-bot-redis rankings-bot-celery-worker probilliards-nginx cf-probilliards 2>/dev/null || true

# Clean up processes using required ports
log "Cleaning up processes using required ports..."
# Kill any processes using port 8003 (API)
if command -v fuser &>/dev/null; then
  fuser -k 8003/tcp 2>/dev/null || true
elif command -v lsof &>/dev/null; then
  lsof -ti:8003 | xargs kill -9 2>/dev/null || true
fi
# Postgres is Docker-network-only (no host port); no port cleanup needed
# Prefer Docker Compose V2 (docker compose); required for Docker path with newer Docker daemon (see docs/UPGRADE_AND_VERSIONS.md)
if $DOCKER compose version &>/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
else
  COMPOSE_CMD=""
fi
echo "=========================================="
echo "  Rankings Bot — Full deploy"
echo "=========================================="
echo "App root: $APP_ROOT"
echo ""

# ---------------------------------------------------------------------------
# Part A: Frontend + API (Docker only - single flow)
# ---------------------------------------------------------------------------
if ! command -v docker &>/dev/null; then
  err "Docker not found. Docker is required (single flow)."
  exit 1
fi
  COMPOSE_FILE="$APP_ROOT/docker-compose.yml"
  if [ -f "$APP_ROOT/production/docker-compose.prod.yml" ]; then
    COMPOSE_FILE="$APP_ROOT/production/docker-compose.prod.yml"
    log "Using production compose."
  fi
  # Load .env for compose variable substitution (avoids "variable is not set. Defaulting to a blank string").
  ENV_FILE="$APP_ROOT/.env"
  if [ -f "$ENV_FILE" ]; then
    COMPOSE_ENV_ARGS="--env-file $ENV_FILE"
  else
    COMPOSE_ENV_ARGS=""
    log "   ⚠ No $ENV_FILE found; compose may show 'variable not set' for JWT_SECRET, BOT_API_KEY, XAI_API_KEY. Copy .env.example to .env and set values."
  fi
  # shellcheck disable=SC1091
  . "$SCRIPT_DIR/export_compose_uid_gid.sh"
  write_compose_host_user_env "$APP_ROOT"
  if [ -n "$COMPOSE_ENV_ARGS" ]; then
    COMPOSE_ENV_ARGS="$COMPOSE_ENV_ARGS --env-file $APP_ROOT/.env.compose-host-user"
  else
    COMPOSE_ENV_ARGS="--env-file $APP_ROOT/.env.compose-host-user"
  fi

  # Same fingerprint as API image (BUILD_HASH); optional embed in frontend for stale/split-deploy detection
  CURRENT_HASH=""
  [ -x "$APP_ROOT/scripts/docker_build_hash.sh" ] && CURRENT_HASH="$("$APP_ROOT/scripts/docker_build_hash.sh" 2>/dev/null || true)"
  if [ -n "$CURRENT_HASH" ] && [ "$CURRENT_HASH" != "unknown" ] && [ -d "$APP_ROOT/frontend" ]; then
    export VITE_API_BUILD_HASH="${VITE_API_BUILD_HASH:-$CURRENT_HASH}"
    log "   Frontend build will embed VITE_API_BUILD_HASH (must match API /api/app-version build_hash)."
  fi

  # FULL DEPLOY: build frontend for production mount (../frontend/dist) — Docker Node only.
  if [ -d "$APP_ROOT/frontend" ]; then
    if [ ! -f "$APP_ROOT/frontend/package.json" ]; then
      err "frontend/package.json not found. Cannot build frontend."
      exit 1
    fi
    if [ -x "$SCRIPT_DIR/clean_frontend_dist.sh" ]; then
      "$SCRIPT_DIR/clean_frontend_dist.sh"
    fi
    if [ ! -f "$SCRIPT_DIR/build_frontend_with_docker.sh" ]; then
      err "scripts/build_frontend_with_docker.sh missing (Docker-only frontend build)."
      exit 1
    fi
    if ! command -v docker &>/dev/null; then
      err "Docker is required to build the frontend (host npm is not supported)."
      exit 1
    fi
    log "1. Building frontend via Docker Node container..."
    bash "$SCRIPT_DIR/build_frontend_with_docker.sh" "$APP_ROOT" || { err "Frontend build failed."; exit 1; }
    log "   ✅ frontend/dist ready."
  else
    log "1. Skipping frontend build (no frontend/ directory)."
  fi

  # BuildKit: intelligent layering, cache mounts, parallel stages (Docker docs)
  export DOCKER_BUILDKIT=1
  export BUILDKIT_PROGRESS=plain
  BUILD_TIMEOUT=900
  if command -v timeout &>/dev/null 2>&1; then
    BUILD_PREFIX="timeout $BUILD_TIMEOUT"
  else
    BUILD_PREFIX=""
  fi
  # CURRENT_HASH was computed before the frontend build (same value passed as API BUILD_HASH below)

  NEED_BUILD=1
  if [ -n "$CURRENT_HASH" ] && [ "$CURRENT_HASH" != "unknown" ] && [ -f "$BUILD_HASH_FILE" ]; then
    STORED_HASH="$(cat "$BUILD_HASH_FILE" 2>/dev/null)"
    if [ "$CURRENT_HASH" = "$STORED_HASH" ]; then
      NEED_BUILD=0
      log "   ✓ Build context unchanged - using cached images"
    fi
  fi

  if [ "$NEED_BUILD" -eq 1 ]; then
    # Optional: prune Docker build cache before heavy compose build (opt-in only; default off)
    _docleanup=0
    case "${RUN_DOCKER_CLEANUP_BEFORE_BUILD:-}" in
      1|yes|true|YES|TRUE) _docleanup=1 ;;
      auto)
        _u=$(df -Pk / 2>/dev/null | awk 'NR==2 {gsub(/%/,"",$5); print $5}')
        _a=$(df -Pk / 2>/dev/null | awk 'NR==2 {print $4}')
        if [ -n "${_u:-}" ] && [ "${_u:-0}" -ge 85 ] 2>/dev/null; then _docleanup=1; fi
        if [ -n "${_a:-}" ] && [ "${_a:-999999999}" -le $((2 * 1024 * 1024)) ] 2>/dev/null; then _docleanup=1; fi
        ;;
    esac
    if [ "$_docleanup" -eq 1 ] && [ -x "$SCRIPT_DIR/cleanup_docker_disk.sh" ]; then
      log "2-pre. Disk/Docker cleanup before image build (RUN_DOCKER_CLEANUP_BEFORE_BUILD=${RUN_DOCKER_CLEANUP_BEFORE_BUILD})..."
      "$SCRIPT_DIR/cleanup_docker_disk.sh" || log "   ⚠ cleanup_docker_disk.sh exited non-zero; continuing"
    fi
    # Use --no-cache only when user requests; otherwise Docker layer cache handles deps vs app
    if [ -n "$NO_CACHE" ]; then
      log "2. 🔄 FULL REBUILD: --no-cache (user requested)"
      BUILD_ARGS="--no-cache"
    else
      log "2. 🚀 FAST BUILD: Docker layer cache (deps layer reused when only app changed)"
      BUILD_ARGS=""
    fi

    # Pass build hash into the image (OCI label + /app/.build-hash) for runtime verification
    if [ -n "$CURRENT_HASH" ] && [ "$CURRENT_HASH" != "unknown" ]; then
      BUILD_ARGS="$BUILD_ARGS --build-arg BUILD_HASH=$CURRENT_HASH"
    fi

    (cd "$APP_ROOT" && $BUILD_PREFIX sudo env DOCKER_BUILDKIT=1 BUILDKIT_PROGRESS=plain $COMPOSE_CMD $COMPOSE_ENV_ARGS -f "$COMPOSE_FILE" build $BUILD_ARGS) || { err "Docker image build failed."; exit 1; }

    # Update hash only after successful build
    if [ -n "$CURRENT_HASH" ] && [ "$CURRENT_HASH" != "unknown" ]; then
      echo "$CURRENT_HASH" > "$BUILD_HASH_FILE"
      log "   Build hash updated: $CURRENT_HASH"
    fi
  fi
  # Ensure external networks exist before compose up (prod/main use tunnel_network: external)
  log "2a. Ensuring Docker networks..."
  $DOCKER network inspect "$NETWORK" &>/dev/null || $DOCKER network create "$NETWORK" 2>/dev/null || true
  $DOCKER network inspect rankings-bot-network &>/dev/null || $DOCKER network create rankings-bot-network 2>/dev/null || true
  log "3. Restarting app containers (single production compose)..."
  (cd "$APP_ROOT" && sudo $COMPOSE_CMD $COMPOSE_ENV_ARGS -f production/docker-compose.prod.yml down -t 2) || true
  UP_TIMEOUT=120
  log "   Bringing up production stack (postgres + redis + API + celery + monitoring)..."
  if command -v timeout &>/dev/null 2>&1; then
    (cd "$APP_ROOT" && timeout $UP_TIMEOUT sudo $COMPOSE_CMD $COMPOSE_ENV_ARGS -f production/docker-compose.prod.yml up -d --force-recreate) || { err "Compose up failed."; exit 1; }
  else
    (cd "$APP_ROOT" && sudo $COMPOSE_CMD $COMPOSE_ENV_ARGS -f production/docker-compose.prod.yml up -d --force-recreate) || { err "Compose up failed."; exit 1; }
  fi
  log "   Waiting for Postgres health..."
  wait_for_container_health "rankings-bot-postgres" 30 || { err "Postgres health check timeout."; exit 1; }
  log "   ✅ App stack up."

  log "2bb. Applying database migrations (container)..."
  if $DOCKER ps --format '{{.Names}}' | grep -q "^rankings-bot-api$"; then
    $DOCKER exec rankings-bot-api python -m alembic upgrade head || { err "Alembic migrations failed in container."; exit 1; }
  else
    err "rankings-bot-api container not running; cannot apply migrations."
    exit 1
  fi
  # Wait for API health using Docker health check (respects docker-compose healthcheck config)
  log "2c. Waiting for API health..."
  wait_for_container_health "rankings-bot-api" 60 || { err "API health check timeout."; exit 1; }
  # Apply standard network pattern (rankings-bot-network + tunnel_network).
  # IMPORTANT: restore script must only connect networks; it must NOT stop or restart rankings-bot-api (or the API may exit and cause Bad Gateway).
  RESTORE_SCRIPT="${HOME:-/home/ansible}/scripts/restore-docker-networks.sh"
  if [ -x "$RESTORE_SCRIPT" ]; then
    log "2d. Restore Docker networks (private + tunnel)..."
    (sudo "$RESTORE_SCRIPT" 2>/dev/null) || true
  fi

echo ""

# ---------------------------------------------------------------------------
# Part B: Nginx, network, UFW, verify, tunnel (from rebuild_and_start_all.sh)
# ---------------------------------------------------------------------------
# Doc refs (AI / maintainers): docs/NETWORKING_DOC_HOOKS.md (nginx compose + ports);
#   docs/PORT_MANAGEMENT.md; docs/PRODUCTION_DEPLOYMENT.md; docs/BAD_GATEWAY_TROUBLESHOOTING.md
# Part B requires Docker for nginx container and tunnel
if [ -z "$COMPOSE_CMD" ] || ! command -v docker &>/dev/null; then
  err "Part B (nginx, tunnel) requires Docker. Install Docker or run from a host with Docker."
  exit 1
fi
log "4. Rebuild nginx image and container..."
if [ -n "$COMPOSE_CMD" ] && [ -f "nginx-config/docker-compose.nginx.yml" ]; then
  export DOCKER_BUILDKIT=1
  export BUILDKIT_PROGRESS=plain
  NGINX_BUILD_TIMEOUT=300
  NGINX_UP_TIMEOUT=60
  NGINX_BUILD_ARGS=""
  [ -n "$NO_CACHE" ] && NGINX_BUILD_ARGS=""
  if command -v timeout &>/dev/null 2>&1; then
    (cd "$APP_ROOT/nginx-config" && timeout $NGINX_BUILD_TIMEOUT sudo env DOCKER_BUILDKIT=1 BUILDKIT_PROGRESS=plain $COMPOSE_CMD -f docker-compose.nginx.yml build $NGINX_BUILD_ARGS) || { err "Nginx image build failed."; exit 1; }
  else
    (cd "$APP_ROOT/nginx-config" && sudo env DOCKER_BUILDKIT=1 BUILDKIT_PROGRESS=plain $COMPOSE_CMD -f docker-compose.nginx.yml build $NGINX_BUILD_ARGS) || { err "Nginx image build failed."; exit 1; }
  fi
  if ! $DOCKER network inspect "$NETWORK" &>/dev/null; then
    $DOCKER network create "$NETWORK" || true
  fi
  # Ensure private network exists (standard pattern: API + DB on private, API also on tunnel)
  $DOCKER network inspect rankings-bot-network &>/dev/null || $DOCKER network create rankings-bot-network 2>/dev/null || true
  $DOCKER stop "$NGINX_CONTAINER" 2>/dev/null || true
  $DOCKER rm "$NGINX_CONTAINER" 2>/dev/null || true
  if command -v timeout &>/dev/null 2>&1; then
    (cd "$APP_ROOT/nginx-config" && timeout $NGINX_UP_TIMEOUT sudo $COMPOSE_CMD -f docker-compose.nginx.yml up -d) || { err "Nginx container failed (or timed out)."; exit 1; }
  else
    (cd "$APP_ROOT/nginx-config" && sudo $COMPOSE_CMD -f docker-compose.nginx.yml up -d) || { err "Nginx container failed."; exit 1; }
  fi
  if $DOCKER ps --format '{{.Names}}' 2>/dev/null | grep -q "^${NGINX_CONTAINER}$"; then
    if ! $DOCKER inspect "$NGINX_CONTAINER" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null | grep -q "$NETWORK"; then
      $DOCKER network connect "$NETWORK" "$NGINX_CONTAINER" 2>/dev/null || true
    fi
    log "   ✅ $NGINX_CONTAINER running, on $NETWORK."
  else
    err "Nginx container not running."
    exit 1
  fi
else
  log "   Skip (no docker-compose or nginx-config)."
fi
echo ""

log "5. Firewall (UFW) allow Docker/tunnel → port $API_PORT"
if command -v ufw &>/dev/null && sudo ufw status 2>/dev/null | grep -q "Status: active"; then
  SUBNETS="172.17.0.0/16"
  if $DOCKER network inspect "$NETWORK" &>/dev/null 2>&1; then
    TUNNEL_SUBNET=$($DOCKER network inspect "$NETWORK" --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null | head -1)
    [ -n "$TUNNEL_SUBNET" ] && SUBNETS="$SUBNETS $TUNNEL_SUBNET"
  fi
  for sub in $SUBNETS; do
    sudo ufw allow from "$sub" to any port "$API_PORT" comment "Rankings bot API from Docker/tunnel" 2>/dev/null || true
  done
  log "   ✅ UFW rules ensured."
else
  log "   Skip (UFW not active or not installed)."
fi
echo ""

log "6. Verify nginx → API ($API_PORT)"
if $DOCKER ps --format '{{.Names}}' 2>/dev/null | grep -q "^${NGINX_CONTAINER}$"; then
  CODE=""
  # Retry until nginx can reach the API (DNS inside the bridge can take a moment; no fixed sleep before first try)
  for i in 1 2 3 4 5 6 7 8 9 10; do
    [ "$i" -gt 1 ] && sleep 3
    # Prefer container name (standard: nginx and API on tunnel_network)
    CODE=$($DOCKER exec "$NGINX_CONTAINER" curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 "http://rankings-bot-api:$API_PORT/api/health" 2>/dev/null || echo "")
    if [ "$CODE" = "200" ]; then
      log "   ✅ Nginx can reach API (rankings-bot-api:$API_PORT)."
      break
    fi
    if [ "$i" -eq 10 ]; then
      err "Nginx cannot reach API after 10 attempts. Run: sudo ./scripts/diagnose_rankings_bot_gateway.sh"
      exit 1
    fi
  done
else
  log "   Skip (nginx container not running)."
fi
echo ""

# 6b. Apply production/maintenance choice (switch nginx config so www shows live app or maintenance page)
if [ -n "${SITE_MODE:-}" ] && $DOCKER ps --format '{{.Names}}' 2>/dev/null | grep -q "^${NGINX_CONTAINER}$"; then
  case "$SITE_MODE" in
    production) NGINX_SITE_CONFIG="production.conf" ;;
    maintenance) NGINX_SITE_CONFIG="maintenance.conf" ;;
    *) NGINX_SITE_CONFIG="production.conf" ;;
  esac
  log "6b. Switching www to $SITE_MODE ($NGINX_SITE_CONFIG)..."
  $DOCKER exec "$NGINX_CONTAINER" cp "/etc/nginx/templates/${NGINX_SITE_CONFIG}" /etc/nginx/conf.d/default.conf
  $DOCKER exec "$NGINX_CONTAINER" nginx -s reload
  log "   ✅ www now in $SITE_MODE mode."
fi
echo ""

log "7. Tunnel $TUNNEL_CONTAINER (site reachable via domain when running)"
TUNNEL_IMAGE="cloudflare/cloudflared:latest"
if $DOCKER ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${TUNNEL_CONTAINER}$"; then
  $DOCKER start "$TUNNEL_CONTAINER" 2>/dev/null || true
  if ! $DOCKER inspect "$TUNNEL_CONTAINER" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null | grep -q "$NETWORK"; then
    $DOCKER network connect "$NETWORK" "$TUNNEL_CONTAINER" 2>/dev/null || true
  fi
else
  if [ -n "${TUNNEL_TOKEN:-}" ]; then
    log "   Creating tunnel container $TUNNEL_CONTAINER (TUNNEL_TOKEN from .env)..."
    $DOCKER network inspect "$NETWORK" &>/dev/null || $DOCKER network create "$NETWORK" 2>/dev/null || true
    $DOCKER run -d \
      --name "$TUNNEL_CONTAINER" \
      --restart unless-stopped \
      --network "$NETWORK" \
      -e TUNNEL_TOKEN="${TUNNEL_TOKEN}" \
      "$TUNNEL_IMAGE" \
      tunnel --no-autoupdate run --token "${TUNNEL_TOKEN}" || { err "Tunnel container creation failed."; exit 1; }
  else
    log "   ⚠️  Tunnel container not found and TUNNEL_TOKEN not set in .env — skipping."
    log "   To make the site reachable at the domain, add TUNNEL_TOKEN to .env and run: ./scripts/start_cf_probilliards.sh"
  fi
fi
# Verify tunnel is running (only fail if we attempted creation)
if $DOCKER ps --format '{{.Names}}' 2>/dev/null | grep -q "^${TUNNEL_CONTAINER}$"; then
  log "   ✅ $TUNNEL_CONTAINER running, on $NETWORK."
elif [ -n "${TUNNEL_TOKEN:-}" ]; then
  err "Tunnel $TUNNEL_CONTAINER failed to start. Check: sudo docker logs $TUNNEL_CONTAINER"
  exit 1
else
  log "   ⚠️  Tunnel not running (add TUNNEL_TOKEN to .env and run ./scripts/start_cf_probilliards.sh for domain access)."
fi
echo ""

# Post-deploy verification: ensure API is reachable AND running the image we just built.
log "8. Post-deploy verification (API reachable + build hash match)..."
if ! wait_for_http_health "http://127.0.0.1:${API_PORT}/api/health" 90; then
  err "API did not return HTTP 200 on host loopback. Check: sudo docker logs rankings-bot-api"
  exit 1
fi
HOST_CODE="000"
HEALTH_JSON=""
if command -v curl &>/dev/null; then
  HEALTH_JSON=$(curl -s --connect-timeout 5 "http://127.0.0.1:$API_PORT/api/health" 2>/dev/null || echo "")
  HOST_CODE=$(echo "$HEALTH_JSON" | python3 -c "import sys; sys.exit(0)" 2>/dev/null && echo "200" || echo "000")
  [ -z "$HOST_CODE" ] || HOST_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://127.0.0.1:$API_PORT/api/health" 2>/dev/null || echo "000")
fi
NGINX_CODE="000"
if $DOCKER ps --format '{{.Names}}' 2>/dev/null | grep -q "^${NGINX_CONTAINER}$"; then
  NGINX_CODE=$($DOCKER exec "$NGINX_CONTAINER" curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://rankings-bot-api:$API_PORT/api/health" 2>/dev/null || echo "000")
  [ -z "$HEALTH_JSON" ] && HEALTH_JSON=$($DOCKER exec "$NGINX_CONTAINER" curl -s --connect-timeout 5 "http://rankings-bot-api:$API_PORT/api/health" 2>/dev/null || echo "")
fi
if [ "$NGINX_CODE" = "200" ] || [ "$HOST_CODE" = "200" ]; then
  log "   ✅ Post-deploy OK: API reachable (host=$HOST_CODE nginx=$NGINX_CODE)."
else
  err "Post-deploy verification failed: host=$HOST_CODE nginx→API=$NGINX_CODE. Site may show Bad Gateway. Run: sudo ./scripts/diagnose_rankings_bot_gateway.sh"
  err "Start API with: cd $APP_ROOT && sudo $COMPOSE_CMD $COMPOSE_ENV_ARGS -f production/docker-compose.prod.yml up -d rankings-bot-api"
  exit 1
fi

# Build hash verification: the running container MUST serve the hash we just built.
if [ -n "$CURRENT_HASH" ] && [ "$CURRENT_HASH" != "unknown" ] && [ -n "$HEALTH_JSON" ]; then
  RUNNING_HASH=$(echo "$HEALTH_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('build_hash',''))" 2>/dev/null || echo "")
  if [ "$RUNNING_HASH" = "$CURRENT_HASH" ]; then
    log "   ✅ Build hash verified: running container matches built image ($CURRENT_HASH)."
  elif [ -z "$RUNNING_HASH" ] || [ "$RUNNING_HASH" = "unknown" ]; then
    log "   ⚠  Build hash not yet in running image (first deploy with hash support). Will verify on next deploy."
  else
    err "BUILD HASH MISMATCH: expected=$CURRENT_HASH running=$RUNNING_HASH"
    err "The running API container is serving stale code. Force-recreate: sudo $COMPOSE_CMD $COMPOSE_ENV_ARGS -f production/docker-compose.prod.yml up -d --force-recreate rankings-bot-api"
    exit 1
  fi
fi
echo ""

if [ "${SKIP_TOURNAMENT_SMOKE:-0}" != "1" ]; then
  log "9. Tournament wizard smoke tests..."
  bash "$SCRIPT_DIR/smoke_test_tournament_wizard.sh" || { err "Tournament wizard smoke failed."; exit 1; }
  echo ""
fi

echo "Done in full_deploy. Open the site and hard-refresh (Ctrl+Shift+R) or use incognito to see updates."

# Verbose: show tunnel and nginx logs (last 30 lines each) for debugging 404/405
if [ -n "${VERBOSE:-}" ]; then
  echo ""
  log "=== Verbose: tunnel logs (last 30 lines) ==="
  $DOCKER logs "$TUNNEL_CONTAINER" --tail 30 2>&1 || true
  echo ""
  log "=== Verbose: nginx access log (last 20 lines) ==="
  $DOCKER exec "$NGINX_CONTAINER" tail -20 /var/log/nginx/rankings-bot-access.log 2>/dev/null || true
  echo ""
  log "=== Verbose: nginx error log (last 20 lines) ==="
  $DOCKER exec "$NGINX_CONTAINER" tail -20 /var/log/nginx/rankings-bot-error.log 2>/dev/null || true
  echo ""
  log "=== Verbose: verify_production ==="
  "$SCRIPT_DIR/verify_production.sh" || true
fi
