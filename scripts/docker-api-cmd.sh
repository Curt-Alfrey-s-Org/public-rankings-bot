#!/usr/bin/env sh
# Production API — multi-worker Uvicorn for medium concurrent traffic.
# Tune UVICORN_WORKERS (default 4). Each worker has its own SQLAlchemy pool; see DB_POOL_SIZE / DB_MAX_OVERFLOW.
set -e
PORT="${API_PORT:-8003}"
WORKERS="${UVICORN_WORKERS:-4}"
# Client IP (rate limits, login lockout, IP blocks): Uvicorn resolves X-Forwarded-For only when
# the TCP peer is a trusted proxy, walking the list right-to-left and skipping trusted hops, so
# client-supplied values are ignored. Default trusts loopback + private ranges (the nginx
# containers on the Docker networks). Narrow FORWARDED_ALLOW_IPS to your proxy subnet(s) if
# anything untrusted can reach the API from a private address. See docs/ENV_VARS.md.
FORWARDED_ALLOW_IPS="${FORWARDED_ALLOW_IPS:-127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.0.2.0/24}"
exec python -m uvicorn api.main:app --host 0.0.0.0 --port "$PORT" --workers "$WORKERS" \
  --proxy-headers --forwarded-allow-ips "$FORWARDED_ALLOW_IPS"
