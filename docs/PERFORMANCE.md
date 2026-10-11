# Rankings Bot API — Performance

## 1. Uvicorn workers (multiple processes)

- **Production (systemd):** Use `--workers 4` for 6+ core hosts. See `docs/rankings-bot-api.service.example` (UVICORN_WORKERS=4).
- **Docker:** `docker-compose.yml` runs API with `--workers 4`.
- **Effect:** More concurrent requests; faster under load. Postgres handles concurrent writes.
- **Usage:**  
  - Dev (reload): `./scripts/start_api.sh` → 1 worker with `--reload`.  
  - Prod: systemd service or `API_WORKERS=4 ./scripts/start_api.sh` (no systemd).

## 2. Database connection pool

- **SQLAlchemy pool:** `SQLALCHEMY_POOL_SIZE=10`, `SQLALCHEMY_MAX_OVERFLOW=15` for production (4 workers). See `docs/ENV_VARS.md`.
- **One `DatabaseManager` per worker process:** Created on first use and reused for all requests in that process.
- **Effect:** Less overhead per request; pool sized for concurrent workers. Postgres handles concurrent access.

## 3. Cache read-heavy endpoints

- **Cached:** `GET /api/rankings/`, `GET /api/rankings/wpba`, `GET /api/rankings/wpa` (in-memory per worker).
- **Invalidation:** On `POST /api/rankings/refresh`, a version file is updated and in-process cache is cleared. All workers see the new version on their next GET and refetch from DB.
- **Effect:** Repeated reads are served from cache; DB and server do less work per request.

## 4. Refresh serialized

- **Only one `POST /api/rankings/refresh` at a time:** File lock (`rankings_refresh.lock`) ensures a single refresh runs across all workers.
- **If lock is held:** Returns `409 Conflict` with detail "Refresh already in progress. Try again shortly."
- **Effect:** Avoids SQLite write contention and keeps refresh behavior predictable.
