# WPA / Heyball Tournament — Single Source of Truth (SSOT) & Leaderboard wiring

**Status:** WPA + Heyball cleaned (June 2026), companion to
[`WPBA_TOURNAMENT_SSOT.md`](WPBA_TOURNAMENT_SSOT.md).

WPA is **HTML-sourced** (wpa.com / per-event ranking pages), not a PDF, so the model differs
from WPBA in three important ways:

1. **No `stops_played` column** anywhere in WPA rankings → tournaments-played cannot use the
   WPBA "authoritative stops column" trick; it is derived from completed-event results.
2. **No `wpa_evt_*` per-event-from-rankings pipeline.** WPA's canonical *completed events* are
   the **digitalpool archive tournaments** (real brackets, dates, placements), imported by
   `fill_tournament_history_from_cp_archives()`. The per-event WPA ranking systems
   (`split_wpa_*_to_column_buttons`) feed the Rankings-page buttons only — they are current
   standings per event, not `tournament_history`.
3. **Names come from two different sources** (HTML rankings vs digitalpool results), so player
   names don't always match exactly — see §5.

Code references: `database/postgres_manager.py`.

---

## 1. Canonical model

| Concept | Source of truth | Where it lives |
|---|---|---|
| Current standings (WPA_Men, WPA_Women, WPA_Heyball_*, WPA_Artistic) | WPA HTML rankings | `rankings` (combined systems) |
| Per-event current standings (buttons) | WPA HTML per-event pages | `rankings` `WPA_*_<event>` systems |
| **Completed** WPA/Heyball events (History / Leaderboard finishes / Hot Streak) | digitalpool tournament archives | `tournament_history` (`YYYY_…` ids) + `tournament_results` |

There is **no** WPA snapshot-pseudo tournament and **no** `wpa_evt_*`. The digitalpool archive
rows are the canonical completed events.

Post-clean steady state (verified): **WPA = 57 completed** archive events, **HEYBALL = 0**
(no archived events yet — see §5), zero snapshot-pseudo rows.

---

## 2. The problem we fixed (snapshot-pseudo pollution)

`fill_tournament_history_from_rankings_snapshots()` keys its `tournament_id` by
**`(association, snapshot_date)`** — so **every** ranking system scraped on a date collapsed
into **one** fake "tournament" (`rankings_snapshot_WPA_<date>`, name `"… Rankings (date)"`) and
accumulated the union of all those systems' players as "results". Examples removed:

- `rankings_snapshot_WPA_2025-12-16` — **501** bogus results
- `rankings_snapshot_HEYBALL_2025-11-08` — **291**
- `rankings_snapshot_WPA_2026-03-08` — **461**

These massively inflated tournaments-played / finishes and were never real events.

**Cleanup (executed, backup first):** deleted **11** snapshot-pseudo `tournament_history` rows
(6 WPA + 5 HEYBALL) and **2,946** associated `tournament_results` (FK `ON DELETE CASCADE`),
then `REFRESH MATERIALIZED VIEW mv_tournament_history_recent`. Backup:
`/home/ansible/db_backups/backups_th_tr_wpa_*.sql`.

---

## 3. The refactor (guard the pseudo writer)

`fill_tournament_history_from_rankings_snapshots()` now **skips `WPBA`, `WPA`, and `HEYBALL`**
(was WPBA-only). Snapshot-pseudo rows are superseded for every current association
(WPBA → `wpba_evt_*`; WPA/Heyball → digitalpool archives), so the writer no longer creates them.
The archive importer (`fill_tournament_history_from_cp_archives`) still runs for WPA/Heyball —
that is the canonical source — and is only guarded against WPBA.

**Idempotency verified:** re-running the pseudo writer for WPA/Heyball systems creates 0 rows.

---

## 4. Leaderboard "tournaments played" & finishes (WPA / Heyball)

`GET /api/tournaments/rankings/current?system=WPA_Women` (etc.) →
`get_leaderboard_from_rankings(ranking_system=…)`.

Finishes + tournaments-played are enabled for `{WPBA, WPA, HEYBALL}` via
`_tournament_stats_by_player(association)`, which counts only **real completed** tournaments
(excludes any `rankings_snapshot*` / `"… Rankings (date)"`).

| Field | WPBA | WPA / HEYBALL |
|---|---|---|
| `total_tournaments_played` | PDF `stops_played` (complete) | **distinct completed events with results** (no stops column exists) |
| `first/second/third_place_finishes` | `tournament_results` placements | `tournament_results` placements (digitalpool) |

Verified live (snapshot 2026-04-07):

```
WPA_Women  #1 Pia Filler      played=12  0/2/2
           #3 Jasmin Ouschan  played=10  3/0/3
WPA_Men    #1 Albin Ouschan   played= 8  1/0/0
           #3 Carlo Biado     played= 5  1/0/1
WPA_Heyball_Men  all 0/0/0  (no archived Heyball events yet — §5)
```

WPBA leaderboard unchanged (Tkach 10, 5/2/2). Combined view (no `system`) stays 0 to avoid
mixing associations.

---

## 5. KNOWN LIMITATIONS

