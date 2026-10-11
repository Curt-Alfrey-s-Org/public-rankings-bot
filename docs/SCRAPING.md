# Rankings Bot - Scraping Architecture

This document explains the scraping architecture, data schema, and troubleshooting guide for the Rankings Bot.

## Overview

The Rankings Bot scrapes player rankings from multiple associations:
- **WPBA** (Women's Professional Billiard Association) -- PDF format
- **WPA Men / WPA Women** -- Web HTML format
- **WPA Heyball Men / Heyball Women** -- Web HTML format
- **WPA Artistic** -- PDF format
- **Fargo** -- Materialized from `players.fargo_score` (not an external scrape)

### Dedicated association entrypoints

Orchestration (`scripts/refresh_rankings.py`) calls one module per association/division for clarity and timeouts:

| Module | Role |
|--------|------|
| `scrapers/wpba_rankings_scraper.py` | WPBA |
| `scrapers/wpa_men_scraper.py` | WPA Men |
| `scrapers/wpa_women_scraper.py` | WPA Women |
| `scrapers/wpa_heyball_men_scraper.py` | Heyball Men |
| `scrapers/wpa_heyball_women_scraper.py` | Heyball Women |
| `scrapers/wpa_artistic_scraper.py` | Artistic |
| `scrapers/fargo_rankings_scraper.py` | Materialize `fargo_rankings` from `players.fargo_score` |

Snapshots are written to the legacy `rankings` table and mirrored into per-association physical tables (Alembic `049_*`).

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│               scripts/refresh_rankings.py                    │
│              (Main Orchestrator & CLI)                       │
└───────────────────┬──────────────────┬──────────────────────┘
                    │                  │
        ┌───────────▼─────────┐   ┌───▼──────────────┐
        │  WPBA Scraper       │   │  WPA Scrapers    │
        │  (PDF Parser)       │   │  (Web + PDF)     │
        └───────────┬─────────┘   └───┬──────────────┘
                    │                  │
                    └──────────┬───────┘
                               │
                    ┌──────────▼──────────┐
                    │  Database Manager   │
                    │   (PostgreSQL)       │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │    API Endpoints    │
                    │   (FastAPI REST)    │
                    └─────────────────────┘
```

### 1. WPBA Scraper (`scrapers/wpba_scraper.py`, entrypoint: `scrapers/wpba_rankings_scraper.py`)

**Purpose**: Extract rankings from WPBA PDF documents

**How it works**:
1. Downloads PDF from WPBA website (discovered from wpba.com/rankings)
2. Parses PDF using `pdfplumber`
3. **Primary**: Table extraction with `text` column-detection strategy -- preserves column positions so blank cells (tournaments not played) correctly map to zero points. A phantom-column detection step removes artifact columns from the text strategy.
4. **Secondary**: Text-line regex parsing when table extraction returns nothing
5. Returns structured data with rolling-10 totals (most recent 10 tournaments) and per-tournament columns for split buttons

**Data extracted**:
- Rank (integer)
- Player name (string)
- Points (float, rolling-10 sum from most recent 10 tournaments when tournament columns present)
- Stops played (integer)
- Per-tournament point columns (e.g. Iron City VI, Jacoby 2025) in `source_data`

**Error handling**:
- Network errors: Raises (retried via `@retry_with_backoff`)
- HTTP 403/404: Raises `NonRetryableError`
- Invalid data: Skips malformed entries

**Rate limits and retries** (shared): Both scrapers use `scrapers/fetch_utils.get_with_retry()`:
- Retries on **429** (rate limit), **502**, **503**, **504** (transient server errors)
- Up to 3 attempts with exponential backoff (2s, 4s, 8s); honors **Retry-After** header when present
- Timeouts and connection errors are also retried with the same backoff
- On final failure the scraper logs and returns an empty list

### 2. WPA Scraper (`scrapers/wpa_scraper.py`)

**Purpose**: Extract rankings from WPA website

**How it works**:
1. Fetches HTML page using `requests.Session`
2. Parses HTML using `BeautifulSoup4`
3. Extracts table data or structured divs
4. **Invocation**: Scrapers run when called from the API, CLI scripts, or tests — the API does not schedule ranking HTML/PDF scrapes on a timer (see `api/services/background_scheduler.py`).
5. **File saving**: Saves scraped data to `scraped_data/wpa/` subfolder
6. Returns structured data as list of dictionaries

**Data extracted**:
- Rank (integer)
- Player name (string)
- Points (float)
- Country (string)
- License (when present)
- **All other table columns** (event/tournament point columns) as extra keys; persisted in DB **`source_data`**
- **`wpa_column_labels`**: per row, a dict mapping **normalized header key** → **original header text** (for friendly labels in dynamic tournament lists)

**Post-save pipeline (Men / Women)**:
- `split_wpa_men_to_column_buttons` / `split_wpa_women_to_column_buttons` create **`WPA_Men_*` / `WPA_Women_*`** rows from hardcoded mappings **plus** columns discovered in the snapshot; columns with **no non-zero points** are skipped (preserves existing per-event data).
- API: **`GET /api/rankings/wpa-men-tournament-systems`** and **`GET /api/rankings/wpa-women-tournament-systems`** drive Rankings page submenu buttons — each returns the **10 most recent** active event columns, **sorted newest-first** (same rolling-window idea as **`/api/rankings/wpba-tournament-systems`**). See **docs/WPA_RANKINGS_DATA_FLOW.md**.

**Divisions scraped**:
- **WPA Women** - Women's professional rankings
- **WPA Men** - Men's professional rankings
- **Heyball Women** - Women's Heyball rankings
- **Heyball Men** - Men's Heyball rankings
- **Artistic Pool** - Artistic pool professional rankings

**Error handling**:
- Network errors: Returns empty list with retry logic
- Parsing errors: Tries multiple strategies for different HTML structures
- Invalid data: Validates and skips malformed entries

**Rate limiting**:
- Uses session with User-Agent header
- Respects standard HTTP timeout (30 seconds default)
- Implements polite scraping practices

### 3. External Pool tournament harvester (`scrapers/externalpool_tournament_harvester.py`)

**Purpose**: Enrich local `tournament_history` from the [external pool site](https://digitalpool.com/tournaments) (GraphQL at `api-nyc.digitalpool.com`): event/bracket URLs, `tournament_history_matches`, and archived tab payloads.

**Matching**:
- Builds several `ilike` patterns: the full normalized name first, then distinctive keywords. The first date window is not abandoned just because 12 events already came back.
- A candidate is written only when the fuzzy score is at least `EXTERNALPOOL_MATCH_MIN_SCORE` (default **0.35**), the years in the two names agree when both names contain a year, and the event name contains a distinctive word from the local name. The words open, championship, world, pool, and billiards do not count. Date proximity is not added to the score. A start date more than 120 days away is refused.
- Inside that event, the division is the tournament whose name passes the same token and year checks. The completed division with the most bracket rows is not used when its name fails those checks.
- Ollama only reviews a near miss. A model error does not create a link, and a confident model answer still has to pass the token and year checks.

**Docker / tuning**: `EXTERNALPOOL_MATCH_MIN_SCORE`, `EXTERNALPOOL_SEARCH_LIMIT`, and `EXTERNALPOOL_TAB_ARCHIVE_DIR`. See `docs/ENV_VARS.md`.

**External Pool tab coverage (GraphQL)**:
- The public SPA loads bracket, live scores, matches, schedule, players, stats, and performance from the same Hasura tables: `tournament_players`, `tournament_brackets`, and `matches` (`division_id` = tournament id). The harvester does **not** rely on separate tab-only GraphQL operations for coverage; it persists explicit per-tab slices (`tab_schedule`, `tab_live_scores`, `tab_stats`, `tab_performance`) derived from those lists via `build_tab_views_from_graphql`, so archives and the API mirror the site tabs.
- **Slug harvest** (no fuzzy event match): resolve `tournaments(where: {slug: {_eq: $slug}})` then pull players/brackets/matches. Examples:
  - Archive JSON only (no local `tournament_history` row):  
    `python3 scripts/scrape_externalpool_tournaments.py --slug 2026-wpba-classics-players-championship`
  - Link to a local row and upsert URLs / results / matches: add `--local-tournament-id <tournament_id>`.
  - With both slug and local id, `--archive-only` skips DB updates and only writes JSON.

**Browser fallback**: Not required for the public GraphQL API. If data were only available in rendered HTML, use a dedicated script (e.g. Selenium-based patterns in `scripts/scrape_externalpool_selenium.py`) with timeouts and logging; keep that path separate from the default GraphQL harvester.

**WPBA PDF events** (`tournament_id` prefix `wpba_evt_`): PDF-derived `tournament_results` points/placements are **not** overwritten; External Pool data still fills bracket URLs and match rows.

### 4. Database Manager (`database/postgres_manager.py`)

**Purpose**: Store and retrieve rankings data

**Key methods**:
- `save_wpba_rankings(data)` - Save WPBA rankings snapshot
- `save_wpa_rankings(data)` - Save WPA rankings snapshot
- `get_wpba_rankings(limit)` - Retrieve latest WPBA rankings
- `get_wpa_rankings(limit)` - Retrieve latest WPA rankings
- `get_wpa_men_tournament_systems()` / `get_wpa_women_tournament_systems()` - Dynamic menu payload for WPA per-event buttons
- `get_ranking_history(player_name, association)` - Get player history

**Features**:
- Upsert logic (INSERT OR REPLACE) prevents duplicates
- Timestamp tracking for each snapshot
- Indexed queries for fast retrieval
- Transaction support for data integrity

### 5. Main Orchestrator (`scripts/refresh_rankings.py`)

**Purpose**: CLI entry point for scraping operations

**Usage**:
```bash
# Refresh all associations (WPBA + WPA divisions + Fargo)
python3 scripts/refresh_rankings.py

# Refresh only WPBA
python3 scripts/refresh_rankings.py --wpba-only

# Refresh only WPA (+ artistic)
python3 scripts/refresh_rankings.py --wpa-only

# Force refresh (ignore staleness check)
python3 scripts/refresh_rankings.py --force
```

**Features**:
- Independent error handling per scraper (one failure doesn't stop the other)
- Per-scraper timeouts via `REFRESH_SCRAPER_TIMEOUT_SEC` (default 180s)
- Parallel WPBA and WPA scraping with `ThreadPoolExecutor`
- Return codes for automation (0 = success, 1 = all scrapers failed)

## Data Schema

### Rankings Table

```sql
CREATE TABLE rankings (
    id SERIAL PRIMARY KEY,
    player_name VARCHAR(512) NOT NULL,
    ranking_system VARCHAR(256) NOT NULL,
    rank INTEGER NOT NULL,
    points DOUBLE PRECISION NOT NULL DEFAULT 0,
    country VARCHAR(255),
    license_number VARCHAR(255),
    stops_played INTEGER,
    snapshot_date DATE NOT NULL,
    source_data JSONB,
    position INTEGER,
    fargo_rating DOUBLE PRECISION,
    alfa_rating DOUBLE PRECISION,
    fargo_robustness INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (ranking_system, snapshot_date, position)
);
```

Per-association physical tables (`wpba_rankings`, `fargo_rankings`, `wpa_men_rankings`, `wpa_women_rankings`, `heyball_men_rankings`, `heyball_women_rankings`, `artistic_rankings`) share this same schema and are populated via mirroring after each save. See Alembic migration `049_*`.

### Indexes

```sql
CREATE INDEX ix_rankings_system_snap ON rankings (ranking_system, snapshot_date DESC);
CREATE INDEX ix_rankings_player ON rankings (player_name);
```

### Data Validation Rules

- **Rank**: Must be positive integer (1-1000)
- **Points**: Must be non-negative float
- **Player name**: Must be non-empty string
- **Country**: Optional, 2-3 letter code or full name
- **Snapshot date**: ISO 8601 format (YYYY-MM-DD)

## API Endpoints

### GET /api/rankings/wpba

Get WPBA rankings with pagination.

**Query parameters**:
- `limit` (default: 100, max: 1000) - Number of rankings to return
- `offset` (default: 0) - Number of rankings to skip

**Response**:
```json
{
  "total": 150,
  "limit": 100,
  "offset": 0,
  "count": 100,
  "rankings": [
    {
      "name": "Player Name",
      "rank": 1,
      "points": 1500.0,
      "country": null,
      "date": "2024-02-02"
    }
  ],
  "association": "WPBA"
}
```

### GET /api/rankings/wpa

Get WPA rankings with pagination.

**Query parameters**: Same as WPBA

**Response**: Same structure as WPBA, with country field populated

### GET /api/rankings/player/{player_name}

Get player data from both associations.

**Response**:
```json
{
  "player_name": "Kristina Tkach",
  "wpba": {
    "current": {
      "date": "2024-02-02",
      "rank": 1,
      "points": 132750.0
    },
    "history": [...]
  },
  "wpa": {
    "current": null,
    "history": []
  }
}
```

### POST /api/rankings/refresh

Trigger manual refresh of rankings.

**Response**:
```json
{
  "timestamp": "2024-02-02T12:00:00",
  "wpba": {
    "success": true,
    "count": 150,
    "error": null
  },
  "wpa": {
    "success": true,
    "count": 200,
    "error": null
  }
}
```

### GET /api/rankings/last-update

Get last successful scrape timestamp.

**Response**:
```json
{
  "wpba": "2024-02-02",
  "wpa": "2024-02-02"
}
```

## Error Detection & Validation

### Validation Checks

1. **Data structure validation**: Verify required fields exist
2. **Rank range check**: Ensure ranks are in reasonable range (1-1000)
3. **Points validation**: Verify points are numeric and non-negative
4. **Name validation**: Check for empty or malformed player names
5. **Count validation**: Alert if scraped count is significantly lower than expected

### Error Logging

All errors are logged to `logs/scraper_errors.log` with:
- Timestamp
- Error level (ERROR, WARNING, INFO)
- Source (WPBA, WPA, Database)
- Detailed error message
- Stack trace for exceptions

### Example log entry:
```
2024-02-02 12:00:00 - scrapers.wpba_scraper - ERROR - Error fetching WPBA PDF: HTTPSConnectionPool...
```

Log files are created with pattern `scraper_YYYYMMDD_HHMMSS.log` in the `logs/` directory.

## Troubleshooting

### Common Issues

#### 1. Network Errors

**Symptom**: "Failed to resolve hostname" or "Connection timeout"

**Solutions**:
- Check internet connection
- Verify firewall/proxy settings
- Try increasing timeout value
- Check if source website is accessible

#### 2. PDF Parsing Errors

**Symptom**: "No rankings data scraped" from WPBA

**Solutions**:
- Verify PDF URL is accessible
- Check if PDF format has changed
- Try downloading PDF manually to inspect structure
- Update regex patterns if format changed

#### 3. HTML Parsing Errors

**Symptom**: "Could not find rankings structure" from WPA

**Solutions**:
- Check if website structure has changed
- Verify User-Agent is accepted
- Try accessing website in browser
- Update BeautifulSoup selectors if needed

#### 4. Database Errors

**Symptom**: "Database locked" or "Unable to write"

**Solutions**:
- Close other connections to database
- Check file permissions
- Ensure database directory is writable
- Try reinitializing database

#### 5. No Data in API Responses

**Symptom**: Empty arrays returned by API

**Solutions**:
- Run scraper manually: `python3 scripts/refresh_rankings.py --force`
- Check database connection: `psql $DATABASE_URL -c "SELECT COUNT(*) FROM rankings;"`
- Verify database has data: `psql $DATABASE_URL -c "SELECT COUNT(*) FROM rankings;"`
- Check API logs for errors

## Rate Limiting & Ethical Scraping

### Best Practices

1. **Respect robots.txt**: Check site's robots.txt file
2. **Use appropriate User-Agent**: Identify your bot clearly
3. **Implement delays**: Don't overwhelm servers
4. **Cache responses**: Avoid re-scraping unchanged data
5. **Handle errors gracefully**: Don't retry infinitely
6. **Monitor bandwidth**: Be aware of data usage

### Current Implementation

- User-Agent header set to identify as bot
- Single request per scrape (no pagination spam)
- 30-second timeout prevents hanging
- Exponential backoff on errors (future enhancement)
- Caching of unchanged data (future enhancement)

### Rate Limit Guidelines

- **WPBA PDF**: Max 1 request per hour (PDF doesn't change frequently)
- **WPA Website**: Max 1 request per 5 minutes (reasonable update frequency)

## Performance Considerations

### Optimization Strategies

1. **Connection pooling**: Reuse HTTP connections
2. **Parallel scraping**: Run WPBA and WPA scrapers concurrently
3. **Database indexing**: Fast queries on common patterns
4. **Caching**: Store parsed results temporarily
5. **Incremental updates**: Only fetch changed data

### Current Performance

- WPBA PDF scrape: ~5-10 seconds
- WPA web scrape: ~2-5 seconds
- Database save: ~100ms for 200 players
- Total scrape time: ~8-15 seconds for both sources

## Testing

### Unit Tests

Located in `tests/backend/test_scrapers.py`

Run with:
```bash
python3 tests/backend/test_scrapers.py
```

Tests cover:
- Scraper initialization
- Mock HTTP/PDF responses
- Error handling
- Data validation

### Integration Tests

Located in `test_scrapers_manual.py`

Run with:
```bash
python3 test_scrapers_manual.py
```

Tests actual scraping from live sources (requires network access).

### Database Tests

Located in `test_database.py`

Run with:
```bash
python3 test_database.py
```

Tests all database operations with temporary test database.

## Maintenance

### Regular Tasks

1. **Monitor scraper health**: Check logs daily
2. **Verify data quality**: Spot-check rankings weekly
3. **Update dependencies**: Keep libraries current
4. **Test after updates**: Run tests after any changes
5. **Backup database**: Regular Postgres backups via `scripts/backup_postgres.sh`

### Updating Scrapers

If source formats change:

1. Update regex patterns or CSS selectors
2. Test with actual data
3. Update tests to match new format
4. Document changes in git commit

## Security Considerations

### Data Privacy

- No personal data stored beyond publicly available rankings
- No authentication credentials in code
- Database can be encrypted at rest

### Input Validation

- All user inputs sanitized
- SQL injection prevention via parameterized queries
- No execution of arbitrary code

### Network Security

- HTTPS only for external requests
- Certificate verification enabled
- Timeout limits prevent DoS

## Future Enhancements

1. **Retry logic**: Exponential backoff for failed requests
2. **Change detection**: Only process if data changed
3. **Email alerts**: Notify on scraping failures
4. **Metrics dashboard**: Track scraping statistics
5. **Historical analysis**: Trend analysis and predictions
6. **Multi-threading**: Parallel scraping for speed
7. **Webhook support**: Notify external systems on updates

## Support

For issues or questions:
1. Check this documentation first
2. Review logs in `logs/` directory
3. Run tests to isolate problem
4. Check GitHub issues for similar problems
5. Open new issue with logs and error messages
