#!/usr/bin/env bash
# Switch www.probilliardssoftware.com between maintenance page and production (live app).
# Usage: ./scripts/switch-site.sh maintenance | production
#        ./scripts/switch-site.sh --maintenance | --production
# No rebuild required — copies the right config and reloads nginx.
#
# Doc refs (AI / maintainers): docs/MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md;
#   docs/NETWORKING_DOC_HOOKS.md (nginx container + related docs)

set -e

MODE="${1:-}"
# Accept --production / --maintenance (common mistake)
case "$MODE" in
  --production|-production) MODE="production" ;;
  --maintenance|-maintenance) MODE="maintenance" ;;
esac

CONTAINER="probilliards-nginx"

case "$MODE" in
  maintenance)
    CONFIG="maintenance.conf"
    ;;
  production|demo)
    CONFIG="production.conf"
    MODE="production"
    ;;
  *)
    echo "Usage: $0 maintenance | production"
    echo "       $0 --maintenance | --production"
    echo "  maintenance — www shows static maintenance page"
    echo "  production — www shows live app"
    exit 1
    ;;
esac

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  echo "Container ${CONTAINER} is not running. Start it first, e.g.:"
  echo "  docker compose -f nginx-config/docker-compose.nginx.yml up -d"
  exit 1
fi

docker exec "${CONTAINER}" cp "/etc/nginx/templates/${CONFIG}" /etc/nginx/conf.d/default.conf
docker exec "${CONTAINER}" nginx -s reload
echo "Switched to: ${MODE} (www now uses ${CONFIG})"
echo "Verify: https://www.probilliardssoftware.com/"
