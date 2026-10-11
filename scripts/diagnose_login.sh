#!/usr/bin/env bash
# Diagnose "Invalid login" at https://www.probilliardssoftware.com/
# Checks: API reachability, /api/auth/login. Login uses DB only (see docs/AUTH_DESIGN.md).
# Optional: set ADMIN_USERNAME/ADMIN_PASSWORD (or in .env) to test login with those credentials.

set -e
API_PORT="${API_PORT:-8003}"
BASE_URL="${BASE_URL:-https://www.probilliardssoftware.com}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [ -f .env ]; then
  set -a
  source .env 2>/dev/null || true
  set +a
fi
ADMIN_USER="${ADMIN_USERNAME:-admin}"
ADMIN_PASS="${ADMIN_PASSWORD:-}"

echo "=== Rankings Bot login diagnostic ==="
echo "  API port: $API_PORT"
echo "  Base URL: $BASE_URL"
echo "  Test user: $ADMIN_USER (login is DB-only; set ADMIN_USERNAME/ADMIN_PASSWORD to test with env creds)"
echo ""

# 1. API health (local)
echo "1. API health (localhost:$API_PORT)"
if curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 "http://127.0.0.1:$API_PORT/api/health" | grep -q 200; then
  echo "   OK: API responds on 127.0.0.1:$API_PORT"
else
  echo "   FAIL: API not responding. Start containers: cd $APP_ROOT && ./scripts/full_deploy.sh"
  echo "   (Ensure .env is loaded or set ADMIN_USERNAME, ADMIN_PASSWORD, JWT_SECRET)"
  exit 1
fi

# 2. Login endpoint (local) with credentials
echo ""
echo "2. POST /api/auth/login (localhost, with credentials)"
if [ -z "$ADMIN_PASS" ]; then
  echo "   SKIP: No password set. Login uses the database only. To test with env creds, set ADMIN_USERNAME and ADMIN_PASSWORD (or add to .env)."
else
  CODE=$(curl -s -o /tmp/rankings_login_resp.json -w "%{http_code}" --connect-timeout 3 \
    -X POST -H "Content-Type: application/json" \
    -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}" \
    "http://127.0.0.1:$API_PORT/api/auth/login")
  if [ "$CODE" = "200" ]; then
    echo "   OK: Login returned 200 (credentials accepted)"
    grep -q access_token /tmp/rankings_login_resp.json 2>/dev/null && echo "   OK: Response contains access_token"
  else
    echo "   FAIL: Login returned $CODE"
    [ -f /tmp/rankings_login_resp.json ] && echo "   Response: $(head -c 200 /tmp/rankings_login_resp.json)"
    echo "   Login is validated from the database only (docs/AUTH_DESIGN.md). Use a username/password that exist in the users table."
    echo "   Optional: try super_admin bootstrap defaults (if no users yet): username tornybotca1, password rtRT."
    echo "   Ensure API has JWT_SECRET and DATABASE_URL; restart API after .env changes."
  fi
  rm -f /tmp/rankings_login_resp.json
fi

# 3. Public URL login (optional)
echo ""
echo "3. POST $BASE_URL/api/auth/login (public URL)"
CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 \
  -X POST -H "Content-Type: application/json" \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}" \
  "$BASE_URL/api/auth/login" 2>/dev/null || echo "000")
if [ "$CODE" = "200" ]; then
  echo "   OK: Public URL login returned 200"
elif [ "$CODE" = "401" ]; then
  echo "   WARN: Public URL returned 401 (invalid credentials or API env not loaded on server)"
elif [ "$CODE" = "000" ] || [ "$CODE" = "502" ] || [ "$CODE" = "504" ]; then
  echo "   FAIL: Cannot reach API via public URL (code=$CODE). Check tunnel, Nginx, firewall."
else
  echo "   Response code: $CODE"
fi

echo ""
echo "4. Checklist (manual)"
echo "   - API must have JWT_SECRET and DATABASE_URL (see docs/AUTH_DESIGN.md). User/password in .env are optional (bootstrap-only)."
echo "   - Login uses the database only; use credentials that exist in the users table."
echo "   - Frontend: same-origin /api (build with VITE_API_URL= VITE_WS_URL= for production)."
echo "   - After changing .env, restart containers: cd $APP_ROOT && ./scripts/full_deploy.sh"
echo ""
echo "Run with: BASE_URL=https://www.probilliardssoftware.com ./scripts/diagnose_login.sh"
echo "Optional: ADMIN_USERNAME=... ADMIN_PASSWORD=... to test login with those credentials."
