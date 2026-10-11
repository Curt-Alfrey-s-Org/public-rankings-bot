# Nginx configs for Rankings Bot

**Doc refs (AI / maintainers):** **docs/NETWORKING_DOC_HOOKS.md** — maps this directory and related compose/scripts to the right docs; then **docs/PORT_MANAGEMENT.md**, **docs/BAD_GATEWAY_TROUBLESHOOTING.md**, **docs/MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md**.

Traffic flow when using **Cloudflare Tunnel (cf-probilliards):** Visitor → Cloudflare → **cf-probilliards** (Docker) → **Nginx** → API :8003. See **docs/CLOUDFLARE_TUNNEL_NGINX.md**.

**`proxy_pass` for `/api/`:** Use `proxy_pass http://backend` (no URI part) so the full request URI is passed unchanged. With a URI part (e.g. `proxy_pass http://backend/api/`), nginx rewrites the URI and can cause 404/405. See [rankings-bot/docs/FIX_PRODUCTION_LOGIN_404_405.md](../docs/FIX_PRODUCTION_LOGIN_404_405.md).

| File | Use when | Certs? |
|------|----------|--------|
| **rankings-bot-cloudflare.conf** | Nginx on **host**; Cloudflare or tunnel sends HTTP to host:80 | **No** — upstream 127.0.0.1:8003. |
| **rankings-bot-maintenance.conf** / **rankings-bot-production.conf** | Nginx in **Docker** (probilliards-nginx); tunnel → container:80. Switch main site with **`./scripts/switch-site.sh maintenance`** or **`production`** (no rebuild). See **docs/MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md**. | **No** |
| ~~rankings-bot-cloudflare-docker-HOST-API.conf~~ | **Deprecated.** Was for host API. Single Docker flow only; see scripts/archive/. | — |
| **rankings-bot.conf** | Direct HTTPS to server (no Cloudflare/tunnel) | **Yes** — Let’s Encrypt; Nginx 80 + 443. |

**Nginx on host:** Copy `rankings-bot-cloudflare.conf` to `/etc/nginx/sites-available/rankings-bot`, enable, reload. Tunnel route: `probilliardssoftware.com` / `www.probilliardssoftware.com` → `http://172.17.0.1:80`.

**Docker image default:** The image includes **maintenance** and **production** configs; default is maintenance. Use **`./scripts/switch-site.sh production`** to show the live app (no rebuild). Upstream = rankings-bot-api:8003 on the same Docker network.

**Nginx in Docker (cf-probilliards → container):** From repo root:
- `cd nginx-config && sudo docker compose -f docker-compose.nginx.yml up -d` (prefer **Docker Compose V2**; see **docs/UPGRADE_AND_VERSIONS.md**).
- If you see `KeyError: 'ContainerConfig'`, install Docker Compose V2 (`sudo apt-get install -y docker-compose-v2`) and use `docker compose` (no hyphen). Fallback, build and run by hand:
  ```bash
  cd nginx-config && sudo docker compose -f docker-compose.nginx.yml build
  sudo docker run -d --name probilliards-nginx --restart unless-stopped \
    --network tunnel_network \
    nginx-config_probilliards-nginx:latest
  ```
  Tunnel route: `probilliardssoftware.com` (and `app.probilliardssoftware.com`) → `http://probilliards-nginx:80`. Container must be on same network as cf-probilliards (`tunnel_network`).
