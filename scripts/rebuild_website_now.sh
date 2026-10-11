#!/usr/bin/env bash
# Build frontend via Docker Node (build_frontend_with_docker.sh), then rebuild Docker images and restart containers.
# Used by the admin "Update website" button. In production this runs on the Docker HOST via the
# deploy dispatcher (scripts/deploy_request_dispatcher.sh + production/systemd/) — the API container
# holds no docker.sock. See docs/ADMIN_DEPLOY_HOST_DISPATCH.md. Docker only — no host npm.
#
# Usage: ./scripts/rebuild_website_now.sh
# Set FAST_REBUILD=1 to skip minification for quicker deploys (~15–30s faster, larger assets).

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_ROOT"

# Prefer path from API (admin button); else logs/ (writable with compose ../logs:/app/logs); else repo root.
if [ -n "${REBUILD_WEBSITE_LOG:-}" ]; then
  REBUILD_LOG="$REBUILD_WEBSITE_LOG"
else
  REBUILD_LOG="${APP_ROOT}/logs/rebuild_website.log"
fi
mkdir -p "$(dirname "$REBUILD_LOG")"
# Write to log file only (no tee) so the API's Popen pipe doesn't fill and block the script
exec >> "$REBUILD_LOG" 2>&1
echo ""

_ts() { date -u '+%H:%M:%S'; }
_start="$(date +%s)"

echo "=========================================="
echo "  Rankings Bot — Rebuild website"
echo "=========================================="
echo "[$(_ts)] App root: $APP_ROOT"
echo ""

# 1. Frontend: Docker Node image only (npm/vite run inside ephemeral container)
echo "[$(_ts)] 1. Building frontend (Docker Node)..."
if ! command -v docker &>/dev/null; then
  echo "   ❌ docker CLI not found. Install Docker or mount docker.sock in the API container."
  exit 1
fi
if [ ! -f "$SCRIPT_DIR/build_frontend_with_docker.sh" ]; then
  echo "   ❌ build_frontend_with_docker.sh missing."
  exit 1
fi
export FAST_REBUILD
# Use bash explicitly: Docker COPY often yields mode 644 so -x would fail even though the file is valid.
if ! bash "$SCRIPT_DIR/build_frontend_with_docker.sh" "$APP_ROOT"; then
  echo "   ❌ Frontend build failed."
  exit 1
fi
_end1="$(date +%s)"
echo "   ✅ frontend/dist updated ($(( _end1 - _start ))s)."
echo ""

# 2. Rebuild images + recreate, or restart API services (Docker only)
# Inside rankings-bot-api: user is HOST_UID (no tty sudo); docker is static CLI + socket.
# Prefer `docker compose` without sudo, then legacy `docker-compose`, then non-interactive sudo
# (host runs), then fall back to `docker restart` so UI-only deploys still complete.
_start2="$(date +%s)"
COMPOSE_CMD=
if docker compose version &>/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null && docker-compose version &>/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
elif sudo -n docker compose version &>/dev/null 2>&1; then
  COMPOSE_CMD="sudo -n docker compose"
elif command -v docker-compose &>/dev/null && sudo -n docker-compose version &>/dev/null 2>&1; then
  COMPOSE_CMD="sudo -n docker-compose"
fi

COMPOSE_REL="docker-compose.yml"
[ -f "$APP_ROOT/production/docker-compose.prod.yml" ] && COMPOSE_REL="production/docker-compose.prod.yml"

if [ -n "$COMPOSE_CMD" ]; then
  echo "[$(_ts)] 2. Rebuilding all images ($COMPOSE_REL)..."
  if ! (cd "$APP_ROOT" && $COMPOSE_CMD -f "$COMPOSE_REL" build --no-cache); then
    echo "   ❌ Docker build failed. Check output above."
    exit 1
  fi
  echo "[$(_ts)] 3. Starting containers..."
  if ! (cd "$APP_ROOT" && $COMPOSE_CMD -f "$COMPOSE_REL" up -d --force-recreate); then
    echo "   ❌ Docker compose up failed. Check output above."
    exit 1
  fi
  _elapsed2=$(( $(date +%s) - _start2 ))
  echo "   ✅ All images rebuilt and containers started (${_elapsed2}s)."
else
  echo "[$(_ts)] 2. docker compose not available in this environment (typical in API container)."
  echo "   Frontend assets are bind-mounted (../frontend → /app/frontend); new dist/ is live without restart."
  echo "   For a full image rebuild (Python/backend changes) run on the Docker host: cd $APP_ROOT && ./scripts/full_deploy.sh"
  # Self-restart would kill this script (we live in rankings-bot-api). We do NOT restart the API
  # because Vite emits hashed filenames and nginx serves the bind-mounted dist/ directly — a hard
  # refresh is sufficient. Celery is restarted only if explicitly requested via REBUILD_RESTART_CELERY=1.
  if [ "${REBUILD_RESTART_CELERY:-0}" = "1" ]; then
    if docker restart rankings-bot-celery-worker >/dev/null 2>&1; then
      echo "   ✅ celery worker restarted."
    else
      echo "   ⚠️  celery restart failed (socket permission or container missing); not fatal for frontend-only deploy."
    fi
  fi
  _elapsed2=$(( $(date +%s) - _start2 ))
  echo "   ✅ Frontend live in ${_elapsed2}s (no API restart needed for frontend-only changes)."
fi

_total=$(( $(date +%s) - _start ))
echo ""
echo "[$(_ts)] Done in ${_total}s. Hard refresh the page (Ctrl+Shift+R) to see updates."

# Restore network connections
if [ -x "/home/ansible/scripts/restore-docker-networks.sh" ]; then
  echo ""
  echo "[$(_ts)] Restoring network connections..."
  sudo /home/ansible/scripts/restore-docker-networks.sh
fi
