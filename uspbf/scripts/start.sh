#!/usr/bin/env bash
# Start USPBF (WordPress + MySQL + nginx + cf-uspbf tunnel). Run from repo root or via ./scripts/start.sh.
# Optional: --production | --maintenance — after compose up, runs scripts/switch-site.sh (nginx apex/www).
# Requires: .env with MYSQL_* (copy from env.example). USPBF_TOKEN optional — if unset, tunnel is skipped.
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
. "$ROOT/scripts/compose-plain.sh"

_usage() {
  echo "Usage: ${0##*/} [--production | --maintenance] [--no-cache]" >&2
  echo "  --production   After up, switch apex/www to production nginx template." >&2
  echo "  --maintenance  After up, switch apex/www to maintenance template." >&2
  echo "  --no-cache     docker compose build --no-cache uspbf-nginx (no stale static HTML)." >&2
}

for arg in "$@"; do
  case "$arg" in
    --production | --maintenance | --no-cache) ;;
    -h | --help)
      _usage
      exit 0
      ;;
    -*)
      echo "Error: unknown option: $arg" >&2
      case "$arg" in
        --no-cahe | --no-cahce | --no-chace | --nocache)
          echo "       Did you mean --no-cache?" >&2
          ;;
      esac
      _usage
      exit 1
      ;;
    *)
      echo "Error: unexpected argument: $arg" >&2
      _usage
      exit 1
      ;;
  esac
done

SWITCH_MODE=""
NO_CACHE=0
for arg in "$@"; do
  case "$arg" in
    --production) SWITCH_MODE=production ;;
    --maintenance) SWITCH_MODE=maintenance ;;
    --no-cache) NO_CACHE=1 ;;
  esac
done

echo "🚀 Starting USPBF..."

sudo docker network inspect tunnel_network >/dev/null 2>&1 || sudo docker network create tunnel_network

for vol in uspbf_wp_data uspbf_db_data; do
  sudo docker volume inspect "$vol" >/dev/null 2>&1 || sudo docker volume create "$vol"
done

echo "Starting WordPress, MySQL, nginx..."
if [ "$NO_CACHE" = 1 ]; then
  # Avoid `up --build` after this: it runs a second bake and prints confusing CACHED lines.
  echo "(build: --no-cache uspbf-nginx; then up -d without --build)"
  uspbf_compose build --no-cache uspbf-nginx
  uspbf_compose up -d
else
  uspbf_compose up -d --build
fi

echo ""
echo "If example.com still shows old menus or HTML after a git pull, rebuild nginx without cache:"
echo "  ./scripts/start.sh --no-cache${SWITCH_MODE:+ --}${SWITCH_MODE}"
echo "  (repo root wrapper, if present: ./start.sh --no-cache${SWITCH_MODE:+ --}${SWITCH_MODE})"
echo "  or: cd \"$ROOT\" && sudo docker compose --progress plain build --no-cache uspbf-nginx && sudo docker compose --progress plain up -d"
echo ""

# Resolve USPBF_TOKEN (env first, then .env) for conditional tunnel start
ENV_FILE="$ROOT/.env"
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

if [ -n "${USPBF_TOKEN:-}" ]; then
  echo "Starting cf-uspbf tunnel..."
  "$ROOT/scripts/start_cf_uspbf.sh"
else
  echo "Skipping cf-uspbf: USPBF_TOKEN is not set. Add it to .env and run ./scripts/start_cf_uspbf.sh (or re-run ./scripts/start.sh)."
fi

if [ -x "/home/ansible/scripts/restore-docker-networks.sh" ]; then
  sudo /home/ansible/scripts/restore-docker-networks.sh >/dev/null 2>&1 || true
fi

echo ""
if [ -n "${USPBF_TOKEN:-}" ]; then
  echo "✅ USPBF started (WordPress, MySQL, nginx, cf-uspbf)"
else
  echo "✅ USPBF started (WordPress, MySQL, nginx)"
fi
echo ""
sudo docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "NAMES|uspbf|cf-uspbf" || true

if [ -n "${SWITCH_MODE}" ]; then
  echo ""
  echo "Switching main site (example.com / www) to: ${SWITCH_MODE}"
  sudo "$ROOT/scripts/switch-site.sh" "${SWITCH_MODE}"
fi
