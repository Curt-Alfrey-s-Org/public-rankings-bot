# Scheduled Rankings Refresh

Rankings data can be refreshed automatically using a cron job or a systemd timer. This keeps WPBA and WPA data up to date without using the web app’s **Refresh** button.

**Important:** On the standard Docker stack, Postgres is reachable from **`rankings-bot-api`** (and other containers) as `rankings-bot-postgres`, **not** from the host OS under that hostname. See **[docs/RANKINGS_REFRESH_RUNBOOK.md](RANKINGS_REFRESH_RUNBOOK.md)** for why host `python3 scripts/refresh_rankings.py` often fails and the **recommended `docker compose exec`** commands.

## Script

- **Script:** `scripts/refresh_rankings.py`
- **Runs:** WPBA and WPA scrapers, then saves results to the database (PostgreSQL).
- **Docker production stack:** Run the script **inside** `rankings-bot-api` so `DATABASE_URL` matches the running API. See **docs/RANKINGS_REFRESH_RUNBOOK.md**.
- **Host-only Python:** Only valid if Postgres is published to the host and `DATABASE_URL` uses `127.0.0.1` (or a real host/IP) — **not** the default in `production/docker-compose.prod.yml`.
- **Exit code:** `0` on success, `1` if refresh failed (useful for cron alerts).

### Recommended: cron via Docker Compose (production file)

Run from a directory where Compose can find `production/docker-compose.prod.yml` (adjust path):

```bash
cd /path/to/rankings-bot/production
docker compose -f docker-compose.prod.yml exec -T rankings-bot-api \
  python3 scripts/refresh_rankings.py --force
```

Optional verbosity (inside the container env):

```bash
docker compose -f docker-compose.prod.yml exec -T -e REFRESH_VERBOSE=1 rankings-bot-api \
  python3 scripts/refresh_rankings.py --force
```

WPA-only:

```bash
docker compose -f docker-compose.prod.yml exec -T rankings-bot-api \
  python3 scripts/refresh_rankings.py --wpa-only --force
```

---

## Cron (Linux Mint / server)

Example: refresh every day at 6:00 AM.

1. Open crontab:
   ```bash
   crontab -e
   ```

2. Add a line using **`docker compose exec`** (replace paths; `-T` avoids TTY issues under cron):
   ```cron
   0 6 * * * cd /path/to/rankings-bot/production && docker compose -f docker-compose.prod.yml exec -T rankings-bot-api python3 scripts/refresh_rankings.py --force >> /var/log/rankings-refresh.log 2>&1
   ```

3. **To run every hour** (recommended; WPBA/WPA sources usually update daily; avoids rate limits):
   ```cron
   0 * * * * cd /path/to/rankings-bot/production && docker compose -f docker-compose.prod.yml exec -T rankings-bot-api python3 scripts/refresh_rankings.py --force >> /var/log/rankings-refresh.log 2>&1
   ```

4. To run every 15–30 minutes (fresher data; still avoids hitting sources every minute):
   ```cron
   */15 * * * * cd /path/to/rankings-bot/production && docker compose -f docker-compose.prod.yml exec -T rankings-bot-api python3 scripts/refresh_rankings.py --force >> /var/log/rankings-refresh.log 2>&1
   ```

5. To run every 1 minute (only if you have a strong reason, e.g. frequent manual imports; risks rate limits from WPBA/WPA):
   ```cron
   * * * * * cd /path/to/rankings-bot/production && docker compose -f docker-compose.prod.yml exec -T rankings-bot-api python3 scripts/refresh_rankings.py --force >> /var/log/rankings-refresh.log 2>&1
   ```

6. To run every 12 hours:
   ```cron
   0 6,18 * * * cd /path/to/rankings-bot/production && docker compose -f docker-compose.prod.yml exec -T rankings-bot-api python3 scripts/refresh_rankings.py --force >> /var/log/rankings-refresh.log 2>&1
   ```

Use the same user that runs the API (e.g. `ansible` on the server) so paths and permissions match. Create the log file if needed:

```bash
sudo touch /var/log/rankings-refresh.log
sudo chown ansible:ansible /var/log/rankings-refresh.log
```

---

## Systemd timer (optional)

For a systemd-based setup (e.g. on a server):

1. **Service** — create `/etc/systemd/system/rankings-refresh.service`:

   ```ini
   [Unit]
   Description=Rankings Bot - refresh WPBA/WPA data
   After=network-online.target
   Wants=network-online.target

   [Service]
   Type=oneshot
   User=ansible
   WorkingDirectory=/home/ansible/rankings-bot/production
   ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml exec -T rankings-bot-api python3 scripts/refresh_rankings.py --force
   Environment=REFRESH_VERBOSE=1

   [Install]
   WantedBy=multi-user.target
   ```

   Adjust `User`, `WorkingDirectory`, and paths to match your install.

2. **Timer** — create `/etc/systemd/system/rankings-refresh.timer`:

   ```ini
   [Unit]
   Description=Run rankings refresh daily

   [Timer]
   OnCalendar=*-*-* 06:00:00
   Persistent=true

   [Install]
   WantedBy=timers.target
   ```

3. Enable and start the timer:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable rankings-refresh.timer
   sudo systemctl start rankings-refresh.timer
   sudo systemctl list-timers
   ```

4. Run once manually to test:
   ```bash
   sudo systemctl start rankings-refresh.service
   ```

---

## Summary

| Method      | Use case                    |
|------------|-----------------------------|
| **Cron**   | Simple, one-liner, any user. Recommended: **hourly** (`0 * * * *`) or every **15–30 min**; avoid every 1 min unless you have a strong reason (rate limits). |
| **Systemd**| Server with systemd, logs via journal |

Both invoke `scripts/refresh_rankings.py` **inside** `rankings-bot-api` so the DB host resolves. For host vs container context and maintenance mode, see **docs/RANKINGS_REFRESH_RUNBOOK.md**. For Data Input, tournament import, and UI refresh, see **docs/HOW_DATA_IS_UPDATED.md**.
