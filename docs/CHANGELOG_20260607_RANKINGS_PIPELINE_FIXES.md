# Changelog — Rankings pipeline fixes (2026-06-07)

End-to-end audit + fixes after a live test run of the WPBA Women, WPA (all divisions),
Load WPBA PDF, and CP (External Pool) admin buttons. Companion SSOT docs hold the deep detail:
[`WPBA_TOURNAMENT_SSOT.md`](WPBA_TOURNAMENT_SSOT.md) and
[`WPA_TOURNAMENT_SSOT.md`](WPA_TOURNAMENT_SSOT.md). Remaining work is tracked in
[`RANKINGS_PIPELINE_ROADMAP.md`](RANKINGS_PIPELINE_ROADMAP.md).

## Files changed

| File | Change |
|---|---|
| `scrapers/wpba_scraper.py` | New **word-position parser** `_parse_pages_by_words()` (primary); table/text parsers kept as fallback. |
| `api/routes/rankings.py` | WPA pipeline **per-division resilience**; CP scraper import fixed (`ExternalPoolScraper` → `CpScraper`). |
| `scrapers/externalpool_scraper.py` | `BASE_URL` domain reverted `api.externalpool.com` → **`api.digitalpool.com`** (resolving). |
| `EXTERNAL_POOL_INTEGRATION_COMPLETE.md`, `scripts/scrape_externalpool_comprehensive.py` | Stale dead-domain references reverted to `digitalpool.com`. |
| `docs/WPBA_TOURNAMENT_SSOT.md`, `docs/WPBA_DATA_FLOW.md`, `docs/WPA_TOURNAMENT_SSOT.md` | Documented all of the below. |

---

## 1. WPBA — per-event detail now covers all 166 players (was 18)

**What:** Replaced the WPBA PDF parser's reliance on pdfplumber table extraction (`text`
strategy) with a **word-position parser** that clusters per-event value tokens into column
anchors by x-coordinate and assigns each player's values to the nearest column (blanks → `0`),
with a per-player `sum(in-window) == total` guard. Table/text parsers remain as fallback.

**Why:** The WPBA PDF has **no ruling lines**, so the `text` table strategy mis-split columns
(it produced a garbled 16-column table with the rank not even in column 0). `_parse_table()`
correctly rejected that garbage and fell back to `_parse_text_lines()`, which can only align
players who played **all 10** rolling events (`extract_text()` collapses the blank cells of
sparse rows). Result: only **18 of 166** players had per-event detail; per-event buttons,
History event rosters, and Leaderboard finishes were incomplete for everyone else.

**Verified live (2026-06-07 re-scrape):**
- Parser: `166 players, 166 with per-event detail (0 skipped on sum-check), 11 column anchors`.
- `tournament_results` (`wpba_evt_*`): **18 → 166** distinct players, **180 → 700** result rows.
- Per-event rosters: **~18 → 62–80** finishers per event.
- Leaderboard: all 166 have `total_tournaments_played` (from `stops_played`); podium finishes
  now computed from the full result set.

Detail: [`WPBA_TOURNAMENT_SSOT.md`](WPBA_TOURNAMENT_SSOT.md) §5.

---

## 2. WPA — per-division resilience in the scrape pipeline

**What:** `_run_scraper_pipeline("wpa")` now saves each division independently (try/except per
division). Blocked/failed divisions are collected and surfaced in the run summary
("N division(s) NOT saved: …"); the remaining divisions still save, split, and refresh.

**Why:** On the 2026-06-07 run, the `save_rankings()` anti-data-loss **drop guard** raised on
`WPA_Men` (134 incoming rows vs 205 prior) and the exception propagated, **aborting the entire
WPA run** — so divisions that actually *grew* (Women, Heyball-Women) never saved either, and the
materialized-view refresh/notify never ran. One blocked division should not block the others.

**Note on the drop itself (not a bug):** scrape-history shows the parser is unchanged and the
divisions moved in *both* directions (Men 205→134, Heyball-Men 206→144 down; Women 74→106,
Heyball-Women 118→129 up; Artistic 27→27), which is a **real site-side change** on wpapool.com,
not a scraping regression. The guard behaved correctly. To accept the smaller men's list
intentionally, re-run WPA with `ALLOW_RANKINGS_DROP=1`.

Detail: [`WPA_TOURNAMENT_SSOT.md`](WPA_TOURNAMENT_SSOT.md) §5d, §5e.

---

## 3. CP (External Pool) — import bug fixed + domain regression reverted

**What:**
1. The route imported `ExternalPoolScraper`, a class that no longer exists → every run died with
   `ImportError`. Fixed to `CpScraper`.
2. A prior "digital pool → external pool" rename had also flipped the **live domain**
   `https://api.digitalpool.com` → `https://api.externalpool.com` (which does **not** resolve).
   Reverted the domain to **`api.digitalpool.com`** (git history confirms it as the original).

**Why:** Code identifiers were intentionally renamed to `externalpool` (`CpScraper`,
`externalpool_scraper.py`, `scraped_data/externalpool/`), but the **domain** should never have
been renamed — that broke DNS resolution and masked the real issue. Only the domain was reverted;
code identifiers stay `externalpool`.

**Status:** the domain now resolves, but `api.digitalpool.com` does not answer the scraper's REST
`/rankings/*` path (connection times out). Digital Pool's real API is **GraphQL** at
`api-nyc.digitalpool.com` (already used by `api/services/competitors_import.py`). Aligning
`CpScraper`'s endpoint shape to the real API is tracked in the roadmap.

Detail: [`WPA_TOURNAMENT_SSOT.md`](WPA_TOURNAMENT_SSOT.md) §5f.

---

## Deployment notes

- `scrapers/` and `api/` are **baked into the image** (not bind-mounted), so these changes
  require an image rebuild + container recreate.
- Use **`docker compose` (v2)**, not `docker-compose` (v1): v1 hit a `KeyError: 'ContainerConfig'`
  on recreate and cached COPY layers incorrectly. v2 build/up worked. As a side effect of mixing
  v1/v2, `postgres`/`redis`/`testcenter` are currently running under hash-prefixed container
  names (healthy, data intact via volumes) — see roadmap for the one-time normalization.
