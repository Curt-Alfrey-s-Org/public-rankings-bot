# Multi-source data integration plan — Digital Pool + Inside Spin

**Status:** Plan (2026-06-09). Pairs with
[`RANKINGS_PIPELINE_ROADMAP.md`](RANKINGS_PIPELINE_ROADMAP.md),
[`WPBA_TOURNAMENT_SSOT.md`](WPBA_TOURNAMENT_SSOT.md),
[`WPA_TOURNAMENT_SSOT.md`](WPA_TOURNAMENT_SSOT.md),
[`SCRAPER_TO_UI_DATA_MAP.md`](SCRAPER_TO_UI_DATA_MAP.md).

**Goal:** Fill as much **current and historical** tournament / player / ranking data as
possible into rankings-bot from two web sources, de-duplicated so the same real event is
never stored twice and players are not double-counted.

> **Policy gate (must read first):** workspace rule `no-automatic-scraping.mdc` applies to
> `rankings-bot/`. All ingestion below is **manual / admin-triggered and rate-limited**
> (Settings → Admin buttons or operator scripts). **No cron / no background scheduler.**
> Past unattended scraping caused account bans. Every scraper here uses bounded retries,
> jittered delay, a descriptive `User-Agent`, and caches aggressively.

---

## 1. The two sources (verified June 2026)

### 1a. Digital Pool ("External Pool" / CP) — `digitalpool.com`

- **Backend:** open Hasura GraphQL at `https://api-nyc.digitalpool.com/v1/graphql`
  (anonymous reads work; **introspection enabled**; 466 root fields). Cloudflare fronts the
  host but legitimate `POST application/json` queries are served.
- **Whole site is enumerable.** Live `_aggregate` counts: events **1,668**,
  tournaments **92,675**, players **163,810**, tournament_players (results) **1,682,883**,
  matches **24,225**, venues **14,380**, leagues **1,240**, tours **313**,
  organizations **501**, `pro_world_rankings` **15,339**.
- **Rankings are first-class data** (not derived from points):
  - `ranking_systems` (8: Fargo World/US/Mens/Womens, Matchroom, WPA Mens/Womens, US Pro Series)
  - `pro_world_rankings` (per player/system, time-series via `rank_date`)
  - composite views: `vw_current_pro_rankings` (`digital_pool_ranking`),
    `vw_current_mens_pro_rankings` (`digital_pool_mens_ranking`),
    `vw_current_womens_pro_rankings` (`digital_pool_womens_ranking`).
- **Date fields** (for de-dup): `events.start_date_time/end_date_time`,
  `tournaments.start_date_time/end_date_time`, `matches.scheduled_time`,
  `pro_world_rankings.rank_date`.
- `robots.txt`: permissive (no `Disallow`).

**Already wired in this repo:** `scrapers/externalpool_tournament_harvester.py` (per-event
GraphQL harvest into `tournament_history`/`tournament_results`/`tournament_history_matches`),
`api/services/competitors_import.py` (wizard import by slug), and — **as of 2026-06-09** —
`scrapers/externalpool_scraper.py::CpScraper.scrape_rankings()` now reads the GraphQL Pro
Rankings views (overall/men/women) → `rankings` as `Competitors_Pool_*`.

### 1b. Inside Spin — `insidesp.in`

- **Not an India site.** "Inside Spin" is a **global pro-pool aggregator** (9/10/8-ball,
  one-pocket) that itself scrapes Matchroom, WPA, Predator, WPBA + many US regional circuits,
  then computes its own ratings (Display/Overall Rating, "RSI"). `SportsOrganization` in JSON-LD.
