# WPBA Tournament — Single Source of Truth (SSOT) & Leaderboard wiring

**Status:** WPBA complete (June 2026). WPA/Heyball cleaned too — see
[`WPA_TOURNAMENT_SSOT.md`](WPA_TOURNAMENT_SSOT.md) (it's HTML-sourced, so the model differs).

This document records the WPBA tournament-data refactor: what the canonical data is,
which writers are allowed to touch it, how the Leaderboard "tournaments played" /
finishes are computed, and the one **known source limitation** that still caps
per-event detail. Read this before doing the equivalent WPA work — the same
pipeline shape and the same traps apply.

Code references are to `database/postgres_manager.py` and `scrapers/wpba_scraper.py`.

---

## 1. Canonical model (what is the truth)

| Concept | Source of truth | Where it lives |
|---|---|---|
| Current standings (points, rank, country, license, **stops played**) | WPBA Women PDF (`ranking_system = 'WPBA_Women'`) | `rankings` table |
| Per-event point breakdown (rolling 10 + rotating 11th) | WPBA Women PDF columns | `rankings.source_data` + `WPBA_Women_*` per-event systems |
| **Completed** WPBA events (for History / Leaderboard finishes / Hot Streak) | Derived from the PDF rolling columns | `tournament_history` rows with `tournament_id = 'wpba_evt_*'` (+ `tournament_results`) |
| **Upcoming** WPBA events | Calendar / manual entry | `tournament_history` rows with `status = 'upcoming'` (non-`wpba_evt_*`) |

**Rule:** the only canonical *completed* WPBA tournaments are the `wpba_evt_*` rows
produced by `fill_tournament_history_from_wpba_women_events()`. There must be **exactly one
row per real event**. Nothing else may create completed WPBA history rows.

Post-refactor steady state (verified): **10 completed `wpba_evt_*` + 5 upcoming = 15** WPBA
rows in `tournament_history`, zero duplicate names.

---

## 2. The problem we fixed (triple-counting)

Before the refactor, three independent writers all created WPBA `tournament_history` rows:

1. `fill_tournament_history_from_wpba_women_events()` → canonical `wpba_evt_*` (correct).
2. `fill_tournament_history_from_rankings_snapshots()` → `rankings_snapshot_*` pseudo-rows
   (a "tournament" per ranking snapshot — **not** a real event).
3. `fill_tournament_history_from_cp_archives()` → `2026_WPBA_*` calendar/history rows imported
   from external JSON archives, many duplicating the `wpba_evt_*` events.

Result: the same real event existed under up to three IDs → players' tournament counts were
inflated (triple-counted) and "single source of truth" was a fiction.

---

## 3. The refactor (guards + date self-sufficiency + cleanup)

All in `database/postgres_manager.py`.

### 3a. Guard the non-canonical writers for WPBA
- `fill_tournament_history_from_rankings_snapshots()` now **skips `association == 'WPBA'`**
  (`continue`) — no snapshot-pseudo rows for WPBA.
- `fill_tournament_history_from_cp_archives()` now **filters out all `WPBA` entries**
  (entries, tournament rows, and result rows) before upserting.

WPA is intentionally **not** guarded — those writers still run for WPA until Phase 2.

### 3b. Date self-sufficiency (so cleanup can't regress dates)
- `_resolve_wpba_event_date()` returns `Optional[date]` — the matched real date or `None`.
  It fuzzy-matches against **non-`wpba_evt_*`** WPBA rows only.
- `_upsert_wpba_event_tournament_history()` uses `matched_date` when present, else a
  `Jan 1 <year>` (or snapshot-date) fallback. The `ON CONFLICT DO UPDATE` only overwrites
  `date` when a `matched_date` exists, so deleting the old duplicate source rows can no
  longer push a good event date back to a fallback.

### 3c. One-time cleanup (already executed; back up first)
Deleted 49 non-canonical WPBA `tournament_history` rows (snapshot-pseudo, duplicate completed
calendar rows, and mislabeled "upcoming") + 2,455 orphaned `tournament_results`
(FK is `ON DELETE CASCADE`), leaving the 10 + 5 canonical set. Then
`REFRESH MATERIALIZED VIEW mv_tournament_history_recent`.

**Idempotency verified:** re-running `fill_tournament_history_from_rankings_snapshots(['WPBA_Women'])`
creates 0 rows; re-running `fill_tournament_history_from_wpba_women_events()` keeps 10 events /
180 results and preserves event dates.

---

## 4. Leaderboard "tournaments played" & finishes

Endpoint `GET /api/tournaments/rankings/current?system=WPBA_Women` →
`get_leaderboard_from_rankings(ranking_system='WPBA_Women')`.

| Field | Source | Why |
|---|---|---|
| `total_tournaments_played` | `rankings.stops_played` (the PDF's own "Stops" column) | Authoritative and present for **every** ranked player (all 166), independent of per-event parsing. |
| `first/second/third_place_finishes` | placements in `tournament_results` (`wpba_evt_*`), via `_tournament_stats_by_player()` | The only podium source we have. Now covers **all ranked players** (per-event parser fixed — see §5). |

Key points:
- `_tournament_stats_by_player(association)` counts only **real completed** tournaments —
  it excludes snapshot-pseudo rows (`rankings_snapshot*` / names like `"… Rankings (date)"`).
- Finishes are **gated to WPBA** (`_ranking_system_to_association` → only `'WPBA'`). WPA and the
  combined view return 0 finishes, because WPA per-event rows are still duplicate-prone
  (Phase 2). This prevents leaking inflated WPA numbers.
- **Root cause of the original "tournaments = 0":** `save_wpba_rankings()` used to **strip
  `stops_played`** on save (assuming History would supply the count). It no longer strips it.
  `stops_played` is now persisted for all WPBA rows and is the SSOT for tournaments-played.

Verified live (2026-06-06 snapshot):

```
#1 Kristina Tkach           played=10  1st=5 2nd=2 3rd=2
#2 Pia Filler               played= 9  (now has full per-event detail; finishes from full data — §5)
#3 Margaret Fefilova-Styer  played=10  1st=4 2nd=2 3rd=2
#5 Savannah Easton          played=10  1st=1 2nd=3 3rd=2
#6 Chieh-Yu Chou            played= 5  (now has full per-event detail — §5)
```

---

## 5. RESOLVED (2026-06-07) — per-event detail now covers ALL ranked players

> **Previously** per-event `tournament_results` (per-event buttons, History event rosters,
> Leaderboard *finishes*) only covered the **18 players who played all 10 rolling events**
> (`stops_played == 10`); the other ~148 ranked players got no per-event detail. This is now
> fixed by a word-position parser.

**Original root cause (confirmed):**
- The WPBA PDF lists per-event points as columns; a player who skipped an event has a **blank
  cell**. The PDF has **no ruling lines** (`page.lines == 0`), only text positioned by
  coordinate.
- `_parse_table()` used pdfplumber's `text` table strategy. With no rules, that strategy
  mis-split columns (it produced a garbled 16-col table where the rank wasn't even in column 0),
  so `_parse_table()` rejected it and `_parse_page()` fell back to `_parse_text_lines()`.
- `extract_text()` collapses blank cells, so a sparse row's numbers can't be aligned to the
  right tournament. The text parser correctly **refused to guess** and only attached per-event
  values when 10 values summed to the total — i.e. only `stops_played == 10` rows.

**The fix — `scrapers/wpba_scraper.py::_parse_pages_by_words()` (primary parser):**
- Words are extracted with their x-coordinates and grouped into rows by `top`.
- Per-event value tokens are clustered **document-wide** into column **anchors** (the live PDF
  yields exactly 11 anchors = 10 in-window events + the rotating/removed 11th).
- For each player, every value is assigned to its **nearest column anchor**, so a blank column
  correctly maps to `0` regardless of how many events the player skipped.
- **Per-player guard:** the 10 in-window values must reconstruct the player's total
  (`abs(sum(in_window) - total) < 1.0`); if not, that player's per-event detail is omitted
  (never guessed). Validated **166/166 players pass** on the current PDF.
- The old `_parse_table()` → `_parse_text_lines()` chain remains as a **fallback** if word
  clustering can't establish 10–11 anchors, so we can never regress below prior behavior.

**Verified live (2026-06-07 re-scrape):**
- Parser: `166 players, 166 with per-event detail (0 skipped on sum-check), 11 column anchors`.
- `tournament_results` for `wpba_evt_*`: **18 → 166 distinct players**, **180 → 700 result rows**.
- Per-event rosters: **62–80 finishers per event** (was ~18 each).
- Leaderboard: all 166 have `total_tournaments_played` (from `stops_played`); podium finishes
  now computed from the full result set.

---

## 5b. RESOLVED (2026-06-08) — column **keys** are now discovered from the PDF header (dynamic rolling window)

> **Previously** `_parse_pages_by_words()` labelled the 10/11 value-column anchors using the
> **hardcoded** `scrapers/wpba_pdf_columns.py::WPBA_ROTATING_TEN_COLUMNS` list. The PDF window
> rotates: when WPBA publishes a new event it enters at the **left**, every event shifts right,
> and the oldest drops out. The static list did not shift, so on the *Post-Islands-US-Open* PDF
> the **two new events (Islands US Open, CPBA Inv) landed under the wrong event names** — column 0
> (Islands data, 12,750 for Tkach) was stored as "2026 Classic Billiards Championship" and the
> whole window was misaligned by two. Data values were correct; **identities were wrong**.

**Root cause (single location):** the assignment loop used the stale positional list:
```python
active_cols = [k for k, _ in WPBA_ROTATING_TEN_COLUMNS]   # STALE — positional, never shifts
```

**The fix — `scrapers/wpba_scraper.py::_extract_column_headers()`** (called from
`_parse_pages_by_words()`), which derives `(column_key, label)` per anchor from the PDF header:
1. **Column count / order / year** come from the PDF: each event header verifiably begins with a
   `"<year> WPBA"` marker. The ordered markers give authoritative left-to-right column boundaries
   and the event year — fully dynamic (a new event simply adds a left-most marker; the oldest
   becomes the rotating-11th and then disappears). If the marker count ≠ value-anchor count, the
   method returns `None` and the parser falls back to the static list (never regress).
2. **Column identity** is resolved by **token-overlap matching** against the known-event
   dictionary (`WPBA_ROTATING_TEN_COLUMNS`), *not* by raw header text. The multi-line event names
   are centre-aligned in narrow columns and the wide words bleed across neighbours, so raw text is
   unreliable; matching by overlap is immune to that bleed. Recurring events therefore keep their
   **canonical keys/labels** (so the existing `WPBA_Women_*` systems and nice labels are reused —
   no duplicate buttons). Match is exact-key first, then strong fuzzy (same year + ≥2 shared
   distinctive tokens, or all of a known event's tokens present), greedy by score, each known
   event used once.
3. **Genuinely new events** (no dictionary match) get a clean key/label minted from the **bottom
   header line**, where each event's short distinguishing name (e.g. `Islands US Open`, `CPBA Inv`)
   sits correctly under its own column → `2026_wpba_islands_us_open`, `2026_wpba_cpba_inv`.

This is why **no `database/postgres_manager.py` change** is needed: new keys flow through the
existing dynamic discovery (`_get_wpba_column_mapping_with_discovered`) and recency ordering
(`_wpba_tournament_columns`), which already mint per-event `ranking_system` names and labels for
unknown keys. `WPBA_ROTATING_TEN_COLUMNS` is now a **known-event matching dictionary + static
fallback**, no longer the primary source of column order.

**Verified live (2026-06-08, current PDF):**
- `WPBA header-parse: 11 columns from PDF headers (9 matched known, 2 new)`.
- Newest two columns: `2026_wpba_islands_us_open`, `2026_wpba_cpba_inv` (were absent before).
- Classic Billiards correctly fuzzy-matched to `2026_wpba_classic_billiards_championship`
  (its value for Tkach is now 11,250, not Islands' 12,750).
- `166 players, 166 with per-event detail (0 skipped on sum-check)` — data assignment unchanged;
  only the key/label per anchor changed.
- Frontend: `Rankings.tsx` accepts any `WPBA_Women_${string}` system (catch-all type + runtime
  `currentRankingInfo` fallback), so new per-event buttons appear from the API with no code change.

---

## 6. The full WPBA pipeline (Load WPBA PDF button)

`POST /rankings/refresh-wpba` → `_scrape_wpba_sync()` → in order:
1. `save_wpba_rankings()` — persists `WPBA_Women` rows **incl. `stops_played`** + `source_data`
   (`_wpba_tournament_columns`, `wpba_column_labels`).
2. `split_wpba_women_to_column_buttons()` — `WPBA_Women_*` per-event systems for the Rankings UI.
3. `fill_tournament_history_from_wpba_women_events()` — canonical `wpba_evt_*` completed events.
4. `refresh_materialized_views()` — `mv_tournament_history_recent`, etc.

Reads:
- Rankings page / Leaderboard current standings → `rankings` (+ `WPBA_Women_*`). Per-event
  button snapshot selection in `get_rankings_paginated()` orders by **`snapshot_date DESC`**
  among snapshots with ≥1 non-zero row (fixed: previously ordered by `nonzero_rows DESC`, which
  served stale events).
- History / Hot Streak / Leaderboard past + finishes → `tournament_history` + `tournament_results`.

---

## 7. WPA Phase 2 — what to replicate

When cleaning WPA (`WPA_Women`, `WPA_Men`, `WPA_Heyball_*`, `WPA_Artistic`):
1. Define a canonical completed-event ID scheme (mirror `wpba_evt_*`) and a single writer.
2. Add the same guards: stop snapshot-pseudo and archive importers from creating WPA completed
   rows once the canonical writer exists.
3. Back up `tournament_history` + `tournament_results`, then dedup to one row per real event.
4. Confirm `stops_played` is captured/persisted for WPA (`save_wpa_rankings` already does not
   strip it) so the Leaderboard "tournaments played" works without per-event detail.
5. Un-gate finishes for WPA in `_ranking_system_to_association()` usage only **after** WPA
   per-event data is clean.
6. Check WPA for the same `_parse_table` fallback limitation (§5) if WPA also parses a PDF.
