# Rankings Data Consolidation

This document describes the current data-management model for rankings, player ratings, and historical preservation.

## License and Country: Scraped Data Sole Source

**Policy:** License and country must come from scraped data (wpapool.com, archives). No fabrication.

- **One license per player** — found in scraped data (e.g. `data/wpa_archive/wpa_women_with_licenses_legacy.json`).
- **If scraped data has no license or country** → leave blank (NULL) in DB. Research missing cells manually later.
- **Never invent** license numbers or country values. `_normalize_display_row` does not fill license from name suffix.
- **Lock tables** (`player_license_locks`, `player_country_locks`) are seeded only from WPA authoritative snapshots.
- **Cross-system enrichment** (`enrich_cross_system_data.py`) copies from rankings to rankings — source remains scraped.

## Current Model (Source of Truth)

- `rankings` table is the source of truth for per-system leaderboard snapshots (`rank`, `points`, `snapshot_date`, per-event `source_data`).
- `players` table is the source of truth for cross-system player identity and live ratings (`fargo_score`, `fargo_robustness`, `alfa_rating`, `est_rating`).
- `player_license_locks` and `player_country_locks` tables are immutable identity sources once seeded from WPA authoritative snapshots.
- UI/API reads rankings and overlays player identity/ratings via name-normalized joins, so incomplete imports do not blank unrelated player metadata.

## Why This Model

Imports and scrapers arrive at different times and from different sources:

- WPA / WPBA ranking snapshots (points/rank order)
- Fargo dashboard/API sync (Fargo + robustness)
- App-calculated ratings (ALFA and EST)
- Manual/admin CSV imports

If one import is incomplete, the `players` table still preserves current rating/identity fields and the historical rows in `rankings` stay intact.

## Operational Scripts Added

### 1) Rebuild coherent "latest" snapshots

`scripts/rebuild_latest_snapshots.py`

- Dry run:
  - `python3 scripts/rebuild_latest_snapshots.py`
- Apply:
  - `python3 scripts/rebuild_latest_snapshots.py --apply`

Selection rule per `ranking_system`:
- Prefer latest snapshot.
- If latest row count is too small vs prior snapshot (`latest/previous < min_ratio`), fallback to previous snapshot.
- Default `min_ratio` is `0.70` (override with `--min-ratio`).

Writes:
- Archives any existing target-date rows to `rankings_archive` with `archive_reason='pre_update'`.
- Rewrites target-date snapshot rows from chosen source snapshot.
- Refreshes `mv_latest_rankings` when present.

### 2) Seed name-format aliases

`scripts/seed_name_aliases_from_rankings.py`

- Dry run:
  - `python3 scripts/seed_name_aliases_from_rankings.py`
- Apply:
  - `python3 scripts/seed_name_aliases_from_rankings.py --apply`

Behavior:
- Reads latest snapshots and finds:
  - names in `Last, First` form
  - legacy `Last First` rows that map to an existing `First Last` player with Fargo
- Upserts `player_name_aliases(scraped_name, canonical_name, ranking_system)` to help matching.

## Matching Improvements

Fargo update and API joins now handle:

- `First Last` <-> `Last, First`
- punctuation/hyphen differences
- diacritic-insensitive keys
- "last token first" fallback for legacy rows like `Kazakis Alexander` -> `Alexander Kazakis`
- strict staged-sync policy for complex names: only high-confidence matches are auto-filled; reduced-name guesses are left for manual review
- immutable identity policy: non-WPA writes cannot introduce/overwrite `license_number` or `country`; WPA snapshots seed locks and all systems reuse those locked values

The fallback is used both when updating `players` from Fargo sync and when reading rankings for UI display.

### Identity Resolution in save_rankings (Single Source of Truth)

When saving rankings, `postgres_manager.save_rankings()` resolves player identity before upserting into `players`:

1. **License lookup**: If `player_license_locks` has this license, use its canonical name.
2. **Name variants**: "Alexander Kazakis" and "Kazakis Alexander" map to the same person via `_generate_name_variants_for_lookup`.
3. **player_name_aliases**: Optional lookup by scraped_name + ranking_system for canonical name.
4. **Existing player match**: If found by license or name variants, reuse that `player_id` and first/last name (no duplicate rows).
5. **No fabricated data**: License is never invented; missing values remain NULL.

## Recommended Refresh Order

1. Rebuild current snapshots:
   - `python3 scripts/rebuild_latest_snapshots.py --apply`
2. Ensure player roster is populated from rankings:
   - `python3 scripts/populate_players_from_rankings.py`
3. Seed aliases (run after rebuild or Fargo refresh; improves Player Performance name resolution):
   - `python3 scripts/seed_name_aliases_from_rankings.py --apply`
4. Run Fargo refresh:
   - `python3 scripts/refresh_fargo.py`

Run `seed_name_aliases_from_rankings.py` regularly (e.g., in post-import or refresh pipelines) so Player Performance can resolve name variants via `player_name_aliases`.

## Verification Queries

- Core latest snapshot counts:
  - `SELECT ranking_system, MAX(snapshot_date), COUNT(*) ...`
- Coverage check (visible Fargo using players overlay):
  - compare `COUNT(*)` vs `COUNT(COALESCE(players.fargo_score, rankings.fargo_rating))`
- Name-format misses:
  - inspect latest rows where direct match is null but swapped-order match has data.
- Current manual-research list:
  - `docs/MISSING_PLAYER_DATA_TRACKER.md` and `reports/manual_data_needed_core_latest_*.csv`

## Notes

- ALFA and EST are app-calculated and should remain managed by app engines; not imported from external files.
- Est. Rating and ALFA are exposed as PRO-tier player features; admins/directors retain visibility for operations and verification.
- License number and country are treated as stable identity data and locked after authoritative WPA ingestion.
- Historical rows are preserved; rebuilding "latest" creates a coherent current snapshot without deleting prior history.
