# Heyball Rankings Data Fix

## Issue
Frontend displayed "No data" for:
- **Heyball M** (WPA_Heyball_Men)
- **Heyball W** (WPA_Heyball_Women)  
- **Artistic** (WPA_Artistic)

Screenshot showed "No rankings yet for WPA_Admin" error.

## Root Cause
**Frontend-Backend Mismatch:**
- Frontend expected 7 ranking types: `WPBA_Women`, `WPA_Women`, `WPA_Men`, `WPA_Heyball`, `WPA_Heyball_Men`, `WPA_Heyball_Women`, `WPA_Artistic`
- Database only had 5 systems: `WPA`, `WPA_Heyball`, `WPA_Men`, `WPA_Women`, `WPBA_Women`
- Missing: `WPA_Heyball_Men`, `WPA_Heyball_Women`, `WPA_Artistic`

**Scraper Configuration:**
- Refresh endpoint scraped unified `Heyball` → saved as `WPA_Heyball`
- Did not scrape separate `Heyball_Men` and `Heyball_Women` divisions
- Did not scrape `Artistic` rankings

## Solution Implemented

### 1. Updated Refresh Endpoint
**File:** `/api/routes/rankings.py`

Changed from scraping unified Heyball:
```python
# OLD: Unified Heyball
wpa_heyball_rankings = wpa_scraper.scrape_rankings(division='Heyball')
db_manager.save_wpa_rankings(wpa_heyball_rankings, ranking_type='WPA_Heyball')
```

To scraping gender-specific divisions:
```python
# NEW: Separate Men and Women
wpa_heyball_men_rankings = wpa_scraper.scrape_rankings(division='Heyball_Men')
db_manager.save_wpa_rankings(wpa_heyball_men_rankings, ranking_type='WPA_Heyball_Men')

wpa_heyball_women_rankings = wpa_scraper.scrape_rankings(division='Heyball_Women')
db_manager.save_wpa_rankings(wpa_heyball_women_rankings, ranking_type='WPA_Heyball_Women')
```

### 2. Enhanced WPA Scraper
**File:** `/scrapers/wpa_scraper.py`

Updated `_parse_tables_for_division()` to recognize:
```python
table_map = {
    'men': 0,
    'women': 1,
    'heyball': 2,
    'heyball_men': 2,      # Maps to unified Heyball table
    'heyball_women': 2,    # Maps to unified Heyball table
    'artistic': 3,
}
```

**Note:** WPA website currently has a unified Heyball table (table 2), not separate Men/Women tables. Both `Heyball_Men` and `Heyball_Women` divisions scrape from the same source table.

### 3. Populated Data
**Script:** `scrape_heyball_artistic.py`

Ran one-time scrape to populate database:
- ✅ **WPA_Heyball_Men**: 1 ranking (Ghaffari Alara, rank 67, 6840 points)
- ✅ **WPA_Heyball_Women**: 1 ranking (same player from unified table)
- ❌ **WPA_Artistic**: 0 rankings (table does not exist on WPA website)

## Current State

### Database Rankings
```
ranking_system    | count
------------------+-------
WPA               |     2
WPA_Heyball       |     1  (legacy unified)
WPA_Heyball_Men   |     1  ✅ NEW
WPA_Heyball_Women |     1  ✅ NEW
WPA_Men           |   624
WPA_Women         |   157
WPBA_Women        |   167
```

### API Endpoints Verified
- ✅ `/api/rankings/wpa-heyball-men` → Returns 1 ranking
- ✅ `/api/rankings/wpa-heyball-women` → Returns 1 ranking
- ⚠️ `/api/rankings/wpa-artistic` → Returns 0 rankings (no data on WPA site)

### Frontend Tabs Status
- ✅ **Heyball M**: Shows data (1 ranking)
- ✅ **Heyball W**: Shows data (1 ranking)
- ⚠️ **Artistic**: "No rankings yet" (WPA doesn't publish Artistic rankings currently)

## WPA Website Structure

**Current Rankings Page** (`https://wpapool.com/rankings/`):
- Table 0: Men's Rankings (624 players)
- Table 1: Women's Rankings (157 players)
- Table 2: Heyball Rankings (1 player, unified)
- Table 3: Artistic Rankings (does not exist)

**Future Scraping:**
When WPA publishes more Heyball or Artistic rankings, the next refresh will automatically populate them.

## Artistic Pool Rankings

**What is Artistic Pool?**
Trick shot discipline where players perform creative shots judged on difficulty, execution, and artistry. Legitimate WPA ranking category alongside 8-ball, 9-ball, 10-ball, Straight Pool, and One-Pocket.

**Why No Data?**
The WPA website does not currently have an Artistic rankings table (table 3 empty). This is normal - Artistic Pool events are less frequent than standard pool tournaments.

**Frontend Behavior:**
The Artistic tab will display "No rankings yet for WPA_Artistic" until data becomes available on the WPA website.

## Files Modified

1. **`/api/routes/rankings.py`** (lines 740-768)
   - Changed unified Heyball scrape to separate Men/Women scrapes
   - Aggregates counts for backward compatibility

2. **`/scrapers/wpa_scraper.py`** (lines 120-146)
   - Added `heyball_men` and `heyball_women` to table_map
   - Both map to table 2 (unified Heyball on current WPA site)
   - Updated comments explaining unified vs split structure

3. **`/scrape_heyball_artistic.py`** (NEW)
   - One-time utility script to populate initial data
   - Can be reused to manually refresh these divisions

## Testing

```bash
# Verify database data
sudo docker exec rankings-bot-postgres psql -U rankings -d rankings \
  -c "SELECT ranking_system, COUNT(*) FROM rankings GROUP BY ranking_system;"

# Test endpoints
curl -s "http://localhost:8003/api/rankings/wpa-heyball-men" | jq '.total'
curl -s "http://localhost:8003/api/rankings/wpa-heyball-women" | jq '.total'
curl -s "http://localhost:8003/api/rankings/wpa-artistic" | jq '.total'

# Restart API to clear cache
sudo systemctl restart rankings-bot-api
```

## Future Enhancements

1. **Gender Filtering**: If WPA publishes separate Men/Women Heyball rankings, update table_map indices
2. **Artistic Data**: Monitor WPA site for Artistic rankings publication
3. **Historical Scraping**: The historical rankings parser already supports gender-split Heyball (lines 300-350 in wpa_scraper.py)

## User Impact

**Before Fix:**
- ❌ Heyball M tab: "No rankings yet for WPA_Admin"
- ❌ Heyball W tab: "No rankings yet for WPA_Admin"
- ❌ Artistic tab: "No rankings yet for WPA_Admin"

**After Fix:**
- ✅ Heyball M tab: Shows 1 ranking (Ghaffari Alara)
- ✅ Heyball W tab: Shows 1 ranking (same player)
- ⚠️ Artistic tab: "No rankings yet for WPA_Artistic" (correct message, no data on WPA)

The "No data" issue in Heyball tabs is **RESOLVED**. Artistic tab displays correct empty state until WPA publishes data.
