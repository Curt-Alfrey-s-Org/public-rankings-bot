# Why Updates Don't Show (Including Incognito)

**Quick checklist:** See **docs/WHY_UPDATES_DONT_SHOW.md** — build on server (`build_frontend_with_docker.sh` or **`deploy_website.sh`**), restart **`rankings-bot-api`** when using Compose, hard refresh, check CDN/Nginx.

**Want to see what talks to what and one command to deploy?** → **docs/REQUEST_FLOW_AND_ARCHITECTURE.md** (includes Mermaid diagrams and optional n8n automation.)

## What happened

After rebuilding the frontend (`./scripts/build_frontend_with_docker.sh`) without restarting **`rankings-bot-api`** (or running **`deploy_website.sh`**), the live site (and incognito) may still show the old UI. **The serving process or container must pick up new `frontend/dist`.**

---

## Development vs deployment (do I rebuild everything every time?)

- **While you’re changing the website (development):**  
  Run the frontend in dev mode so you see changes instantly:
  ```bash
  cd frontend && npm run dev
  ```
  Open the URL it prints (e.g. http://localhost:5173). Edits to React/TS will hot‑reload; no Docker, no full rebuild.

- **When you want the live site (Docker Compose + mounted `dist/`) to show your changes:**  
  Run **`./scripts/deploy_website.sh`** (Docker frontend build + **`docker restart rankings-bot-api`**) or at minimum **`build_frontend_with_docker.sh`** then restart that container. You do **not** need a full **`full_deploy.sh`** for UI-only edits. Rebuild the **frontend image** only if you use a **split frontend container** layout.

- **Deploy builds:** **`scripts/start.sh`**, **`scripts/full_deploy.sh`**, and **`scripts/build_frontend_with_docker.sh`** use a **Docker-only** Node build (ephemeral container). **Do not use host npm** for production frontend output.

---

## How the app can run

1. **Default production (Compose):** **`rankings-bot-api`** serves **`frontend/dist`** from a **host bind mount**. Run **`./scripts/deploy_website.sh`** after UI changes (or **`build_frontend_with_docker.sh`** + **`docker restart rankings-bot-api`**). **`restart_api.sh`** in this repo **only** restarts that **Docker** service via Compose—it does **not** start host uvicorn.

2. **Optional: split frontend container** — **`rankings-bot-frontend`** image bakes in `dist/`. You must **rebuild that image** and recreate the container when the site changes; updating host `frontend/dist` alone is not enough.

3. **Optional legacy: uvicorn on the host :8003** — Build with **`build_frontend_with_docker.sh`**, then restart your **host** process (e.g. systemd), not `restart_api.sh` unless you’ve pointed it at Compose.

See **docs/WHY_UPDATES_DONT_SHOW.md** and **docs/REQUEST_FLOW_AND_ARCHITECTURE.md**.

## What to do after code changes

- **If you use Docker (production):**  
  Run:
  ```bash
  ./scripts/full_deploy.sh
  ```
  This runs the full production deploy path: Docker builds (including **`frontend/dist`** via **`scripts/build_frontend_with_docker.sh`** — no host npm), restarts app containers, then rebuilds nginx and brings up the tunnel as configured. Use `sudo` if your Docker setup requires it. **See docs/FULL_DEPLOY_AND_ERRORS.md** for how the script runs (clean bash, swarm leave, timeouts) and common errors to avoid (swarm, rebuild button not available, API ImportError, .env typos).

  **Only frontend changed (mounted `dist/`)?** Prefer:
  ```bash
  ./scripts/deploy_website.sh
  ```
  For a **split frontend container** layout only, rebuild/recreate **`rankings-bot-frontend`** (see **docs/REQUEST_FLOW_AND_ARCHITECTURE.md**).

- **Legacy host uvicorn on :8003:**  
  `./scripts/build_frontend_with_docker.sh`, then restart the **host** API (systemd, etc.). Do **not** expect **`restart_api.sh`** to manage host uvicorn.

After deploying, do a hard refresh (Ctrl+Shift+R) or open the site in an incognito window to avoid cached HTML/JS.

---

## Hard refresh / incognito didn’t change the site

If Ctrl+Shift+R and incognito still show the old site, the browser is getting stale content from somewhere. Work through these in order.

### 1. Which backend is actually serving the site?

You have two possible setups. **What you must do depends on which one is in use.**

| Setup | How traffic reaches the app | What must be updated for UI changes |
|--------|------------------------------|--------------------------------------|
| **Nginx → `rankings-bot-api` (default)** | Nginx proxies to **:8003** (container name or host, per config). **`rankings-bot-api`** serves **`frontend/dist`** from a mount. | **`./scripts/deploy_website.sh`** or `build_frontend_with_docker.sh` + **`docker restart rankings-bot-api`**. |
| **Split `rankings-bot-frontend` image** | Nginx sends `/` to a **frontend** container. | Rebuild/recreate **`rankings-bot-frontend`**; host `frontend/dist` does not apply. |
| **Host uvicorn :8003 (legacy)** | Nginx reaches the host listener. | `build_frontend_with_docker.sh` + restart **host** API; **`restart_api.sh` is not for host uvicorn**. |

**How to tell which you use**

- **`docker ps`** lists **`rankings-bot-api`** and you use mounted **`frontend/dist`** → use **`deploy_website.sh`**.
- **`rankings-bot-frontend`** serves static files → rebuild that image.
- Only **host** process on 8003 → restart that process after building `dist/`.

### 2. Containers really updated? (Docker setup)

If you use Docker with the frontend container, confirm it is the new one:

```bash
sudo docker ps -a --filter name=rankings-bot-frontend --format "{{.ID}} {{.Image}} {{.CreatedAt}}"
```

Rebuild and recreate, then run the same command again — the container ID and “CreatedAt” should change. If they don’t, the old container is still running (e.g. `up -d --force-recreate` failed). Use the manual steps in “If `up -d --force-recreate` fails” below.

### 3. Nginx in front (if you use nginx-config/rankings-bot.conf)

- Reload nginx after any backend or config change: `sudo systemctl reload nginx`.
- The repo’s `nginx-config/rankings-bot.conf` is set so `/` and `/index.html` are not cached (`proxy_no_cache`, `proxy_cache_bypass`, and `Cache-Control: no-store` for HTML). If you changed the config on the server, copy the repo version over and run `sudo nginx -t` then `sudo systemctl reload nginx`.

### 4. “Problems elsewhere”

If the UI is up to date but something else is broken (e.g. API errors, wrong data, features not working), that’s separate from caching. Check API logs, browser Network tab for failing requests, and the docs for the feature (e.g. `docs/TROUBLESHOOT_BOT_NOT_VISIBLE.md`).

---

## If `up -d --force-recreate` fails (name conflict or swarm)

Stop and remove the existing frontend container, then start again:

```bash
sudo docker stop rankings-bot-frontend 2>/dev/null
sudo docker rm rankings-bot-frontend 2>/dev/null
sudo docker-compose -f production/docker-compose.prod.yml up -d rankings-bot-frontend rankings-bot-api
```

Or, to recreate only the frontend (new build) and leave API/redis as-is:

```bash
sudo docker stop rankings-bot-frontend
sudo docker rm rankings-bot-frontend
cd /path/to/Rankings-Bot
sudo docker-compose -f production/docker-compose.prod.yml build --no-cache rankings-bot-frontend
sudo docker-compose -f production/docker-compose.prod.yml up -d rankings-bot-frontend
```
