#!/usr/bin/env bash
# Diagnose "Bad Gateway" for https://www.probilliardssoftware.com/
# Flow: Cloudflare → cf-probilliards → probilliards-nginx:80 → host:8003

NGINX_CONTAINER="probilliards-nginx"
# Tunnel container for this repository (cf-probilliards only)
TUNNEL_CONTAINER="cf-probilliards"
API_PORT=8003
NETWORK="tunnel_network"
# Always use sudo for Docker so the script works without the user being in the docker group
DOCKER="sudo docker"

echo "=== Rankings Bot gateway diagnostic ==="
echo ""

# 1. probilliards-nginx
echo "1. Container: $NGINX_CONTAINER"
if ! $DOCKER ps -a --format '{{.Names}}' | grep -q "^${NGINX_CONTAINER}$"; then
  echo "   FAIL: Container $NGINX_CONTAINER not found. Create it (see nginx-config/README.md)."
else
  state=$($DOCKER inspect -f '{{.State.Status}}' "$NGINX_CONTAINER" 2>/dev/null || true)
  if [ "$state" != "running" ]; then
    echo "   FAIL: Container exists but is not running (status=$state). Start: $DOCKER start $NGINX_CONTAINER"
  else
    echo "   OK: Container is running."
  fi
  if $DOCKER inspect "$NGINX_CONTAINER" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null | grep -q "$NETWORK"; then
    echo "   OK: On network $NETWORK."
  else
    echo "   FAIL: Not on network $NETWORK. Run: $DOCKER network connect $NETWORK $NGINX_CONTAINER"
  fi
  if $DOCKER inspect "$NGINX_CONTAINER" --format '{{range .HostConfig.ExtraHosts}}{{.}} {{end}}' 2>/dev/null | grep -q "host.docker.internal"; then
    echo "   OK: Has host.docker.internal (needed to reach host API)."
  else
    echo "   WARN: No host.docker.internal. Recreate container with: --add-host=host.docker.internal:host-gateway"
  fi
fi
echo ""

# 2. Host API on 8003
echo "2. Host API port $API_PORT"
if command -v ss >/dev/null 2>&1; then
  if ss -tlnp 2>/dev/null | grep -q ":$API_PORT "; then
    echo "   OK: Something is listening on $API_PORT."
  else
    echo "   FAIL: Nothing listening on $API_PORT. Start containers: cd $APP_ROOT && ./scripts/full_deploy.sh"
  fi
else
  if curl -s -o /dev/null -w "" --connect-timeout 1 http://127.0.0.1:$API_PORT/api/health 2>/dev/null; then
    echo "   OK: API responds on 127.0.0.1:$API_PORT"
  else
    echo "   FAIL: No response from http://127.0.0.1:$API_PORT/api/health. Start the API."
  fi
fi
if curl -s --connect-timeout 2 http://127.0.0.1:$API_PORT/api/health >/dev/null 2>&1; then
  echo "   OK: curl 127.0.0.1:$API_PORT/api/health returns 200."
else
  echo "   FAIL: curl http://127.0.0.1:$API_PORT/api/health failed."
fi
echo ""

# 3. From Nginx container to API (container or host)
echo "3. From $NGINX_CONTAINER to API ($API_PORT)"
if $DOCKER ps --format '{{.Names}}' | grep -q "^${NGINX_CONTAINER}$"; then
  # Prefer rankings-bot-api (API in Docker on same network); fallback host.docker.internal (API on host)
  code=$($DOCKER exec "$NGINX_CONTAINER" curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 http://rankings-bot-api:$API_PORT/api/health 2>/dev/null || echo "000")
  if [ "$code" = "200" ]; then
    echo "   OK: Nginx container can reach rankings-bot-api:$API_PORT (HTTP 200)."
  else
    code=$($DOCKER exec "$NGINX_CONTAINER" curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 http://host.docker.internal:$API_PORT/api/health 2>/dev/null || echo "000")
    if [ "$code" = "200" ]; then
      echo "   OK: Nginx container can reach host.docker.internal:$API_PORT (HTTP 200)."
    else
      echo "   FAIL: Nginx container cannot reach rankings-bot-api:$API_PORT or host.docker.internal:$API_PORT (got $code)."
      echo "   Ensure API binds 0.0.0.0:$API_PORT. If UFW is active, allow 8003 from Docker/tunnel subnets, e.g.:"
      echo "   sudo ufw allow from 172.17.0.0/16 to any port 8003"
      echo "   sudo ufw allow from 172.18.0.0/16 to any port 8003"
      echo "   sudo ufw allow from 172.21.0.0/16 to any port 8003   # tunnel_network on many hosts"
    fi
  fi
else
  echo "   SKIP: Container not running."
fi
echo ""

# 4. Tunnel
echo "4. Tunnel: $TUNNEL_CONTAINER"
if $DOCKER ps --format '{{.Names}}' | grep -q "^${TUNNEL_CONTAINER}$"; then
  echo "   OK: Tunnel container is running."
  if $DOCKER inspect "$TUNNEL_CONTAINER" --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' 2>/dev/null | grep -q "$NETWORK"; then
    echo "   OK: Tunnel on network $NETWORK (can reach $NGINX_CONTAINER)."
  else
    echo "   FAIL: Tunnel not on $NETWORK."
  fi
else
  echo "   WARN: Tunnel container not running or different name."
fi
echo ""

echo "=== Tunnel route (Zero Trust) ==="
echo "In Cloudflare Zero Trust → Tunnels → cf-probilliards (probilliards) → Public Hostname:"
echo "  www.probilliardssoftware.com → http://probilliards-nginx:80"
echo ""
echo "If all checks pass but site still shows Bad Gateway, restart tunnel: sudo docker restart $TUNNEL_CONTAINER"
echo "Then wait ~30s and test: curl -sI https://www.probilliardssoftware.com/"
