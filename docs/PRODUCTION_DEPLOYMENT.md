# Production Deployment Guide

**Purpose:** Concise production deployment steps for Rankings-Bot using Docker Compose.

**Single stack:** All services (Postgres, Redis, API, Celery, Prometheus, Grafana, exporters, cAdvisor) are defined in **`production/docker-compose.prod.yml`**. The repo-root **`docker-compose.yml`** is a thin wrapper that `include:`s the production file for backward compatibility — do not maintain two competing service definitions. Postgres data uses the external volume **`rankings-bot_postgres_data`**. **CLI rankings refresh** from cron or a laptop should use **`docker compose exec rankings-bot-api`** (see **docs/RANKINGS_REFRESH_RUNBOOK.md**); nginx **maintenance** vs **production** does not change that.

---

## Prerequisites

- Docker and Docker Compose installed
- PostgreSQL running (external or containerized); `DATABASE_URL` set
- Nginx (or Cloudflare Tunnel) for HTTPS and load balancing

---

## 1. Environment Setup

Create or update `.env` file with required variables:

```bash
# Required
DATABASE_URL="postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot"
JWT_SECRET="<strong-random-secret>"  # Never use default in production

# Optional (see docs/ENV_VARS.md)
CORS_ORIGINS="https://www.probilliardssoftware.com,https://app.probilliardssoftware.com"
LOG_LEVEL=INFO
```

**API throughput (medium traffic defaults):** `production/docker-compose.prod.yml` sets **`UVICORN_WORKERS=4`** and a **smaller per-worker DB pool** (`DB_POOL_SIZE` / `DB_MAX_OVERFLOW`) so total Postgres usage stays bounded. Override in `.env` if needed; see **docs/ENV_VARS.md**. Nginx **`/api/`** upstreams use **keepalive** to the API (see `nginx-config/rankings-bot-*.conf`).

---

## 2. Database Setup

Database migrations are applied during deployment by `full_deploy.sh` (step 2bb). To run manually (from the running API container, same image as production):

```bash
docker exec rankings-bot-api python -m alembic upgrade head
```

---

## 3. Backups

```bash
# One-time backup
./scripts/backup_postgres.sh

# Cron (daily 2 AM)
0 2 * * * /path/to/Rankings-Bot/scripts/backup_postgres.sh >> /path/to/backup_postgres.log 2>&1
```

See [POSTGRES_BACKUPS_AND_CUTOVER.md](POSTGRES_BACKUPS_AND_CUTOVER.md).

---

## 4. Deploy with Docker Compose

Prefer **`./scripts/start.sh`** or **`./scripts/full_deploy.sh`**: they set **`HOST_UID` / `HOST_GID`** (via `.env.compose-host-user`) so API and Celery run as your host user (e.g. `ansible`) and **do not root-own** `frontend/` or `logs/` on bind mounts.

**Ownership policy:** Production files under the repo on disk (`frontend/`, `logs/`, `config/`, etc.) should be owned by the **`ansible`** deploy user (or the non-root account that runs deploys), not `root`. The container’s `user:` line must match that account’s UID/GID. If something was created as root (e.g. an old run without `.env.compose-host-user`), fix ownership once with `sudo chown -R ansible:ansible …` on the affected paths (see also `scripts/clean_frontend_dist.sh` for `dist/`).

```bash
# Production deployment (manual compose — from repo root, after sourcing UID helper)
# . ./scripts/export_compose_uid_gid.sh && write_compose_host_user_env "$PWD"
# docker compose --env-file .env --env-file .env.compose-host-user -f production/docker-compose.prod.yml up -d

# Or use the unified scripts (recommended)
./scripts/full_deploy.sh --production

# Development stack
./scripts/start.sh
```

**Disk / Docker:** See **[DOCKER_DISK_CLEANUP.md](DOCKER_DISK_CLEANUP.md)** for `./scripts/cleanup_docker_disk.sh`, flags, and optional **`RUN_DOCKER_CLEANUP_BEFORE_BUILD`** for `./scripts/full_deploy.sh` (default: cleanup before build is off).

---

## 5. Frontend build and **Update website** (Admin UI)

**Policy:** Frontend builds are **Docker-only** (`scripts/build_frontend_with_docker.sh` → ephemeral `node:20-alpine`). **Do not use host npm** for production deploys.

