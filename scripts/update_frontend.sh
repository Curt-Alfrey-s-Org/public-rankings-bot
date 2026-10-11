#!/usr/bin/env bash
# Update frontend only: Docker-based build, then restart rankings-bot-api (Docker container).
# No API image rebuild. Use when only frontend/ changed.
# Run from project root: ./scripts/update_frontend.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_ROOT"

echo "=========================================="
echo "  Rankings Bot — Update frontend only"
echo "=========================================="
echo "App root: $APP_ROOT"
echo ""

if ! command -v docker &>/dev/null; then
  echo "ERROR: docker is required (build_frontend_with_docker.sh)." >&2
  exit 1
fi

echo "1. Building frontend (Docker)..."
bash "$SCRIPT_DIR/build_frontend_with_docker.sh"
echo "   Done: frontend/dist ready."
echo ""

echo "2. Restarting API container..."
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

echo ""
echo "Done. Hard refresh (Ctrl+Shift+R) or incognito to see frontend updates."
