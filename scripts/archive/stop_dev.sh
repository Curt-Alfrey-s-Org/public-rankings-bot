#!/usr/bin/env bash
# Stop Rankings Bot Development Environment
# Stops API, frontend dev server, and dependencies
# Preserves nginx (probilliards-nginx) and tunnel (cf-probilliards) containers
# which serve maintenance mode and production traffic
#
# Usage: ./scripts/stop_dev.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🛑 Stopping Rankings Bot Development Environment..."

# Stop the GUI/development processes
if [ -f "$APP_ROOT/scripts/start_gui.sh" ]; then
  echo "Stopping GUI development processes..."
  # Kill any processes started by start_gui.sh
  pkill -f "uvicorn.*api.main:app" || true
  pkill -f "vite" || true
  pkill -f "npm.*dev" || true
fi

# Stop Docker containers if running
if command -v docker &> /dev/null; then
  echo "Stopping development Docker containers..."
  cd "$APP_ROOT"

  # Stop app containers (postgres, redis, api, celery, frontend)
  # Note: This preserves nginx (probilliards-nginx) and tunnel (cf-probilliards)
  # containers which serve maintenance mode and production traffic
  docker compose down 2>/dev/null || true

  # Stop dependencies if they're running (postgres/redis only)
  ./scripts/stop_deps.sh 2>/dev/null || true
fi

# Kill any remaining development processes
echo "Cleaning up any remaining processes..."
pkill -f "python.*uvicorn" || true
pkill -f "node.*vite" || true
pkill -f "npm.*run.*dev" || true

# Remove any lock files
LOCK_FILE="/tmp/rankings-bot-browser-open.lock"
if [ -f "$LOCK_FILE" ]; then
  rm -f "$LOCK_FILE"
fi

echo "✅ Development environment stopped successfully"
echo "📋 Note: nginx (probilliards-nginx) and tunnel (cf-probilliards) containers preserved for maintenance mode"
echo ""
echo "To restart development:"
echo "  ./scripts/start_gui.sh    # Start API + frontend + open browser"
echo "  # OR manually:"
echo "  ./scripts/start_deps.sh    # Start postgres/redis"
echo "  ./scripts/start_app.sh     # Start API/celery/frontend"