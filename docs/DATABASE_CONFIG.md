# Database configuration — rankings-bot

This doc describes how the bot uses PostgreSQL and how to keep schema and config correct.

## Single database (Postgres only)

All application data lives in one PostgreSQL instance:

- **Config:** `DATABASE_URL` (required; see `.env.example`). Docker Compose sets `postgresql://...@rankings-bot-postgres:5432/...` on the internal network ([DOCKER_POSTGRES_ONLY.md](DOCKER_POSTGRES_ONLY.md)).
- **Test Center (optional):** `TEST_CENTER_DATABASE_URL` — separate Postgres database for isolated `test_*` tournament tables.
- **Code:** `database` package (`database/__init__.py`) — SQLAlchemy engine, sessions, `get_database_manager()` → `PostgresManager`.
- **Tables:** ORM models (`users`, auth, payments, …) plus rankings/tournament tables in the same database. Rankings use first-class columns plus `source_data` JSONB ([RANKINGS_TABLE_DESIGN.md](RANKINGS_TABLE_DESIGN.md)).

SQLite (`.db` files, `database/db_manager.py`, `schema_tournament_management.sql`) was removed in July 2026. There is no `DATABASE_PATH` or file-based fallback.

## Consistency

- **Docker:** Compose sets `DATABASE_URL=postgresql://...@postgres:5432/...`. Postgres is Docker-network-only (no host port). Use `docker exec rankings-bot-postgres psql ...` for admin SQL. See [DOCKER_POSTGRES_ONLY.md](DOCKER_POSTGRES_ONLY.md).
- **Migrations:** Alembic uses the same engine as the app (`from database import engine` in `alembic/env.py`). Set `DATABASE_URL` (or `.env`) before running `alembic upgrade head` so migrations apply to the correct DB file.

## Source data (source_data)

The `rankings` table uses **first-class columns** for core fields (e.g. `player_name`, `rank`, `points`, `country`, `license_number`, `stops_played`, `snapshot_date`) and a **`source_data` JSONB** column for all other columns from each source (Heyball 18 cols, WPA Men/Women, WPBA PDF). This keeps the schema stable while storing full source rows. The API merges `source_data` into each ranking row so the UI can show columns dynamically. See [RANKINGS_TABLE_DESIGN.md](RANKINGS_TABLE_DESIGN.md) for design details and code paths.

## Schema verification

From project root:

```bash
source venv/bin/activate
python scripts/verify_db_schema.py
```

This checks that ORM tables and columns match the models. Fix any reported issues by running pending migrations:

```bash
alembic upgrade head
```

## Migrations

- **Location:** `alembic/versions/`.  
- **Current revision:** `alembic current`.  
- **Apply all:** `alembic upgrade head`.  
- **Create new (after model change):** `alembic revision -m "description"` then edit the new file.

## Required env (for login and DB)

- **Auth:** `JWT_SECRET` (required). Login uses the database only; user/password in env are optional (bootstrap-only). See **docs/AUTH_DESIGN.md**.
- **DB:** `DATABASE_URL` (Postgres only; Docker compose sets `postgresql://...@postgres:5432/...`).
- See `.env.example` and **docs/AUTH_DESIGN.md** for optional bootstrap vars.
