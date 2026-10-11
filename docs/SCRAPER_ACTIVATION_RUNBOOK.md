# Rankings-Bot: Scraper Activation Runbook
**Date:** February 18, 2026  
**Purpose:** Step-by-step guide to activate all three data scrapers and populate missing player data

---

## PREREQ CHECK

Verify the system is ready:

```bash
# Check database connectivity
psql -U rankings -h localhost rankings -c "SELECT COUNT(*) as player_count FROM rankings;" || echo "DB ERROR"

# Check if API is running
curl -s http://127.0.0.1:8003/api/system/status | jq . || echo "API DOWN"

# Check available disk space
df -h | grep /
```

Expected output:
```
 player_count
──────────────
        2798
{"status": "ok"}
Filesystem      Size  Used Avail Use% Mounted on...
```

---

## ACTIVATION SEQUENCE (CORRECT ORDER REQUIRED)

### PHASE 1: BASELINE DATA CHECK (Before)

**Run this to see current state:**

```bash
psql -U rankings -h localhost rankings << 'SQL'
\echo '=== BASELINE DATA CHECK ==='
\echo ''
\echo 'Rankings by System:'
SELECT ranking_system, COUNT(*) as players
FROM rankings
GROUP BY ranking_system
ORDER BY ranking_system;

\echo ''
\echo 'Fargo Coverage (% with ratings):'
SELECT ranking_system, 
  COUNT(*) as total,
  COUNT(CASE WHEN fargo_rating IS NOT NULL THEN 1 END) as with_fargo,
  ROUND(100.0 * COUNT(CASE WHEN fargo_rating IS NOT NULL THEN 1 END) / COUNT(*), 1) as pct
FROM rankings
GROUP BY ranking_system
ORDER BY ranking_system;

\echo ''
\echo 'Tournament Data:'
SELECT 'Tournaments' as metric, COUNT(*) as value FROM tournament_history
UNION ALL
SELECT 'Tournament Results', COUNT(*) FROM tournament_results
UNION ALL
SELECT 'Players in Results', COUNT(DISTINCT player_name) FROM tournament_results;

\echo ''
\echo 'Timestamp of this check:'
SELECT NOW();
SQL
```

**Expected Output:**
```
=== BASELINE DATA CHECK ===

Rankings by System:
 ranking_system  | players
─────────────────+---------
 WPA_Heyball     |       1
 WPA_Heyball_Men |     187
 WPA_Heyball_Women|     105
 WPA_Men         |     904
 WPA_Women       |     467
 WPBA_Women      |     332

Fargo Coverage (% with ratings):
 ranking_system  | total | with_fargo |  pct
─────────────────+-------+────────────+────────
 WPA_Men         |   904 |        410 | 45.4
 WPA_Women       |   467 |        343 | 73.4
 WPBA_Women      |   332 |        251 | 75.6
 WPA_Heyball_Men |   187 |          5 | 2.7
 WPA_Heyball_Women|   105 |         17 | 16.2
 WPA_Heyball     |     1 |          1 | 100.0

Tournament Data:
      metric      | value
──────────────────+───────
 Tournaments      |    59
 Tournament Results|     5
 Players in Results|     2

Timestamp of this check:
 2026-02-18 14:45:30.123456+00
```

Save this output for comparison later.

---

### PHASE 2: STEP 1 - RANKINGS REFRESH (5-10 minutes)

**Purpose:** Update/refresh all WPBA and WPA rankings

**Step 2a: Verify you have admin token**

```bash
# If you don't have a token, log in
TOKEN=$(curl -s -X POST http://127.0.0.1:8003/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "YOUR_PASSWORD_HERE"
  }' | jq -r '.access_token // empty')

if [ -z "$TOKEN" ]; then
  echo "ERROR: Could not get token. Check credentials."
  exit 1
fi

echo "✅ Got admin token: ${TOKEN:0:20}..."
```

**Step 2b: Trigger rankings refresh**

```bash
echo "🔄 Starting Rankings Refresh..."
RESPONSE=$(curl -s -X POST http://127.0.0.1:8003/api/rankings/refresh \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")

echo "$RESPONSE" | jq .

# Check if it started successfully
if echo "$RESPONSE" | jq -e '.started == true' > /dev/null 2>&1; then
  echo "✅ Rankings refresh STARTED"
else
  echo "❌ Rankings refresh FAILED"
  exit 1
fi
```

**Expected Response:**
```json
{
  "started": true,
  "message": "Rankings refresh started in background. Watch the banner at top for progress.",
  "timestamp": "2026-02-18T14:46:15.123456"
}
```

**Step 2c: Monitor progress (watch logs)**

