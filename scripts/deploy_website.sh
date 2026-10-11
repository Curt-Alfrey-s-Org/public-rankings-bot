#!/usr/bin/env bash
# Deploy website changes: build frontend/dist via Docker, then restart rankings-bot-api (Docker only).
# Use when only frontend/ changed (or after pulling UI updates). Same logic as update_frontend.sh.
#
# See docs/REQUEST_FLOW_AND_ARCHITECTURE.md and docs/PRODUCTION_DEPLOYMENT.md.
#
# Usage: ./scripts/deploy_website.sh   [--reload-nginx]

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_ROOT"

RELOAD_NGINX=
for arg in "$@"; do
  [ "$arg" = "--reload-nginx" ] && RELOAD_NGINX=1
done

if ! command -v docker &>/dev/null; then
  echo "ERROR: docker is required (build_frontend_with_docker.sh)." >&2
  exit 1
fi

echo "Building frontend (Docker)..."
bash "$SCRIPT_DIR/build_frontend_with_docker.sh"
echo "   Done: frontend/dist ready."
echo ""

echo "Restarting API container..."
if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -qx 'rankings-bot-api'; then
  if sudo docker restart rankings-bot-api 2>/dev/null || docker restart rankings-bot-api 2>/dev/null; then
    echo "   Done: rankings-bot-api restarted."
  else
    echo "ERROR: docker restart rankings-bot-api failed." >&2
    exit 1
  fi
else
  echo "ERROR: rankings-bot-api container not found. Start the stack with Docker Compose first, e.g.:" >&2
  echo "  ./scripts/start.sh --app-only" >&2
  echo "  ./scripts/full_deploy.sh" >&2
  exit 1
fi

if [ -n "$RELOAD_NGINX" ]; then
  NGINX_CONTAINER="probilliards-nginx"
  if sudo docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^$NGINX_CONTAINER$" || docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^$NGINX_CONTAINER$"; then
    echo "Reloading nginx..."
    sudo docker exec "$NGINX_CONTAINER" nginx -s reload 2>/dev/null || docker exec "$NGINX_CONTAINER" nginx -s reload
    echo "   ✅ nginx reloaded."
  else
    echo "   ⚠️  nginx container not running. Reload skipped."
  fi
fi

if [ "${SKIP_TOURNAMENT_SMOKE:-0}" != "1" ]; then
  echo ""
  echo "Running tournament wizard smoke tests..."
  bash "$SCRIPT_DIR/smoke_test_tournament_wizard.sh"
fi

echo ""
echo "Done. Hard refresh (Ctrl+Shift+R) or incognito if you don’t see changes."
