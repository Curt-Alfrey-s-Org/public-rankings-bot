#!/usr/bin/env bash
# Behavioural tests for the USPBF nginx configs (production + maintenance templates).
#
# Runs a real nginx binary (no Docker needed) against a stand-in rankings-bot-api
# (echo_backend.py) and asserts, for review findings of 2026-09-25:
#   - static site (example.com, www, LAN :8089): only allowlisted public endpoints are proxied
#     with the server-side BOT_API_KEY; everything else is 404/400 and never reaches the API;
#     client X-User-Role / X-API-Key / Authorization / Cookie are replaced or dropped
#   - app.example.com: client-supplied X-User-Role / X-API-Key are stripped on every proxied path
#   - nginx starts (and keeps serving the static site) when rankings-bot-api is down/unresolvable
#   - docker-entrypoint.d/99-uspbf-bot-api-key.sh fails fast on missing/unsafe BOT_API_KEY
#
# Usage: tests/nginx/run.sh            (needs: nginx, python3, curl)
#        NGINX_BIN=/path/to/nginx tests/nginx/run.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NGX="$ROOT/nginx-config"
NGINX_BIN="${NGINX_BIN:-$(command -v nginx || echo /usr/sbin/nginx)}"
[ -x "$NGINX_BIN" ] || { echo "nginx binary not found (set NGINX_BIN)" >&2; exit 2; }
command -v curl >/dev/null || { echo "curl is required" >&2; exit 2; }

WORK="$(mktemp -d)"
BACKEND_PORT="${BACKEND_PORT:-18003}"
P80="${P80:-18080}"; P8089="${P8089:-18089}"; P8080="${P8080:-18090}"
TEST_KEY="test-key-not-a-secret"
FAILS=0; PASSES=0
BACKEND_PID=""

cleanup() {
  [ -f "$WORK/nginx.pid" ] && kill "$(cat "$WORK/nginx.pid")" 2>/dev/null || true
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
  rm -rf "$WORK"
}
trap cleanup EXIT

pass() { PASSES=$((PASSES + 1)); echo "  ok   $*"; }
fail() { FAILS=$((FAILS + 1)); echo "  FAIL $*"; }

# ---------------------------------------------------------------------------
# Entrypoint script (fail fast on BOT_API_KEY)
# ---------------------------------------------------------------------------
echo "== entrypoint: BOT_API_KEY handling"
ENTRY="$NGX/docker-entrypoint.d/99-uspbf-bot-api-key.sh"
export USPBF_BOT_API_KEY_TEMPLATE="$NGX/bot-api-key-headers.conf.template"
export USPBF_BOT_API_KEY_SNIPPET="$WORK/snippets/bot-api-key-headers.conf"
if env -u BOT_API_KEY sh "$ENTRY" 2>/dev/null; then fail "missing BOT_API_KEY accepted"; else pass "missing BOT_API_KEY -> exit non-zero"; fi
if BOT_API_KEY='' sh "$ENTRY" 2>/dev/null; then fail "empty BOT_API_KEY accepted"; else pass "empty BOT_API_KEY -> exit non-zero"; fi
if BOT_API_KEY='abc";evil' sh "$ENTRY" 2>/dev/null; then fail "quote in BOT_API_KEY accepted"; else pass "unsafe chars (quote) -> exit non-zero"; fi
if BOT_API_KEY='abc$host' sh "$ENTRY" 2>/dev/null; then fail "\$ in BOT_API_KEY accepted"; else pass "unsafe chars (\$) -> exit non-zero"; fi
BOT_API_KEY="$TEST_KEY" sh "$ENTRY"
if grep -q "X-API-Key \"$TEST_KEY\"" "$USPBF_BOT_API_KEY_SNIPPET"; then pass "valid key -> snippet generated"; else fail "snippet not generated"; fi

