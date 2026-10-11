# Fargo Scraper Three-Tier Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       FARGO SYNC ORCHESTRATOR                            │
│                 sync_fargo_ratings_rate_limited()                        │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │  Get Database Context │
                    │  - Player names       │
                    │  - Ambiguous names    │
                    └───────────┬───────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌──────────────┐        ┌──────────────┐       ┌──────────────┐
│   TIER 1     │        │   TIER 2     │       │   TIER 3     │
│  Official    │        │    Fuzzy     │       │  FairMatch   │
│  FargoRate   │        │  Matching    │       │   Scraper    │
│     API      │        │              │       │  (Fallback)  │
└──────┬───────┘        └──────┬───────┘       └──────┬───────┘
       │                       │                      │
       │ ┌─────────────────────┘                      │
       │ │                                            │
       ▼ ▼                                            ▼
┌──────────────────────────────┐            ┌─────────────────┐
│  TIER 1: Official Lists      │            │ TIER 3: Lookup  │
│  ────────────────────────    │            │ ─────────────── │
│  1. World Top 100           │            │ Only triggered  │
│  2. Country Top 100         │            │ for players NOT │
│  3. Women Top 100           │            │ matched by      │
│  4. Men Top 100             │            │ TIER 1+2        │
│                              │            │                 │
│  Result: ~300 players       │            │ Uses:           │
│  Coverage: 158 matched      │            │ - Chrome/driver │
│                              │            │ - Rate limited  │
│  ✓ Keep FIRST occurrence    │            │ - Retry logic   │
│    (World = authoritative)  │            │                 │
└──────────────┬───────────────┘            └────────┬────────┘
               │                                     │
               │ ┌───────────────────────────────────┘
               │ │
               ▼ ▼
       ┌────────────────────────┐
       │  TIER 2: Fuzzy Match   │
       │  ─────────────────────  │
       │  Uses TIER 1 results + │
       │  database names:       │
       │                        │
       │  1. Canonical form:    │
       │     "Alex Kazakis" →   │
       │     "Kazakis,Alexander"│
       │                        │
       │  2. Nickname map:      │
       │     alex → alexander   │
       │     jos → joseph       │
       │     ... (26+ pairs)    │
       │                        │
       │  3. Fuzzy string match:│
       │     SequenceMatcher    │
       │     threshold = 0.85   │
       │                        │
       │  Result: 167 additional│
       │  Coverage: No API calls│
       └────────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │  Database Update     │
         │  ───────────────     │
         │  UPDATE rankings     │
         │  SET                 │
         │    fargo_rating = X  │
         │    fargo_last_updated│
         │    fargo_source_name │
         │                      │
         │  ✓ Parameterized SQL │
         │  ✓ Source tracking   │
         │  ✓ Transaction safe  │
         └──────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │   Summary & Logging  │
         │   ─────────────────  │
         │   Total: 325 updated │
         │   TIER1: 158         │
         │   TIER2: 167         │
         │   TIER3: 0           │
         │   Failed: 1          │
         │                      │
         │   ✓ Admin messages   │
         │   ✓ Problem tracking │
         └──────────────────────┘


═══════════════════════════════════════════════════════════════
                      DATA FLOW DETAIL
