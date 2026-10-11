#!/usr/bin/env bash
# Local smoke checks for stacks listening on localhost (adjust URLs per compose publish rules).
# For tunnel/nginx paths: probe publicly routed URLs from outside this host.

set -u

probe() {
  local url="$1"
  local label="$2"
  if curl -sf "$url" >/dev/null 2>&1; then
    printf '[OK] %s (%s)\n' "$label" "$url"
    return 0
  fi
  printf '[WARN] %s (%s) not reachable\n' "$label" "$url"
  return 1
}

probe "http://127.0.0.1:8003/api/health" "rankings-bot API health"
probe "http://127.0.0.1:9090/-/healthy" "prometheus"
docker ps --format '{{.Names}} {{.Status}}' | head -n 40 || true
echo "Edit URLs above if your compose binds different host ports."
