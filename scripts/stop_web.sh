#!/usr/bin/env bash
# Stop web app only: API + frontend dev server.
# Does not stop mobile (Metro). Use stop_mobile.sh for that.
#
# Usage: ./scripts/stop_web.sh

set -e
API_PORT="${API_PORT:-8003}"
FRONTEND_PORT="${FRONTEND_PORT:-5174}"

echo "Stopping web app (API + frontend)..."

pkill -f "uvicorn.*api.main:app" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
pkill -f "npm.*dev" 2>/dev/null || true
pkill -f "python.*uvicorn" 2>/dev/null || true
pkill -f "node.*vite" 2>/dev/null || true
pkill -f "npm.*run.*dev" 2>/dev/null || true

# Fallback: kill by port
for port in $API_PORT $FRONTEND_PORT; do
  pid=$(lsof -t -i ":$port" 2>/dev/null || true)
  [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
done

rm -f /tmp/rankings-bot-browser-open.lock 2>/dev/null || true

echo "✅ Web app stopped."
