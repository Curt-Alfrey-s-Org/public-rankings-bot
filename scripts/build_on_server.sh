#!/bin/bash
# Build frontend on the server using Docker only (scripts/build_frontend_with_docker.sh).
# Run from the Rankings-Bot app root ON THE SERVER (the directory that has frontend/, api/, Dockerfile).
#
# Usage:
#   ./scripts/build_on_server.sh           # build frontend only (root or subdomain)
#   ./scripts/build_on_server.sh --restart # informational: use full_deploy for container refresh
#   ./scripts/build_on_server.sh --path   # VITE_BASE_PATH=/rankings-bot for path deploys
#   ./scripts/build_on_server.sh --path --restart
#
# Requires: Docker (no host Node/npm).

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_ROOT"

RESTART_API=
BUILD_FOR_PATH=
for arg in "$@"; do
  [ "$arg" = "--restart" ] || [ "$arg" = "-r" ] && RESTART_API=1
  [ "$arg" = "--path" ] || [ "$arg" = "-p" ] && BUILD_FOR_PATH=1
done

echo "=========================================="
echo "  Rankings Bot — Build on server (Docker)"
echo "=========================================="
echo "App root: $APP_ROOT"
echo ""

if ! command -v docker &>/dev/null; then
  echo "❌ Docker is required. Install Docker; host npm is not used for frontend builds."
  exit 1
fi

if [ ! -f "$SCRIPT_DIR/build_frontend_with_docker.sh" ]; then
  echo "❌ scripts/build_frontend_with_docker.sh missing."
  exit 1
fi

if [ -n "$BUILD_FOR_PATH" ]; then
  export VITE_BASE_PATH=/rankings-bot
  echo "Building with VITE_BASE_PATH=/rankings-bot..."
else
  unset VITE_BASE_PATH
fi

bash "$SCRIPT_DIR/build_frontend_with_docker.sh" "$APP_ROOT"
echo "✅ frontend/dist is ready."
echo ""

if [ -n "$RESTART_API" ]; then
  echo "⚠️  To pick up changes in running containers, run full deploy from app root:"
  echo "   cd $APP_ROOT && ./scripts/full_deploy.sh"
  echo ""
fi

if [ -n "$BUILD_FOR_PATH" ]; then
  echo "Done. Set tunnel route to probilliards-nginx (see docs/CLOUDFLARE_TUNNEL_NGINX.md), then open: https://probilliardssoftware.com/rankings-bot"
  echo "See docs/PATH_UNDER_MAIN_DOMAIN.md for full steps."
else
  echo "Done. Open the site in the browser (e.g. https://www.probilliardssoftware.com) and hard-refresh (Ctrl+Shift+R) if needed."
fi
