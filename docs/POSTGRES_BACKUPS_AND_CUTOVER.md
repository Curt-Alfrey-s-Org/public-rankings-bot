# Postgres Backups and Production Cutover

## Quick start (Linux server)

1. **Run one backup** (Postgres must be running). The script loads `.env` from the project root. Postgres is Docker-network-only; when `DATABASE_URL` points at `postgres` or `rankings-bot-postgres`, the script uses `docker exec` automatically.
   ```bash
   cd /home/ansible/rankings-bot/Rankings-Bot
   ./scripts/backup_postgres.sh
   ```
   Output: `Backed up to backups/rankings_YYYYMMDD_HHMM.dump`. Override with `DATABASE_URL=...` or `BACKUP_DIR=...` if needed.

2. **Add cron** (daily at 2:00 AM): `crontab -e`, then add. Use `DATABASE_URL` pointing at `postgres` or `rankings-bot-postgres` so the script uses `docker exec` (see `scripts/cron_backup_postgres.example`).
   ```cron
   0 2 * * * cd /home/ansible/rankings-bot/Rankings-Bot && DATABASE_URL='postgresql://rankingsbot_user:PASSWORD@postgres:5432/rankingsbot' ./scripts/backup_postgres.sh >> backup_postgres.log 2>&1
   ```
   Replace `PASSWORD` with your `POSTGRES_PASSWORD`. The script auto-uses `docker exec` when host is `postgres` or `rankings-bot-postgres`.

**If you see "pg_dump not found":** Install the PostgreSQL client on the server: `sudo apt install postgresql-client` (Debian/Ubuntu).

## Backups

- **Logical backup (recommended):** Use `scripts/backup_postgres.sh` (reads `.env`, uses `docker exec` when Postgres is in Docker). Manual example:
  ```bash
  docker exec rankings-bot-postgres pg_dump -U rankingsbot_user -Fc rankingsbot -f /tmp/rankings.dump
  docker cp rankings-bot-postgres:/tmp/rankings.dump ./rankings_$(date +%Y%m%d_%H%M).dump
  ```
  Restore: `./scripts/restore_from_backup.sh --docker backups/rankings_YYYYMMDD_HHMM.dump`. See [DOCKER_POSTGRES_ONLY.md](DOCKER_POSTGRES_ONLY.md).

- **Automation:** Run `pg_dump` on a schedule (cron or CI), store dumps in a safe location (e.g. S3, backup volume). Use **scripts/backup_postgres.sh** (reads `DATABASE_URL`, writes to `BACKUP_DIR`) and **scripts/cron_backup_postgres.example** for a cron example. Optionally use a managed Postgres backup feature (RDS, Cloud SQL) if you move to a managed service.

- **Where dumps are stored:** Default `BACKUP_DIR` is the project root `backups/` (e.g. `Rankings-Bot/backups`). Override with `BACKUP_DIR=/path/to/dumps ./scripts/backup_postgres.sh`. Filenames: `rankings_YYYYMMDD_HHMM.dump`.

- **Volume snapshots:** If Postgres data is on a single volume, snapshot that volume for point-in-time recovery where supported; prefer `pg_dump` for portability and single-DB restores.

- **Test restore:** Periodically restore a dump to a spare DB and run a quick smoke check (e.g. API health, one rankings request) to confirm backups are usable.

## Production cutover

1. **Pre-cutover:** Postgres is running; schema applied (API startup or manual); backups of Postgres are in place.
2. **Config:** Set `DATABASE_URL=postgresql://...` for the API (Compose env or host env).
3. **Restart API:** Restart the API (and any workers) so they use Postgres.
4. **Verify:** Hit health and rankings endpoints; confirm data and no 5xx.

If something goes wrong, restore from a Postgres backup and fix `DATABASE_URL` or schema as needed.
