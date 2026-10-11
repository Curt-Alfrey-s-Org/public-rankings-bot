# Debug: Console errors (API timeouts, WebSocket, Workbox, QUIC, contentScript)

## Summary

| Symptom | Root cause | Fix |
|--------|------------|-----|
| `GET /splash-config` (and other API calls) timeout after 15s | **API server not running** on port 8003 | Start API (e.g. run `./scripts/start_gui.sh` or `uvicorn api.main:app --port 8003`) |
| `GET /health` timeout (5000ms) | **API not responding** — backend down, slow, or unreachable | `curl -s http://127.0.0.1:8003/api/health`; restart API; check nginx/tunnel |
| WebSocket connection timeout → "WebSocket is closed before the connection is established" | Same: **nothing listening on 8003**; Vite proxies `/ws` to 8003 | Start API on 8003 |
| `WebSocket disconnected (code: 1006)` | Browser sets 1006 when connection fails or is closed abnormally; our code uses 1000 on timeout | Already fixed in app; 1006 here is from the **browser** after proxy target is down |
| `add-to-cache-list-conflicting-entries` (Workbox, alfa-head.png) | Same asset in precache twice: `includeAssets` + `globPatterns` | Fixed in vite.config: remove `assets/*.png` from includeAssets. Rebuild + unregister old SW. |
| `ERR_QUIC_PROTOCOL_ERROR` on `/api/live/updates` | **QUIC/HTTP3** transport failure — CDN, browser, or network | Try HTTP/2: disable HTTP/3 in Cloudflare or browser; or ignore if transient |
| `contentScript.js: ... indexOf` / `chrome-extension://...` | **Browser extension** (e.g. i18n, password manager), not app code | Ignore or disable the extension |

## Root cause (verified)

1. **Frontend** runs on **port 5174** (Vite dev server).
2. **Vite proxy** (`frontend/vite.config.ts`) forwards:
   - ` /api/*` → `http://localhost:8003`
   - `/ws` → `ws://localhost:8003`
3. **API** is expected on **port 8003**. If nothing is listening there:
   - Every API request (e.g. `/api/splash-config`) is proxied to 8003 and **hangs** until the client timeout (15s).
   - WebSocket `ws://localhost:5174/ws` is proxied to `ws://localhost:8003`; the connection never completes, so after 10s the app closes it (with code 1000). The browser may then report 1006 for the failed connection.

So: **all timeouts and WebSocket failures in the log are caused by the API not running on port 8003.**

## How to fix

1. **Run the full stack** (recommended for local dev):
   ```bash
   cd /home/ansible/rankings-bot
   ./scripts/start_gui.sh
   ```
   This starts Postgres (if needed), the API on 8003, and the frontend on 5174.

2. **Or start API only** (if you already have the frontend running):
   ```bash
   cd /home/ansible/rankings-bot
   source .venv/bin/activate   # or your venv
   export DATABASE_URL='postgresql://...'   # required
   python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8003
   ```
   Ensure `DATABASE_URL` is set and Postgres is reachable, or the API may fail to start or hang on startup.

3. **Check that the API is up**:
   ```bash
   curl -s http://localhost:8003/api/health
   ```
   You should get a JSON response, not a connection error or timeout.

## Workbox precache conflict

**Error:** `add-to-cache-list-conflicting-entries` with `alfa-head.png` and `alfa-head.png?__WB_REVISION__=...`

**Cause:** The same file was added twice: once via `includeAssets: ['assets/*.png']` (no revision) and once via `globPatterns` (with revision). Workbox rejects duplicate URLs.

**Fix:** In `frontend/vite.config.ts`, use `includeAssets: ['favicon.ico']` only — `globPatterns` already precaches PNGs. Rebuild the frontend; users may need to unregister the old service worker (DevTools → Application → Service Workers → Unregister) or hard-refresh.

## ERR_QUIC_PROTOCOL_ERROR

**Error:** `Failed to load resource: net::ERR_QUIC_PROTOCOL_ERROR` on `/api/live/updates` or other API calls.

**Cause:** QUIC (HTTP/3) transport failure — often transient. Can occur with Cloudflare, certain browsers, or when HTTP/3 is enabled but misconfigured.

**Fix:** (1) Try a different network or disable HTTP/3 in browser flags. (2) If using Cloudflare: Dashboard → Network → disable HTTP/3 (QUIC). (3) Usually transient; app falls back to polling if WebSocket fails.

## /health timeout (5000ms)

**Error:** `[WARN] API request timeout {url: '/health', method: 'GET', timeout: true, duration: 5001}`

**Cause:** The health-check endpoint (`/api/health` or `/health`) is not responding within 5 seconds. Backend may be down, overloaded, or unreachable (nginx/tunnel misconfiguration).

**Fix:** (1) `curl -s http://127.0.0.1:8003/api/health` from the server. (2) Restart API: `sudo systemctl restart rankings-bot-api` or `./scripts/restart_api.sh`. (3) Check nginx proxy_pass and Cloudflare tunnel.

## Other console messages (not app bugs)

- **contentScript.js / chrome-extension://...**  
  These come from a **Chrome extension** (e.g. the one with ID `mbckjcfnjmoiinpgddefodcighgikkgn`). They are not from the rankings-bot app. To reduce noise: disable the extension or use an incognito window without extensions.

- **installHook.js**  
  Often from a devtools or React extension. The underlying errors (timeouts, WebSocket) are still from the missing API.

## References

- Vite proxy: `frontend/vite.config.ts` (server.proxy for `/api` and `/ws`)
- API base URL: `frontend/src/api/client.ts` (`API_BASE_URL`; relative `/api` when `VITE_API_URL` is unset)
- WebSocket URL: `frontend/src/hooks/useWebSocket.ts` (same-origin `ws://${host}/ws` for proxy)
- Start script: `scripts/start_gui.sh` (API_PORT=8003, FRONTEND_PORT=5174)
