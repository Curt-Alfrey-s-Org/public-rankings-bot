# USPBF — example.com

United States Pro Billiards Federation: **static marketing site** (HTML/CSS/JS in `nginx-config/site/`, baked into the nginx image) + nginx reverse proxy + Cloudflare Tunnel. The **homepage** includes an **ALFa AI demo** that calls **`POST /api/ai-narrative/demo-ask`** on **rankings-bot-api** (same-origin via `/api/`); Ollama must be enabled on the API for answers. Optional **WordPress** + MySQL remain in Compose for future CMS use. **Public links** on the marketing site point to **probilliardssoftware.com** (Pro Billiards Software). Operators may still route **`app.example.com`** through this nginx to the same **rankings-bot** SPA and **rankings-bot-api** on **`tunnel_network`** when DNS and tunnel hostnames are configured—there is no separate USPBF-branded product beyond Pro Billiards Software and this site.

## Prerequisites

- Docker and Docker Compose v2
- External Docker network **`tunnel_network`** (create: `sudo docker network create tunnel_network`)
- **Named volumes** **`uspbf_wp_data`** and **`uspbf_db_data`** — same pattern as Alfa: declared **`external: true`** in Compose. **`./scripts/start.sh`** creates them if they do not exist (`docker volume create …`) before `compose up`.
- Cloudflare zone for **example.com** with DNS managed in Cloudflare
- **rankings-bot** production API container named **`rankings-bot-api`** on **`tunnel_network`** (required for `app.example.com` and for apex **`/api/`** proxy from `uspbf-nginx`)

### Docker networking (aligned with Alfa)

| Network | Attached services | Role |
|---------|-------------------|------|
| **`tunnel_network`** (external) | `uspbf-nginx`, `uspbf_wordpress_1`, `rankings-bot-api`, `cf-uspbf` | Ingress: Cloudflare tunnel → nginx; nginx → WordPress or static site; nginx → API for `/api/*`. |
| **`uspbf_db`** (bridge) | `uspbf_db_1`, `uspbf_wordpress_1` only | Private MySQL traffic. **MySQL is not on `tunnel_network`** (same as Alfa’s `alfa1_db`). **Nginx is not on `uspbf_db`** — it talks to WordPress by hostname on `tunnel_network`. |

After restarts, **`/home/ansible/scripts/restore-docker-networks.sh`** reconnects `uspbf_wordpress_1`, `uspbf_db_1`, and `uspbf-nginx` to the correct networks (same script used for Alfa).

## Setup

