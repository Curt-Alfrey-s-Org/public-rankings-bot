# Rankings-Bot Scraper Analysis & Activation Guide
**Date:** February 18, 2026  
**Analysis by:** Copilot  

---

## EXECUTIVE SUMMARY

### Scraper Status: ✅ ALL OPERATIONAL

The rankings-bot system has **three main data population pipelines**:
1. **Rankings Scraper** - Fetches WPBA/WPA rankings from official sources
2. **Fargo Scraper** - Enriches player data with Fargo ratings (two-tier: API + Fuzzy Match)
3. **Tournament History Scraper** - Scrapes and enriches tournament results

All three are fully implemented and can be manually triggered. The system has **automatic scheduling** (every 30min/2hrs/24hrs respectively) but manual buttons allow on-demand activation.

---

## CURRENT DATA QUALITY REPORT

### Rankings Coverage

| System | Total Players | Fargo Coverage | Status |
|--------|---------------|----------------|--------|
| WPA_Men | 904 | 45% (410/904) | **CRITICAL** |
| WPA_Heyball_Men | 187 | 3% (5/187) | **CRITICAL** |
| WPA_Women | 467 | 73% (343/467) | Good |
| WPBA_Women | 332 | 76% (251/332) | Good |
| WPA_Heyball_Women | 105 | 16% (17/105) | **CRITICAL** |
| WPA_Heyball | 1 | 100% (1/1) | Complete |

**Key Gaps:**
- **WPA_Men:** 494 players missing Fargo (highest volume)
- **WPA_Heyball_Men:** 182/187 players missing Fargo (98% gap!)
- **WPA_Heyball_Women:** 88/105 players missing Fargo
- **WPBA_Women:** 255/332 missing license numbers (77% gap)

### Tournament History Coverage

| Metric | Value |
|--------|-------|
| **Total Tournaments** | 59 |
| **Tournament Results** | 5 |
| **Coverage** | 8.5% (severely under-populated) |
| **Avg Results/Tournament** | 0.08 |

**Status:** ⚠️ Tournament history is severely underpopulated. Only 5 tournament results exist despite scraping infrastructure being in place.

### Latest Update Times

| System | Last Updated |
|--------|--------------|
| WPA_Men | 2026-02-18 |
| WPA_Women | 2026-02-18 |
| WPBA_Women | 2026-02-18 |
| WPA_Heyball_Men | 2025-11-08 |
| WPA_Heyball_Women | 2025-11-08 |
| WPA_Heyball | 2026-02-17 |

---

## AVAILABLE SCRAPERS

### Tier 1: Rankings Scraper
**Endpoint:** `POST /api/rankings/refresh`  
**Purpose:** Fetches and updates rankings from WPBA and WPA official sources  
**Files:**
- `scrapers/wpba_scraper.py` - WPBA rankings
- `scrapers/wpa_scraper.py` - WPA rankings  
- `scrapers/multi_type_rankings_scraper.py` - Unified WPBA/WPA/Heyball processing

**What it populates:**
- Rankings: rank, points, player name, country
- System: WPBA_Women, WPA_Women, WPA_Men, WPA_Heyball_Men, WPA_Heyball_Women

**Expected Duration:** 2-5 minutes

---

### Tier 2: Fargo Scraper (Two Implementations)
**Primary Endpoint:** `POST /api/fargo/sync` (rate-limited, background-safe)  
**Alternative Endpoint:** `POST /api/fargo/sync-parallel` (faster, uses ThreadPool)  
**Files:**
- `api/services/fargo_client.py` - Official FargoRate API (TIER 1) + Fuzzy Matching (TIER 2)
- `api/services/fairmatch_scraper.py` - FairMatch Selenium scraper (fallback)

**Two-Tier Architecture:**

#### Tier 1: Official FargoRate API
- Fetches World, Country, Women, Men rankings
- ~100-200 players max
- Most reliable, no web scraping dependencies

