# Rankings pipeline — roadmap / open work

Living TODO for the WPBA + WPA/Heyball + CP rankings data pipeline. Pairs with
[`WPBA_TOURNAMENT_SSOT.md`](WPBA_TOURNAMENT_SSOT.md),
[`WPA_TOURNAMENT_SSOT.md`](WPA_TOURNAMENT_SSOT.md), and
[`CHANGELOG_20260607_RANKINGS_PIPELINE_FIXES.md`](CHANGELOG_20260607_RANKINGS_PIPELINE_FIXES.md).

Status legend: ✅ done · 🟡 in progress / partial · ⬜ not started.

---

## Done

### 2026-06-07

- ✅ **WPBA word-position parser** — all 166 players get per-event detail (was 18).
- ✅ **WPBA dynamic column keys** — `_extract_column_headers()` reads rolling window from PDF
  header; new events (Islands US Open, CPBA Inv) get correct keys/labels.
- ✅ **WPBA tournament-history SSOT** — canonical `wpba_evt_*`; snapshot-pseudo + archive writers
  guarded; one-time dedup cleanup done.
- ✅ **WPBA/WPA leaderboard wiring** — `stops_played`, podium finishes from `tournament_results`.
- ✅ **WPA per-division resilience** — one blocked division no longer aborts the run.
- ✅ **CP import fix** + domain revert (`api.digitalpool.com`).
- ✅ **Tournament History player counts** — `/tournaments/results-counts` + cards show real
  `tournament_results` counts (replaces misleading "Coverage 0/8" for PDF events).
- ✅ **Compose project name** pinned (`name: rankings-bot` in prod compose).

### 2026-06-08 (post full-stack audit)

- ✅ **WPBA pages verified** — Rankings buttons, Leaderboard top 5, Hot Streak, Tournament History
  player counts all match API/DB/scrape SSOT (see audit notes below).
- ✅ **Future Tournaments WPBA bridge** — `refresh-upcoming` ingests `tournament_history`
  upcoming rows; UI shows WPBA (4) + WPA Men (5).
- ✅ **Admin live-log honesty** — parse `[OK]` / `[ERROR]` / "NOT saved" for honest modal status.
- ✅ **Tournament History date display** — `formatLocalDate()` fixes UTC off-by-one on cards.
- ✅ **WPA Men dynamic per-event systems (054)** — `rankings_ranking_system_check` allows
  `WPA_Men_*`; split creates 20 per-event buttons @ 2026-06-08 snapshot (134 players each).

---

## 2026-06-08 audit summary (operator button run)

After pressing all update buttons (excluding Fargo), live verification against API/DB/scrape:

| Area | Verdict | Notes |
|------|---------|-------|
| WPBA Rankings buttons | **PASS** | 11 per-event + overall; Islands/CPBA first |
| WPBA Leaderboard | **PASS** | Tkach 146,750 / 10 stops; top 5 exact match |
| WPBA Hot Streak | **PASS** | Rebekah +53, Savannah +43, Eleanor +39 verified in SQL |
| WPBA Tournament History counts | **PASS** | 62–64 players per newest events |
| WPA scraper | **PARTIAL** | WPA_Men blocked (134 vs 205 = 65.37%); other divisions saved |
| CP scraper | **FAIL** | REST timeout to `api.digitalpool.com`; zero rows saved |
| Future Tournaments | **FAIL (WPBA)** | UI showed WPBA (0) while 5 upcoming rows exist in `tournament_history` |
| Admin success toasts | **FAIL** | "Finished successfully" on CP error and WPA partial save |

---

## Open work (prioritized)

### P0 — Operator trust / honest UI

- ✅ **Admin live-log outcome detection** — modals/toasts distinguish success / warning / failure.
- ⬜ **Shared live-log hook for rebuild + scraper modals** — dedupe the three parallel stream
  implementations in `SettingsAdmin.tsx` (rebuild, scraper-run, shared) into one hook path.
- ⬜ **External Pool tab harvester** — `EXTERNALPOOL_TAB_ARCHIVE_DIR` never populated; every
  tournament still 0/8 on detail tabs if harvest sections are shown. Run
  `scripts/scrape_externalpool_tournaments.py` or hide empty harvest UI (partially done for PDF
  events).

### P1 — Data correctness / completeness

- ✅ **WPA Men drop guard + per-event split** — overall 134 @ 2026-06-08; migration 054 enables
  dynamic `WPA_Men_*` per-event systems (20 buttons).
