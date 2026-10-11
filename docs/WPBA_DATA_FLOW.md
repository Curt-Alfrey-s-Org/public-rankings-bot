# WPBA data flow (PDF → DB → pages)

> **See also:** [`WPBA_TOURNAMENT_SSOT.md`](WPBA_TOURNAMENT_SSOT.md) — canonical `wpba_evt_*`
> model, the tournament-history de-duplication refactor, Leaderboard tournaments-played /
> finishes wiring, and the known per-event parser limitation (only full-schedule players get
> per-event detail). Read it before doing the WPA Phase 2 work.

## Source of truth

WPBA Women's professional events are **9-ball**; the app treats WPBA association rows as 9-ball in Tournament History (inferred game type).

1. **Ingestion**  
   The official WPBA Women PDF is parsed into the **`rankings`** table:
   - `ranking_system = 'WPBA_Women'` for the overall row (rolling total + per-event columns in **`source_data`** JSONB).
   - Optional **`WPBA_Women_*`** rows from `split_wpba_women_to_column_buttons()` for per-event views on the Rankings page.

2. **PDF display names**  
   The scraper attaches **`wpba_column_labels`**: a map from internal column key to header text from the PDF. This is stored in **`source_data`** so Tournament History can show the same names as the PDF.

3. **Tournament-shaped reads**  
   Tournament History, Leaderboard "past events", and Hot Streak read **`tournament_history`** + **`tournament_results`**, populated by **`fill_tournament_history_from_wpba_women_events()`** after a PDF load. Names prefer **`wpba_column_labels`** when present; otherwise the app uses **`WPBA_WOMEN_COLUMN_MAPPING`** labels.

4. **Rankings-shaped reads**  
   Rankings and Leaderboard "current standings" read **`rankings`** (overall and `WPBA_Women_*` systems).
   - **Overall button (`WPBA_Women`)**: uses strict columns matching WPA layout (Rank, Name, Country, License, Fargo, Points). Per-tournament columns are **not** sent in the API response for the overall view.
   - **Per-tournament buttons (`WPBA_Women_*`)**: each shows that tournament's points. The button list comes from the API endpoint `/rankings/wpba-tournament-systems` (dynamic, no hardcoded fallback).

## After "Load WPBA PDF" (Settings > Admin)

The **Load WPBA PDF** button is in **Settings > Admin** (admin/super_admin). It calls `POST /rankings/refresh-wpba` which runs the full pipeline: save -> split -> fill per-event history -> refresh **`mv_tournament_history_recent`** -> invalidate **`tournament-history`** cache.

The **WPBA Women Run/Force Run** buttons (super_admin only, same page) call `POST /rankings/scrapers/wpba/run` and execute the same full pipeline.

## Do other pages "auto-update"?

- **Yes**, in the sense that they all read from the **database**; there is no separate PDF fetch per page.
- **No**, in the sense that **not every page reads `rankings` only**:
  - History / hot streak / leaderboard past blocks need **`tournament_history`** filled by the pipeline above.
  - If **`rankings`** is updated without running the fill step, those pages can be stale until the next full WPBA load or a manual fill.

## Rotating 10 vs 11th column

The PDF may list **10** tournaments that count toward the rolling total plus an **11th** numeric column (event rotating out). That 11th value is stored under **`wpba_rotating_11th_slot`** and is **excluded** from **`_wpba_tournament_columns`** so the rolling-10 sum matches the PDF total.

## PDF parsing

The scraper uses a **word-position parser** (`_parse_pages_by_words`) as the **primary** parser. The WPBA PDF has no ruling lines, so column membership is encoded purely by x-coordinate: value tokens are clustered document-wide into column anchors (10 in-window events + the rotating 11th), and each player's values are assigned to the nearest anchor — blank columns correctly map to `0`. A per-player guard requires the 10 in-window values to reconstruct the player's total before per-event detail is accepted. Table extraction (`_parse_table`) and text-line regex parsing (`_parse_text_lines`) remain as **fallbacks** if column anchors can't be established.

> **Fixed (2026-06-07):** the previous `text` table strategy mis-split the rule-less PDF and fell back to text parsing, which could only align players who played all 10 events (~18 of 166). The word-position parser now gives **all 166 players** full per-event detail (validated 166/166 on `sum(in-window) == total`), so per-event buttons, History event rosters, and Leaderboard **finishes** cover every ranked player. See [`WPBA_TOURNAMENT_SSOT.md`](WPBA_TOURNAMENT_SSOT.md) §5.

## Dynamic column keys (rolling window)

Column **keys/labels** are discovered from the PDF header by **`_extract_column_headers()`**, not from a hardcoded list. Each event header begins with a `"<year> WPBA"` marker; the ordered markers give the live column count, order and year (so a newly published event automatically enters at the left and the oldest rotates out — no code edit). Column **identity** is resolved by token-overlap against the known-event dictionary (`WPBA_ROTATING_TEN_COLUMNS`) so recurring events keep their canonical keys/labels despite the centre-aligned header words bleeding across narrow columns; genuinely new events get a clean key from the bottom header line (e.g. `2026_wpba_islands_us_open`, `2026_wpba_cpba_inv`). `WPBA_ROTATING_TEN_COLUMNS` is now a **matching dictionary + static fallback** only (used when the header can't be read confidently). New keys flow through the existing dynamic discovery in `postgres_manager.py` (`_get_wpba_column_mapping_with_discovered`), so the per-event buttons appear with no DB/API change; `Rankings.tsx` accepts any `WPBA_Women_${string}` system.

> **Fixed (2026-06-08):** before this, the word parser labelled anchors from the static positional list, so the two newest events (Islands US Open, CPBA Inv) landed under the wrong event names and the rolling window was misaligned by two. See [`WPBA_TOURNAMENT_SSOT.md`](WPBA_TOURNAMENT_SSOT.md) §5b.

## External Pool enrichment

Per-event rows created from the WPBA PDF use **`tournament_id`** values like `wpba_evt_WPBA_Women_*`. For those IDs:

- **Placements and points** in **`tournament_results`** stay **PDF-derived** (rolling column points, sorted standings).
- The **`ExternalPoolTournamentHarvester`** (GraphQL at `api-nyc.digitalpool.com`) still:
  - Sets **`source_url`** / **`bracket_url`** on **`tournament_history`**
  - Writes **bracket/match** rows and **archived tab JSON** for the Tournament History UI  
  - **Does not** overwrite **`tournament_results`** for `wpba_evt_*` tournaments, so names/points stay aligned with the PDF.

Other tournaments (non-`wpba_evt_*`) may still receive placements/points from the External Pool harvester when harvested.