1. Copy environment file and set secrets:

   ```bash
   cd /home/ansible/USPBF
   cp env.example .env
   ```

   Edit `.env`:

   - **`USPBF_TOKEN`** — from Cloudflare Zero Trust → **Networks** → **Tunnels** → create or open tunnel **cf-uspbf** → **Configure** → copy the **token**
   - **`BOT_API_KEY`** (**required**) — same value as **rankings-bot-api** `BOT_API_KEY`. Nginx injects it **server-side** into requests from **`uspbf-nginx` → `rankings-bot-api:8003`** on **`tunnel_network`** (container-to-container on the host, not a round trip through Cloudflare), **only** for the allowlisted public endpoints of the static site (see [API proxy security](#api-proxy-security)). `docker compose` and the nginx container **refuse to start** if it is unset; allowed characters are `A-Z a-z 0-9 . _ ~ + / = -` (e.g. `openssl rand -hex 32`).
   - **`MYSQL_ROOT_PASSWORD`**, **`MYSQL_DATABASE`**, **`MYSQL_USER`**, **`MYSQL_PASSWORD`** — strong passwords; database name is often `wordpress` (for WordPress if you start those services)

2. **Cloudflare Tunnel public hostnames** (Zero Trust → Tunnels → **cf-uspbf** → **Public Hostname**):

   | Subdomain | Service |
   |-----------|---------|
   | `example.com` | `http://uspbf-nginx:80` |
   | `www.example.com` | `http://uspbf-nginx:80` |
   | `app.example.com` | `http://uspbf-nginx:80` |

   All three hostnames can point to the same origin (**uspbf-nginx**); nginx routes by `Host` header to the static marketing site vs **app.example.com** (Pro Billiards Software UI).

3. **DNS** (Cloudflare dashboard for example.com):

   - For each hostname above, use **CNAME** to the tunnel (Cloudflare usually fills this when you add the public hostname), or follow the tunnel UI’s DNS instructions.

4. Start the stack:

   **Public site live (recommended):** brings the stack up **and** switches **example.com** / **www** to the static marketing site (not maintenance):

   ```bash
   cd /home/ansible/USPBF
   ./start.sh --production
   ```

   **Force a full nginx image rebuild** (no Docker layer cache for `uspbf-nginx` — e.g. after changing `nginx-config/site/`):

   ```bash
   ./start.sh --no-cache --production
   ```

   With **`--no-cache`**, the script runs **`docker compose build --no-cache uspbf-nginx`** then **`up -d`** without a second **`--build`**, so you do not see a redundant second bake in the logs.

   Same as `./scripts/start.sh --production`. From `/home/ansible`: `./start-uspbf.sh --production`.

   **Stack only** (nginx still **defaults to maintenance** on apex/www until you run `switch-site.sh` or use `--production`):

   ```bash
   cd /home/ansible/USPBF
   ./scripts/start.sh
   ```

   Equivalent: `./start.sh` at repo root delegates to `scripts/start.sh` and forwards arguments (`--production`, `--maintenance`).

   From the server home directory you can also run:

   ```bash
   /home/ansible/start-uspbf.sh
   /home/ansible/start-uspbf.sh --production
   ```

   **`USPBF_TOKEN`:** If it is missing or empty in `.env`, **`scripts/start.sh` still starts WordPress, MySQL, and nginx** and **skips** the Cloudflare tunnel. Add the token and run `./scripts/start_cf_uspbf.sh`, or run `./scripts/start.sh` again.

   Compose only (no tunnel script):

   ```bash
   sudo docker compose --progress plain up -d --build
   ./scripts/start_cf_uspbf.sh
   ```

   Prefer **`./start.sh`** when you can: it uses **`--progress plain`** (via `scripts/compose-plain.sh`) so build/up logs stay **line-oriented** and readable in any terminal width.

5. **If the stack is already running** without `--production**, run `./scripts/switch-site.sh production` so **example.com** / **www** serve the static site. The image **defaults to maintenance** on the main hostnames until you switch. **`./start.sh --maintenance`** switches back to the maintenance page after startup. Optional: start WordPress and complete setup if you use the CMS later (`./scripts/start.sh` / `docker compose --progress plain up -d` includes it).

6. **Stop** (stack only; tunnel keeps running unless you set `STOP_TUNNEL=1`):

   ```bash
   ./scripts/stop.sh
   /home/ansible/stop-uspbf.sh
   # Also stop tunnel:
   STOP_TUNNEL=1 ./scripts/stop.sh
   ```

## Maintenance vs production (main site)

By default, **`example.com`** and **`www.example.com`** serve a static **Under Maintenance** page (`nginx-config/maintenance/index.html`). **`app.example.com`** still proxies to Pro Billiards Software in both modes.

**Dev preview (port 8089):** `uspbf-nginx` publishes **`8089:8089`**. Open **`http://<server-ip>:8089/`** — you get the **full marketing site** plus **`/api/`** proxied to **rankings-bot-api** (set **`BOT_API_KEY`** in `.env`). This works in both maintenance and production nginx modes so you can polish the site while the public apex still shows the small maintenance page. Harden with host firewall rules if the server is reachable from untrusted networks (same idea as Pro Billiards `8088` in [rankings-bot/nginx-config/docker-compose.nginx.yml](../rankings-bot/nginx-config/docker-compose.nginx.yml)).

Switch without rebuilding:

```bash
cd /home/ansible/USPBF
./scripts/switch-site.sh production   # static marketing site on apex / www
./scripts/switch-site.sh maintenance  # Under Maintenance on apex / www
```

While the public site is in **maintenance**, visitors still see `maintenance/index.html` on **example.com**; **8089** is for building and testing the real site. For WordPress admin (optional), use the **default_server** block in maintenance config (e.g. request with `Host: localhost` to the nginx container).

## API proxy security

Hardened after the 2026-09-25 security review:

- **Static site (`example.com`, `www`, LAN `:8089`) → allowlisted API only.** The `/api/` location there adds the server-side `BOT_API_KEY` and a fixed `X-User-Role: user`, so it is effectively anonymous access with the key. It now forwards **only** the read-only endpoints the marketing pages call (`GET`/`HEAD`) plus the public ALFa demo (`POST /api/ai-narrative/demo-ask`). The list lives in [`nginx-config/snippets/uspbf-public-api-allowlist.conf`](nginx-config/snippets/uspbf-public-api-allowlist.conf). Anything else under `/api/` returns **404** without reaching rankings-bot-api. Request paths with dot segments, encoded `/` `.` `\`, or `//` return **400**. Visitor `Authorization` and `Cookie` headers are not forwarded on this proxy. **If the static site starts calling a new endpoint, add it to the allowlist and to `tests/nginx/run.sh`.**
- **`app.example.com` → client trust headers stripped.** Client-supplied `X-User-Role` and `X-API-Key` are removed on every location that proxies to rankings-bot-api (`snippets/strip-client-auth-headers.conf`). rankings-bot-api falls back to `X-User-Role` when there is no Bearer token, so a spoofed `X-User-Role: admin` must never reach it. Users' `Authorization: Bearer …` tokens are still forwarded unchanged. Note: the Pro Billiards SPA may still send a build-time `VITE_API_KEY` as `X-API-Key`. rankings-bot-api does not currently enforce that header, and a key baked into a public bundle is not a secret anyway, so authenticate app users with JWTs.
- **nginx no longer depends on rankings-bot-api at startup.** The backend is resolved at request time (Docker DNS `127.0.0.11`), so `example.com` keeps serving when the API container is down; `/api/` returns 502 until it is back.

## Tests

No Docker needed; CI runs the same checks (`.github/workflows/tests.yml`):

```bash
node --test tests/js/*.test.js   # api.js timeout/abort handling, safe href URLs
bash tests/nginx/run.sh          # real nginx + echo backend: allowlist, header stripping, startup without API, BOT_API_KEY fail-fast
# Needs nginx, curl, python3, envsubst (Debian/Ubuntu: apt-get install nginx-core gettext-base); NGINX_BIN=/path/to/nginx to override
```

## Repository layout

| Path | Purpose |
|------|---------|
| `docker-compose.yml` | Full stack: `uspbf-nginx`, WordPress, MySQL; **`tunnel_network`** + **`uspbf_db`**; **external** volumes `uspbf_wp_data` / `uspbf_db_data` (Alfa-style) |
| `nginx-config/` | Dockerfile, nginx confs, `maintenance/`, **`site/`** (marketing pages) |
| `nginx-config/snippets/` | Shared nginx includes: public `/api/` allowlist + proxy settings, client trust-header stripping |
| `tests/` | `tests/nginx/run.sh` (nginx behaviour tests) and `tests/js/` (node:test unit tests) |
| `scripts/start.sh` / `scripts/stop.sh` | Compose up/down + tunnel when `USPBF_TOKEN` is set; **`--production`** / **`--maintenance`** run `switch-site.sh` after up |
| `scripts/compose-plain.sh` | Sourced helper: `docker compose --progress plain` (or `CI=1` + legacy `docker-compose`) for readable logs |
| `start.sh` / `stop.sh` (repo root) | Thin wrappers → `scripts/start.sh` / `scripts/stop.sh` (passes `"$@"`) |
| `scripts/switch-site.sh` | Toggle main site: `maintenance` \| `production` |
| `scripts/start_cf_uspbf.sh` | Runs **cf-uspbf** (`cloudflared`) on `tunnel_network` |
| `scripts/backup.sh` | MySQL dump + `wp-content` archive → `backups/` (see [docs/BACKUP_AND_RECOVERY.md](docs/BACKUP_AND_RECOVERY.md)) |
| `/home/ansible/start-uspbf.sh` | Wrapper: `exec` → `USPBF/scripts/start.sh` (passes `"$@"`, e.g. `--production`) |
| `/home/ansible/stop-uspbf.sh` | Wrapper: `exec` → `USPBF/scripts/stop.sh` |
| `docs/rules/` | WPA / WPBA rule PDFs (see `docs/rules/README.md`) |
| `docs/WORDPRESS_PAGES.md` | Recommended pages after WordPress is live |
| `docs/WORDPRESS_THEME.md` | Colors/CSS to match Pro Billiards + USPBF gold |
| `scripts/download-rules-pdfs.sh` | Re-fetch official rule PDFs from WPA/WPBA |

## Rules PDFs

From repo root:

```bash
./scripts/download-rules-pdfs.sh
```

Upload PDFs from `docs/rules/` into WordPress **Media** or link from pages. See [docs/rules/README.md](docs/rules/README.md).

## Standards

- **Production processes:** Twelve-Factor; this stack is container-only (Docker Compose). See project `docs/PRODUCTION_DEPLOYMENT.md` where applicable.
- **Single owner per service:** Only Compose manages these containers; do not duplicate another process on the same published ports.

## Troubleshooting

- **`app.example.com` / `example.com/api/*` 502:** Ensure `rankings-bot-api` is running and attached to **`tunnel_network`** with the same network name the tunnel connector uses. nginx itself now starts without it.
- **`uspbf-nginx` exits at startup / `docker compose` says `BOT_API_KEY is required`:** set `BOT_API_KEY` in `.env` (same value as rankings-bot-api; allowed characters `A-Z a-z 0-9 . _ ~ + / = -`). The container log names the problem.
- **Static site shows "Not found" for a new widget:** its `/api/...` endpoint is not in `nginx-config/snippets/uspbf-public-api-allowlist.conf`.
- **Tunnel errors:** Confirm **USPBF_TOKEN** matches the **cf-uspbf** tunnel and that public hostnames use **`http://uspbf-nginx:80`** (not HTTPS to the container).
- **MySQL password change with existing volume:** See [alfaqd-website/docs/MYSQL_CREDENTIAL_CHANGE.md](../alfaqd-website/docs/MYSQL_CREDENTIAL_CHANGE.md) for the same MySQL-in-Docker pattern.
