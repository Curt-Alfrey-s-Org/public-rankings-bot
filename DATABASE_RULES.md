# Database Architecture Rules

## CRITICAL: PostgreSQL Only - NO SQLite (ENFORCED)

**Effective Date:** February 23, 2026  
**Enforcement:** Required for all commits

### Rule: No SQLite Under Any Circumstance

#### ✅ ALLOWED
- PostgreSQL (psycopg2, asyncpg, SQLAlchemy with psycopg2)
- PostgreSQL schema files (`schema_tournament_postgres.sql`, `schema_*.sql` that target Postgres)
- Testing with Postgres fixtures (use test containers or test databases)
- SQL files that create/modify Postgres tables

#### ❌ FORBIDDEN
- `import sqlite3`
- `sqlite:///` connection strings
- `.db` file database (except in documentation/comments explaining historical context)
- `schema_tournament_management.sql` (or any SQLite-specific schema files)
- `DatabaseManager(db_path=...)` instantiation with SQLite
- Fallback logic that uses SQLite if Postgres unavailable
- Any new test database that isn't Postgres

### Why

1. **Data Consistency:** All tournament data (tournaments, matches, games, tournament_players) lives in one Postgres instance
2. **Production Deployment:** Postgres is the only database container in docker-compose; SQLite files cannot be backed up or replicated
3. **API Expectations:** FastAPI routes expect Postgres connection strings (DATABASE_URL with psycopg2 driver)
4. **Concurrency:** Postgres handles concurrent requests; SQLite write-locks cause race conditions

### For Developers

**If you see SQLite code:**
1. Refactor to use Postgres (see `api/tournament_manager.py` for examples)
2. Use `psycopg2` or `asyncpg` directly, or SQLAlchemy with Postgres backend
3. Contact tech lead if migration is complex

**Test Database?**
- Use Postgres test container (Docker) or fixture with test database on Postgres instance
- Example: See `/home/ansible/rankings-bot/conftest.py` for pytest fixture patterns

### Verification Checklist

Before committing:
```bash
# Check for SQLite imports
grep -r "import sqlite" rankings-bot/api rankings-bot/database --include="*.py"
# Should return: (no results)

# Check for sqlite:// connection strings
grep -r "sqlite://" rankings-bot --include="*.py" --include="*.yml" --include=".env*"
# Should return: (no results only in comments/docs)

# Check for .db file references in active code
grep -r "\.db" rankings-bot/api rankings-bot/database --include="*.py" | grep -v "test_" | grep -v "#"
# Should return: (only in schema filenames, not database paths)
```

### One-Time Cleanup (July 2026)

- Removed SQLite artifacts from repo: `database/schema_tournament_management.sql`, `scripts/init_db.sh`, stale `DATABASE_STATUS.md`
- Audited `probilliards` and `apps` clones: **no** `*.db` / `rankings.db` / `bot_auth.db` files on disk (Postgres-only runtime confirmed)
- Production data is in Docker volume `rankings-bot_postgres_data` on `probilliards`; backup via `scripts/backup_postgres.sh` (`.dump`, not SQLite)

### Questions?

If a feature requires database access, ask:
- "Is this Postgres schema defined in `schema_tournament_postgres.sql`?"
- "Does the API use `DATABASE_URL` (Postgres) or hardcoded SQLite path?"
- "Can I test this with a Postgres test fixture?"

If the answer to any is "no", refactor before implementing.