```bash
# In separate terminal, watch rankings log
tail -f /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log | grep -E "\[RANKINGS\]|\[SCRAPER\]|refresh"

# Expected output:
# [RANKINGS] Starting WPA_Women scraper...
# [RANKINGS] Loaded 467 players from WPA
# [RANKINGS] Starting WPBA_Women scraper...
# [RANKINGS] Loaded 332 players from WPBA
# [RANKINGS] Refresh complete in 4.2 seconds
```

**Step 2d: Verify completion (check DB after 5 min)**

```bash
# After 5 minutes, run the baseline query again
psql -U rankings -h localhost rankings << 'SQL'
SELECT 'Post-Refresh' as phase,
  ranking_system,
  COUNT(*) as players,
  ROUND(100.0 * COUNT(CASE WHEN fargo_rating IS NOT NULL THEN 1 END) / COUNT(*), 1) as fargo_coverage_pct
FROM rankings
GROUP BY ranking_system
ORDER BY ranking_system;
SQL
```

**Expected:** Same player counts as before (Fargo % unchanged - will change in Step 3)

✅ **Phase 2 Complete when:** You see log message "refresh complete" or database query returns data

---

### PHASE 3: STEP 2 - FARGO SYNC (3-10 minutes AFTER Phase 2)

**⏸️ WAIT 2-3 MINUTES** before starting Fargo sync (let rankings commit)

**Purpose:** Enrich player data with Fargo ratings

**Step 3a: Choose sync strategy**

Two options:

**Option A: Missing-Only (RECOMMENDED for maintenance)**
```bash
echo "🔄 Starting Fargo Sync (Missing Only)..."
RESPONSE=$(curl -s -X POST "http://127.0.0.1:8003/api/fargo/sync?org_code=WPBA&full_refresh=false" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")

echo "$RESPONSE" | jq .
```

**Option B: Full Refresh (RECOMMENDED first-time)**
```bash
echo "🔄 Starting Fargo Sync (Full Refresh)..."  
RESPONSE=$(curl -s -X POST "http://127.0.0.1:8003/api/fargo/sync?org_code=WPBA&full_refresh=true" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")

echo "$RESPONSE" | jq .
```

**Option C: Parallel Mode (10x FASTER)**
```bash
echo "🔄 Starting Fargo Sync (Parallel Mode - FASTEST)..."
RESPONSE=$(curl -s -X POST "http://127.0.0.1:8003/api/fargo/sync-parallel?org_code=WPBA" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")

echo "$RESPONSE" | jq .
```

**Expected Response:**
```json
{
  "updated": 0,
  "org_code": "WPBA",
  "players_processed": 332,
  "error": null,
  "started": true,
  "message": "Fargo sync started in background for WPBA",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Step 3b: Monitor Fargo sync progress**

```bash
# Watch logs for Fargo updates
tail -f /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log | grep -E "\[FARGO\]|\[TIER"

# Expected output:
# [FARGO] [TIER1] Fetched FargoRate API rankings...
# [FARGO] [TIER2] Starting fuzzy match for 494 players...
# [FARGO] [TIER2] Matched "alex johnson" (alex j) - rating 750
# [FARGO] [TIER2] Matched "dan smith" (d. smith) - rating 680
# [FARGO] Fargo sync completed: 156 ratings updated
```

**Step 3c: Verify Fargo coverage improvement**

After ~3-5 minutes, check if Fargo ratings increased:

```bash
psql -U rankings -h localhost rankings << 'SQL'
SELECT ranking_system,
  COUNT(*) as total,
  COUNT(CASE WHEN fargo_rating IS NOT NULL THEN 1 END) as with_fargo,
  ROUND(100.0 * COUNT(CASE WHEN fargo_rating IS NOT NULL THEN 1 END) / COUNT(*), 1) as pct
FROM rankings
GROUP BY ranking_system
ORDER BY pct DESC;
SQL
```

**Expected Output (after full refresh):**
```
 ranking_system  | total | with_fargo |  pct
─────────────────┤───────┼────────────┼────────
 WPBA_Women      |   332 |        297 | 89.4  ← improved from 75.6%
 WPA_Women       |   467 |        403 | 86.3  ← improved from 73.4%
 WPA_Men         |   904 |        623 | 68.9  ← improved from 45.4%
 WPA_Heyball     |     1 |          1 | 100.0
 WPA_Heyball_Women|    105 |         72 | 68.6  ← improved from 16.2%
 WPA_Heyball_Men |   187 |         89 | 47.6  ← improved from 2.7%
