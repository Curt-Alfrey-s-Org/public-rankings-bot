# Hot Streak Page: Change Log and Feature Documentation

**Last updated:** March 2026

This document records all changes made to the Hot Streak page (`/hot-streak`) across multiple enhancement phases.

---

## Overview

The Hot Streak page highlights players whose tournament placements have improved the most over a recent window. It answers: "Who is on the rise?"

---

## Phase 1: Placement Chart and Algorithm Refinement

### Algorithm Change (Past 4 → Past 3, Jump-Only)

**Before:** Hot streak considered the past 4 tournaments for all players.

**After:**
- **Lookback:** Past 3 tournaments only.
- **Eligibility:** Only players who **improved** (newest placement better than oldest) appear. Players on a decline or flat trend are excluded.
- **Sorting:** By "jump" (oldest placement minus newest placement), descending. Biggest jump = hottest.

### Placement Display (Chart Only, Numbers on Chart)

**Before:** Text list of placements (e.g., "44th, 44th, 32nd").

**After:**
- **Chart only:** Compact line chart in the "Recent Placements" column.
- **Numbers on chart:** Raw placement values (e.g., 44, 32, 12) shown on each point via `LabelList`.
- **Order:** Oldest on left, newest on right (matches time flow).

### Files Modified

- [rankings-bot/database/postgres_manager.py](rankings-bot/database/postgres_manager.py) — `get_hot_streak_players`: lookback=3, min_tournaments=3, jump-only logic, placements oldest-first.
- [rankings-bot/frontend/src/pages/HotStreak.tsx](rankings-bot/frontend/src/pages/HotStreak.tsx) — `PlacementChart` component (recharts), chart-only display.
- [rankings-bot/frontend/src/api/tournaments.ts](rankings-bot/frontend/src/api/tournaments.ts) — `getHotStreakPlayers` defaults: lookback=3, min_tournaments=3.

---

## Phase 2: Association Tabs

### Goal

Filter hot streak players by tournament association, matching the Rankings page tab pattern.

### Backend

- **Parameter:** `association: Optional[str] = None` added to `get_hot_streak_players`.
- **SQL filter:** When set, `AND COALESCE(NULLIF(TRIM(th.association), ''), 'WPA') ILIKE :association`.
- **API route:** `association: Optional[str] = Query(None, ...)` on `/hot-streak`.

### Frontend

- **Tabs:** All, WPBA, WPA Women, WPA Men, Heyball Men, Heyball Women, Artistic.
- **State:** `useState` for selected tab; pass `association` to API.
- **Query key:** `['hot_streak_players', 3, 3, association]` for per-tab caching.
- **Empty state:** "No players jumped in [Association] in the past 3 tournaments."

### Tab Configuration

| Tab ID       | Label        | Association Value   |
|-------------|--------------|---------------------|
| all         | All          | null                |
| wpba        | WPBA         | WPBA                |
| wpa_women   | WPA Women    | WPA Women           |
| wpa_men     | WPA Men      | WPA Men             |
| heyball_men | Heyball Men  | WPA Heyball Men     |
| heyball_women | Heyball Women | WPA Heyball Women |
| artistic    | Artistic     | WPA Artistic        |

### Files Modified

- [rankings-bot/database/postgres_manager.py](rankings-bot/database/postgres_manager.py) — association filter in SQL.
- [rankings-bot/api/routes/tournaments.py](rankings-bot/api/routes/tournaments.py) — association query param.
- [rankings-bot/frontend/src/api/tournaments.ts](rankings-bot/frontend/src/api/tournaments.ts) — `association` in params and query.
- [rankings-bot/frontend/src/pages/HotStreak.tsx](rankings-bot/frontend/src/pages/HotStreak.tsx) — tab UI, state, API call.

---

## Phase 3: Chart Tooltips and Fargo Chart

### Placement Chart Tooltip

**Before:** Tooltip showed "Tournament 1", "Tournament 2", etc.

**After:** Tooltip shows the **tournament name** at each point (from `tournament_history.name`).

### Data Structure Change for Placements

- **Before:** `last_placements: number[]` (e.g., `[44, 32, 12]`).
- **After:** `last_placements: Array<{placement: number; tournament_name: string}>`.

### Fargo Column: Number → Chart

**Before:** Single Fargo number per player.

**After:**
- **Fargo chart:** Line chart of Fargo score changes over time (same structure as placements: oldest left, newest right).
- **Data source:** `tournament_results.fargo_rating_at_scrape` — Fargo at each tournament in the same 3-tournament window.
- **Fallback:** If fewer than 2 Fargo points, show latest `fargo_score` or "—".
- **Color:** Sky/sky-500 to differentiate from placement chart (orange).

### Backend Changes