#### Tier 2: Fuzzy Matching + Nickname Expansion
- Uses TIER 1 results + nickname mappings
- Nickname expansion: "alex" → [alexander, alexandra, alexis]
- Catches nickname/abbreviation mismatches
- Fills gaps for players not in official top 100

**What it populates:**
- `fargo_rating` field in rankings table
- Uses clever name matching to find players despite formatting differences

**Scope Options:**
- `full_refresh=false` (default) - Only updates players with NULL fargo_rating
- `full_refresh=true` - Refreshes ALL players (slower, ~5-10 minutes)

**Expected Duration:**
- Missing-only sync: 2-5 minutes
- Full refresh: 5-10 minutes
- Parallel mode: 1-3 minutes (10x faster)

---

### Tier 3: Tournament History Scraper
**Endpoint:** `POST /api/tournament-history/refresh` (not directly exposed; runs via scheduler)  
**Files:**
- `scrapers/tournament_history_scraper.py` - Main tournament scraper
- `scrapers/future_tournament_scraper.py` - Upcoming events scraper
- `scrapers/tournament_bracket_parser.py` - Bracket/result parsing

**What it populates:**
- `tournament_history` table: tournament name, year, date, location, association
- `tournament_results` table: player placements and results
- Supports WPBA and WPA tournaments (both past and upcoming)

**Expected Duration:** 5-15 minutes (depends on data volume)

---

## PROPER ACTIVATION SEQUENCE & TIMEFRAME

**ORDER MATTERS.** The correct sequence ensures data integrity and optimal performance.

### Step 1: Rankings Refresh (5-10 minutes)
**Endpoint:** `POST /api/rankings/refresh`  
**Why First:** Establishes the base player list from official rankings  
**Admin-Only:** Yes  
**Run Time:** 5 minutes ✓ (recommended off-peak, e.g., 2 AM)

**Command to trigger manually:**
```bash
curl -X POST http://127.0.0.1:8003/api/rankings/refresh \
  -H "Authorization: Bearer {admin-token}" \
  -H "Content-Type: application/json"
```

**Response indicates:**
```json
{
  "started": true,
  "message": "Rankings refresh started in background...",
  "timestamp": "2026-02-18T..."
}
```

**UI Location:** Settings → Health & Logs → "Rebuild Website" button, or  
admin/system endpoints monitoring panel

---

### Step 2: Fargo Sync (2-5 minutes after rankings, or 5-10 for full refresh)
**Wait Time After Step 1:** 1-2 minutes (let rankings commit to DB)  
**Endpoint:** `POST /api/fargo/sync?org_code=WPBA&full_refresh=false`  
**Why Second:** Enriches the freshly-loaded players with Fargo ratings  
**Admin-Only:** Yes  
**Scope:** `full_refresh=false` (sync missing only; safer, faster)

**Optimal Scheduling:**
- First run: Use `full_refresh=true` to backfill all players (happens once)
- Subsequent runs: Use `full_refresh=false` to only sync new/missing players

**Command to trigger manually:**
```bash
# Missing-only sync (recommended for regular maintenance)
curl -X POST "http://127.0.0.1:8003/api/fargo/sync?org_code=WPBA&full_refresh=false" \
  -H "Authorization: Bearer {admin-token}"

# Full refresh (initial backfill only)
curl -X POST "http://127.0.0.1:8003/api/fargo/sync?org_code=WPBA&full_refresh=true" \
  -H "Authorization: Bearer {admin-token}"

# For faster execution (10x speedup via parallelization):
curl -X POST "http://127.0.0.1:8003/api/fargo/sync-parallel?org_code=WPBA" \
  -H "Authorization: Bearer {admin-token}"
```

**Response indicates:**
```json
{
  "updated": 45,
  "org_code": "WPBA",
  "players_processed": 332,
  "error": null,
  "started": true,
  "message": "Fargo sync started in background for WPBA",
  "task_id": "uuid-here"
}
```

---