```

✅ **Phase 3 Complete when:** You see significant improvement in Fargo coverage %

---

### PHASE 4: STEP 3 - TOURNAMENT HISTORY ENRICHMENT (5-20 minutes AFTER Phase 3)

**⏸️ WAIT 5-10 MINUTES** before starting tournament sync (architecture allows updates to propoagate)

**Purpose:** Scrape and populate tournament results

**⚠️ NOTE:** Tournament history doesn't have a simple REST button. The scheduler runs it automatically every 2 hours. For manual trigger, use Python:

**Step 4a: Manually trigger via Python (if needed)**

```bash
cd /home/ansible/rankings-bot/Rankings-Bot

python3 << 'PYTHON'
import sys
sys.path.insert(0, '.')
from database import engine
from scrapers.tournament_scraper_improved import EnhancedTournamentScraper

print("🔄 Starting Tournament History Scrape...")

try:
    scraper = EnhancedTournamentScraper(engine=engine, rate_limit_delay=2.0)
    result = scraper.scrape_tournaments(
        wpba=True,
        wpa=True,
        include_future=True,
        attach_fargo=False,
        force_rescrape=False,
        limit=None
    )
    
    print(f"✅ Tournament scrape completed")
    print(f"   Events discovered: {result.get('events_discovered', 0)}")
    print(f"   Events processed: {result.get('events_processed', 0)}")
    print(f"   Results loaded: {result.get('results_loaded', 0)}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
PYTHON
```

**Expected Output:**
```
🔄 Starting Tournament History Scrape...
✅ Tournament scrape completed
   Events discovered: 145
   Events processed: 89
   Results loaded: 847
```

**Step 4b: Verify tournament results increased**

```bash
psql -U rankings -h localhost rankings << 'SQL'
SELECT 'Before Refresh' as phase, COUNT(*) as count FROM tournament_results
UNION ALL
SELECT 'Status: RUNNING', 0
UNION ALL
SELECT 'After Refresh (Re-run in 10 min)', COUNT(*) FROM tournament_results;
SQL
```

**Expected:**
- Before: ~5 results
- After: 800+ results (10-100x improvement)

✅ **Phase 4 Complete when:** tournament_results table has >100 entries

---

## PHASE 5: FINAL VALIDATION

**Run complete data check to compare before/after:**

```bash
psql -U rankings -h localhost rankings << 'SQL'
\echo '=== FINAL VALIDATION ==='
\echo ''
\echo 'Final Fargo Coverage:'
SELECT ranking_system,
  COUNT(*) as total,
  COUNT(CASE WHEN fargo_rating IS NOT NULL THEN 1 END) as with_fargo,
  ROUND(100.0 * COUNT(CASE WHEN fargo_rating IS NOT NULL THEN 1 END) / COUNT(*), 1) as pct
FROM rankings  
GROUP BY ranking_system
ORDER BY pct DESC;

\echo ''
\echo 'Tournament Data:'
SELECT 'Tournaments' as metric, COUNT(*) as value FROM tournament_history
UNION ALL
SELECT 'Tournament Results', COUNT(*) FROM tournament_results
UNION ALL  
SELECT 'Coverage %', ROUND(100.0 * COUNT(*)::numeric / (SELECT COUNT(*) FROM tournament_history), 1)::bigint FROM tournament_results;

\echo ''
\echo 'Final timestamp:'
SELECT NOW();
SQL
```

**Success Criteria:**
- [ ] Fargo coverage improved by 10-30% (depending on system)
- [ ] Tournament results: >100 entries (from 5)
- [ ] No SQL errors
- [ ] Logs show clean completion

---

## TROUBLESHOOTING

### Fargo Sync Returns 0 Updated
**Symptom:** Response shows `"updated": 0`  
**Cause:** All players already have ratings (expected after first run)  
**Fix:** Normal. Run again only for new rankings.

### Rankings Refresh Hangs (>10 min)
**Symptom:** Process doesn't complete after 10 minutes  
**Cause:** Network issue or scraper blocked  
**Fix:**
```bash
# Kill hanging process
pkill -f "python.*rankings.*refresh"

# Check logs
tail -50 /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log | tail -20

# Retry with fresh token
```

### Fargo Sync Timeout  
**Symptom:** "Fargo sync timed out after 5 minutes" error  
**Cause:** Either network slow or too many players  
**Fix:** Use parallel mode (10x faster)
```bash
curl -X POST "http://127.0.0.1:8003/api/fargo/sync-parallel?org_code=WPBA" \
  -H "Authorization: Bearer $TOKEN"
```

### Tournament Results Still 5
**Symptom:** Tournament scrape completes but no new results  
**Cause:** 
1. Scraper may not be extracting results
2. Data source (websites) may not have result data
3. Parser may be failing silently

**Fix:**
```bash
# Check detailed scraper logs
grep -i "tournament" /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log | tail -50

# Check database for tournaments
psql -U rankings -h localhost rankings -c "
  SELECT tournament_id, name, date, COUNT(*) as results 
  FROM tournament_history
  LEFT JOIN tournament_results USING (tournament_id)
  GROUP BY tournament_id, name, date
  ORDER BY date DESC
  LIMIT 20;"
```

### "Authorization Bearer $TOKEN" Not Working
**Symptom:** 401 Unauthorized error  
**Cause:** Token expired or invalid  
**Fix:**
```bash
# Get fresh token
curl -s -X POST http://127.0.0.1:8003/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "YOUR_PASSWORD"
  }' | jq -r '.access_token'

