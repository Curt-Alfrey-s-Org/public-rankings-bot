#!/usr/bin/env bash
# One-time setup: Nginx proxies to HOST API; host API serves frontend/dist from disk.
# Frontend is built with Docker (build_frontend_with_docker.sh) — no host npm.
# After this, often only a rebuild is needed for UI changes; see docs/WEBSITE_UPDATES_NO_RESTART.md.
#
# Run from project root: ./scripts/setup_website_no_restart.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_ROOT"

echo "=== Rankings Bot: setup website updates without restart ==="
echo ""

if ! command -v docker &>/dev/null; then
  echo "ERROR: docker is required." >&2
  exit 1
fi

# 1. Stop API container so host can bind 8003
echo "1. Stopping rankings-bot-api container (if running)..."
sudo docker stop rankings-bot-api 2>/dev/null || true
echo "   Done."
echo ""

# 2. Build frontend so dist exists
echo "2. Building frontend (Docker)..."
"$APP_ROOT/scripts/build_frontend_with_docker.sh"
echo "   Done."
echo ""

# 3. Start host API on 0.0.0.0:8003
echo "3. Starting host API on 0.0.0.0:8003..."
bash "$APP_ROOT/scripts/restart_api.sh"
echo "   Done."
echo ""

# 4. Rebuild and restart nginx container (uses HOST-API config)
echo "4. Rebuilding and restarting nginx container (proxy to host API)..."
cd nginx-config
if command -v docker-compose &>/dev/null; then
  sudo docker-compose -f docker-compose.nginx.yml build --no-cache
  sudo docker-compose -f docker-compose.nginx.yml up -d --force-recreate
elif docker compose version &>/dev/null 2>&1; then
  sudo docker compose -f docker-compose.nginx.yml build --no-cache
  sudo docker compose -f docker-compose.nginx.yml up -d --force-recreate
else
  echo "   docker compose not found. Rebuild/restart nginx container manually; use config rankings-bot-cloudflare-docker-HOST-API.conf"
  exit 1
fi
cd ..
echo "   Done."
echo ""

echo "=== Setup complete ==="
echo "Frontend-only changes: ./scripts/build_frontend_with_docker.sh from repo root"
echo "No API or container restart needed (host API reads dist per request). Hard refresh if cached."
echo "See docs/WEBSITE_UPDATES_NO_RESTART.md for details."
