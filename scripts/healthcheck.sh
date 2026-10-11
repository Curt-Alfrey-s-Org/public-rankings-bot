#!/bin/bash
# Health check and container monitoring for Rankings Bot
# Checks: container running, healthy, not crashing, API responding
# Env: CONTAINER_API (default rankings-bot-api), CONTAINER_FRONTEND (default rankings-bot-frontend), SKIP_FRONTEND (set to 1 to skip), API_PORT, FRONTEND_PORT

set -e

CONTAINER_API="${CONTAINER_API:-rankings-bot-api}"
CONTAINER_FRONTEND="${CONTAINER_FRONTEND:-rankings-bot-frontend}"
API_PORT="${API_PORT:-8003}"
FRONTEND_PORT="${FRONTEND_PORT:-5176}"
SKIP_FRONTEND="${SKIP_FRONTEND:-0}"
HEALTH_ENDPOINT="http://localhost:${API_PORT}/api/health"

# Docker command (use sudo if needed)
DOCKER="${DOCKER:-docker}"
if ! $DOCKER info &>/dev/null; then
  DOCKER="sudo docker"
fi
if ! $DOCKER info &>/dev/null; then
  echo "Error: Docker not available (install Docker or run with sudo)." >&2
  exit 2
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=== Rankings Bot Container Health Check ==="
echo "Timestamp: $(date)"
echo "API container: $CONTAINER_API | Frontend: $CONTAINER_FRONTEND (skip=$SKIP_FRONTEND)"
echo

# Function to check if container exists and is running
check_container_status() {
    local container=$1
    local port=$([ "$container" = "$CONTAINER_API" ] && echo $API_PORT || echo $FRONTEND_PORT)
    
    echo "Checking $container..."
    
    # Check if container exists
    if ! $DOCKER ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
        echo -e "${RED}✗ Container $container does not exist${NC}"
        return 1
    fi
    
    # Check if running
    local status=$($DOCKER ps --format '{{.Names}}\t{{.Status}}' | grep "^${container}") || {
        echo -e "${RED}✗ Container $container is not running${NC}"
        return 1
    }
    
    echo -e "${GREEN}✓ Container $container is running${NC}"
    echo "  Status: $status"
    
    # Check health status if available
    local health=$($DOCKER inspect "$container" --format='{{.State.Health.Status}}' 2>/dev/null || echo "none")
    if [ "$health" != "none" ]; then
        if [ "$health" = "healthy" ]; then
            echo -e "${GREEN}✓ Health check: $health${NC}"
        else
            echo -e "${YELLOW}⚠ Health check: $health${NC}"
        fi
    fi
    
    # Check uptime
    local uptime=$($DOCKER inspect "$container" --format='{{.State.StartedAt}}' 2>/dev/null)
    echo "  Started: $uptime"
    
    return 0
}

# Function to check API responsiveness
check_api_health() {
    echo "Checking API health endpoint..."
    
    if curl -f -s "$HEALTH_ENDPOINT" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ API health endpoint responding${NC}"
        return 0
    else
        echo -e "${RED}✗ API health endpoint not responding${NC}"
        return 1
    fi
}

# Function to check frontend responsiveness
check_frontend_health() {
    echo "Checking frontend..."
    
    if curl -f -s "http://localhost:${FRONTEND_PORT}/" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Frontend responding on port $FRONTEND_PORT${NC}"
        return 0
    else
        echo -e "${RED}✗ Frontend not responding on port $FRONTEND_PORT${NC}"
        return 1
    fi
}

# Main checks
status=0

check_container_status "$CONTAINER_API" || status=1
echo

if [ "$SKIP_FRONTEND" != "1" ]; then
  check_container_status "$CONTAINER_FRONTEND" || status=1
  echo
fi

check_api_health || status=1
echo

if [ "$SKIP_FRONTEND" != "1" ]; then
  check_frontend_health || status=1
else
  echo "Skipping frontend check (SKIP_FRONTEND=1)"
fi

echo
if [ $status -eq 0 ]; then
    echo -e "${GREEN}All health checks passed${NC}"
    exit 0
else
    echo -e "${RED}Some health checks failed${NC}"
    exit 1
fi