- ⬜ **WPA Heyball Men asymmetry** — dropped 206→144 (~30%) but **was saved** because
  `WPA_Heyball_Men` is not in `RANKINGS_DROP_GUARD_SYSTEMS`. Decide: add to guard set or document
  as intentional.
- ✅ **CP / External Pool scraper — GraphQL rewrite (was P1 blocker)** — `CpScraper.scrape_rankings()`
  rewritten (2026-06-09) to use Digital Pool's real GraphQL Pro Rankings at
  `api-nyc.digitalpool.com/v1/graphql` (`vw_current_pro_rankings` overall / `vw_current_mens_pro_rankings`
  / `vw_current_womens_pro_rankings`). No more REST timeout; returns live ranks + country, with
  per-system ranks (Fargo/Matchroom/WPA/weighted) preserved in `rankings.source_data`. Pro Rankings are
  rank-position systems so `points=0.0` (no points fabricated). Verified live. Multi-source full-site
  ingestion + insidesp.in is planned separately — see
  [`MULTI_SOURCE_DATA_INTEGRATION_PLAN.md`](MULTI_SOURCE_DATA_INTEGRATION_PLAN.md).
- ✅ **Multi-source de-dup Phase 1 + Inside Spin Phase 2 (done 2026-06-09, deployed `apps`)** —
  `source_event_crosswalk` (Alembic `055`) + `EventCrosswalkResolver` (date-first merge, ollama
  arbitration) keep one `tournament_history.tournament_id` per real event across sources; digitalpool
  backfill seeded 6 rows. Inside Spin Tier-1 scraper (`scrapers/insidesp_scraper.py`, schema.org
  JSON-LD) added with admin button + CLI; ratings saved as `InsideSpin_<discipline>` (Alembic `056`,
  rating/matches in `source_data`, `points=0.0`); events de-dup via the crosswalk (no silent merge).
  Live: 346 ratings + 100 events resolved (all IS-only). See
  [`MULTI_SOURCE_DATA_INTEGRATION_PLAN.md`](MULTI_SOURCE_DATA_INTEGRATION_PLAN.md) §6.
- ✅ **Multi-source Digital Pool Phase 3 (done 2026-06-09, deployed `apps`)** — event discovery +
  curated ingestion (3a/3b: enumerator quantified 1,668 events / 865 public, ingested 13 pro-like-
  with-placements into `tournament_history`) **plus historical rankings fill (3c)**:
  `CpScraper.scrape_pro_world_rankings_history()` + `scripts/load_digitalpool_ranking_history.py`
  load Digital Pool's `pro_world_rankings` time-series (8 systems, 125 snapshots, **15,339 rows**,
  2021-09-30 → 2023-09-05) into `rankings` as `DigitalPool_<system>` (Alembic `057`; rank-position,
  `points=0.0`). Wired into the Rankings UI ("Digital Pool (history)" menu; latest snapshot shown,
  ordered by rank). Historical — complements live CP `vw_current_*` Pro Rankings. See
  [`MULTI_SOURCE_DATA_INTEGRATION_PLAN.md`](MULTI_SOURCE_DATA_INTEGRATION_PLAN.md) §6.
- ✅ **Digital Pool Fargo enrichment Phase 3d (done 2026-06-09, deployed `apps`)** — Alembic `058`
  adds `players.digitalpool_player_id`; `scripts/enrich_players_fargo_from_digitalpool.py` links it by
  unambiguous exact name and fills `players.fargo_score`/`fargo_robustness`/`nationality` (COALESCE
  only — no overrides, country-lock respected). Live: 908 linked, 765 fetched, Fargo coverage
  961 → **1,403** players (+442). Also closed out DP events (UK Open 2022 ingested; 14 DP events
  total — local/regional rest intentionally excluded). See
  [`MULTI_SOURCE_DATA_INTEGRATION_PLAN.md`](MULTI_SOURCE_DATA_INTEGRATION_PLAN.md) §6.
- ✅ **Inside Spin Tier-2 + data quality Phase 4/5 (done 2026-06-09, deployed `apps`)** —
  Tier-2 uses Inside Spin list API (year range) + RSC ``participantRows`` (no headless);
  crosswalk-aware gap-fill/insert via ``insidesp_tier2`` admin scraper. Phase 5 adds
  ``GET /api/admin/data-quality/summary``, drift/crosswalk/Fargo report in SettingsAdmin,
  and alias-seed hook. See [`MULTI_SOURCE_DATA_INTEGRATION_PLAN.md`](MULTI_SOURCE_DATA_INTEGRATION_PLAN.md) §6.