- **Tech:** Next.js (RSC) behind nginx. **Not WordPress** (`/wp-json/` → 404).
- **Scrapeable surfaces (server-rendered):** listing pages embed the **latest/top 100**
  records as schema.org JSON-LD inside the RSC payload (`self.__next_f.push(...)`) — parseable
  with plain `requests`:
  - `/tournaments` ≡ `/events` → `SportsEvent` items with **`startDate` + `endDate`** (ISO),
    `sport`, `location.name` ("City, ST, US"), `winner.name` (completed only),
    `additionalProperty Discipline`.
  - `/players` → `Person` items with `nationality` (ISO-3 alpha-3) + "Overall Rating".
  - `/ratings/9-ball|10-ball|8-ball|one-pocket` → name, nationality, Display Rating, Discipline,
    Matches Rated. **No snapshot date.**
- **Gated / hard parts:** detail pages (`/tournaments/<slug>`, `/players/<slug>`) are
  **JS-rendered** (brackets, placements, scores, player history not in initial HTML); the
  backend `/api/*` returns **401 Unauthorized**; `sitemap.xml` is **broken** (points at
  `localhost:3000`). Historical depth is **2020–2026** but archives (2020–2025) are only
  reachable via the JS app. Phase 4 confirmed the SPA list API
  (``/api/tournaments?beginYear=&endYear=`` + ``Referer``) and RSC ``participantRows`` on
  detail pages are parseable with ``requests`` — **no headless browser** for Tier-2 ingest.
- `robots.txt`: `Allow: /` (fully permissive). No Cloudflare/WAF observed. Be polite anyway.
- **Slugs:** `<year><normalized-name>` e.g. `2026wpbasoaringeaglemasters`.

**Overlap with Digital Pool:** **high** on US regional/amateur events (those are commonly
bracketed on digitalpool.com); **low** on major-tour events (Matchroom/WPA/Predator/WPBA),
which Inside Spin aggregates but digitalpool usually does not host. → cross-source de-dup is
essential exactly where overlap is high.

---

## 2. Target schema (rankings-bot) — recap

| Table | Natural key / unique | Filled by |
|---|---|---|
| `tournament_history` | `tournament_id` UNIQUE | history importers, harvester |
| `tournament_results` | `(tournament_id, player_name)` UNIQUE (upsert) | importers, harvester |
| `tournament_history_matches` | none (delete+reinsert per tournament) | harvester only |
| `rankings` | `(ranking_system, snapshot_date, position)` UNIQUE | `save_rankings`; extras → `source_data` JSONB |
| `upcoming_events` | `dedupe_key` SHA-256 UNIQUE | upcoming refresh |
| `players` (+ `player_name_aliases`, `*_locks`) | name / player_id | identity resolution in `save_rankings` |

`tournament_id` schemes today: `wpba_evt_*` (WPBA PDF), `{year}_{ASSOC}_{slug}` (CP archives).
**The repo does NOT auto-merge two different `tournament_id`s for the same real event** — so the
de-dup design below must assign a *single shared* `tournament_id` per real event across sources.

---

## 3. Cross-source de-dup strategy (the core requirement)

We de-dup at **three levels**: events, results/players, rankings.

### 3a. Event de-dup — date is the primary key signal

Build a canonical **event fingerprint** and a crosswalk table so each real event maps to one
`tournament_id` regardless of which source(s) it came from.

**Fingerprint = normalized(name) + date window + normalized(location).**

1. **Date** (strongest, both sources expose it cleanly):
   - Digital Pool: `tournaments.start_date_time` / `events.start_date_time` (+ `end_date_time`).
   - Inside Spin: `SportsEvent.startDate` / `endDate`.
   - Match if date windows **overlap or start within ±2 days** (multi-day events, TZ slop).
2. **Name** (reuse existing harvester logic — do **not** invent new fuzzy code):
   - `ExternalPoolTournamentHarvester._norm_name()` strips tour words/years/punctuation.
   - Score = `0.72*SequenceMatcher + 0.28*token_Jaccard` (same blend as `_event_score`).
3. **Location** (tie-breaker): normalize "City, ST" / "City, Country"; Inside Spin gives
   `location.name`, Digital Pool gives `events.location` / `venues`.
