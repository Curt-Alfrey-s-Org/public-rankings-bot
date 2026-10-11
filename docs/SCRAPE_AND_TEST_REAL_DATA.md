# Scrape and Test with Real Data

Use real WPBA/WPA (and optional Fargo) data for local or CI testing.

## One command

From the **Rankings-Bot** project root (directory that contains `scripts/` and `database/`):

```bash
./scripts/scrape_and_test.sh
```

This will:

1. **Scrape WPBA + WPA rankings** via `scripts/refresh_rankings.py` (real data from live sources) and save to your Postgres DB (`DATABASE_URL`).
2. **Optionally run Fargo sync** for WPBA and WPA (set `SKIP_FARGO=1` to skip for a faster run).
3. **Run tests** for `tests/backend/test_database.py` and `tests/test_health_check.py`.

## Prerequisites

- Python deps installed (`pip install -r requirements-api.txt` etc.).
- For **Postgres**: set `DATABASE_URL=postgresql://user:pass@host:5432/dbname` and ensure the DB is running and schema is applied (API startup or `ensure_rankings_tables_postgres()`).
- Network access so scrapers can reach WPBA/WPA (and Fargo) sources.

## Options

| Env var | Effect |
|--------|--------|
| `REFRESH_VERBOSE=1` | Verbose scraper logs (default on for this script). |
| `SKIP_FARGO=1` | Skip Fargo sync (faster run). |
| `DATABASE_URL` | Postgres URL (required). Docker: `postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot`. See docs/DOCKER_POSTGRES_ONLY.md. |

## Manual steps (same result)

```bash
# 1. Scrape rankings
REFRESH_VERBOSE=1 python3 scripts/refresh_rankings.py

# 2. (Optional) Fargo
REFRESH_VERBOSE=1 python3 scripts/refresh_fargo.py

# 3. Tests
pytest tests/backend/test_database.py tests/test_health_check.py -v
```

## Verify in the API

After scraping, start the API and check:

- `GET /api/health` — healthy.
- `GET /api/rankings?org=WPBA` — returns scraped WPBA rankings.
- `GET /api/rankings?org=WPA` — returns scraped WPA rankings.

Or use the frontend: Rankings page, switch WPBA/WPA tabs.
