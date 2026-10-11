#!/bin/bash
# Start FastAPI server in development mode (--reload).
# For production, use Docker: ./scripts/full_deploy.sh (API runs in container)
# This script is for local development only.
# Usage: ./scripts/start_api.sh

cd "$(dirname "$0")/.."
APP_ROOT="$(pwd)"

# Load environment variables from .env file if it exists
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# Check if virtual environment exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Set API port (default 8003 for dev)
export API_PORT=${API_PORT:-8003}
# Enable Rebuild & deploy button in Settings > Admin
export REBUILD_WEBSITE_SCRIPT="${REBUILD_WEBSITE_SCRIPT:-$APP_ROOT/scripts/rebuild_website_now.sh}"
export REBUILD_ALL_IMAGES_SCRIPT="${REBUILD_ALL_IMAGES_SCRIPT:-$APP_ROOT/scripts/full_deploy.sh}"

# Dev only: start with hot reload
echo "Starting in development mode with --reload..."
python3 -m uvicorn api.main:app --host 0.0.0.0 --port $API_PORT --reload
