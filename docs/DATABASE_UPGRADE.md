# Database & Platform Upgrade (Roadmap)

**Goal:** Use PostgreSQL only (SQLite has been fully removed) so we can scale (multi-instance, 1000+ users) and add HA later.

**Fresh start (no data migration):** To start from empty data, see **docs/FRESH_POSTGRES_UPGRADE.md**. Use env-based login and repopulate via refresh/scrapes.

## Current state (sources of truth)

| Store | Used by | How |
|-------|--------|-----|
| **PostgreSQL** (DATABASE_URL) | Rankings, tournaments, auth (User), org_metadata, media, etc. | `database/__init__.py` and `database.py` (re-exports). Docker: `postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot`. See docs/DOCKER_POSTGRES_ONLY.md. SQLite is no longer supported. |

**Read/write paths:** All data (auth, rankings, tournaments, media) uses the same Postgres database via the shared engine and `get_database_manager()` where applicable.


## Phases

### Phase 1: Postgres in Docker + DATABASE_URL (this PR)

- [x] Add Postgres service to `docker-compose.yml`; optional `docker-compose.override.yml` or env for local Postgres.
- [x] Document `DATABASE_URL=postgresql://user:pass@host:5432/dbname`; app uses it when set.
- [x] Make `database/__init__.py` Postgres-ready (engine from `DATABASE_URL`, no `check_same_thread` for non-SQLite).
- [x] Add `psycopg2-binary` to `requirements-api.txt`.
- [x] **SQLite removed:** App requires Postgres; `DATABASE_URL` must be a `postgresql://` URL. Docker: `postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot`.

### Phase 2: Rankings schema in Postgres

- [x] Add `database/schema_postgres.sql` (Postgres-compatible version of `schema.sql`).
- [x] Refactor `DatabaseManager` to accept optional `engine=` from `database.engine`; use shared engine when set (SQLite: raw_connection; Postgres: adapter with text() + named params).
- [x] Rankings routes and `get_db_connection()` / `get_db_manager()` use `get_database_manager()` (single source from `DATABASE_URL`).
- [x] Scripts: `scripts/refresh_rankings.py` uses `get_database_manager()`.
- [x] On startup (or migration), if using Postgres, ensure rankings tables exist (run schema_postgres.sql when `rankings` table missing). See `database.ensure_rankings_tables_postgres()` called from API lifespan.

### Phase 3: Data migration and scripts

- [x] Data is stored in Postgres only. For backups and restore, see **docs/POSTGRES_BACKUPS_AND_CUTOVER.md**.
- [x] Update `scripts/refresh_rankings.py`, `scripts/refresh_fargo.py`, `scripts/load_initial_data.py`, `scripts/init_tournament_history.py` to use `get_database_manager()` or `database.engine` (shared Postgres layer).
- [x] Run tests against Postgres (CI or local with `DATABASE_URL` set). See **docs/TESTS_AGAINST_POSTGRES.md** and the **postgres-tests** job in `.github/workflows/tests.yml`.

### Phase 4: Backups and cutover

- [x] Document and automate Postgres backups (`pg_dump` or volume snapshots); test restore. See **docs/POSTGRES_BACKUPS_AND_CUTOVER.md**.
- [x] Production cutover: set `DATABASE_URL` on host/Compose, migrate data, switch. Steps documented in **docs/POSTGRES_BACKUPS_AND_CUTOVER.md**.

### Later (optional)

- HA: managed Postgres (RDS/Cloud SQL) or primary+standby; multiple app replicas; Redis Sentinel if needed.

## Standards and manuals

Per project rule (`.cursor/rules/standard-driven-changes.mdc`): follow official manuals when publicly available. For this upgrade:

- **SQLAlchemy 2**: Prefer [SQLAlchemy 2.0 docs](https://docs.sqlalchemy.org/en/20/) — use `engine.connect()`, `text()`, and bound parameters; long-term target is `Result.mappings()` and explicit `text()` throughout instead of a cursor-style adapter.
- **PostgreSQL**: Use [PostgreSQL documentation](https://www.postgresql.org/docs/) for schema (e.g. `schema_postgres.sql`) and operations.
- **Docker**: Follow [Postgres image docs](https://hub.docker.com/_/postgres) for Compose and env.

## References

- [OWASP Database Security](https://cheatsheetseries.owasp.org/cheatsheets/Database_Security_Cheat_Sheet.html)
- [PostgreSQL Docker](https://hub.docker.com/_/postgres)
- Project rule: `.cursor/rules/standard-driven-changes.mdc` (map sources, follow manuals, then implement).