# Copy the static snippets next to the generated one.
cp "$NGX"/snippets/*.conf "$WORK/snippets/"
sed -i "s#/etc/nginx/snippets/#$WORK/snippets/#g" "$WORK"/snippets/*.conf

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
render_conf() { # $1=template $2=backend host:port -> $WORK/site.conf
  sed -e "s#rankings-bot-api:8003#$2#g" \
      -e "s#resolver 127.0.0.11 [^;]*;#resolver 127.0.0.1:1 valid=10s ipv6=off; resolver_timeout 2s;#" \
      -e "s#/etc/nginx/snippets/#$WORK/snippets/#g" \
      -e "s#/var/www/#$NGX/#g" \
      -e "s#/var/log/nginx/#$WORK/#g" \
      -e '/listen \[::\]/d' \
      -e "s#listen 80 default_server;#listen $P80 default_server;#" \
      -e "s#listen 80;#listen $P80;#" \
      -e "s#listen 8089;#listen $P8089;#" \
      -e "s#listen 8080;#listen $P8080;#" \
      "$1" > "$WORK/site.conf"
  # maintenance.conf root is /var/www/maintenance -> $NGX/maintenance (same layout), site -> $NGX/site
  cat > "$WORK/nginx.conf" <<CONF
pid $WORK/nginx.pid;
error_log $WORK/error.log warn;
events { worker_connections 64; }
http {
  access_log $WORK/access.log;
  client_body_temp_path $WORK/tmp_body;
  proxy_temp_path $WORK/tmp_proxy;
  fastcgi_temp_path $WORK/tmp_fcgi;
  uwsgi_temp_path $WORK/tmp_uwsgi;
  scgi_temp_path $WORK/tmp_scgi;
  include $WORK/site.conf;
}
CONF
}

start_nginx() {
  "$NGINX_BIN" -e "$WORK/error.log" -p "$WORK" -c "$WORK/nginx.conf" -t -q
  "$NGINX_BIN" -e "$WORK/error.log" -p "$WORK" -c "$WORK/nginx.conf"
  for _ in $(seq 1 50); do curl -fsS "http://127.0.0.1:$P8080/health" >/dev/null 2>&1 && return 0; sleep 0.1; done
  echo "nginx did not come up" >&2; cat "$WORK/error.log" >&2; return 1
}

stop_nginx() {
  if [ -f "$WORK/nginx.pid" ]; then
    kill "$(cat "$WORK/nginx.pid")" 2>/dev/null || true
    for _ in $(seq 1 50); do [ -f "$WORK/nginx.pid" ] || break; sleep 0.1; done
  fi
}

# req <port> <host> <method> <path> [extra curl args...] -> sets STATUS and BODY
req() {
  local port="$1" host="$2" method="$3" path="$4"; shift 4
  BODY="$(curl -sS --path-as-is -o - -w '\n%{http_code}' -X "$method" -H "Host: $host" "$@" "http://127.0.0.1:$port$path" || true)"
  STATUS="${BODY##*$'\n'}"; BODY="${BODY%$'\n'*}"
}

hdr() { # value of forwarded header $1 in echo BODY ("" if absent)
  python3 -c 'import json,sys
try: print(json.loads(sys.argv[1])["headers"].get(sys.argv[2],""))
except Exception: print("<no-backend-json>")' "$BODY" "$1"
}

expect_status() { # $1=expected $2=label
  if [ "$STATUS" = "$1" ]; then pass "$2 -> $1"; else fail "$2 -> got $STATUS, want $1 (body: ${BODY:0:120})"; fi
}
expect_hdr() { # $1=header $2=expected value ("" = absent) $3=label
  local got; got="$(hdr "$1")"
  if [ "$got" = "$2" ]; then pass "$3: $1='${2}'"; else fail "$3: $1='$got', want '$2'"; fi
}

SPOOF=(-H "X-User-Role: admin" -H "X-API-Key: spoofed" -H "Authorization: Bearer spoofed" -H "Cookie: session=spoofed")

static_site_tests() { # $1=port $2=host $3=label
  local port="$1" host="$2" l="$3"
  req "$port" "$host" GET "/api/rankings/wpa-men?limit=5" "${SPOOF[@]}"
  expect_status 200 "$l GET allowlisted /api/rankings/wpa-men"
  expect_hdr x-api-key "$TEST_KEY" "$l allowlisted"
  expect_hdr x-user-role "user" "$l allowlisted"
  expect_hdr authorization "" "$l allowlisted"
  expect_hdr cookie "" "$l allowlisted"
  expect_hdr host "app.example.com" "$l allowlisted"
  for p in "/api/login-features?variant=full" "/api/news?limit=6" "/api/rankings/player-names?limit=5000" \
           "/api/rankings/player/Jane%20Doe%20Jr." "/api/tournament-history/upcoming?limit=8" \
           "/api/tournament-history/years" "/api/tournament-history/leaderboard-results?limit=15" \
           "/api/tournament-history/search?q=open" "/api/tournament-history/tournaments?limit=100"; do
    req "$port" "$host" GET "$p"; expect_status 200 "$l GET $p"
  done
  req "$port" "$host" POST "/api/ai-narrative/demo-ask" -H "Content-Type: application/json" --data '{"question":"hi"}' "${SPOOF[@]}"
  expect_status 200 "$l POST /api/ai-narrative/demo-ask"
  expect_hdr x-user-role "user" "$l demo-ask"
  # Not allowlisted -> never reaches the backend
  req "$port" "$host" GET "/api/admin/users" "${SPOOF[@]}"; expect_status 404 "$l GET /api/admin/users"
  req "$port" "$host" GET "/api/users"; expect_status 404 "$l GET /api/users"
  req "$port" "$host" POST "/api/rankings/wpa-men"; expect_status 404 "$l POST /api/rankings/wpa-men"
  req "$port" "$host" DELETE "/api/rankings/player/x"; expect_status 404 "$l DELETE /api/rankings/player/x"
  req "$port" "$host" GET "/api/ai-narrative/demo-ask"; expect_status 404 "$l GET demo-ask"
  req "$port" "$host" GET "/api/rankings/player/..%2F..%2Fadmin%2Fusers"; expect_status 400 "$l encoded traversal"
  req "$port" "$host" GET "/api/admin/users/../../rankings/wpa-men"; expect_status 400 "$l raw dot-segment traversal"
  req "$port" "$host" GET "/api//rankings/wpa-men"; expect_status 400 "$l double slash"
  req "$port" "$host" GET "/api/rankings/player/a%5C..%5Cadmin"; expect_status 400 "$l encoded backslash"
  req "$port" "$host" GET "/api/rankings/player/%2e%2e"; expect_status 400 "$l encoded dots"
  # WebSocket path: trust headers stripped
  req "$port" "$host" GET "/ws" "${SPOOF[@]}"; expect_status 200 "$l GET /ws (proxied)"
  expect_hdr x-user-role "" "$l /ws"; expect_hdr x-api-key "" "$l /ws"
}

app_tests() { # $1=label
  local l="$1"
  for p in "/api/admin/users" "/api/rankings/wpa-men" "/" "/index.html" "/assets/video/a.mp4" "/branding/x.png" "/app.js" "/ws"; do
    req "$P80" app.example.com GET "$p" "${SPOOF[@]}"
    expect_status 200 "$l app GET $p"
    expect_hdr x-user-role "" "$l app $p"
    expect_hdr x-api-key "" "$l app $p"
  done
  req "$P80" app.example.com GET "/api/rankings/wpa-men" -H "Authorization: Bearer abc"
  expect_hdr authorization "Bearer abc" "$l app keeps user's Bearer token"
  # Caching (review 2026-09-26): /api/* never gets the 1-year static-file headers; the PWA
  # service worker files are revalidated; hashed static assets keep long caching.
  expect_cache "/api/assets/serve/splash/logo.png" "no-store" "$l app /api/*.png"
  expect_cache "/api/rankings/export.js" "no-store" "$l app /api/*.js"
  expect_cache "/sw.js" "no-cache" "$l app /sw.js"
  expect_cache "/registerSW.js" "no-cache" "$l app /registerSW.js"
  expect_cache "/assets/index-abc123.js" "immutable" "$l app hashed asset"
}

expect_cache() { # $1=path on app.example.com $2=substring Cache-Control must contain $3=label
  local cc
  cc="$(curl -sS --path-as-is -o /dev/null -D - -H "Host: app.example.com" "http://127.0.0.1:$P80$1" \
        | tr -d '\r' | awk 'tolower($1)=="cache-control:"{sub(/^[^:]*: */,""); printf "%s;", $0}')"
  if [[ "$cc" == *"$2"* ]] && { [ "$2" = immutable ] || [[ "$cc" != *immutable* ]]; }; then
    pass "$3: Cache-Control has '$2'"
  else
    fail "$3: Cache-Control='$cc', want '$2'"
  fi
}