4. **Decision thresholds** (mirror harvester defaults, env-tunable):
   - `name_score ≥ 0.55` **and** date-window match → **same event** (merge).
   - `0.40 ≤ name_score < 0.55` with date + location match → **LLM arbitration** via
     `api/services/ollama_name_resolver.py` (already used by the harvester); confident → merge.
   - else → **distinct events** (keep both, no silent merge).

**Crosswalk table (new):**

```sql
CREATE TABLE IF NOT EXISTS source_event_crosswalk (
    id              SERIAL PRIMARY KEY,
    tournament_id   VARCHAR(255) NOT NULL REFERENCES tournament_history(tournament_id) ON DELETE CASCADE,
    source          VARCHAR(32)  NOT NULL,   -- 'digitalpool' | 'insidesp'
    source_event_id VARCHAR(255) NOT NULL,   -- DP tournament id / IS slug
    source_url      TEXT,
    match_method    VARCHAR(32),             -- 'date+name' | 'llm' | 'manual'
    match_score     DOUBLE PRECISION,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source, source_event_id)
);
```

- **Single source of truth for placements/scores stays Digital Pool** where both cover an
  event (DP has real brackets/scores; Inside Spin detail data is JS-gated and is its own
  derived metric). Inside Spin then **only fills gaps** (events DP doesn't have, or
  date/location/winner metadata) — never overwrites DP placements.
- `tournament_id` precedence for a merged event: existing `wpba_evt_*` > existing
  `{year}_{ASSOC}_{slug}` (DP) > new `insidesp_{slug}`. Record every source in the crosswalk.

### 3b. Player de-dup — identity, not surname fuzz

Reuse the existing identity stack (`_canonical_player_name`, `player_name_aliases`,
`player_*_locks`, `ollama_name_resolver`). **Honor `WPA_TOURNAMENT_SSOT.md` §5a: do NOT merge
on fuzzy surname/word-order** (risks merging distinct players).

- **Best join key across sources = Fargo id / rating + country.** Digital Pool exposes
  `players.fargo_id` / `fargo_rating` and `country`; carry these into a shared identity map.
  Inside Spin gives only name + ISO-3 nationality (no license/fargo), so:
  - join Inside-Spin players to Digital Pool players by **normalized name + country**, and when
    a Digital Pool match has a `fargo_id`, adopt it as the canonical identity key;
  - unresolved Inside-Spin-only players → store under canonical name, seed
    `player_name_aliases` (script `scripts/seed_name_aliases_from_rankings.py` already exists),
    flag for manual review rather than guess-merging.
- `tournament_results` upserts remain `(tournament_id, player_name)`; the crosswalk + canonical
  name keep one row per player per merged event.

### 3c. Rankings de-dup — keep sources side-by-side, key on date

- Digital Pool Pro Rankings → `rankings` as `Competitors_Pool_*` (current code) **and**
  optionally `pro_world_rankings` history keyed by `rank_date` (snapshot_date).
- **Inside Spin ratings have no snapshot date and are its own metric** → do **not** try to
  reconcile them with Digital Pool ranks. Store them in a **separate** `ranking_system`
  (e.g. `InsideSpin_<discipline>`) stamped with the **scrape date** as `snapshot_date`, clearly
  labeled as a third-party rating. Never blend Inside Spin ratings into DP/WPA points.

---

## 4. Full-site ingestion design

### 4a. Digital Pool — full enumeration (current + historical)

New module `scrapers/digitalpool_full_harvester.py` (extends the existing harvester's polite
GraphQL client). **Keyset pagination by `id`** (offset degrades at 92K/1.68M rows):

```graphql
query EnumTournaments($lastId: bigint!, $batch: Int!) {
  tournaments(where: { id: { _gt: $lastId } }, order_by: { id: asc }, limit: $batch) {
    id slug name status game_type start_date_time end_date_time
    event_id event { id slug name location }
  }
}
```

Ingestion order (cheap → heavy), each step idempotent + checkpointed:

1. `ranking_systems` (8) → `pro_world_rankings` (15K, `rank_date` history) → `vw_current_pro_rankings*`.
2. `players` (164K) — identity dimension; keep `fargo_id` for cross-source join.
3. `events` (1.7K) → `tournaments` (93K) — with date fields → `tournament_history` (+ crosswalk).
4. `tournament_players` (1.68M) **per tournament** → `tournament_results`.
5. `matches` (24K) + `tournament_brackets` → `tournament_history_matches`.
6. (optional) `tours` / `tour_tournaments`, `leagues` / `organizations`.

Scope control: the rankings-bot product is WPA/WPBA-centric, so default the bulk import to a
filter (e.g. events linked to WPA/WPBA/Matchroom systems, or `start_date_time >= 2015`) to avoid
ingesting all 92K amateur brackets. Full-firehose mode is opt-in via an admin flag.

### 4b. Inside Spin — two-tier scraper

New module `scrapers/insidesp_scraper.py`:

- **Tier 1 (no browser, default):** fetch `/tournaments`, `/players`, `/ratings/<discipline>`,
  extract the embedded schema.org JSON-LD from the RSC payload → latest-pool_opt_in events (with
  `startDate`/`endDate`/location/winner/discipline) + top ratings. Cheap, robust, covers
  **current** data. This is the primary path.
- **Tier 2 (historical, opt-in):** ``GET /api/tournaments?beginYear=&endYear=`` for the
  full catalog (requires ``Referer`` + ``Accept: application/json``) plus RSC
  ``participantRows`` on ``/tournaments/{slug}`` detail pages. No headless browser
  required (verified 2026-06-09). Playwright remains a documented fallback if the
  API or RSC embedding changes.
- Output: normalized event/player/rating dicts → de-dup pipeline (§3) → DB writers (§5).

### 4c. Politeness/robustness (both)

`set -euo pipefail`-style guards in scripts; bounded retries + jittered delay (reuse harvester
`_pace`/`_graphql`); `_aggregate`/`numberOfItems` up front to size runs and detect drift; archive
raw payloads to `data/digitalpool_archive/` and `data/insidesp_archive/` before DB writes
(matches the existing `fill_tournament_history_from_cp_archives` archive-then-load pattern).

---

## 5. Incorporation into rankings-bot

| Data | Writer (new/extended) | Table | Dedup |
|---|---|---|---|
| DP Pro Rankings (current) | `CpScraper.scrape_rankings` → `save_cp_rankings` **(done)** | `rankings` `Competitors_Pool_*` | `(system,date,position)` |
| DP `pro_world_rankings` history | new `save_pro_world_rankings()` | `rankings` per-system, `rank_date` | `(system,date,position)` |
| DP events/tournaments | extend `fill_tournament_history_from_cp_archives` / full harvester | `tournament_history` (+ `source_event_crosswalk`) | crosswalk + `tournament_id` unique |
| DP results / matches | existing harvester `_upsert_enriched_tournament` | `tournament_results`, `tournament_history_matches` | `(tournament_id,player_name)` / delete+reinsert |
| IS events (current) | new `insidesp` importer | `tournament_history` (gap-fill) + `upcoming_events` | crosswalk, `dedupe_key` |
| IS results/brackets (history, Tier 2) | extend harvester writer | `tournament_results` (gap-fill only) | crosswalk |
| IS ratings | new `save_insidesp_ratings()` | `rankings` `InsideSpin_<discipline>` | `(system,date,position)` |

**Admin/trigger surface (follow the `externalpool` pattern):**

1. Scraper modules above.
2. Register `insidesp` (and optionally `digitalpool_full`) in `_SCRAPER_REGISTRY` +
   `_run_scraper_pipeline()` branch in `api/routes/rankings.py`; add log-stream routes.
3. New importer routes mirroring `POST /api/tournament-history/fill-from-cp-archives`
   (e.g. `.../fill-from-insidesp-archives`, `.../fill-from-digitalpool-full`).
4. Buttons in `frontend/src/pages/SettingsAdmin.tsx` + extend
   `ScraperName` in `frontend/src/api/rankings.ts`.
