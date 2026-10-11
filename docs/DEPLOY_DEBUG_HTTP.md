# Deploy, Debug, Test & HTTP/API

Guide for the **Deploy, Debug, Test & Fixes** roadmap section.

## Test

- **Startup:** `python3 tests/startup_test.py`
- **Backend (imports + scrapers):** `python3 tests/runner.py`
- Scraper tests mock `scrapers.fetch_utils.get_with_retry` (not `requests`) so they run without network.

### Test with real WPBA/WPA data (optional)

To verify rankings flow end-to-end with live sources:

1. **Start API:** `source venv/bin/activate` then `./start_api.sh` (or `python3 -m uvicorn api.main:app --host 127.0.0.1 --port 8003`).
2. **Refresh rankings:** In the web app, sign in as Admin and click **Refresh** on the Rankings page; or run `python3 scripts/refresh_rankings.py` (with venv active). This fetches from WPBA PDF and WPA site and saves to the DB.
3. **Check in GUI:** Open Rankings, switch WPBA/WPA tabs; confirm table shows data (or “no data” if sources are down). Check Movement page after a second refresh to see changes.
4. **Optional:** Run `python3 test_scrapers_manual.py` for a quick manual scrape test (no API).

## Find errors

- Run the test suite above; fix any failing tests.
- With API running: check browser DevTools → Network for failed requests (4xx/5xx, CORS).
- Check API logs (e.g. `rankings_bot.log`) and frontend console for stack traces.

## Fix HTTP and API

- **CORS:** Set `CORS_ORIGINS` when frontend is on a different origin (e.g. `https://www.probilliardssoftware.com,http://...`). Default allows localhost:5174, 3000.
- **Base URL:** For production, build frontend with same-origin API (`VITE_API_URL=` and `VITE_WS_URL=`) and serve both via Nginx (Cloudflare Tunnel → probilliards-nginx) so `/api` and `/` are same origin. If frontend and API are different hosts, set `VITE_API_URL` to the API base (e.g. `https://api.yoursite.com`).
- **Health:** `GET /api/health` and `GET /api/system/health` for monitoring.
- **Proxying:** Nginx proxies to the API (e.g. uvicorn on 0.0.0.0:8003). Ensure WebSocket `/ws` is proxied if the app uses it. See `docs/CLOUDFLARE_TUNNEL_NGINX.md` and `nginx-config/`.

## Deploy to website

### Frontend production build (verified)

**Production / server:** From project root run **`./scripts/build_frontend_with_docker.sh`**. That runs `npm ci` + `npm run build` **inside** a Node container and writes **`frontend/dist/`** (no host npm). For same-origin API, export before the script: `VITE_API_URL= VITE_WS_URL= ./scripts/build_frontend_with_docker.sh`. See **`docs/PRODUCTION_DEPLOYMENT.md`** and **`docs/ENV_VARS.md`**.

**Local development only:** `cd frontend && npm run dev` / `npm run build` on a machine with Node installed.

### Steps

1. **Build:** From project root, `./scripts/build_frontend_with_docker.sh` (and set `VITE_*` as needed), or use **`./scripts/full_deploy.sh`** for the full stack.
2. **API:** Run API with CORS for your domain, e.g. `export CORS_ORIGINS="https://www.probilliardssoftware.com,http://..."; python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8003`. Use systemd or screen/tmux to keep it running.
3. **Nginx / Tunnel:** Run probilliards-nginx on the same Docker network as cf-probilliards (see `docs/CLOUDFLARE_TUNNEL_NGINX.md` and `nginx-config/`). Tunnel route: `www.probilliardssoftware.com` → `http://probilliards-nginx:80`.
4. **Optional:** Copy `.env.example` to `.env` and set `JWT_SECRET`, `ADMIN_*`, `DIRECTOR_*`, and optional SMTP/WEBHOOK_URL.

**Example configs (in this repo):**
- **Nginx:** `nginx-config/` — run `docker-compose -f nginx-config/docker-compose.nginx.yml up -d` (see `nginx-config/README.md`).
- **systemd:** `docs/rankings-bot-api.service.example` — copy to `/etc/systemd/system/`, set `User`, `WorkingDirectory`, and `ExecStart` paths, then `systemctl enable --now rankings-bot-api`.

See [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md), `master_setup.sh --production`, and `docker-compose.yml` for more.

## Debug

Use this when the app fails after deploy or you see runtime errors (logs, browser console, API responses).

### Logs and where to look

- **API logs (host):** `tail -f rankings-api.log` in project root, or `journalctl -u rankings-bot-api -f` if using systemd.
- **API logs (Docker):** `docker logs --timestamps -f --tail 80 rankings-bot-api` or `./scripts/tail_api_logs.sh`.
- **Nginx:** `sudo tail -f /var/log/nginx/error.log` (and `access.log`). If Nginx is in Docker: `docker logs -f probilliards-nginx`.
- **Browser console:** DevTools → Console. Look for red errors (CORS, 404, 500, failed fetches). Note the failing URL and status.
- **Browser Network:** DevTools → Network. Filter by XHR/Fetch; click a failed request to see response body and headers.

### Quick API checks (curl)

```bash
# Health
curl -s http://127.0.0.1:8003/api/health
# Rankings (no auth)
curl -s "http://127.0.0.1:8003/api/rankings/wpa?limit=2"
# Login (replace user/pass from .env)
curl -s -X POST -H "Content-Type: application/json" -d '{"username":"ADMIN_USER","password":"ADMIN_PASS"}' http://127.0.0.1:8003/api/auth/login
```

For production, use the public URL (e.g. `https://www.probilliardssoftware.com`) and run `./scripts/smoke_check.sh` with `BASE_URL=https://...` (see SMOKE_CHECK.md).

### Common issues

- **502 Bad Gateway:** Site returns 502 when Nginx cannot reach the API. Common causes: API on wrong port (must be 8003), UFW blocking Docker→host, API not bound to 0.0.0.0. See **[BAD_GATEWAY_TROUBLESHOOTING.md](BAD_GATEWAY_TROUBLESHOOTING.md)** for diagnosis and fix.
- **API not reachable:** Confirm uvicorn is bound to the expected host/port (`ss -tlnp | grep 8003`); if Nginx is in Docker, API must bind `0.0.0.0:8003` so the container can reach it via `host.docker.internal:8003`. Check firewall and Nginx.
- **401 on /api/rankings/refresh:** Admin token required; sign in as Admin and retry.
- **CORS errors in browser:** Add the frontend origin to `CORS_ORIGINS` and restart the API.
- **502 Bad Gateway:** Nginx can’t reach the backend. Ensure API is running on 8003 and (if Docker Nginx) that the container has `host.docker.internal` and the API listens on `0.0.0.0:8003`.
