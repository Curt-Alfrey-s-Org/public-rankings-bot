# Tournament History Scraper (Refactored)

> **Production note (2026):** The Python package `scrapers/tournament_history_scraper.py` was removed during the SQLite → PostgreSQL migration. **Settings → Admin → Sync tournament history** calls **`POST /api/tournament-history/refresh-past`** (super admin): it does **not** crawl WPBA/WPA sites; it rebuilds **`tournament_history`** / **`tournament_results`** from **`rankings`** (data already written by live rankings scrapers and Admin Refresh) and from **`fill_tournament_history_from_wpba_women_events`** (latest WPBA PDF snapshot). For JSON-on-disk CP archives, use **`POST /api/tournament-history/fill-from-cp-archives`**. See [BUTTON_REFRESH_ARCHITECTURE.md](BUTTON_REFRESH_ARCHITECTURE.md) and [SCRAPER_TO_UI_DATA_MAP.md](SCRAPER_TO_UI_DATA_MAP.md).

The tournament history scraper can **scrape past tournament results** from WPBA and WPA, including **player match scores**, **tournament placements (rankings)**, and optionally **Fargo rating at scrape time**.

## What it does

1. **Discovery** – Fetches WPBA and WPA event/calendar pages and finds past events with:
   - Event name, date range, location
   - Event URL (for result text)
   - Bracket URL when available (e.g. External Pool)

2. **Parsing** – For each event:
   - Fetches the event page and (if present) the bracket page
   - Extracts **champion**, **runner-up**, **final score** from page text
   - Parses **match scores** from bracket/results tables when available (e.g. External Pool HTML)
   - Builds **placements** (1st, 2nd, …) from parsed data

3. **Save** – Writes to Postgres:
   - `tournament_history` – event metadata, champion, runner_up, final_score, source_url, bracket_url
   - `tournament_results` – one row per player per tournament: placement, optional `fargo_rating_at_scrape`
   - `tournament_history_matches` – one row per match: operator/2, scores, winner, round, match_date

4. **Fargo** – If requested, looks up **current** Fargo rating for each player and stores it as `fargo_rating_at_scrape`. This is **not** historical Fargo at tournament time; it is the rating at scrape time for reference.

## Schema

- **tournament_history** – `tournament_id`, name, date, location, year, association, championship, champion, runner_up, final_score, status, prize_pool, source_url, bracket_url
- **tournament_results** – tournament_id, player_name, placement, points, **fargo_rating_at_scrape**, notes
- **tournament_history_matches** – tournament_id, operator_name, player2_name, operator_score, player2_score, winner_name, round_num, match_num, match_date, notes

See `database/schema_postgres.sql`.

## Usage

### Seed only (no web scrape)

Uses curated `TOURNAMENT_DATA` in the scraper (no HTTP):

```bash
python scripts/init_tournament_history.py
```

### Scrape past events from the web

```bash
# Discover and scrape WPBA + WPA past events
python scripts/scrape_tournament_history.py

# Attach current Fargo to each result row
python scripts/scrape_tournament_history.py --fargo

# Limit to first 5 events (for testing)
python scripts/scrape_tournament_history.py --limit 5

# Only WPBA or only WPA
python scripts/scrape_tournament_history.py --wpba-only
python scripts/scrape_tournament_history.py --wpa-only
```

### From the scraper module

```python
from database import engine
from scrapers.tournament_history_scraper import TournamentHistoryScraper

scraper = TournamentHistoryScraper(engine=engine)
scraper.init_tournament_tables()
# Seed from curated data
scraper.import_tournament_history()
# Scrape past events and save placements + matches (+ optional Fargo)
result = scraper.scrape_past_tournaments(wpba=True, wpa=True, attach_fargo=False, limit=None)
# result: {"saved": N, "errors": 0, "discovered": M}
```

## Modules

- **scrapers/tournament_history_discovery.py** – Discovers past (and optional future) events from WPBA/WPA pages; extracts event URL and bracket URL (e.g. External Pool).
- **scrapers/tournament_bracket_parser.py** – Fetches event/bracket pages; parses champion, runner-up, final score, and match table rows (External Pool-style HTML).
- **scrapers/tournament_history_scraper.py** – Orchestrates discovery → parse → save; seed import from `TOURNAMENT_DATA`; optional Fargo lookup and `fargo_rating_at_scrape`.

## Limitations

- **Bracket pages** – Many bracket UIs (e.g. External Pool) are JS-rendered; the parser uses HTML table patterns where available. If a page has no server-rendered table, match scores may be empty and only champion/runner-up from the event page are stored.
- **Historical Fargo** – Fargo API does not provide historical ratings. We only store **current** rating at scrape time as `fargo_rating_at_scrape` for reference.
- **Rate limits** – Discovery and bracket fetches use `scrapers.fetch_utils.get_with_retry`; use `--limit` to avoid hammering sites.

## API

Tournament history is exposed via:

- `GET /api/tournament-history/tournaments` – list (filter by year, association)
- `GET /api/tournament-history/tournaments/{tournament_id}` – detail + results + matches
- `GET /api/tournament-history/players/{player_name}/history` – player’s results
- `GET /api/tournament-history/statistics` – counts, years, associations
- `GET /api/tournament-history/search?q=...` – search by name/location/championship
- `GET /api/tournament-history/years` – available years
