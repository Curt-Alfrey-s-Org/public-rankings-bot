# Rankings Table Design

How the `rankings` table stores data: **first-class columns** for core fields and **`source_data` JSONB** for full source columns, following flexible-schema practices.

## Design

- **First-class columns:** `player_name`, `ranking_system`, `rank`, `points`, `country`, `license_number`, `stops_played`, `snapshot_date`, **`position`**, plus enriched fields (e.g. `fargo_rating`, `alfa_rating`). These are dedicated table columns and used for filtering, sorting, and display.
- **`position` (list order):** 1-based index in the list (1, 2, 3, …). Unique key is `(ranking_system, snapshot_date, position)` so the stored list matches the import 1:1. **`rank`** can have ties (e.g. 51, 51, 53) as in WPA/Heyball/WPBA/Artistic; position is always unique.
- **`source_data` (JSONB):** All other columns from each source (scrapers, PDF/CSV import) are stored in a single JSONB column. This preserves the full row from the source without adding a new table column for every possible field.

**References:**

- PostgreSQL JSONB: [PostgreSQL docs — JSON Types](https://www.postgresql.org/docs/current/datatype-json.html)
- Project standards: [.github/CODING_STANDARDS.md](../.github/CODING_STANDARDS.md) (e.g. PostgreSQL best practices, JSONB usage)

## Source column coverage

- **Heyball:** Can store all 18 columns; extras go into `source_data`.
- **WPA Men / WPA Women / WPBA PDF:** All available columns from the scrape or import are stored; first-class fields are in dedicated columns, the rest in `source_data`. WPA HTML rows also carry **`wpa_column_labels`** in `source_data` (header display names). Per-event **`WPA_Men_*` / `WPA_Women_*`** systems are produced by split logic that merges **hardcoded column mappings** with **discovered** numeric keys in the snapshot (see **docs/WPA_RANKINGS_DATA_FLOW.md**).

The **overall buttons** (WPBA Women, WPA Men, WPA Women, Heyball, Artistic) use **strict columns** matching a consistent layout: Rank, Name, Country, License, Fargo, Points. Per-tournament columns from `source_data` are **not** included in the overall API response; they are served only via the per-tournament buttons (`WPBA_Women_*`, `WPA_Men_*`, etc.).

## Code paths

| Layer | Where | What |
|-------|--------|------|
| **Save** | `database/postgres_manager.py` → `save_rankings` | Splits each row into first-class columns vs `source_data`; inserts/upserts with `source_data::jsonb`. |
| **Read** | `database/postgres_manager.py` → `get_rankings_paginated` | Selects first-class columns + `source_data`; merges `source_data` into each row so the API returns one flat object per ranking. |
| **Scrapers / import** | `scrapers/wpa_scraper.py`, `scrapers/wpba_scraper.py`, `api/parsers/rankings_import.py` | Build full row dicts; `save_rankings` does the split. |
| **Frontend** | `frontend/src/components/RankingsTable.tsx`, `frontend/src/api/rankings.ts` | Table builds column list from first row keys (known columns + extras from API); API type allows `[key: string]` for `source_data`-sourced fields. |

## Migration

- **`source_data` column:** Added in `alembic/versions/026_add_rankings_source_data.py`.
- **`position` column and unique on (ranking_system, snapshot_date, position):** Added in `alembic/versions/028_rankings_position_for_ties.py`. Supports tied ranks; display order is by `position`.

## Future: live scorekeeper and live updates

When scores are entered during a current tournament (score keeper), rankings updates should use the **same** `save_rankings` path: build the list in the desired order, assign **position = 1, 2, 3, …** from that order, and call `save_rankings` with the same (system, snapshot_date). Fargo rating and points/rankings recalculated after every game (live updates) will feed into this list; the same position-based uniqueness keeps the displayed list matching the computed order.
