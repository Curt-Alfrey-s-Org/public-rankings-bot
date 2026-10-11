# Why website changes don’t show

Use this checklist when you’ve changed the frontend but the live site (or incognito) still shows the old UI.

---

## 0. Nginx must proxy to the host API (so updates = build only, no restart)

**Recommended (host API path):** Nginx proxies to the **host** API at `host.docker.internal:8003` (config: **`rankings-bot-cloudflare-docker-HOST-API.conf`**). The API serves `frontend/dist` from disk. Rebuild with **`./scripts/build_frontend_with_docker.sh`** from the repo root (**Docker-only**; no host npm). Often **no restart** is needed if the API reads files per request — hard refresh if the browser cached the old page.

- **If nginx was pointing at the container** (`rankings-bot-api:8003`): the **API container** must see updated `frontend/dist` on the mounted volume; use the same Docker-based build on the server, then **`docker restart rankings-bot-api`** if needed.

---

## 1. Build must run where the site is served

The app serves files from **`frontend/dist`** on the **same machine** that runs the API (host or server where the container runs).

- If you edit on a laptop and push to the server: you must **build on the server** after syncing (e.g. `git pull` then **`./scripts/build_frontend_with_docker.sh`**), or copy/sync `frontend/dist` to the server.
- If you only build on your laptop and deploy code via git/rsync **without** rebuilding on the server, the server’s `frontend/dist` is stale → no updates.

---

## 2. Restart what serves the site

What you do next depends on **what is on port 8003** (the process Nginx proxies to).

### Host API (no Docker on 8003)

- After building on the server: restart the API so it serves the new `frontend/dist`:
  ```bash
  cd /path/to/rankings-bot/Rankings-Bot
  ./scripts/deploy_website.sh --reload-nginx
  ```
  Or: `./scripts/build_frontend_with_docker.sh && ./scripts/restart_api.sh`, then `sudo systemctl reload nginx` if you use Nginx.

### Docker API (rankings-bot-api container on 8003) — Option B

- The API container **mounts** `frontend/dist` from the host (see `production/docker-compose.prod.yml`). So:
  1. On the **server** (where Docker runs): **`./scripts/build_frontend_with_docker.sh`** (not host npm).
  2. Restart the API container so it sees the updated mount (or clear any in-process cache):
     ```bash
     sudo docker restart rankings-bot-api
     ```
- You do **not** need to rebuild the Docker image (Option B = no frontend in the image).

**How to tell which you have:** On the server, run `ss -tlnp | grep 8003` or `lsof -i :8003`. If the process is from Docker (e.g. `docker-proxy` or a container PID), you’re on Docker; otherwise it’s the host API.

---

## 3. Hard refresh / incognito

Browsers and CDNs cache HTML and assets.

- Do a **hard refresh**: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac).
- Or open the site in an **incognito/private** window.

If you still see the old site after that, the server is still sending old content (go back to steps 1–2).

---

## 4. Cloudflare or other CDN

If the domain goes through Cloudflare (or another CDN):

- **Purge cache** for the site (e.g. Cloudflare Dashboard → Caching → Purge Everything), or
- Set a short TTL for HTML (or disable cache for `/*` or `/`).

Otherwise the CDN can keep serving old HTML/JS even after the server is updated.

---

## 5. Nginx in front

If Nginx is the reverse proxy:

- Reload Nginx after deploying so it doesn’t keep old connections:
  ```bash
  sudo systemctl reload nginx
  ```

The repo’s `nginx-config/rankings-bot.conf` is set to avoid caching HTML; if you use a different config, make sure HTML isn’t cached.

---

## One-command deploy (host API)

If the live site is served by the **host** API (standard Nginx → host :8003):

```bash
cd /path/to/rankings-bot/Rankings-Bot
./scripts/deploy_website.sh --reload-nginx
```

Then hard refresh or incognito. If you use **Docker** for the API (Option B), use step 2 (Docker) above instead.

---

See also: **docs/DEPLOY_UPDATES.md**, **docs/REQUEST_FLOW_AND_ARCHITECTURE.md**, **docs/DOCKER_BASE_AND_SMALL_EDITS.md**.