- **SQL:** Add `th.name AS tournament_name, tr.fargo_rating_at_scrape` to SELECT.
- **Grouping:** Store `(placement, date, tournament_name, fargo_at_scrape)` per row.
- **Output:**
  - `last_placements`: `[{placement, tournament_name}, ...]` (oldest-first).
  - `fargo_history`: `[{date, rating, tournament_name}, ...]` (oldest-first), only where `fargo_rating_at_scrape` is not null.

### API Model

- `HotStreakPlayerResponse.last_placements`: `List[Dict]` with `placement` and `tournament_name`.
- `HotStreakPlayerResponse.fargo_history`: `List[Dict]` with `date`, `rating`, `tournament_name`.

### Frontend Changes

- **PlacementChart:** Accept `placements: Array<{placement, tournament_name}>`; tooltip shows `tournament_name`.
- **FargoChart:** New component; props `fargoHistory`; tooltip shows tournament name and rating.
- **Table cell:** Render `FargoChart` when `fargo_history.length >= 2`, else show `fargo_score` or "—".

### Files Modified

- [rankings-bot/database/postgres_manager.py](rankings-bot/database/postgres_manager.py) — extended query, grouping, `last_placements` and `fargo_history` output.
- [rankings-bot/api/models/tournament_models.py](rankings-bot/api/models/tournament_models.py) — `HotStreakPlayerResponse` schema.
- [rankings-bot/frontend/src/api/tournaments.ts](rankings-bot/frontend/src/api/tournaments.ts) — types for `last_placements` and `fargo_history`.
- [rankings-bot/frontend/src/pages/HotStreak.tsx](rankings-bot/frontend/src/pages/HotStreak.tsx) — PlacementChart tooltip, FargoChart, table cell.

---

## Backward Compatibility

- **Legacy `last_placements`:** If API returns `number[]`, frontend can map to `[{placement: p, tournament_name: `Tournament ${i+1}`}]`.
- **Empty `fargo_history`:** Fall back to `fargo_score` when no history.

---

## Related Documentation

- [docs/INDEX.md](INDEX.md) — Documentation index.
- [docs/ROADMAP.md](ROADMAP.md) — Project roadmap.
- [.cursor/plans/hot_streak_association_tabs_f7ca1cf7.plan.md](../.cursor/plans/hot_streak_association_tabs_f7ca1cf7.plan.md) — Association tabs plan.
- [.cursor/plans/hot_streak_chart_enhancements_210de69f.plan.md](../.cursor/plans/hot_streak_chart_enhancements_210de69f.plan.md) — Chart tooltips and Fargo chart plan.

---

## Phase 4: Event-Based Streaks by Association (No Combined "All")

### Why this changed

The previous implementation could include synthetic rankings snapshot rows (`rankings_snapshot_*`) and allowed a player who dropped between events to remain listed if newest vs oldest was still improved.

### Backend behavior

- **Real events only:** Hot streak now excludes rankings snapshots and news/event placeholder rows, matching the Tournament History "real tournaments" filter.
- **Association scoped:** Query remains filtered by `association` (WPBA, WPA Women, WPA Men, etc.), and UI now always sends one association value.
- **Monotonic streak rule:** Across each player's last 3 events (oldest → newest), placements must never worsen at any step; and there must be overall improvement (newest better than oldest).
  - Included example: `8 → 4 → 2`
  - Excluded example: `8 → 4 → 5`

### Frontend behavior

- **Tabs:** Association tabs only (WPBA, WPA Women, WPA Men, Heyball Men, Heyball Women, Artistic). The combined **All** tab is removed.
- **Query key:** `['hot_streak_players', 3, 3, association]` to cache per association.
- **Copy update:** Page messaging now describes real-event streak logic and explicit streak break when placement worsens.

### Admin refresh linkage

- **WPBA PDF load:** `Load WPBA PDF` now also invalidates `hot_streak_players` queries so hot streak data refetches immediately after a successful load.

---

## Phase 5: Resilience (1 year vs career)

### Behavior

- **Rank hot streak table** still uses the last three real events for eligibility, trend (+ spots), and the placement sparkline.
- **Resilience** is computed separately on two windows for the same association: **last 365 days** (`resilience_1yr`) and **full career** (`resilience_career`). Each value is `null` if the player has fewer than two results in that window.
- Formula: 0–100 blend of bounce-back (latest finish vs worst in window), consistency of field-normalized finishes, latest-event strength, and normalized improvement from first to last in the window (`database/postgres_manager.py`).

### API / UI

- `HotStreakPlayerResponse`: `resilience_1yr`, `resilience_career` (optional floats); `resilience_score` removed.
- Hot Streak page: two columns and intro copy describing the split.
