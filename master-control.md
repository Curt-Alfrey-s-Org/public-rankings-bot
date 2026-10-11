# Master control — scripts and commands on the server

Run these from the **Rankings-Bot project root** on the server (e.g. `~/rankings-bot/Rankings-Bot` or `/home/ansible/rankings-bot/Rankings-Bot`). Use `sudo` where noted.

---

## 1. Internet switch (allow / forbid)

The switch controls in/outbound internet for the bot while keeping local/LAN traffic working. It is driven by the **API** (no standalone script). Use `curl` from the server.

**Base URL:** Standard API port is **8003** (Nginx and UFW expect this). Use `http://127.0.0.1:8003`. Do not use 5174 unless Nginx and UFW are configured for it.

| Action | Command |
|--------|--------|
| **Get status** | `curl -s http://127.0.0.1:8003/api/network/access` |
| **Forbid internet** | `curl -s -X GET "http://127.0.0.1:8003/api/network/access/forbid"` |
| **Allow internet** | `curl -s -X GET "http://127.0.0.1:8003/api/network/access/allow"` |
| **Set via POST** | `curl -s -X POST "http://127.0.0.1:8003/api/network/access" -H "Content-Type: application/json" -d '{"allowed":false}'` (forbid) or `{"allowed":true}` (allow) |

If the API requires auth, add a valid `Authorization: Bearer <token>` header. Config is stored in `config/.internet_access` (bind-mounted in Docker); iptables rules are applied when the API process can run `iptables` (see `IPTABLES_ENABLED`, `docs` on internet access).

---

## 2. Rebuild and start (full bring-up)

| Script | Purpose |
|--------|--------|
| **`./scripts/full_deploy.sh`** | Full deploy: **Docker Compose only** — rebuild images (frontend `dist` via `build_frontend_with_docker.sh`), app stack, **restore Docker networks** (rankings-bot-network + tunnel_network), nginx, UFW, verify nginx→API, tunnel. **`--no-docker` is rejected.** Optional **`--force-docker`** is a no-op (backward compatibility). Use `sudo` if Docker needs it. |
| **`./scripts/start.sh`** | Start everything without rebuilding: Docker stack + nginx. Use when services were only stopped. |

```bash
cd ~/rankings-bot/Rankings-Bot
./scripts/full_deploy.sh
# or (no rebuild):
./scripts/start.sh
```

---

## 3. API start / stop / restart

| Script | Purpose |
|--------|--------|
| **`./scripts/restart_api.sh`** | Stop process on `API_PORT` (default 8003), then start API in background. Logs to `rankings-api.log`. |
| **`./scripts/stop.sh --api-only`** | Stop the API process on the configured port. |
| **`./scripts/start_api.sh`** | Start the API in the foreground (for debugging). Use `restart_api.sh` for background. |

```bash
cd ~/rankings-bot/Rankings-Bot
./scripts/restart_api.sh
# or stop only:
./scripts/stop.sh --api-only
```

**With Docker Compose:**

```bash
# Start API container
docker compose up -d rankings-bot-api

# Stop API container
docker compose stop rankings-bot-api

# Restart API container
docker compose restart rankings-bot-api
```

---

## 4. Deploy and build

| Script | Purpose |
|--------|--------|
| **`./scripts/deploy_website.sh --reload-nginx`** | **`build_frontend_with_docker.sh`**, restart API (container or host via `restart_api.sh`), optional nginx reload. |
| **`./scripts/build_on_server.sh --restart`** | On server: **`./scripts/build_frontend_with_docker.sh`** (Docker-only; no host npm), then guidance to restart via **`./scripts/full_deploy.sh`** / Compose as appropriate. |
| **`./scripts/deploy.sh ansible@HOST`** | From your dev machine: rsync code to HOST. Then on server run `./scripts/build_on_server.sh --restart`. |

---

## 5. Diagnostics and health

| Script | Purpose |
|--------|--------|
| **`sudo ./scripts/diagnose_rankings_bot_gateway.sh`** | Check container, API port, nginx→API connectivity, tunnel. Use when the site shows 502 or Bad Gateway. |
| **`./scripts/smoke_check.sh`** | Hit health and key endpoints. Optional: `BASE_URL=https://www.probilliardssoftware.com ./scripts/smoke_check.sh`. |
| **`./scripts/verify_ports_and_health.sh`** | Verify ports and API health. |
| **`./scripts/diagnose_login.sh`** | Diagnose login/API auth issues. Optional: `BASE_URL=... ADMIN_USERNAME=... ADMIN_PASSWORD=... ./scripts/diagnose_login.sh`. |

---

## 6. Data and refresh

| Script | Purpose |
|--------|--------|
| **`python3 scripts/refresh_rankings.py`** | Scrape WPBA/WPA and write to Postgres via `get_database_manager()`. Run from project root (requires `DATABASE_URL`). Often run via cron (e.g. hourly). |
| **`python3 scripts/refresh_fargo.py`** | Update Fargo ratings in the DB. Run from project root. |
| **`alembic upgrade head`** | Apply Postgres schema migrations (one-time or after pull). Requires `DATABASE_URL`. |

---

## 7. Docker containers (manual)

If you start/stop containers by hand:

```bash
# Start
sudo docker start b8dc6988700a_rankings-bot-redis  # or container name for redis
sudo docker start probilliards-nginx
sudo docker start rankings-bot-frontend   # if used
sudo docker start cf-probilliards        # Cloudflare tunnel (probilliardssoftware.com)

# Stop
sudo docker stop probilliards-nginx rankings-bot-api rankings-bot-frontend cf-probilliards
# (redis container name may vary; list with: sudo docker ps -a)
```

---

## 8. Quick reference

| Goal | Command (from project root) |
|------|-----------------------------|
| Forbid internet | `curl -s "http://127.0.0.1:8003/api/network/access/forbid"` |
| Allow internet | `curl -s "http://127.0.0.1:8003/api/network/access/allow"` |
| Full rebuild and start | `./scripts/full_deploy.sh` |
| Start all (no rebuild) | `./scripts/start.sh` |
| Restart API only | `./scripts/restart_api.sh` or `docker compose restart rankings-bot-api` |
| Deploy website change | `./scripts/deploy_website.sh --reload-nginx` |
| 502 / gateway check | `sudo ./scripts/diagnose_rankings_bot_gateway.sh` |
| Smoke check | `./scripts/smoke_check.sh` |
| Refresh rankings data | `python3 scripts/refresh_rankings.py` |

**Use port 8003** so the site works with Nginx and UFW. If the API was ever set to 5174, update the Docker Compose configuration (see **docs/BAD_GATEWAY_TROUBLESHOOTING.md**).
