#!/usr/bin/env bash
# Start mobile app only: Metro bundler (React Native).
# Does not start web (API + frontend). Use start_web.sh for that.
#
# For dev, set EXPO_PUBLIC_API_URL=http://localhost:8003 so mobile uses local API.
#
# Usage: ./scripts/start_mobile.sh
#   Runs in foreground; press Ctrl+C to stop. Or run stop_mobile.sh in another terminal.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_ROOT"

if [ ! -d "mobile" ]; then
  echo "ERROR: mobile/ directory not found."
  exit 1
fi

echo "Starting mobile app (Metro bundler)..."
echo "  API: Set EXPO_PUBLIC_API_URL=http://localhost:8003 to use local API"
echo "  Press Ctrl+C to stop"
echo ""

cd mobile
exec npm start