- ✅ **Future Tournaments WPBA (0)** — bridge from `tournament_history` SSOT; refresh loads
  WPBA upcoming events (location TBD fallback for archive rows).
- ⬜ **Cross-source player-name variance (WPA)** — HTML ranking names vs digitalpool result names
  (e.g. married/maiden). License-based identity or curated alias map — not fuzzy surname match.
  See `WPA_TOURNAMENT_SSOT.md` §5a.
- ⬜ **Heyball 0 archived completed events** — leaderboard wiring ready; counts appear once events
  archived.
- ⬜ **2 residual `Competitors_Pool` snapshot-pseudo rows** in `tournament_history` — decide keep vs
  clean.
- ⬜ **12 vs 10 completed `wpba_evt_*` rows** — two rotated-out legacy events (`NAPA2024`,
  `CapitalCity2024`) remain in history; doc says 10. Cosmetic unless they appear in UI menus.

### P2 — Parser / pipeline robustness

- ⬜ **WPBA parser self-test cron** — download live PDF, assert ≥N players with
  `sum(in-window)==total`; catch layout regressions before silent degrade.
- ⬜ **WPA per-division delta in admin log** — surface incoming vs previous count and % in the
  scraper log footer (not just drop-guard block message).
- ⬜ **WPBA event calendar dates** — newest events stored with scrape-date fallback (`2026-06-08`)
  when `_resolve_wpba_event_date()` finds no calendar match; enrich from WPBA schedule source.
- ⬜ **Concurrent scraper log interleaving** — CP + WPA runs can interleave lines in shared log
  handlers; use per-job log file isolation or structured logging.

### P3 — Ops / hygiene

- ✅ **Normalize container names** — `name: rankings-bot` in prod compose (2026-06-08).
- ⬜ **Buildx builder selection** — `alfa-builder` cannot see local `rankings-bot-base:local`;
  document `BUILDX_BUILDER=default` for compose builds on `apps`.
- ⬜ **`scraped_data/*.json` retention** — tracked in git and accumulating; confirm policy.
- ⬜ **(Optional) CI/CD auto-deploy** on push to `apps` → rebuild+recreate without manual
  `./scripts/start.sh`.

### P4 — Fargo (deferred by operator)

- ⬜ **Fargo rating refresh** — separate button/runbook; do after rankings pipeline stable.

---

## Update model (operator reference)

- **Data buttons = live.** Scraper / Load PDF / sync run inside the container, write DB, refresh MVs.
  No rebuild needed for data-only updates.
- **Code changes = rebuild + recreate.** Source is baked into images (`rankings-bot-api`,
  `celery-worker`). Frontend `dist/` is bind-mounted and can update via "Update website" without API
  restart.
- **Deploy path:** `git pull` on target host → `./scripts/start.sh` (or selective rebuild as in
  `docs/PRODUCTION_DEPLOYMENT.md`).

---

## Verification commands

```bash
# WPBA per-event coverage (expect distinct_players ~= 166)
docker exec rankings-bot-postgres psql -U rankingsbot_user -d rankingsbot -c \
  "SELECT COUNT(DISTINCT tr.player_name), COUNT(*) FROM tournament_results tr \
   JOIN tournament_history th ON th.tournament_id=tr.tournament_id \
   WHERE th.association='WPBA' AND th.tournament_id LIKE 'wpba_evt_%';"

# WPA Men snapshot (expect 2026-06-08 after ALLOW_RANKINGS_DROP run)
docker exec rankings-bot-postgres psql -U rankingsbot_user -d rankingsbot -c \
  "SELECT ranking_system, snapshot_date, COUNT(*) FROM rankings \
   WHERE ranking_system='WPA_Men' GROUP BY 1,2 ORDER BY 2 DESC LIMIT 3;"

# Upcoming events by association
docker exec rankings-bot-postgres psql -U rankingsbot_user -d rankingsbot -c \
  "SELECT association, COUNT(*) FROM upcoming_events GROUP BY 1 ORDER BY 1;"

# API checks (from inside API container — host 127.0.0.1:8003 not published)
docker exec rankings-bot-api curl -sf http://localhost:8003/api/rankings/wpba-tournament-systems
docker exec rankings-bot-api curl -sf http://localhost:8003/api/tournament-history/upcoming-events
```