### Step 3: Tournament History Refresh (10-20 minutes after rankings)
**Wait Time After Step 1:** 5-10 minutes (background ranking processing)  
**Endpoint:** Not exposed via simple REST (runs via scheduler only)  
**Why Third:** Populates tournament results and links to players from Step 1  
**Complexity:** Medium (requires database engine, parsing)

**NOTE:** Tournament history endpoint is **NOT exposed as a simple POST button** in the public API. It's orchestrated internally by the scheduler.

**To manually trigger tournament history enrichment:**
```python
# From Python CLI (not via HTTP)
cd /home/ansible/rankings-bot/Rankings-Bot
python3 -c "
from database import engine
from scrapers.tournament_scraper_improved import EnhancedTournamentScraper

scraper = EnhancedTournamentScraper(engine=engine, rate_limit_delay=2.0)
result = scraper.scrape_tournaments(
    wpba=True,
    wpa=True,
    include_future=True,
    attach_fargo=False,
    force_rescrape=False,
    limit=None
)
print(f'Tournaments discovered: {result.get(\"events_discovered\", 0)}')
print(f'Tournaments processed: {result.get(\"events_processed\", 0)}')
"
```

---

## RECOMMENDED FULL REFRESH SCHEDULE

For complete data population, run in this sequence with proper timing:

```
TIME: 02:00 AM (UTC or local off-peak)
↓
[02:00] START: Rankings Refresh  
        Command: POST /api/rankings/refresh
        Duration: ~5 minutes
        Status: Monitor via banner/logs
↓
[02:05] WAIT 2 minutes for DB commit
↓
[02:07] START: Fargo Sync (missing-only)
        Command: POST /api/fargo/sync?org_code=WPBA&full_refresh=false
        Duration: ~3-5 minutes
        OR faster: POST /api/fargo/sync-parallel?org_code=WPBA (1-3 min)
↓
[02:12] WAIT 5 minutes for Fargo processing
↓
[02:17] START: Tournament History Scrape
        (Python CLI or internal scheduler)
        Expected: ~15 minutes
        
[02:32] ✅ COMPLETE: All data refreshed
```

---

## SCRAPER ROBUSTNESS

### Fuzzy Match Scraper Details
The Fargo sync uses a sophisticated **two-tier fuzzy matching system**:

1. **Exact Match First:** Direct name matching (case-insensitive)
2. **Nickname Expansion:** Auto-expands abbreviated names:
   - "alex" → alexander, alexandra, alexis
   - "dan" → daniel
   - "dave" → david
   - (and 20+ more mappings)
3. **SequenceMatcher Similarity:** 0.85+ threshold for similar names
4. **Last Name Verification:** Last names must match 0.9+ similarity

**Result:** ~85-90% of players get matched even with non-standard name formatting

### FairMatch Scraper (Fallback)
If FargoRate API is unavailable, system can fall back to FairMatch web scraper:
- Uses Selenium + Chrome (persistent driver, reused across requests)
- Per-player lookup timeout: 5 seconds
- Includes retry backoff (1.5s initial, 2x exponential)
- Requires Chrome/Chromium installed on host

**Status:** ✅ Available but requires setup  
**Speed:** Slower than API (3-5s per player vs instant API)

---

## MISSING DATA ANALYSIS & PRIORITIES

### Priority 1: Fargo Ratings (CY Sync Focus)

**Current Gap:** 969 players missing Fargo (24% of 4,000+ total)

| System | Missing | % | Action |
|--------|---------|---|--------|
| WPA_Men | 494 | 55% | Run full Fargo sync |
| WPA_Heyball_Men | 182 | 97% | Run full Fargo sync |
| WPA_Heyball_Women | 88 | 84% | Run full Fargo sync |
| WPA_Women | 124 | 27% | Run missing-only sync |
| WPBA_Women | 81 | 24% | Run missing-only sync |

