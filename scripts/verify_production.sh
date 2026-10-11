#!/usr/bin/env bash
# Verify API and (optionally) public URL when running production (live app).
# Run from repo root. Requires: API reachable on 127.0.0.1:8003 when stack is up.

set -e

API_BASE="http://127.0.0.1:8003"
PUBLIC_BASE="${PUBLIC_BASE:-https://www.probilliardssoftware.com}"

echo "=== Production verification ==="
echo ""

# 1. Direct API: GET /api/splash-config
echo "1. Direct API: GET /api/splash-config"
code=$(curl -s -o /dev/null -w "%{http_code}" "$API_BASE/api/splash-config" 2>/dev/null || echo "000")
if [ "$code" = "200" ]; then
  echo "   OK ($code)"
else
  echo "   FAIL (got $code, expected 200). Is the API running? (e.g. rankings-bot-api on :8003)"
fi
echo ""

# 2. Direct API: POST /api/auth/login (expect 401 or 200)
echo "2. Direct API: POST /api/auth/login"
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API_BASE/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"x","password":"y"}' 2>/dev/null || echo "000")
if [ "$code" = "401" ] || [ "$code" = "200" ]; then
  echo "   OK ($code) — API accepts POST"
else
  echo "   FAIL (got $code, expected 401 or 200). If 405, API may not be receiving POST."
fi
echo ""

# 3. Optional: public URL (only if PUBLIC_BASE is set and curl can reach it)
if [ -n "${PUBLIC_BASE}" ] && [ "${PUBLIC_BASE}" != "none" ]; then
  echo "3. Public URL: GET $PUBLIC_BASE/api/splash-config"
  code=$(curl -s -o /dev/null -w "%{http_code}" "$PUBLIC_BASE/api/splash-config" 2>/dev/null || echo "000")
  if [ "$code" = "200" ]; then
    echo "   OK ($code)"
  else
    echo "   Got $code (expected 200). If 404, check tunnel/nginx and that site is in production (./scripts/switch-site.sh production)."
  fi
  echo ""

  echo "4. Public URL: POST $PUBLIC_BASE/api/auth/login"
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$PUBLIC_BASE/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"x","password":"y"}' 2>/dev/null || echo "000")
  if [ "$code" = "401" ] || [ "$code" = "200" ]; then
    echo "   OK ($code) — POST reaches API"
  else
    echo "   Got $code (expected 401 or 200). If 405, Cloudflare/tunnel may be converting POST to GET. See docs/CLOUDFLARE_PRODUCTION_CHECKLIST.md"
  fi
else
  echo "3–4. Skip public URL (set PUBLIC_BASE to test, or PUBLIC_BASE=none to skip)"
fi
echo ""
echo "Done. If direct API is OK but public URL fails, fix Cloudflare/tunnel per docs/CLOUDFLARE_PRODUCTION_CHECKLIST.md"
