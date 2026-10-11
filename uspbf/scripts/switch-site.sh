#!/usr/bin/env bash
# Switch example.com / www between maintenance page and production (WordPress).
# Usage: ./scripts/switch-site.sh maintenance | production
# No rebuild — copies template into default.conf and reloads nginx.
set -e

MODE="${1:-}"
CONTAINER="uspbf-nginx"

case "$MODE" in
  maintenance)
    CONFIG="maintenance.conf"
    ;;
  production)
    CONFIG="production.conf"
    ;;
  *)
    echo "Usage: $0 maintenance | production"
    echo "  maintenance — example.com / www show static maintenance page"
    echo "  production  — example.com / www show static marketing site (nginx-config/site/)"
    exit 1
    ;;
esac

if ! sudo docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER}$"; then
  echo "Container ${CONTAINER} is not running. Start the stack first:"
  echo "  cd /home/ansible/USPBF && sudo docker compose --progress plain up -d --build"
  exit 1
fi

sudo docker exec "${CONTAINER}" cp "/etc/nginx/templates/${CONFIG}" /etc/nginx/conf.d/default.conf
sudo docker exec "${CONTAINER}" nginx -s reload
echo "Switched to: ${MODE} (using ${CONFIG})"