# Copy output and use in curl headers
```

---

## SHELL SCRIPT: FULL AUTOMATION

**Save this as `activate_scrapers.sh` and run:**

```bash
#!/bin/bash
set -e

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
API_HOST="http://127.0.0.1:8003"
DB_HOST="localhost"
DB_USER="rankings"
DB_NAME="rankings"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-}"

if [ -z "$ADMIN_PASS" ]; then
  read -sp "Enter admin password: " ADMIN_PASS
  echo
fi

# Helper functions
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Get token
log_info "Getting admin token..."
TOKEN=$(curl -s -X POST $API_HOST/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PASS\"}" \
  | jq -r '.access_token // empty')

if [ -z "$TOKEN" ]; then
  log_error "Could not authenticate. Check password."
  exit 1
fi
log_info "Got token: ${TOKEN:0:20}..."

# Baseline check
log_info "Baseline data check..."
psql -U $DB_USER -h $DB_HOST $DB_NAME << 'SQL' > /tmp/baseline.txt
SELECT 'Baseline Fargo %'::text,
  ROUND(100.0 * COUNT(CASE WHEN fargo_rating IS NOT NULL THEN 1 END) / COUNT(*), 1)::text
FROM rankings;
SQL
cat /tmp/baseline.txt
BASELINE=$(tail -1 /tmp/baseline.txt | awk '{print $NF}')
log_info "Starting Fargo coverage: ${BASELINE}%"

# PHASE 1: Rankings Refresh
log_info "PHASE 1: Starting Rankings Refresh..."
curl -s -X POST $API_HOST/api/rankings/refresh \
  -H "Authorization: Bearer $TOKEN" | jq .

log_warn "Waiting 5 minutes for rankings to complete..."
sleep 300

# PHASE 2: Fargo Sync
log_info "PHASE 2: Starting Fargo Sync (Parallel mode)..."
curl -s -X POST "$API_HOST/api/fargo/sync-parallel?org_code=WPBA" \
  -H "Authorization: Bearer $TOKEN" | jq .

log_warn "Waiting 3 minutes for Fargo to complete..."
sleep 180

# Check improvement
log_info "Checking Fargo coverage improvement..."
psql -U $DB_USER -h $DB_HOST $DB_NAME << 'SQL' > /tmp/after.txt
SELECT 'Final Fargo %'::text,
  ROUND(100.0 * COUNT(CASE WHEN fargo_rating IS NOT NULL THEN 1 END) / COUNT(*), 1)::text
FROM rankings;
SQL
cat /tmp/after.txt
AFTER=$(tail -1 /tmp/after.txt | awk '{print $NF}')

# Final report
log_info "========== FINAL REPORT =========="
echo "Baseline Fargo coverage: ${BASELINE}%"
echo "Final Fargo coverage:    ${AFTER}%"
IMPROVEMENT=$(echo "$AFTER - $BASELINE" | bc)
echo "Improvement:             +${IMPROVEMENT}%"
echo "======================================"

if [ "$(echo "$AFTER > $BASELINE" | bc)" -eq 1 ]; then
  log_info "✅ SUCCESS: Fargo coverage improved!"
else
  log_warn "⚠️  No improvement detected. Check logs."
fi
```

**Run it:**
```bash
chmod +x activate_scrapers.sh
./activate_scrapers.sh
```

---

## EXPECTED TIMELINE (Full Run)

```
Time    Component              Duration    Status
────────────────────────────────────────────────────
00:00   START
00:00   Rankings Refresh       5 min       🔄 Running
00:05   [Wait for DB]          2 min       ⏳ Waiting
00:07   Fargo Sync (Parallel)  3 min       🔄 Running
00:10   [Wait for propagation] 3 min       ⏳ Waiting
00:13   Tournament History     15 min      🔄 Running (optional)
00:28   COMPLETE               28 min      ✅ Done
```

**Total Time:** 28 minutes for full refresh
**Recommended:** Run in off-peak hours (2-4 AM UTC)

---

**Last Updated:** 2026-02-18  
**Next Review:** 2026-02-25