# ---------------------------------------------------------------------------
# Start backend
# ---------------------------------------------------------------------------
python3 "$ROOT/tests/nginx/echo_backend.py" "$BACKEND_PORT" &
BACKEND_PID=$!
for _ in $(seq 1 50); do curl -fsS "http://127.0.0.1:$BACKEND_PORT/" >/dev/null 2>&1 && break; sleep 0.1; done

for mode in production maintenance; do
  echo "== $mode: backend up"
  render_conf "$NGX/uspbf-nginx-$mode.conf" "127.0.0.1:$BACKEND_PORT"
  start_nginx
  if [ "$mode" = production ]; then
    static_site_tests "$P80" example.com "$mode apex"
    req "$P80" www.example.com GET "/api/admin/users"; expect_status 404 "$mode www GET /api/admin/users"
  else
    # maintenance apex serves maintenance/ (demo chat + api.js) with the same /api/ allowlist
    static_site_tests "$P80" example.com "$mode apex"
  fi
  static_site_tests "$P8089" anything.local "$mode :8089"
  app_tests "$mode"
  stop_nginx

  echo "== $mode: rankings-bot-api down / unresolvable"
  render_conf "$NGX/uspbf-nginx-$mode.conf" "rankings-bot-api.invalid:8003"
  if start_nginx; then pass "$mode: nginx starts with unresolvable rankings-bot-api"; else fail "$mode: nginx failed to start"; continue; fi
  req "$P8089" anything.local GET "/"; expect_status 200 "$mode :8089 static site still served"
  req "$P8089" anything.local GET "/api/rankings/wpa-men"; expect_status 502 "$mode :8089 API unavailable"
  stop_nginx
done

echo
echo "passed: $PASSES  failed: $FAILS"
[ "$FAILS" -eq 0 ]
