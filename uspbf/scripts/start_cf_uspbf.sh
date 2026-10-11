#!/usr/bin/env bash
# Start the cf-uspbf Cloudflare Tunnel (example.com, www.example.com, app.example.com).
# Reads USPBF_TOKEN from USPBF/.env. Service URL in Cloudflare: http://uspbf-nginx:80
# Usage: ./scripts/start_cf_uspbf.sh (from USPBF repo root or any cwd)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USPBF_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$USPBF_ROOT/.env"

CONTAINER_NAME="cf-uspbf"
IMAGE="cloudflare/cloudflared:2026.3.0"
NETWORK="tunnel_network"

# Load USPBF_TOKEN from .env if not already set
if [ -z "${USPBF_TOKEN:-}" ] && [ -f "$ENV_FILE" ]; then
  _tline=$(grep -E '^[[:space:]]*USPBF_TOKEN[[:space:]]*=' "$ENV_FILE" 2>/dev/null | head -1)
  if [ -n "${_tline}" ]; then
    _val="${_tline#*=}"
    _val="${_val#"${_val%%[![:space:]]*}"}"
    _val="${_val%"${_val##*[![:space:]]}"}"
    _val="${_val#\"}"; _val="${_val%\"}"
    _val="${_val#\'}"; _val="${_val%\'}"
    export USPBF_TOKEN="${_val}"
  fi
  if [ -z "${USPBF_TOKEN:-}" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE" 2>/dev/null || true
    set +a
  fi
fi

if [ -z "${USPBF_TOKEN}" ]; then
  echo "ERROR: USPBF_TOKEN is not set. Copy env.example to .env and set USPBF_TOKEN."
  echo "  cp env.example .env"
  echo "  # Edit .env — add token from Cloudflare Zero Trust → Tunnels → cf-uspbf"
  exit 1
fi

if sudo docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER_NAME}$"; then
  echo "Container ${CONTAINER_NAME} already exists. Starting it..."
  sudo docker start "${CONTAINER_NAME}"
else
  echo "Creating and starting ${CONTAINER_NAME}..."
  sudo docker network inspect "$NETWORK" >/dev/null 2>&1 || sudo docker network create "$NETWORK"
  sudo docker run -d \
    --name "${CONTAINER_NAME}" \
    --restart unless-stopped \
    --network "${NETWORK}" \
    -e TUNNEL_TOKEN="${USPBF_TOKEN}" \
    "${IMAGE}" \
    tunnel --no-autoupdate run --token "${USPBF_TOKEN}"
fi

echo "Done. Check: sudo docker logs ${CONTAINER_NAME} --tail 20"