Production Compose mounts the **`frontend/`** tree into `rankings-bot-api` (read/write) so built assets land in `frontend/dist/`. **Settings → Update website** does **not** run Docker from inside the API container — the container holds no `/var/run/docker.sock` (docker-group/socket access is root-equivalent on the host per <https://docs.docker.com/engine/security/#docker-daemon-attack-surface>). Instead:

- The API writes a request file into `logs/deploy-requests/` (`DEPLOY_REQUEST_DIR`).
- The host systemd pair `rankings-bot-deploy.path` / `rankings-bot-deploy.service` (`production/systemd/`) runs `scripts/rebuild_website_now.sh` (or `full_deploy.sh`) **on the host** and appends to the same bind-mounted log files the API streams.
- One-time install: see `docs/ADMIN_DEPLOY_HOST_DISPATCH.md`.

If the button finishes immediately but the site does not change: open **View rebuild log**, or on the server run `tail -50 logs/rebuild_website.log` and `tail -20 logs/deploy_dispatcher.log`; check `systemctl status rankings-bot-deploy.path` and that `frontend/dist/` updates on disk.

Manual rebuild on the host (same build path as the button):

```bash
./scripts/rebuild_website_now.sh
```

For Python/API image changes after pulling code, use `./scripts/full_deploy.sh` on the host.

---

## 6. Verify Deployment

```bash
# Check container status
docker compose ps

# Smoke test (health, app-version, privacy)
./scripts/smoke_test.sh
# Or: curl https://www.probilliardssoftware.com/api/health  # Expect 200

# Full production verification
./scripts/verify_production.sh
```

---

## 7. Monitoring (central stack on `192.0.2.20`)

Production monitoring is the **central stack** in the separate `monitoring` repo —
Rankings Bot does **not** run its own Prometheus/Grafana in production. The central
Prometheus scrapes the API `/metrics` over the shared `rankings-bot-network`.
Full guide: [MONITORING_RANKINGS_BOT.md](MONITORING_RANKINGS_BOT.md).

### Access Monitoring

- **Prometheus:** http://192.0.2.20:9092 (UI; internal scrape/eval on container `:9090`)
- **Grafana:** http://192.0.2.20:3000 (folder **Homelab** → Rankings Bot dashboards)

### Configure Monitoring Links in Frontend

Add to `.env` (point at the central stack):
```bash
VITE_GRAFANA_BASE_URL=http://192.0.2.20:3000
VITE_PROMETHEUS_BASE_URL=http://192.0.2.20:9092
```

This enables Grafana and Prometheus links in `Settings > Admin > Health & logs` (`/settings/admin/health-logs`).

### Verify Monitoring Stack

```bash
# Check the rankings-bot-api target is up
curl -s 'http://192.0.2.20:9092/api/v1/targets' \
  | jq '.data.activeTargets[] | select(.labels.job=="rankings-bot-api") | {health, lastError}'

# Check API metrics endpoint (host loopback)
curl -s http://127.0.0.1:8003/metrics | head -20

# Verify Grafana is running
curl -s http://192.0.2.20:3000/api/health
```

### Credentials

- **Grafana** admin credentials are managed in the `monitoring` repo `.env`
  (`GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD`), not in this repo.

### Dashboards

Pre-configured dashboards:
- **System Overview** - API, containers, database, Redis, system metrics
- **API Performance** - Request rates, latency, error rates by endpoint

See [MONITORING_SETUP_GUIDE.md](MONITORING_SETUP_GUIDE.md) for detailed configuration.

---

## Troubleshooting

- **502 Bad Gateway:** Check if API container is running and listening on port 8003
- **Container won't start:** Check logs with `docker compose logs rankings-bot-api`
- **DB connection errors:** Verify `DATABASE_URL`, ensure PostgreSQL is accessible from containers
- **Port conflicts:** Ensure no other services are using ports 8003 (API), 6379 (Redis). Postgres is Docker-network-only (no host port).

**See:** [BAD_GATEWAY_TROUBLESHOOTING.md](BAD_GATEWAY_TROUBLESHOOTING.md), [CONTAINER_DRIFT_PREVENTION.md](CONTAINER_DRIFT_PREVENTION.md)

### Stale splash video after deploy

Hashed JS/CSS under `/assets/` may be cached with long TTLs; **splash video** under **`/assets/video/`** is configured in **`nginx-config/rankings-bot-production.conf`** (and maintenance default_server block) with **`location ^~ /assets/video/`** and **`no-cache, must-revalidate`** so replacements are visible sooner. The app also uses **`splash_media_revision`** from `/api/splash-config` to add a **`smr`** query on media URLs (see [SPLASH_CONFIG.md](SPLASH_CONFIG.md)).
