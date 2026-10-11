# What Actually Controls the Website

**Short answer:** **Nginx** (reverse proxy container) forwards traffic to the **Rankings Bot API** (FastAPI in Docker) on port **8003**. The API serves both the **frontend** (built files from `frontend/dist`) and the **API** routes.

**Current mode:** The main site (www.probilliardssoftware.com) can show a **static maintenance page** or **production** (live app). See **[MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md](MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md)** for how to switch: `./scripts/switch-site.sh maintenance | production`.

**To be reachable from the internet** (phone, tablet, any network): you need **public DNS** (hostname → public IP), **port forwarding** (80/443 to the server) if behind a router, and a **valid HTTPS cert**. See **docs/INTERNET_ACCESS.md**.

---

## Request flow

1. **Browser** (PC or phone) → `https://www.probilliardssoftware.com`
2. **Cloudflare Tunnel** → `probilliards-nginx:80`
3. **Nginx container** (reverse proxy on `tunnel_network`)
   - Proxies to `rankings-bot-api:8003` (container DNS)
   - Serves static frontend and API routes
4. **Rankings Bot API** (Docker container, port **8003**)
   - **File:** `api/main.py`
   - Serves:
     - **Static frontend:** `frontend/dist/`
     - **API:** `/api/*` (e.g. `/api/rankings/wpba`, `/api/health`)

So: **Nginx** decides *where* the request goes; the **API** (this app) decides *what* is served (HTML, CSS, JS, API).

---

## Key files

| What | File / location |
|------|------------------|
| **Nginx config** | `nginx-config/rankings-bot-cloudflare.conf` (or equivalent) |
| **API app (serves site + API)** | `api/main.py` |
| **Frontend build output** | `frontend/dist/` (production: **`./scripts/build_frontend_with_docker.sh`** — Docker-only; local dev may use `npm run build` in `frontend/`) |
| **Start/stop/restart** | **docs/START_STOP_RESTART.md** |

---

## If the site works on PC but not on phone or iPad

- **Same URL:** Use `https://www.probilliardssoftware.com` on all devices (not IP:port).
- **DNS / network:** Phone and iPad must resolve that hostname (same Wi‑Fi as PC, or public DNS if using cellular).
- **Full checklist:** See **docs/MOBILE_ACCESS.md** (DNS, cache, HTTPS cert, restart API, clear site data).
- **CSS/theme not loading on phone:** The API serves HTML and `/assets/*` (CSS/JS). If data loads but layout doesn't, the device may be blocking or failing to load `/assets/*` (cache, network, or mixed content). Restart the stack (see **docs/START_STOP_RESTART.md**) and hard-refresh on the phone (or clear site data / use private window).
