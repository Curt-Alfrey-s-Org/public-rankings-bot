# Running Tests Against PostgreSQL

To validate the app and tests against Postgres instead of SQLite:

1. **Start Postgres** (e.g. via Docker):
   ```bash
   docker compose up -d postgres
   ```
   Or use an existing Postgres instance.

2. **Create a test database** (if needed):
   ```bash
   createdb -h localhost -U postgres rankings_test
   ```
   Or with Docker: `docker exec -it <postgres_container> psql -U postgres -c "CREATE DATABASE rankings_test;"`

3. **Set DATABASE_URL** and run pytest:
   ```bash
   export DATABASE_URL=postgresql://postgres:change-me@localhost:5432/rankings_test
   pytest tests/ -v
   ```
   Use the same user/password/host as your Postgres setup.

4. **CI:** The **postgres-tests** job in `.github/workflows/tests.yml` runs tests against Postgres: it starts a Postgres 16 service, sets `DATABASE_URL`, and runs `tests/backend/test_database.py` and `tests/test_health_check.py`. The test `TestPostgresWhenConfigured.test_postgres_connect_and_rankings_table` calls `ensure_rankings_tables_postgres()` so the schema is applied during the test run.

Schema is applied automatically when the API starts with Postgres (`ensure_rankings_tables_postgres()`), or by the Postgres CI test above.