5. CLI scripts mirroring `scripts/scrape_externalpool_tournaments.py`.
6. Migration: add `source_event_crosswalk` (Alembic, next after `054`); reversible.

**No infra changes** — no new ports, no compose/network edits (workspace `.cursorrules`). DB-only
writes + MV refresh (`refresh_materialized_views()` + `notify_data_changed()`) as today.

---

## 6. Phased rollout

- **Phase 0 (done):** CP rankings scraper → GraphQL Pro Rankings (live, verified).
- **Phase 1 (done 2026-06-09; deployed on `apps`):** `source_event_crosswalk` migration
  (Alembic `055`) + crosswalk-aware merge helper `api/services/event_crosswalk.py`
  (`EventCrosswalkResolver`) reusing the harvester's `_norm_name`/`_token_jaccard` blend +
  `ollama_name_resolver` arbitration, with a digitalpool backfill
  (`scripts/backfill_digitalpool_crosswalk.py`). Helpers unit-verified on host (matching
  events score 1.0, distinct 0.30 < 0.55 threshold). Deployed: api rebuilt →
  `alembic upgrade head` (055) → backfill recorded 6 digitalpool crosswalk rows.
- **Phase 2 (done 2026-06-09; deployed on `apps`):** Inside Spin Tier-1 scraper
  (`scrapers/insidesp_scraper.py`) parsing the server-rendered schema.org `ItemList`
  JSON-LD for `/tournaments` (events w/ dates) and `/ratings/<discipline>` (9/10/8-ball,
  one-pocket). Wired into the admin scraper registry/pipeline (`POST
  /api/rankings/scrapers/insidesp/run`, live-log stream, SettingsAdmin "Inside Spin"
  button) + CLI `scripts/scrape_insidesp.py`. Ratings persist as `InsideSpin_<discipline>`
  (Alembic `056`; Inside Spin's Display Rating + Matches Rated kept in
  `rankings.source_data`, `points=0.0`). Events de-dup against `tournament_history` via the
  Phase-1 crosswalk (date-first; no new tournaments created, no silent merge).
  **Audit fix (2026-06-09):** disciplines were initially hardcoded by guess (4); corrected to the
  live `/ratings` index = **7 systems** (`9Ball/10Ball/8Ball/OnePocket` + cohort overall
  `Overall/Women/Juniors`) — the **Women** list had been missed. Raw Inside Spin nationality now
  preserved in `source_data.insidesp_nationality` (the `country` column is governed/nulled for this
  non-authoritative source). `InsideSpin_*` is now wired into the Rankings UI (top-level "Inside
  Spin" menu → 7 leaves → `/by-system/<sys>`, ordered by rank not points) — previously the saved
  rows were invisible. Verified live: **619 ratings** across 7 systems; `/by-system/InsideSpin_Women`
  returns `association=Inside Spin` ranked. **Known limit (Tier-1):** only the latest ~100 events
  and top ~100 ratings/discipline are exposed by the source's JSON-LD; full historical depth is
  covered by Tier-2 (API catalog + RSC ``participantRows`` — Phase 4, no headless browser).
- **Phase 3a (done 2026-06-09; deployed on `apps`):** Digital Pool event *discovery*
  enumerator (`scrapers/externalpool_event_enumerator.py`, CLI
  `scripts/enumerate_digitalpool_events.py`) — keyset-paginates the public `events`
  catalog (date floor), de-dups each against `tournament_history` via the Phase-1
  crosswalk (records crosswalk rows for matches only), classifies DP-only events by
  pro-relevance, and archives them. **Read-only on DP; creates NO `tournament_history`
  rows** (ingestion scope is an explicit operator decision — Phase 3b).
  Reality vs original assumption: the `events` table is **1,668 rows (865 public)**, not
  92k; org-name scoping is tiny (wpa=10, wpba=18, matchroom=0); most events are local/
  regional. Live run (public, since 2023): 865 scanned, ~83 matched local, **782 DP-only**
  (438 with placements; **13 pro-like with placements** = WPBA invitationals, NWPA tour,
  WPA Heyball worlds, World Pool Championship).
- **Phase 3b (done 2026-06-09; deployed on `apps`):** ingestion path added to the enumerator
  (`ExternalPoolEventEnumerator.ingest()`, CLI `--ingest`): for scoped DP-only events it INSERTs a
  `tournament_history` row (`tournament_id=dp_<slug>`, association classified WPBA/WPA/DigitalPool,
  bad dates clamped to the name-year) and enriches placements + bracket/match rows + tab archive via
  the existing local-first harvester, recording an `ingest` crosswalk row (idempotent). Operator-
  approved scope = the **13 pro-like-with-placements** events; ingested live: 13 `tournament_history`
  rows + 13 crosswalk rows + bracket/match coverage (e.g. Palmetto: 4 placements, 126 matches).
  Re-run verified idempotent (inserted 0). `--ingest-all-placements` widens to all 438 on request.
- **Phase 3c (done 2026-06-09; deployed on `apps`):** Digital Pool **historical pro_world_rankings**
  fill — the previously-TODO time-series. `CpScraper.scrape_pro_world_rankings_history()` keyset-
  paginates the full `pro_world_rankings` table and groups it by ranking system + `rank_date`; the
  CLI `scripts/load_digitalpool_ranking_history.py --save` writes each (system, rank_date) snapshot
  into `rankings` under `DigitalPool_<suffix>` with `snapshot_date = rank_date` (Alembic `057`
  allows the prefix). These are **rank-position** systems (`points=0.0`; Digital Pool `player_id`
  kept in `source_data`). The save is an atomic per-(system, date) replace, so re-runs are
  idempotent and never clobber other dates or the live rank lists. Live fetch verified: **8 systems,
  125 snapshots, 15,339 rows, span 2021-09-30 → 2023-09-05** (Fargo World/Men's/Women's/US,
  Matchroom World 9-Ball, WPA World Men's/Women's, US Pro Series). Wired into the Rankings UI under a
  top-level **"Digital Pool (history)"** menu (8 leaves → `/by-system/DigitalPool_*`, ordered by
  rank). `get_rankings_paginated` filters to `MAX(snapshot_date)` per system, so the UI shows the
  latest historical snapshot (≈2023-09) while all snapshots remain queryable as history. **Note:**
  this is *historical* data ending 2023-09-05 — it complements (does not replace) the live composite
  Pro Rankings from the CP scraper's `vw_current_*` views.
  - **Events follow-up (done):** re-ran the enumerator back to a 2019 floor — the curated
    pro-relevant set is now **complete** (the 13 ingested earlier show as `matched_existing`; only
    **UK Open 2022** remained pro-like-with-placements and was ingested → 14 DP events total). The
    other ~492 DP-only-with-placements events are local/regional and were **intentionally left out**
    (pro-rankings DB; dilution risk per §7).
- **Phase 3d (done 2026-06-09; deployed on `apps`):** Digital Pool **Fargo player enrichment**
  (fill-only). Alembic `058` adds `players.digitalpool_player_id` (external key). The CLI
  `scripts/enrich_players_fargo_from_digitalpool.py --save` (1) seeds that key by **unambiguous exact
  canonical full-name** equality against DP-sourced `rankings` rows (only names mapping to exactly one
  DP id *and* one of our players — no fuzzy/ambiguous identity), then (2) batch-fetches DP profiles
  (`CpScraper.fetch_players_by_ids()`, GraphQL `id _in`) and (3) fills `players.fargo_score` /
  `fargo_robustness` / `nationality` / `fargo_last_updated` with **COALESCE only** (never overrides →
  country-lock respected). Live: **908 players linked**, **765 profiles fetched**, Fargo coverage
  961 → **1,403** players (+442; missing 1,701 → 1,259). e.g. Sánchez-Ruiz `fargo=845, rob=14846,
  ESP`. Re-runnable/idempotent (fill-only + link-if-null).
- **Phase 4 (done 2026-06-09; deployed on `apps`):** Inside Spin Tier-2 historical backfill.
  Research corrected the plan: bare ``/api/tournaments`` returns 401, but
  ``/api/tournaments?beginYear=&endYear=`` + ``Referer`` returns the full catalog
  (3,439 events for 2020–2026; no headless browser required). Detail pages embed
  ``participantRows`` in Next.js RSC (``unicode_escape`` + ``JSONDecoder.raw_decode``).
  ``scrapers/insidesp_tier2_scraper.py`` + ``api/services/insidesp_tier2_importer.py``
  + CLI ``scripts/scrape_insidesp_tier2.py`` + admin scraper ``insidesp_tier2``.
  Crosswalk-first: gap-fills ``tournament_results`` on matched events only when local
  count is zero; inserts ``insidesp_{slug}`` for IS-only pro events with results.
  Default scope: pro-like keywords + ``results_count > 0`` (same conservative pattern as DP 3b).
- **Phase 5 (done 2026-06-09; deployed on `apps`):** Data-quality pass.
  ``api/services/data_quality_pass.py`` + ``GET /api/admin/data-quality/summary``
  (crosswalk breakdown, Inside Spin API vs local drift, rankings snapshot counts,
  Fargo coverage) + CLI ``scripts/run_data_quality_pass.py`` + SettingsAdmin
  "Data quality (Phase 5)" report button. Alias seeding delegates to
  ``scripts/seed_name_aliases_from_rankings.py`` (extended systems incl. InsideSpin/DigitalPool).
- **Phase 5 follow-up (done 2026-06-09; deployed on `apps`):** Crosswalk review + 1:1 guard.
  ``EventCrosswalkResolver.resolve()`` now rejects fuzzy ``date+name`` matches onto a tournament
  the *same source* already owns under a different event id (1:1 per-source mapping — prevents
  sibling-event merges like Championship League "Group 3" vs "Group 5", Men's vs Women's
  Eurotour/Heyball divisions, junior age brackets). Review API:
  ``GET /api/admin/data-quality/crosswalk/review`` (fuzzy rows pending, lowest score first),
  ``POST .../crosswalk/{id}/confirm``, ``DELETE .../crosswalk/{id}`` (reject; re-ingest creates
  the event), ``POST .../crosswalk/purge-same-source-duplicates`` (super admin). SettingsAdmin
  "Crosswalk review" table with Confirm/Reject. Cleanup run live: **63** provably-wrong fuzzy
  rows purged + 2 women's Heyball rejects → re-ingest inserted the formerly-swallowed events.
  Final: **187** ``insidesp_*`` tournaments, **9,706** results, **0** 1:1 violations,
  **14** fuzzy rows pending operator review. Legacy ``GET /api/rankings/quality`` now requires
  director/admin auth (parity with ``/audit``).

## 7. Risks / open decisions

- **`points` for rank-position systems:** DP Pro Rankings + Inside Spin ratings have no points;
  stored as rank only (`points=0.0`), real values in `source_data`. Confirm leaderboard UI
  treats these as rank-based (don't sort by points for `Competitors_Pool_*` / `InsideSpin_*`).
- **Scope of DP ingestion (Phase 3b):** the DP `events` table is ~1.7k rows (865 public), not
  92k, and ~768 of the DP-only events are local/regional (low relevance to a pro rankings DB).
  Recommend ingesting the curated pro-like-with-placements set first (13), then widening only on
  request. Firehose (all 782) would dilute `tournament_history`. Operator decision — the Phase-3a
  enumerator quantifies each option before any insert.
- **Inside Spin ToS:** none surfaced; it is itself an aggregator. Treat as public-but-courtesy;
  attribute as third-party. Headless history scraping is the most fragile/aggressive part — keep
  opt-in and low-rate.
- **Identity without licenses:** Inside Spin has no license/fargo id; some IS-only players will
  need manual alias review (never fuzzy-surname auto-merge, per §3b).
