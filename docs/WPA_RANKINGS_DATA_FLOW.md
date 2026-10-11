# WPA Men / Women rankings data flow (HTML → DB → UI)

This complements [WPBA_DATA_FLOW.md](WPBA_DATA_FLOW.md). WPBA uses a **PDF** with fixed rotating columns; WPA uses **HTML tables** on [wpapool.com/rankings/](https://wpapool.com/rankings/) where **header text becomes normalized keys** on each row.

## Ingestion

1. **`scrapers/wpa_scraper.py`** — `WPAScraper.scrape_rankings(division='Men'|'Women'|...)`:
   - Men = first `<table>`, Women = second (same page).
   - All non–first-class cells are kept on the row dict; `save_rankings` stores extras in **`source_data`** (JSONB).
   - Each row includes **`wpa_column_labels`**: map from normalized header key → original header text (for display labels when building dynamic tournament lists).

2. **Save** — `save_wpa_rankings()` → `save_rankings()` with `ranking_type` `WPA_Men` or `WPA_Women`. For those systems, **`points`** can be aligned with the sum of numeric event columns (`_sum_all_event_points`).

## Split (per-event `ranking_system` rows)

After each refresh, **`split_wpa_men_to_column_buttons()`** and **`split_wpa_women_to_column_buttons()`** in `database/postgres_manager.py`:

- Start from hardcoded **`WPA_MEN_COLUMN_MAPPING`** / **`WPA_WOMEN_COLUMN_MAPPING`** (stable `ranking_system` names and labels).
- **Merge** with **discovered** numeric columns present in the latest snapshot (same idea as WPBA’s `_get_wpba_column_mapping_with_discovered`).
- **Active columns only**: columns where at least one player has points **> 0** are written; all-zero columns are **skipped** so existing per-event snapshots are not wiped.
- **Cap (split)**: `WPA_MEN_WOMEN_EVENT_COLUMN_LIMIT` (default 25) limits how many tournaments are processed when writing per-event `ranking_system` rows (same headroom pattern as WPBA split vs menu).
- **Men snapshot selection**: splits use the latest `WPA_Men` snapshot that has **8-ball-related keys** in `source_data` (`get_latest_snapshot_with_8ball_data`), so multi-discipline tables stay consistent with CP 8-ball flows.

Each per-event system is still **`WPA_Men_*` / `WPA_Women_*`** with **`ranking_system` VARCHAR(32)**.

## Fargo propagation

After split, **`copy_fargo_from_wpa_men_to_cp_systems`** / **`copy_fargo_from_wpa_women_to_cp_systems`** copy Fargo from the overall snapshot into CP targets and **all** `WPA_Men_*` / `WPA_Women_*` systems found in the DB (hardcoded list **plus** distinct child systems from SQL), so dynamically added tournaments still receive Fargo.

## API (Rankings page menus)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/rankings/wpa-men-tournament-systems` | `{ systems: [{ ranking_system, label }] }` for WPA Men drill menu — the **10 most recent** active event columns (where at least one player has points > 0), **ordered newest-first** (year descending, then base mapping order). If fewer than 10 columns have points, the list is shorter. Constant: `RANKINGS_MENU_RECENT_TOURNAMENT_LIMIT`. Same rolling-window idea as WPBA’s `wpba-tournament-systems` and [10_TOURNAMENT_RULE.md](10_TOURNAMENT_RULE.md). |
| `GET /api/rankings/wpa-women-tournament-systems` | Same for WPA Women. The UI prepends the overall row as a separate button. |
| `GET /api/rankings/by-system/{ranking_system}` | Paginated rows for each per-event system |

On failure, tournament-systems endpoints return **`200`** with `systems: []` and optional `degraded` (same pattern as WPBA).

**`GET /api/rankings/by-system/...`** sets **`association`** and **`division`** from the path (e.g. `WPA_Women_*` → Women, `WPBA_Women_*` → WPBA).

## Frontend

- **`frontend/src/pages/Rankings.tsx`** — WPA Men / Women submenu leaves are loaded from the two tournament-systems endpoints (like WPBA’s `wpba-tournament-systems`).
- **`frontend/src/pages/SettingsAdmin.tsx`** — After full rankings refresh or WPA scraper run, React Query invalidates `wpa-men-tournament-systems` and `wpa-women-tournament-systems` so menus stay in sync.

## Super-admin WPA scraper run

`POST /api/rankings/scrapers/wpa/run` uses a **dict** keyed by `women`, `men`, `heyball_men`, `heyball_women`, `artistic`; each non-empty division is saved and the matching **split** helper runs (WPA Men/Women/Heyball/Artistic).

## Related docs

- [SCRAPING.md](SCRAPING.md) — scraper overview
- [RANKINGS_TABLE_DESIGN.md](RANKINGS_TABLE_DESIGN.md) — `rankings` + `source_data`
- [HOW_DATA_IS_UPDATED.md](HOW_DATA_IS_UPDATED.md) — refresh and UI invalidation
