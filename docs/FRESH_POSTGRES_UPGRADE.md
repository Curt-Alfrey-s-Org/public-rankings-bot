# Fresh Postgres Upgrade (Start from Scratch)

Use this path when you want to **fully switch to Postgres and start with empty data**. No migration from SQLite; all data will be recreated by the app (scrapes, manual input, env-based users).

## Steps

1. **Start PostgreSQL** (e.g. Docker):
   ```bash
   docker compose up -d postgres
   ```
   Or use an existing Postgres instance. Create a database if needed, e.g. `createdb rankings`.

2. **Set `DATABASE_URL`** to your Postgres URL and **do not** set any SQLite path:
   ```bash
   export DATABASE_URL=postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot
   ```

3. **Start the API.** On first run with Postgres:
   - Auth/ORM tables are created from `Base.metadata.create_all` (users, sessions, etc.).
   - Rankings and tournament tables are created from `schema_postgres.sql` and `schema_tournament_postgres.sql` when the corresponding tables are missing.

4. **Log in with env-based users** (no DB users yet):
   - **Super admin:** `SUPER_ADMIN_USERNAME` / `SUPER_ADMIN_PASSWORD` (username defaults to `tornybotca1`; there is **no default password**, and production refuses to start without `SUPER_ADMIN_PASSWORD` on a fresh DB).
   - **Admin:** `ADMIN_USERNAME` / `ADMIN_PASSWORD`
   - **Director:** `DIRECTOR_USERNAME` / `DIRECTOR_PASSWORD`
   - **User:** `USER_USERNAME` / `USER_PASSWORD`  
   Set these in `.env` or the environment before starting the API.

5. **Repopulate data as needed:**
   - Run **Refresh rankings** (WPBA/WPA) from the UI or `scripts/refresh_rankings.py` to pull rankings into Postgres.
   - Use **FARGO sync/import** and **tournament** features as normal; they work with Postgres.
   - Create additional users via the app (admin/director/user) once logged in as admin/super_admin.

## What runs on Postgres

- **Auth:** Same DB (engine from `DATABASE_URL`). Login uses env credentials and/or DB users.
- **Rankings:** Stored in Postgres; refresh and history work as before.
- **FARGO:** Sync and import use Postgres when `DATABASE_URL` is Postgres.
- **Tournaments:** Tournament manager and scrape-hometowns use Postgres when `DATABASE_URL` is Postgres.

## No migration script

You are **not** copying data from another database. The app uses Postgres only; data is created via scrapes, manual input, and env-based users.

## Backups

After going live, set up Postgres backups (e.g. `scripts/backup_postgres.sh` and cron). See **docs/POSTGRES_BACKUPS_AND_CUTOVER.md**.