### 5a. Cross-source player-name variance (accuracy caveat)
WPA ranking names (HTML) and digitalpool result names come from **different sources**, so the
same player can appear under different spellings. `_canonical_player_name` normalizes
`"Last, First" → "first last"` and strips license suffixes, which covers the common case, but it
**cannot** reconcile:
- **married/maiden or surname differences** — e.g. ranking `"Fefilova-Styer, Margarita"` vs
  result `"Fefilova, Margarita"`. She played 8 WPA events but shows `played=0` because the
  surnames differ.
- **reversed two-token names without a comma** — e.g. `"Fefilova Margarita"` → `"fefilova
  margarita"` (rare in WPA: 1 of 74 in `WPA_Women`).

Impact: a small number of players undercount on the WPA leaderboard. It never inflates and never
invents data. **Proper fix:** license-based player-identity resolution that maps ranking
identities to result identities across sources (digitalpool results currently carry no license),
or a curated alias map. Do not "fix" with fuzzy surname/word-order matching — it risks merging
genuinely distinct players.

### 5b. Heyball has no archived events yet
After removing the pseudo rows, HEYBALL has **0** completed `tournament_history` events, so all
Heyball leaderboard tournaments-played/finishes are `0` (honest — no source data). The wiring is
already enabled, so counts appear automatically once Heyball tournaments are archived.

### 5c. WPBA women's events dual-tracked under WPA (intentional, kept)
5 women's pro events are tracked by **both** tours: canonical `wpba_evt_*` (WPBA) and
`2025_WPA Women_wpba_*` (WPA), e.g. Colorado Classic, Raxx Mezz, SE Masters, DR Pool, Olhausen
IronCity 2025. These are **not** duplicates within an association — `tournament_history` reads
are association-scoped, so each tour counts the event for its own leaderboard. Left in place.

### 5d. Anti-data-loss drop guard on the WPA scrape (working as designed)
`save_rankings()` refuses to overwrite a snapshot when the incoming row count falls to ~65% of
the previous snapshot, raising `ValueError` ("Set `ALLOW_RANKINGS_DROP=1` to override"). On the
2026-06-07 scrape this **correctly blocked** `WPA_Men` (134 rows vs 205 on 2026-04-07) and
`WPA_Heyball_Men` (144 vs 206).

Investigation (scrape-JSON history `scraped_data/wpa/`): between April and June the divisions
moved in **both** directions with an unchanged parser — Men 205→134 and Heyball-Men 206→144
**down**, while Women 74→106 and Heyball-Women 118→129 **up**, Artistic 27→27 unchanged. A parser
regression would lose rows uniformly, never grow other divisions, so this is a **real
site-side change** on wpapool.com (a shorter men's list), not a scraping bug. The guard behaved
correctly; to accept the smaller list intentionally, re-run the WPA scrape with
`ALLOW_RANKINGS_DROP=1`.

### 5e. Per-division resilience in the WPA pipeline (fixed 2026-06-07)
Previously a single blocked division (e.g. the drop guard above) raised through
`_run_scraper_pipeline("wpa")` and **aborted the entire WPA run** — so divisions that *grew*
(Women, Heyball-Women) never saved either, and the materialized-view refresh/notify never ran.
`api/routes/rankings.py` now wraps each division's `save_wpa_rankings()` in try/except:
blocked/failed divisions are collected and surfaced in the run summary
("N division(s) NOT saved: …"), while the remaining divisions still save, split, and refresh.

### 5f. External Pool / "CP" scraper — import + domain fixed
Two bugs were fixed on the CP path:
1. **Import:** the route imported `ExternalPoolScraper`, a class name that no longer exists, so
   the run died with `ImportError`. Fixed to `CpScraper` (`api/routes/rankings.py`).
2. **Domain regression:** a prior refactor renamed the "digital pool" scraper to "external pool"
   but **also flipped the live domain** `https://api.digitalpool.com` → `https://api.externalpool.com`
   (which does not resolve). The domain is reverted to **`https://api.digitalpool.com`** (the
   original, resolving host); only **code identifiers** stay `externalpool` (`CpScraper`,
   `scrapers/externalpool_scraper.py`, `scraped_data/externalpool/`).

Note: Digital Pool's primary API is **GraphQL** at `api-nyc.digitalpool.com` (see
`api/services/competitors_import.py::COMPETITORS_GRAPHQL`); `CpScraper`'s REST `/rankings/*`
shape may still need to be aligned with the real API before it returns live rankings. The 2
existing `Competitors` `tournament_history` rows came from the archive/GraphQL path, not this
REST scraper.

---

## 6. WPA writers (reference)

- `save_wpa_rankings()` / `save_wpa_*` → `rankings` (combined + per-event `WPA_*_<event>`).
- `split_wpa_{men,women,heyball_men,heyball_women,artistic}_to_column_buttons()` → per-event
  ranking systems for the Rankings UI (not `tournament_history`).
- `fill_tournament_history_from_cp_archives()` → **canonical** WPA/Heyball completed events
  (digitalpool). WPBA filtered out here.
- `fill_tournament_history_from_rankings_snapshots()` → **disabled** for WPBA/WPA/HEYBALL
  (snapshot-pseudo; superseded).
