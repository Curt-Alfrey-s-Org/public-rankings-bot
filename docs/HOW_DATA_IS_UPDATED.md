# How rankings data is updated

This doc confirms how data changes (Refresh, Data Input, tournament import, scrapers) and what to do so the UI shows updates.

---

## Quick checklist

- **Built-in scheduler:** APScheduler starts with no scraper jobs (`api/services/background_scheduler.py`). Rankings and tournament scrapes run only when triggered (Admin Refresh or `scripts/refresh_rankings.py`). Fargo ratings change only through a manual CSV import. Set **`SKIP_BACKGROUND_SCHEDULER=1`** to skip starting the empty scheduler.
- **Startup:** Rankings refresh if stale (>12h) or missing; tournament history populated if empty. Set **`SKIP_STARTUP_REFRESH=1`** to disable (e.g. tests).
- **Cron (optional backup):** **`scripts/refresh_rankings.py`** when API is down (see **docs/SCHEDULED_REFRESH.md**).
- **Historical rankings:** `refresh_rankings.py` also scrapes WPA previous-ranking page and WPBA historical PDFs. Use year tabs on the Rankings page to view past years.
- **Data Input / tournament import:** After import, **confirm** the import and run **Update rankings** so the main rankings tables are updated.
- **License + country are immutable:** Identity values are locked from WPA authoritative snapshots. Non-WPA imports cannot overwrite them, and manual row edit does not allow changing `license_number` or `country`.
- **Admin correction flow:** Use admin identity lock endpoints to unlock/relock a specific player when a trusted correction is needed (`/api/admin/identity-locks/unlock`, `/api/admin/identity-locks/relock`, `/api/admin/identity-locks/enforce-wpa`).
- **Immediate UI refresh:** Use Admin **Refresh** in Settings or on the Rankings page (Admin only). **Admin Refresh is rate-limited:** max **1 per 5 minutes**; if exceeded, the API returns **429** and asks you to wait; check API logs for errors (429, 500).
- **WPA Men/Women tournament menus:** After refresh or WPA scraper run, the UI refetches **`wpa-men-tournament-systems`** and **`wpa-women-tournament-systems`** so per-event buttons match the DB (same pattern as WPBA). See **docs/WPA_RANKINGS_DATA_FLOW.md**.
- **Tournament history sync (super admin):** In **Settings → Admin**, **Sync tournament history** runs **`POST /api/tournament-history/refresh-past`**. It does **not** scrape the web; it copies/sculpts **`tournament_history`** from **`rankings`** (already filled by live scrapers) and refreshes WPBA Women per-event rows from the latest PDF snapshot. Run live scrapers or **Load WPBA PDF** first. Disk JSON archives: **`POST /api/tournament-history/fill-from-cp-archives`** separately.
- **Fargo:** Fargo ratings are updated via manual CSV imports. Use the `/api/fargo/import` endpoint or `scripts/import_fargo_csv.py` with an official FargoRate spreadsheet. See **docs/FARGO_LOOKUP.md**.

---

## Ways data changes

| Source | What it does | How to see it in the UI |
|--------|----------------|-------------------------|
| **Built-in scheduler** | APScheduler starts with no scraper jobs. There is no 30 min / 2 h / 24 h Fargo auto-refresh. | UI refetches rankings every 1 min, last-update every 30 s. Data changes when a manual refresh or CSV import runs. |
| **Startup refresh** | On API start, background rankings refresh runs if data stale (>12h) or missing. Tournament history populated if empty. | After restart, wait 1–2 min; Rankings shows updated data. |
| **Admin Refresh** | Manual trigger for WPBA/WPA scrapers. **Rate-limited:** 1 per 5 minutes. | Use **Refresh** in Settings or Rankings page (Admin only). |
| **Cron (optional)** | `scripts/refresh_rankings.py` runs when API is down. | Backup only. Normal updates are Admin Refresh or this script. |
| **Data Input** | Directors/Admins add or edit rows (rank, name, points) or upload files (CSV, XLSX, etc.). `license_number` and `country` are WPA-locked and cannot be edited manually. | After import, **confirm** the import and run **Update rankings** so the main rankings tables are updated. Then the Rankings page will show changes on its next refetch (up to ~1 min) or use Admin Refresh for immediate refetch. |
| **Tournament import** | Tournament results are imported; then they must be applied to rankings. | **Confirm** the tournament import and run **Update rankings** (Data Input / tournament flow). Then rankings list and last-update will reflect the new data on next refetch or after Admin Refresh. |

---

## Data Input / tournament imports: confirm and Update rankings

