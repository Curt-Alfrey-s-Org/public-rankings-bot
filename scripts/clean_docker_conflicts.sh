#!/bin/bash
# Clean up Docker container name conflicts for rankings bot
# Run this before full_deploy.sh if you encounter container name conflicts

set -e

echo "🧹 Cleaning up Docker container conflicts..."

# Function to stop and remove containers safely
cleanup_containers() {
    local containers="$1"
    echo "Stopping containers: $containers"
    docker stop $containers 2>/dev/null || true

    echo "Removing containers: $containers"
    docker rm $containers 2>/dev/null || true
}

# Stop and remove rankings-bot related containers (cf-probilliards tunnel only)
RANKINGS_CONTAINERS="rankings-bot-api rankings-bot-postgres rankings-bot-redis rankings-bot-celery-worker probilliards-nginx cf-probilliards"
echo "Cleaning up rankings containers..."
cleanup_containers "$RANKINGS_CONTAINERS"

# Clean up any containers with similar names (in case of variations)
echo "Cleaning up any remaining rankings-related containers..."
docker ps -a --format "{{.Names}}" | grep -E "(rankings|probilliards)" | xargs -r docker rm -f 2>/dev/null || true

# Clean up processes using required ports
echo "Cleaning up processes using required ports..."
# Kill any processes using port 8003 (API)
if command -v fuser >/dev/null 2>&1; then
  fuser -k 8003/tcp 2>/dev/null || true
elif command -v lsof >/dev/null 2>&1; then
  lsof -ti:8003 | xargs kill -9 2>/dev/null || true
fi
# Postgres is Docker-network-only (no host port); no 5434 cleanup needed

# Clean up unused networks
echo "Cleaning up unused networks..."
docker network prune -f

# Clean up unused images (optional, can be slow)
# echo "Cleaning up unused images..."
# docker image prune -f

# Clean up build cache (optional)
# echo "Cleaning up build cache..."
# docker builder prune -f

echo "✅ Docker conflicts cleaned up!"
echo ""
echo "You can now run:"
echo "  ./scripts/full_deploy.sh --no-cache"
echo ""
echo "If you still get conflicts, try:"
echo "  docker system prune -a -f  # WARNING: This removes ALL unused Docker resources"