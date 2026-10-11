#!/usr/bin/env bash
# Start web app via Docker: Postgres, Redis, API, frontend (Docker network only).
# API connects to Postgres via Docker network. No host Postgres port.
# Does not start mobile (Metro). Use start_mobile.sh for that.
#
# Usage: ./scripts/start_web.sh
# Access (nginx-only ingress): http://localhost:8088 on same host, or http://<server-ip>:8088 from LAN
#
# Doc refs (AI / maintainers): docs/NETWORKING_DOC_HOOKS.md; docs/PORT_MANAGEMENT.md (8088);
#   docs/MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_ROOT"

"$SCRIPT_DIR/start.sh" --deps-only
"$SCRIPT_DIR/start.sh" --app-only
(cd "$APP_ROOT/nginx-config" && sudo docker compose -f docker-compose.nginx.yml up -d)