- Imports (manual rows or file upload, or tournament imports) are not live in the main rankings view until:
  1. The import is **confirmed** (e.g. in Data Input or tournament import UI).
  2. **Update rankings** has been run so the rankings tables are recalculated/updated.
- After that, the Rankings page will show the new data within its refetch interval (**1 minute**) or immediately if an Admin clicks **Refresh**.

---

## Scrapers: cron should run refresh inside the API container

- For automatic updates from WPBA/WPA sources, use cron (or systemd) to run **`scripts/refresh_rankings.py` inside `rankings-bot-api`** (`docker compose exec`), not bare host Python, unless Postgres is published to the host. See **docs/RANKINGS_REFRESH_RUNBOOK.md** and **docs/SCHEDULED_REFRESH.md**.
- **Hourly (recommended) example:** `0 * * * * cd /path/to/rankings-bot/production && docker compose -f docker-compose.prod.yml exec -T rankings-bot-api python3 scripts/refresh_rankings.py --force >> /var/log/rankings-refresh.log 2>&1` (see **docs/RANKINGS_REFRESH_RUNBOOK.md** if WPA scrape returns empty.)
- **Fargo** ratings are updated via manual CSV imports (see below).
- **Which scraper updates which pages?** See **[SCRAPER_TO_UI_DATA_MAP.md](SCRAPER_TO_UI_DATA_MAP.md)** for the full entrypoint-to-page matrix, including why Admin Refresh does not update Heyball/Artistic rankings.

---

## Admin Refresh rate limit

- **Limit:** 1 refresh per **5 minutes** (300 seconds). Enforced by **api/rate_limiter.py** on `POST /api/rankings/refresh`.
- **When exceeded:** The API returns **429** with a message like “Refresh endpoint rate limited. Please wait X seconds before retrying.” The frontend may show an error; wait the indicated time and try again.
- **Logs:** Check API logs for “Refresh rate limit exceeded” if you see 429 in the browser Network tab.

---

## Immediate UI refresh

- **Admin Refresh:** In the app, use the **Refresh** action in **Settings** or on the **Rankings** page (Admin only). This triggers a refetch so updated data appears right away (subject to the 5‑minute rate limit above).
- **Otherwise:** The Rankings page refetches the list every **1 minute** and the last-update timestamp every **30 seconds**; **refetchOnWindowFocus** is on so switching back to the tab triggers a refetch. So updates can take up to ~1 minute to appear without clicking Refresh.

---

## If updates still don’t appear

- **Host `python3 scripts/refresh_rankings.py` fails with “could not translate host name postgres” (or similar):** The script is running on the **host** with a container-only DB hostname. Use **`docker compose exec rankings-bot-api`** as in **docs/RANKINGS_REFRESH_RUNBOOK.md**, or point `DATABASE_URL` at a host-reachable Postgres only if you expose the port on purpose.
- **Check API logs** for errors (e.g. 429 rate limit, 500 server error) on refresh or scrape:
  - Host API: `tail -f rankings-api.log` in project root, or `journalctl -u rankings-bot-api -f` if using systemd.
  - Docker API: `docker logs -f rankings-bot-api`.
- **Check refresh responses:** In the browser DevTools → Network, trigger Refresh and look for failed or non-200 responses (429, 500, etc.). Fix rate limits or server errors so the backend can return updated data.

---

## Refetch intervals (frontend)

| What | Interval |
|------|----------|
| Rankings list (WPBA/WPA) | 1 minute |
| Last-update timestamp | 30 seconds |
| Sidebar health | 10 seconds |

**refetchOnWindowFocus** is enabled for rankings and last-update so switching back to the tab refetches (efficient: refetch when user returns instead of only polling). These intervals are tuned for efficiency: minimal requests while staying responsive. Admin **Refresh** bypasses the interval and refetches immediately.

**Note:** `staleTime` does not block `refetchInterval`; when the query is active, React Query will refetch on the interval even if data is still "fresh."

---

## Fargo: Manual CSV Import

- **Where:** Provide a CSV file (e.g. from FargoRate LMS) to the `POST /api/fargo/import` endpoint, or run `python3 scripts/import_fargo_csv.py <path_to_csv>`.
- **What it does:** Reads the CSV mapping (Player Name, Fargo Rating, Robustness), safely normalizes the names, and overlays the ratings into the **Postgres** `players` table (`fargo_score`, `fargo_robustness`, `fargo_last_updated`).
- **Why:** Replaces the old slow and error-prone Selenium scraper. It guarantees exact matches and skips rate limits entirely.
