# Bot Updating the Page

The **page** (probilliardssoftware.com/rankings-bot) shows data from **PostgreSQL**. The **bot** that updates that database is the **refresh script**: it scrapes WPBA and WPA and writes via `get_database_manager()` / Postgres. The API reads from the DB; the frontend refetches from the API every 30 seconds.

So for the page to keep updating:

1. **API is running** (so the page can load data) — see **docs/CONNECT_BOT.md**.
2. **Refresh runs periodically** (so the DB gets new data) — see below.

---

## Run refresh once (manual)

On the server:

```bash
cd ~/rankings-bot
python3 scripts/refresh_rankings.py
```

Optional verbose: `REFRESH_VERBOSE=1 python3 scripts/refresh_rankings.py`

---

## Run refresh on a schedule (cron)

So the bot keeps updating the page without you clicking “Refresh” in the UI:

1. **Crontab** (as the user that runs the API, e.g. `ansible`):

   ```bash
   crontab -e
   ```

   Add one of these (fix the path if your app is elsewhere):

   **Daily at 6:00 AM:**
   ```cron
   0 6 * * * /home/ansible/rankings-bot/scripts/cron_refresh_rankings.sh >> /home/ansible/rankings-bot/rankings-refresh.log 2>&1
   ```

   **Every 12 hours (6:00 and 18:00):**
   ```cron
   0 6,18 * * * /home/ansible/rankings-bot/scripts/cron_refresh_rankings.sh >> /home/ansible/rankings-bot/rankings-refresh.log 2>&1
   ```

2. **Make the script executable** (once):

   ```bash
   chmod +x /home/ansible/rankings-bot/scripts/cron_refresh_rankings.sh
   ```

3. **Create the log file** (optional):

   ```bash
   touch /home/ansible/rankings-bot/rankings-refresh.log
   ```

More options (e.g. systemd timer): **docs/SCHEDULED_REFRESH.md**.

---

## Summary

| What | Purpose |
|------|--------|
| **API** | Serves the page and reads from DB; must be running (port 8003). |
| **refresh_rankings.py** | Scrapes WPBA/WPA and updates DB; run manually or via cron. |
| **Cron** | Runs the refresh on a schedule so the page data stays up to date. |
