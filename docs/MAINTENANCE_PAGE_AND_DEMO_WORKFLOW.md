# Maintenance vs Production — Easy Switch

**AI / maintainers:** **docs/NETWORKING_DOC_HOOKS.md** links `scripts/switch-site.sh`, `nginx-config/docker-compose.nginx.yml`, and **docs/PORT_MANAGEMENT.md** (optional host **8088** for LAN testing).

One script switches the **public site** (www.probilliardssoftware.com) between a static maintenance page and production (live app). No config editing, no rebuild to switch.

**Nginx behavior:** In **maintenance** mode, public `www` serves static HTML; **localhost** (and the default_server block) can still proxy to the API so you can test the app. In **production** mode, public `www` proxies to `rankings-bot-api:8003`. Switch only affects which `server` block handles the public hostname — see `nginx-config/rankings-bot-maintenance.conf` and `rankings-bot-production.conf`.

---

## Switch commands

From repo root:

| Goal | Command |
|------|--------|
| **Show maintenance page** (default after deploy) | `./scripts/switch-site.sh maintenance` |
| **Show live app** (production) | `./scripts/switch-site.sh production` |

Nginx reloads immediately; no Docker rebuild. Verify at https://www.probilliardssoftware.com/

---

## When the site is in maintenance mode

- **Public site** shows the static “Under Maintenance” page.
- **To work on the app locally**, use Docker endpoints:

### Local development (nginx-only ingress)

1. Run `./scripts/start.sh` and choose `m` for maintenance.
2. Open **http://localhost:8088** if the browser runs **on the same machine** as Docker, or **http://192.0.2.10** (replace with the server's LAN address) from another PC on your private network (headless server + Chrome on Win11). `nginx-config/docker-compose.nginx.yml` publishes **8088** on all host interfaces for that reason; loopback-only binding would block cross-machine access.
3. Nginx routes requests to the app backend over Docker network.

This keeps public `www` on maintenance while local development still uses the full app through nginx.

---

## When the site is in production

- **Public site** serves the live app (SPA + API via nginx).
- Ensure the app stack is up (API, DB, Redis as needed), e.g. `./scripts/full_deploy.sh` or your usual start.
- If login or API calls return 405/404, run `./scripts/verify_production.sh` and follow **docs/CLOUDFLARE_PRODUCTION_CHECKLIST.md**.

---

## How it works

- The nginx image includes two configs: **maintenance** (main site = static page) and **production** (main site = proxy to API).
- `switch-site.sh` copies the chosen config to `default.conf` and runs `nginx -s reload` in the container.
- Config files: `nginx-config/rankings-bot-maintenance.conf`, `nginx-config/rankings-bot-production.conf`.

---

## First-time / after image rebuild

Default is **maintenance**. If you rebuild the nginx image, the container starts with maintenance. Use `./scripts/switch-site.sh production` when you want the live site.

---

## Troubleshooting: 405 on login / 404 on splash-config (production)

When in **production**, if the app shows **405** on login or **404** on splash-config: (1) Run **`./scripts/verify_production.sh`**. (2) Fix the tunnel so all www traffic goes to nginx: see **docs/FIX_PRODUCTION_LOGIN_404_405.md** (step-by-step) and **docs/CLOUDFLARE_PRODUCTION_CHECKLIST.md**.
