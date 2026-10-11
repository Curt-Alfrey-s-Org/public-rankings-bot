#!/bin/bash
# Run ON THE SERVER to get the website live.
# Standard: Docker (API container) + Nginx container. See docs/PRODUCTION_DEPLOYMENT.md.
# Usage: from repo root: ./scripts/archive/start_website_server.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# This file lives under scripts/archive/ — repo root is two levels up.
APP_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$APP_ROOT"

echo "=========================================="
echo "  Rankings Bot — Start website (Docker + Nginx)"
echo "=========================================="
echo "App root: $APP_ROOT"
echo ""

# 1. Ensure .env exists
if [ ! -f ".env" ]; then
  echo "1. Creating .env from .env.example..."
  cp .env.example .env
  echo "   Edit .env and set POSTGRES_PASSWORD, JWT_SECRET, DATABASE_URL, etc."
else
  echo "1. .env exists."
fi

# 2. Ensure networks exist
echo "2. Ensuring Docker networks..."
docker network create tunnel_network 2>/dev/null || true
docker network create rankings-bot-network 2>/dev/null || true

# 3. Frontend build (Docker; for production bind-mount of dist/)
if [ ! -d "frontend/dist" ] || [ ! -f "frontend/dist/index.html" ]; then
  echo "3. Building frontend (Docker)..."
  ./scripts/build_frontend_with_docker.sh
else
  echo "3. Frontend already built."
fi

# 4. Full deploy (Docker Compose)
echo "4. Deploying via Docker..."
./scripts/full_deploy.sh

echo ""
echo "=========================================="
echo "  Done. Site: https://www.probilliardssoftware.com"
echo "  Health:  https://www.probilliardssoftware.com/api/health"
echo "=========================================="
