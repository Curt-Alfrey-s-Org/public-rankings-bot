#!/usr/bin/env bash
# Build Vite frontend inside Docker (no host Node/npm required).
# Usage: ./scripts/build_frontend_with_docker.sh [APP_ROOT]
# Env: FAST_REBUILD=1 — vite build --minify false (matches rebuild_website_now.sh)
set -euo pipefail
APP_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ "${1:-}" != "" ] && APP_ROOT="$(cd "$1" && pwd)"
# Two distinct paths when running inside the API container against the host Docker daemon:
#   FRONTEND_LOCAL  = path on this filesystem (used for existence checks, "OK:" message).
#   FRONTEND_MOUNT  = path the host Docker daemon will see (used in `docker run -v <src>:...`).
# When run on the host directly they are identical; inside the API container the mount source
# must be the *host* path because the Docker daemon resolves bind sources on the host fs.
FRONTEND_LOCAL="$APP_ROOT/frontend"
FRONTEND_MOUNT="$FRONTEND_LOCAL"
if [ -f /.dockerenv ] && [ -n "${HOST_REPO_ROOT:-}" ]; then
  FRONTEND_MOUNT="${HOST_REPO_ROOT%/}/frontend"
fi
# Node 20.11 was below Vite 7 / jsdom engine ranges (^20.19); use current 20 LTS line.
NODE_IMAGE="${FRONTEND_NODE_IMAGE:-node:20-alpine}"

if [ ! -f "$FRONTEND_LOCAL/package.json" ]; then
  echo "ERROR: $FRONTEND_LOCAL/package.json not found" >&2
  if [ -f /.dockerenv ]; then
    echo "Hint: production compose must bind-mount ../frontend to /app/frontend on rankings-bot-api (see production/docker-compose.prod.yml)." >&2
  fi
  exit 1
fi
if [ -f /.dockerenv ] && [ -z "${HOST_REPO_ROOT:-}" ]; then
  echo "ERROR: HOST_REPO_ROOT is required inside the API container so the host Docker daemon can bind-mount frontend/." >&2
  echo "Set HOST_REPO_ROOT in .env to the host path of this repo (e.g. /home/ansible/rankings-bot)." >&2
  exit 1
fi

if ! command -v docker &>/dev/null; then
  echo "ERROR: docker is required for containerized frontend build." >&2
  exit 1
fi

echo "Building frontend in container: $NODE_IMAGE"
USER_ARGS=()
if [ "$(id -u)" != "0" ]; then
  USER_ARGS=(-u "$(id -u):$(id -g)")
fi
# Shared npm cache: /srv/dep-cache/npm is bind-mounted as the npm cache so every
# subsequent build (here or in any other bot repo) reuses tarballs instead of
# hitting registry.npmjs.org. See /srv/dep-cache/README.md.
NPM_CACHE_HOST="${DEP_CACHE_NPM:-/srv/dep-cache/npm}"
NPM_CACHE_ARGS=()
if [ -d "$NPM_CACHE_HOST" ] && [ -w "$NPM_CACHE_HOST" ]; then
  NPM_CACHE_ARGS=(-v "$NPM_CACHE_HOST:/npm-cache" -e npm_config_cache=/npm-cache)
else
  echo "note: $NPM_CACHE_HOST not writable — falling back to ephemeral /tmp/npm-cache" >&2
  NPM_CACHE_ARGS=(-e npm_config_cache=/tmp/npm-cache)
fi
docker run --rm \
  "${USER_ARGS[@]}" \
  "${NPM_CACHE_ARGS[@]}" \
  -e NPM_CONFIG_FETCH_RETRIES="${NPM_FETCH_RETRIES:-7}" \
  -e NPM_CONFIG_FETCH_RETRY_MINTIMEOUT="${NPM_FETCH_RETRY_MINTIMEOUT:-20000}" \
  -e NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT="${NPM_FETCH_RETRY_MAXTIMEOUT:-120000}" \
  -e NPM_CONFIG_FETCH_TIMEOUT="${NPM_FETCH_TIMEOUT:-300000}" \
  -e VITE_API_URL= \
  -e VITE_WS_URL= \
  ${VITE_BASE_PATH:+-e VITE_BASE_PATH="$VITE_BASE_PATH"} \
  ${VITE_API_BUILD_HASH:+-e VITE_API_BUILD_HASH="$VITE_API_BUILD_HASH"} \
  -v "$FRONTEND_MOUNT:/workspace" \
  -w /workspace \
  "$NODE_IMAGE" \
  sh -c '
    set -e
    mkdir -p "${npm_config_cache:-/tmp/npm-cache}"
    ok=0
    n=1
    while [ "$n" -le 5 ]; do
      if npm ci --no-audit --no-fund; then
        ok=1
        break
      fi
      echo "npm ci failed (network/registry); retry $n/5 in ${NPM_RETRY_SLEEP_SEC:-15}s..." >&2
      n=$((n + 1))
      [ "$n" -le 5 ] && sleep "${NPM_RETRY_SLEEP_SEC:-15}"
    done
    [ "$ok" = 1 ] || { echo "ERROR: npm ci failed after 5 attempts (e.g. ECONNRESET/proxy)." >&2; exit 1; }
    if [ "${FAST_REBUILD:-}" = "1" ]; then
      echo "FAST_REBUILD=1: vite build --minify false"
      npx vite build --minify false
    else
      npm run build
    fi
  '

echo "OK: $FRONTEND_LOCAL/dist"
