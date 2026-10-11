# Postgres is Docker-Network-Only

**Postgres runs only inside Docker.** There is no host port mapping. Do not run Postgres on the host.

**Single flow:** All services (API, Postgres, Redis, monitoring, etc.) are defined in **`production/docker-compose.prod.yml`**. Root `docker-compose.yml` only `include:`s that file for legacy tooling. Use `./scripts/start.sh`, `./scripts/full_deploy.sh`, or `./scripts/stop.sh`. No host API in production.

## DATABASE_URL for Docker

Use the container hostname (resolves on Docker network only):

```
postgresql://rankingsbot_user:YOUR_PASSWORD@rankings-bot-postgres:5432/rankingsbot
```

The Postgres service is named `postgres` in Compose, but the **container name** is **`rankings-bot-postgres`**. Production `DATABASE_URL` uses `@rankings-bot-postgres:5432` (see `production/docker-compose.prod.yml`).

Replace `PASSWORD` with your `POSTGRES_PASSWORD`. The `:5432` is the container's internal port (not a host port).

**Data volume:** Compose maps the named volume **`rankings-bot_postgres_data`** (`external: true`) so existing databases survive stack recreates.

**Host-side scripts** (cron, manual): Use `backup_postgres.sh` and `restore_from_backup.sh`; they use `docker exec` when `DATABASE_URL` points at `rankings-bot-postgres`. Scripts like `populate_stops.sh` use `docker exec` for psql/pg_dump. Python scripts that need DB access (e.g. `ensure_super_admin.py`, `silent_stops_update.py`) must run inside the API container: `docker exec rankings-bot-api python scripts/SCRIPT.py`.

## Why

- Avoids confusion: host port refs suggest Postgres runs on the host.
- Prevents duplicate Postgres instances (one in Docker, one on host).
- Single source of truth: all DB access goes through the container.

## How to Access the Database

### Admin SQL (one-off commands)

```bash
docker exec rankings-bot-postgres psql -U rankingsbot_user -d rankingsbot -c "SELECT 1;"
```

### Interactive psql

```bash
docker exec -it rankings-bot-postgres psql -U rankingsbot_user -d rankingsbot
```

### Backups and Restores

Use `scripts/backup_postgres.sh` and `scripts/restore_from_backup.sh`. They use `docker exec` when Postgres is in Docker.

### Migrations

Run migrations **inside the running API container** (same image as production):

```bash
docker exec rankings-bot-api python -m alembic upgrade head
```

Avoid bind-mounting host Alembic over the image for routine upgrades; see **CONTAINER_DRIFT_PREVENTION.md**.
