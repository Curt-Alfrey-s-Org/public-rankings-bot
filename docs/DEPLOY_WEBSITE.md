# Deploy Rankings Bot to the live website

Get **https://www.probilliardssoftware.com** (or your domain) up and running using **Docker** and **Nginx**.

---

## Prerequisites

- **Internet access:** For the site to work from anywhere (phone, tablet, other networks), see **docs/INTERNET_ACCESS.md** — you need **public DNS**, **port forwarding** (80/443) if behind a router, and a **valid HTTPS cert**.
- **DNS:** Your domain points to the server. For internet access this must be the server's **public IP** (see INTERNET_ACCESS.md).
- **SSH:** You can log in as `ansible@<server>`.
- **Docker:** Docker and Docker Compose installed on the server. Nginx runs in a container; no host Nginx required for the standard path.

---

## Standard deployment (Docker + Nginx)

Production uses **Docker** for the API and **Nginx** (container) as the reverse proxy. See **docs/PRODUCTION_DEPLOYMENT.md** for the locked architecture.

### One-command deploy

From the project root on the server:

```bash
cd ~/rankings-bot
./scripts/full_deploy.sh --force-docker
```

This:

1. Builds the frontend
2. Rebuilds API and Celery images
3. Starts Postgres, Redis, API, Celery, Nginx, and Cloudflare Tunnel
4. Verifies health

### One-time setup (before first deploy)

1. **Sync code** to the server:
   ```bash
   ./scripts/deploy.sh ansible@<server>
   ```

2. **Environment:** Copy `.env.example` to `.env` and set:
   - `DATABASE_URL` — Postgres connection (or use default from compose)
   - `POSTGRES_PASSWORD` — required for Postgres
   - `JWT_SECRET` — for auth
   - `TUNNEL_TOKEN` — for Cloudflare Tunnel (if using)

3. **Networks:** Ensure `tunnel_network` and `rankings-bot-network` exist:
   ```bash
   docker network create tunnel_network 2>/dev/null || true
   docker network create rankings-bot-network 2>/dev/null || true
   ```

4. **Initial DB:** On first run, Postgres will initialize. For schema, see **docs/FRESH_POSTGRES_UPGRADE.md** or **docs/DATABASE_UPGRADE.md**.

---

## Quick checklist

| Step | Where | Action |
|------|--------|--------|
| Sync code | This machine | `./scripts/deploy.sh ansible@<server>` |
| One-time: .env | Server | `cp .env.example .env` and set DATABASE_URL, POSTGRES_PASSWORD, JWT_SECRET |
| One-time: networks | Server | `docker network create tunnel_network` (and rankings-bot-network if needed) |
| Deploy | Server | `./scripts/full_deploy.sh --force-docker` |
| Update | Server | `./scripts/full_deploy.sh --force-docker` (or "Update website" from Admin UI) |

---

## Verify

- **Health:** https://www.probilliardssoftware.com/api/health → `{"status":"healthy",...}`
- **Site:** https://www.probilliardssoftware.com/ → Rankings Bot app loads

See **SMOKE_CHECK.md** for a full post-deploy checklist.

---

## References

- **docs/PRODUCTION_DEPLOYMENT.md** — locked Nginx + Docker architecture
- **docs/PRODUCTION_READINESS.md** — env vars and preconditions
- **docs/DATABASE_UPGRADE.md** — Postgres setup
