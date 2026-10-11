# Website updates without restart

After a **one-time setup**, frontend-only changes show after **`./scripts/build_frontend_with_docker.sh`** (Docker-based build from repo root) — often **no API or container restart** when the host API serves `frontend/dist` from disk.

## How it works

- **Nginx** (container) proxies to the **host API** at `host.docker.internal:8003`.
- The **host API** serves files from **`frontend/dist`** on disk (FastAPI reads on each request).
- So when you run the Docker-based build, the next request gets the new files. No restart (typical host-API setup).

## One-time setup (do this once)

1. **Free port 8003** so the host API can bind to it:
   ```bash
   sudo docker stop rankings-bot-api 2>/dev/null || true
   ```
2. **Start the API** (via Docker Compose):
   ```bash
   cd /path/to/rankings-bot/Rankings-Bot
   ./scripts/restart_api.sh
   ```
   Ensure it listens on **0.0.0.0:8003** (the script uses `--host 0.0.0.0`).
3. **Use nginx config that points at the host:**  
   The repo nginx image uses **rankings-bot-cloudflare-docker-HOST-API.conf** (upstream = host.docker.internal:8003). Rebuild and restart the nginx container:
   ```bash
   cd /path/to/rankings-bot/Rankings-Bot/nginx-config
   sudo docker-compose -f docker-compose.nginx.yml build --no-cache
   sudo docker-compose -f docker-compose.nginx.yml up -d --force-recreate
   ```
4. **Optional:** Configure Docker Compose to start services on boot (see production/docker-compose.prod.yml).

## After setup: updating the website

For **frontend-only** changes:

```bash
cd /path/to/rankings-bot
./scripts/build_frontend_with_docker.sh
```

No restart (host API path). Do a hard refresh (Ctrl+Shift+R) or incognito if the browser cached the old page.

---

## When does “no restart” apply?

| Setup | After `./scripts/build_frontend_with_docker.sh` | Notes |
|-------|------------------------|------|
| **Host-API** (this setup) | API serves built static files from disk. The **next request** gets the new assets; **no API restart** needed. | Nginx proxies to host:8003; API reads `frontend/dist` on each request. |
| **Separate CDN / static host** | Build only updates local `frontend/dist`. You must **deploy** the new assets to the CDN or static host (e.g. rsync, upload, or CI). | “No restart” does not apply until the CDN/static host is updated. |
| **Dev server (`npm run dev`)** | Production builds are not used. For production assets on disk, use **`build_frontend_with_docker.sh`** (or CI); local `npm run dev` is for development only. |

## If you still use the API container

To point nginx back at the **rankings-bot-api** container, use the standard compose layout. Then website updates require: **`./scripts/build_frontend_with_docker.sh`** **and** `sudo docker restart rankings-bot-api` when the container does not pick up new files automatically.