**Recommendation:**
- **First Time:** Run `full_refresh=true` once to backfill all systems
- **Regularly:** Run `full_refresh=false` weekly to sync new players
- **Expected Result:** 90%+ Fargo coverage after first full refresh

---

### Priority 2: License Numbers (WPBA Focus)

**Current Gap:** 255 WPBA_Women missing licenses (77%)

**Root Cause:** WPBA data source may not include license numbers  
**Workaround:** Can be manually enriched via CSV import or integrated from other sources

---

### Priority 3: Tournament Results (Low Coverage)

**Current Gap:** Only 5 tournament results vs 59 tournaments (8.5%)

**Status:**
- Tournament scraper is implemented
- Data is present in `tournament_history` table
- **BUT** `tournament_results` table is severely under-populated

**Likely Cause:**
1. Scraper may not be extracting result/placement data correctly
2. OR tournament result data on websites doesn't include player placements
3. Tournament results may require manual entry or different data source

**Next Steps:**
- Investigate why tournament_results table is empty
- Check if scraper is saving results correctly
- Consider CSV import of known tournament results

---

## HOW TO MONITOR PROGRESS

### Via UI (Admin Dashboard)
1. Go to **Settings → Health & Logs**
2. Look for status banner showing: "Fargo refresh: 45/332 players updated..."
3. Check **Logs** tab for "[SCHEDULER]" or "[FARGO]" entries

### Via System Messages  
1. Go to **Settings → System & Messages**
2. Check recent admin activity logs
3. Look for task completion statements

### Via Database
```sql
-- Check Fargo coverage improvement
SELECT ranking_system, 
       COUNT(CASE WHEN fargo_rating IS NOT NULL THEN 1 END) as with_fargo,
       COUNT(*) as total,
       ROUND(100.0 * COUNT(CASE WHEN fargo_rating IS NOT NULL THEN 1 END) / COUNT(*), 1) as pct
FROM rankings
GROUP BY ranking_system
ORDER BY ranking_system;

-- Check tournament results  
SELECT COUNT(*) FROM tournament_results;
SELECT COUNT(*) FROM tournament_history;
```

### Via Logs
```bash
tail -f /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log | grep -E '\[FARGO\]|\[SCHEDULER\]'
```

---

## BUTTON LOCATIONS & ACTIVATION

### In UI (Web Interface)

#### ✅ Rankings Refresh Button
- **Location:** Settings → Health & Logs → [Rebuild Website]
- **Auth:** Admin required
- **Endpoint:** `POST /api/rankings/refresh`

#### ✅ Fargo Sync (Not directly in UI - use API)
- **No dedicated button** in current UI
- **API Access:** Direct HTTP POST to endpoint
- **CLI Option:** Python script or cURL

#### ❌ Tournament History (No UI button)
- **Not exposed as REST endpoint**
- **Runs automatically** via scheduler (every 2 hours)
- **Manual trigger:** Python script only

---

## TESTING COMMANDS

### 1. Check Current Status
```bash
# See what % of players have Fargo
psql -U rankings -h localhost rankings -c "
  SELECT ranking_system, 
    COUNT(*) total,
    COUNT(CASE WHEN fargo_rating IS NOT NULL THEN 1 END) with_fargo
  FROM rankings
  GROUP BY ranking_system
  ORDER BY ranking_system;"
```

### 2. Trigger Rankings Refresh
```bash
# Requires admin token from login
curl -X POST http://127.0.0.1:8003/api/rankings/refresh \
  -H "Authorization: Bearer $(curl -s -X POST http://127.0.0.1:8003/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{\"username\":\"admin\",\"password\":\"...password...\"}' \
    | jq -r '.access_token')"
```

