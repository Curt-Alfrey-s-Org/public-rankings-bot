# Performance Tuning — Max Performance Configuration

Applied per industry standards (Twelve-Factor, FastAPI deployment, CODING_STANDARDS.md).
For hosts with 6+ cores and 32GB RAM.

## Summary of Applied Changes

| Component | Setting | Value | Where |
|-----------|---------|-------|-------|
| **API (Uvicorn)** | Workers | 4 | systemd example, docker-compose |
| **SQLAlchemy** | Pool size | 10 | docker-compose env, ENV_VARS.md |
| **SQLAlchemy** | Max overflow | 15 | docker-compose env |
| **SQLAlchemy** | Pool recycle | 1800s | ENV_VARS.md |
| **PostgreSQL** | shared_buffers | 2GB | docker-compose postgres command |
| **PostgreSQL** | effective_cache_size | 8GB | postgres-performance.conf (reference) |
| **PostgreSQL** | work_mem | 64MB | docker-compose |
| **PostgreSQL** | maintenance_work_mem | 512MB | docker-compose |
| **Celery** | Concurrency | 4 | docker-compose |
| **Fargo** | Batch size | 25 | docker-compose |
| **Fargo** | Batch delay | 0.5s | docker-compose |

## Applying to Production (Host API)

1. **Systemd:** Copy `docs/rankings-bot-api.service.example` to `/etc/systemd/system/rankings-bot-api.service`. It includes `UVICORN_WORKERS=4` and `--workers $UVICORN_WORKERS`.
2. **Environment:** Add to `.env` (or systemd `Environment=`):
   ```
   SQLALCHEMY_POOL_SIZE=10
   SQLALCHEMY_MAX_OVERFLOW=15
   SQLALCHEMY_POOL_RECYCLE=1800
   ```
3. **Restart:** `sudo systemctl daemon-reload && sudo systemctl restart rankings-bot-api`

## Applying to Docker

Tuning lives in **`production/docker-compose.prod.yml`** (single production stack). From repo root:

```bash
docker compose --env-file .env --env-file .env.compose-host-user -f production/docker-compose.prod.yml up -d
```

Postgres tuning is applied via `command` in the postgres service when present. No manual config needed for defaults.

## Override for Smaller Hosts

- **Uvicorn workers:** Set `UVICORN_WORKERS=2` in systemd or edit docker-compose `command`.
- **Postgres:** Remove or reduce `shared_buffers` in docker-compose if RAM < 16GB.
- **Celery:** Change `--concurrency=4` to `2` in docker-compose.

## Cache and live updates

The app defaults to **live-update** behavior (short cache TTLs, frequent refetch) because it is not I/O- or CPU-heavy. Backend: `CACHE_TTL_SECONDS=60`, `RANKINGS_CACHE_TTL_SECONDS=60`. Frontend: React Query `staleTime: 0`, `refetchOnWindowFocus: true`, and 15–30s `refetchInterval` on key pages. To reduce server load, increase TTLs via env (see [DEPENDENCIES.md](DEPENDENCIES.md)).

## References

- [DEPENDENCIES.md](DEPENDENCIES.md) — All deps and live-update env vars
- [ENV_VARS.md](ENV_VARS.md) — All environment variables
- [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) — Nginx + host API flow