═══════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────┐
│  INPUT: Database Player Names (Latest Snapshot)             │
│  ─────────────────────────────────────────────────────────  │
│  Example:                                                   │
│  - "Kazakis, Alexander"  (Last, First format)              │
│  - "Lee, Jeanette"                                         │
│  - "Van Boening, Shane"                                    │
│  Total: 280 players (WPA_Men)                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  TIER 1 FETCH: dashboard.fargorate.com/api/TopListsForWeb  │
│  ─────────────────────────────────────────────────────────  │
│  Returns:                                                   │
│  - "Alexander Kazakis": 824  (First Last format)           │
│  - "Jeanette Lee": 900                                     │
│  - "Shane Van Boening": 847                                │
│                                                             │
│  ⚠️  KEY FIX: Keep FIRST occurrence (World), not highest    │
│      If World=824 and Country=860 → Keep 824 ✅             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  TIER 2 MATCHING: Canonical + Fuzzy + Nicknames            │
│  ─────────────────────────────────────────────────────────  │
│  1. Build lookup maps:                                     │
│     canonical_to_db = {                                    │
│       "alexander kazakis": ["Kazakis, Alexander"],         │
│       "jeanette lee": ["Lee, Jeanette"],                   │
│       ...                                                  │
│     }                                                      │
│                                                            │
│  2. For each TIER1 result:                                │
│     a) Try exact canonical match:                         │
│        "Alexander Kazakis" → "alexander kazakis"          │
│        → Found: "Kazakis, Alexander" ✓                    │
│                                                            │
│     b) If no match, try fuzzy with nicknames:             │
│        "Alex Kazakis" vs "Kazakis, Alexander"             │
│        → parse_name("Alex Kazakis") = ("alex", "kazakis") │
│        → parse_name("Kazakis, Alexander") =               │
│          ("alexander", "kazakis")                         │
│        → NICKNAME_MAP["alex"] = ["alexander", ...]        │
│        → Last names match + nickname match → MATCH! ✓     │
│                                                            │
│  3. Skip ambiguous names (in both men's/women's systems)  │
│                                                            │
│  Result: 167 additional matches via fuzzy logic           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  TIER 3 FALLBACK: FairMatch Scraper                        │
│  ─────────────────────────────────────────────────────────  │
│  Only runs for players NOT in TIER1+2 results:             │
│  - Remaining: ["Thaha Rafeek, Musthak Ahamed"]             │
│                                                             │
│  Process:                                                   │
│  1. Batch players (default: 25 per batch)                  │
│  2. Parallel lookups (default: 10 workers)                 │
│  3. Rate limit between batches (0.5s delay)                │
│  4. Retry on transient errors (2 retries, 2s delay)        │
│                                                             │
│  Result: 0 successful, 1 failed                             │
│  Failed logged to admin_messages for manual review          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  DATABASE UPDATE: Parameterized SQL                         │
│  ─────────────────────────────────────────────────────────  │
│  UPDATE rankings                                            │
│  SET                                                        │
│    fargo_rating = %s,              -- 824                  │
│    fargo_last_updated = %s,        -- '2026-02-17...'      │
│    fargo_source_name = %s          -- 'Alexander Kazakis'  │
│  WHERE player_name = %s;           -- 'Kazakis, Alexander' │
│                                                             │
│  ✓ SQL injection safe (parameterized)                      │
│  ✓ Source name tracked for future lookups                  │
│  ✓ Transaction commits on success                          │
│                                                             │
│  Result: 325 rows updated (158 + 167 + 0)                  │
└─────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════
                    ERROR HANDLING FLOW
═══════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────┐
│  TIER 1 Fails (Network/API Down)                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                 ┌────────────────────────┐
                 │  Log warning           │
                 │  Set last_error        │
                 │  Continue to TIER 2    │
                 │  (graceful degradation)│
                 └────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  TIER 2 Skipped (No TIER1 results)                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                 ┌────────────────────────┐
                 │  Proceed to TIER 3     │
                 │  All players attempted │
                 └────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  TIER 3 Fails (Rate Limit / Chrome Not Available)          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                 ┌────────────────────────┐
                 │  Log to admin_messages │
                 │  Return failed list    │
                 │  Set error message     │
                 └────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  FINAL SUMMARY                                              │
│  ─────────────────────────────────────────────────────────  │
│  Total updated: N (sum of all tiers that succeeded)        │
│  Error: "Most severe error encountered" or None            │
│  Failed: [list of players requiring manual attention]      │
└─────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════
                      LOGGING EXAMPLES
═══════════════════════════════════════════════════════════════

[TIER1] Starting fetch of official FargoRate Top-pool_opt_in lists...
[TIER1] Fetched 291 unique players from Top-pool_opt_in lists
[TIER1] Updated 158/291 TIER1 players in database

[TIER2] Starting fuzzy match of 291 TIER1 results to 280 database players...
[TIER2] Fuzzy match: 'Alex Kazakis' ↔ 'Kazakis, Alexander' (nicknames: alex ↔ alexander)
[TIER2] Fuzzy match complete: 291 newly matched from TIER1
[TIER2] Updated 167/291 TIER2-fuzzy-matched players in database

[TIER3] Starting per-player lookups for 1 players using FairMatch (batch_size=25, workers=10)
[TIER3] Complete: 0 successful, 1 failed, error: Rating not found for player 'Thaha Rafeek, Musthak Ahamed' after 2 variants

FARGO SYNC COMPLETE: updated=325, failed=1, error=Rating not found...
```
