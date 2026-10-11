#!/usr/bin/env bash
# Start the cf-probilliards Cloudflare Tunnel (probilliardssoftware.com).
# Requires: TUNNEL_TOKEN set (from Cloudflare Zero Trust → Tunnels → your probilliards tunnel → Configure).
# Tunnel must be on tunnel_network to reach probilliards-nginx:80.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Load TUNNEL_TOKEN from .env if not already set
if [ -z "${TUNNEL_TOKEN:-}" ] && [ -f "$APP_ROOT/.env" ]; then
  # Try grep for TUNNEL_TOKEN= or TUNNEL_TOKEN = (strip quotes from value)
  _tline=$(grep -E '^[[:space:]]*TUNNEL_TOKEN[[:space:]]*=' "$APP_ROOT/.env" 2>/dev/null | head -1)
  if [ -n "${_tline}" ]; then
    _val="${_tline#*=}"
    _val="${_val#"${_val%%[![:space:]]*}"}"
    _val="${_val%"${_val##*[![:space:]]}"}"
    _val="${_val#\"}"; _val="${_val%\"}"
    _val="${_val#\'}"; _val="${_val%\'}"
    export TUNNEL_TOKEN="${_val}"
  fi
  # Fallback: source .env (works if .env has simple KEY=value lines)
  if [ -z "${TUNNEL_TOKEN:-}" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$APP_ROOT/.env" 2>/dev/null || true
    set +a
  fi
fi

CONTAINER_NAME="cf-probilliards"
IMAGE="cloudflare/cloudflared:2026.3.0"
NETWORK="tunnel_network"

if [ -z "${TUNNEL_TOKEN:-}" ]; then
  echo "ERROR: TUNNEL_TOKEN is not set. Get it from Cloudflare Zero Trust → Tunnels → your probilliards tunnel → Configure."
  echo "  export TUNNEL_TOKEN='your_token'"
  exit 1
fi

if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER_NAME}$"; then
  echo "Container ${CONTAINER_NAME} already exists. Starting it..."
  sudo docker start "${CONTAINER_NAME}"
else
  echo "Creating and starting ${CONTAINER_NAME}..."
  sudo docker run -d \
    --name "${CONTAINER_NAME}" \
    --restart unless-stopped \
    --network "${NETWORK}" \
    -e TUNNEL_TOKEN="${TUNNEL_TOKEN}" \
    "${IMAGE}" \
    tunnel --no-autoupdate run --token "${TUNNEL_TOKEN}"
fi

echo "Done. Check: sudo docker logs ${CONTAINER_NAME} --tail 20"