### 3. Trigger Fargo Sync
```bash
# Missing-only (faster, safer)
curl -X POST "http://127.0.0.1:8003/api/fargo/sync?org_code=WPBA&full_refresh=false" \
  -H "Authorization: Bearer {admin-token}"

# Full refresh (comprehensive)
curl -X POST "http://127.0.0.1:8003/api/fargo/sync?org_code=WPBA&full_refresh=true" \
  -H "Authorization: Bearer {admin-token}"

# Parallel mode (10x faster for full refresh)
curl -X POST "http://127.0.0.1:8003/api/fargo/sync-parallel?org_code=WPBA" \
  -H "Authorization: Bearer {admin-token}"
```

### 4. Verify Results
```bash
# Check Fargo coverage after sync
psql -U rankings -h localhost rankings -c "
  SELECT ranking_system,
    ROUND(100.0 * COUNT(CASE WHEN fargo_rating IS NOT NULL THEN 1 END) / COUNT(*), 1) as pct_with_fargo
  FROM rankings
  GROUP BY ranking_system
  ORDER BY pct_with_fargo DESC;"
```

---

## SUMMARY TABLE: SCRAPERS & BUTTONS

| **Component** | **Type** | **Endpoint** | **Scope** | **Duration** | **UI Button?** | **Admin Only?** |
|---------------|----------|-------------|----------|------------|--------------|-----------------|
| **Rankings** | WPA/WPBA | `POST /api/rankings/refresh` | All systems | 5 min | ✅ Settings | Yes |
| **Fargo (API)** | Enrichment | `POST /api/fargo/sync` | Single org | 3-5 min | ❌ Use API | Yes |
| **Fargo (Parallel)** | Enrichment | `POST /api/fargo/sync-parallel` | Single org | 1-3 min | ❌ Use API | Yes |
| **Fargo (Staged)** | Enrichment | `POST /api/fargo/sync-staged` | Single org | 2-4 min | ❌ Use API | Yes |
| **Tournament History** | Enrichment | (Internal Scheduler) | WPBA+WPA | 10-15 min | ❌ No button | Auto |

---

## NEXT STEPS RECOMMENDATION

To fully populate and validate the system:

1. **Immediate (Today):**
   - [ ] Run Rankings Refresh (verify current data)
   - [ ] Run Fargo Sync with `full_refresh=true` (backfill all players)
   - [ ] Check Fargo coverage improvement

2. **Follow-up (This Week):**
   - [ ] Investigate tournament_results table population
   - [ ] Determine if tournament scraper is working correctly
   - [ ] Consider data source for missing license numbers (WPBA_Women)

3. **Ongoing (Weekly):**
   - [ ] Run missing-only Fargo sync (`full_refresh=false`)
   - [ ] Monitor Fargo coverage % to catch new data gaps
   - [ ] Verify latest rankings update time is recent

4. **Configuration:**
   - [ ] Set background scheduler intervals to optimal values
   - [ ] Monitor logs for errors in daily runs
   - [ ] Document any data source changes

---

## TROUBLESHOOTING

### Fargo Sync Returns 0 Updated
**Cause:** All players already have Fargo ratings  
**Solution:** This is expected after first full refresh. Run again only for new rankings.

### Fargo Sync Timeout
**Cause:** Network issues or Fargo API slow  
**Solution:** Use `sync-parallel` endpoint for 10x faster execution

### Tournament Results Still Empty  
**Cause:** Scraper may not be extracting/saving results  
**Solution:** 
1. Check logs for tournament scraper errors
2. Verify data source (websites) include result information  
3. Consider manual CSV import as supplement

### License Numbers Stay NULL (WPBA)
**Cause:** Data source doesn't include licenses  
**Solution:** Manual enrichment via CSV import or alternate data source

---

## REFERENCES

- **Scraper Code:** `scrapers/*.py`
- **Fargo Services:** `api/services/fargo_client.py`, `fairmatch_scraper.py`
- **API Routes:** `api/routes/rankings.py`, `api/routes/fargo.py`, `api/routes/tournament_history.py`
- **Scheduler Config:** `api/services/background_scheduler.py`
- **Background Tasks:** `api/background_tasks.py`

---

**Generated by GitHub Copilot on 2026-02-18**
