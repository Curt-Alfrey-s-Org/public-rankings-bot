# Fargo Rating Enrichment Guide

## Overview

**Status**: Fargo scraper code exists and is fully functional. Need to install dependencies and run enrichment.

**Current Coverage** (as of Feb 13, 2026):
- **WPA_Men**: 0/279 have Fargo (100% missing)
- **WPA_Women**: 29/155 have Fargo (81% missing) 
- **WPBA_Women**: 37/166 have Fargo (78% missing)
- **TOTAL**: 66/600 have Fargo (**534 missing - 89%**)

---

## ✅ What Already Exists

### 1. FairMatch Scraper ([fairmatch_scraper.py](Rankings-Bot/api/services/fairmatch_scraper.py))
- Uses Selenium/Chrome to automate fairmatch.fargorate.com
- Finds "Search for Players" button
- Enters player name, reads Official Rating
- Tries multiple name formats: "First Last", "Last First", "Last, First"
- **Rate limited**: 1.5 seconds between lookups

### 2. Fargo Client ([fargo_client.py](Rankings-Bot/api/services/fargo_client.py))
- Batch processing: 25 players per batch
- 0.5 second delay between batches
- Up to 10 parallel lookups within a batch
- 24-hour caching (avoids re-scraping same player)
- Updates rankings table with fargo_rating and fargo_last_updated

### 3. API Endpoints ([/api/fargo](Rankings-Bot/api/routes/fargo.py))
- `POST /api/fargo/sync?org_code=WPBA` - Sync all missing Fargo ratings (background)
- `GET /api/fargo/lookup?name={name}` - Single player lookup
- `POST /api/fargo/import` - Manual CSV import (if you have bulk data)

### 4. Enrichment Script ([enrich_all_fargo.py](enrich_all_fargo.py))
- **NEW**: Complete enrichment tool with proper rate limiting
- Respects 3-runs-per-day limit (won't blow up the server!)
- Shows dry-run preview before actually scraping
- Detailed progress logging
- Can target specific systems (WPBA or WPA)

---

## 🚀 Setup Instructions

### Step 1: Install Dependencies

```bash
cd /home/ansible/rankings-bot/Rankings-Bot

# Install Selenium
pip3 install selenium

# Install Chrome/Chromium (if not already installed)
sudo apt update
sudo apt install -y chromium-browser chromium-chromedriver

# OR if using Chrome:
# sudo apt install -y google-chrome-stable
```

### Step 2: Verify Installation

```bash
cd /home/ansible/rankings-bot
python3 -c "
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
options = Options()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
driver = webdriver.Chrome(options=options)
print('✓ Selenium + Chrome working!')
driver.quit()
"
```

### Step 3: Test with One Player (Dry Run)

```bash
cd /home/ansible/rankings-bot
python3 enrich_all_fargo.py
```

**Expected Output:**
```
🎱 Fargo Rating Enrichment Tool
============================================================
  Mode:   DRY RUN
  System: ALL
============================================================

🔍 Finding players missing Fargo ratings (system=ALL)...

📊 Players Missing Fargo Ratings:
============================================================
  WPA_Men         : 279 players
  WPA_Women       : 126 players
  WPBA_Women      : 129 players
============================================================
  TOTAL           : 534 players

🔸 DRY RUN MODE - No actual scraping
   Run with --execute to actually scrape

📝 Would scrape 534 players:
   - Lookup delay: 1.5s between players
   - Batch delay: 5.0s every 25 players
   - Estimated time: 16.5 minutes
```

---

## 📋 Execution Options

### Option 1: Enrichment Script (Recommended)

**Dry run (see what would be scraped):**
```bash
cd /home/ansible/rankings-bot
python3 enrich_all_fargo.py
```

**Actually scrape ALL systems:**
```bash
python3 enrich_all_fargo.py --execute
```

**Only scrape WPBA Women:**
```bash
python3 enrich_all_fargo.py --execute --system WPBA
```

**Only scrape WPA (Women + Men):**
```bash
python3 enrich_all_fargo.py --execute --system WPA
```

### Option 2: API Endpoint (Background Processing)

Start the Rankings Bot API, then:

```bash
# Sync WPBA Women
curl -X POST "http://localhost:8003/api/fargo/sync?org_code=WPBA" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"

# Sync WPA Women
curl -X POST "http://localhost:8003/api/fargo/sync?org_code=WPA" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```

**Note**: This runs in background and doesn't block the API. Watch logs for progress:
```bash
docker logs -f rankings-api
```

### Option 3: Manual Script (Top 100 Only)

For players in Top 100 lists (fastest, no scraping individual pages):

```bash
cd /home/ansible/rankings-bot/Rankings-Bot/scripts
python3 manual_fargo_scrape.py --apply
```

---

## ⚠️ Rate Limiting (IMPORTANT!)

### Automatic Protection

**3 Runs Per Day Maximum** - The script tracks executions in `.fargo_scrape_log`:
```
2026-02-13 07:30:00 searched=534 found=521 failed=13
2026-02-13 14:15:00 searched=13 found=12 failed=1
2026-02-13 19:00:00 searched=1 found=1 failed=0
```

If you try to run a 4th time:
```
❌ Rate limit exceeded: 3 runs already today (max 3)
   Last runs: ['2026-02-13 07:30:00', '2026-02-13 14:15:00', '2026-02-13 19:00:00']
```

### Polite Scraping

- **1.5 seconds** between individual player lookups
- **5 seconds** between 25-player batches
- **15 second timeout** per lookup (prevents hanging)
- Headless Chrome (no GUI overhead)

**Estimated times:**
- **534 players (all)**: ~16 minutes
- **129 players (WPBA)**: ~4 minutes  
- **126 players (WPA Women)**: ~4 minutes
- **279 players (WPA Men)**: ~8 minutes

---

## 📊 Monitoring Progress

### Live Progress Logging

```
[07:30:15] INFO - [1/534] WPA_Men         | Shane Van Boening
[07:30:15] INFO -           ✓ Found: 850 (updated 1 records)
[07:30:17] INFO - [2/534] WPA_Men         | Joshua Filler
[07:30:17] INFO -           ✓ Found: 842 (updated 1 records)
...
[07:30:55] INFO - ⏸  Batch complete (25/534), waiting 5.0s...
[07:31:00] INFO - [26/534] WPA_Men        | Carlo Biado
```

### Final Summary

```
============================================================
✅ Fargo Enrichment Complete
============================================================
  Searched:  534
  Found:     521 (97.6%)
  Failed:     13 (2.4%)
  Updated:   521 database records
  Time:      16.2 minutes
============================================================
```

### Check Results

```bash
sudo docker exec rankings-bot-postgres psql -U rankings -d rankings -c "
SELECT 
    ranking_system,
    COUNT(*) as total,
    COUNT(fargo_rating) as has_fargo,
    COUNT(*) - COUNT(fargo_rating) as missing
FROM rankings
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM rankings)
GROUP BY ranking_system
ORDER BY ranking_system;
"
```

**Expected after enrichment:**
```
 ranking_system | total | has_fargo | missing 
----------------+-------+-----------+---------
 WPA_Men        |   279 |       270 |       9
 WPA_Women      |   155 |       149 |       6
 WPBA_Women     |   166 |       159 |       7
```

---

## 🔧 Troubleshooting

### "Selenium not installed"

```bash
pip3 install selenium
```

### "Chrome/Chromium not available"

```bash
# Try Chromium first (lighter weight)
sudo apt install -y chromium-browser chromium-chromedriver

# OR Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb
```

### "Rating not found for this player"

Some players may not be in FairMatch system yet. This is expected. The script logs these and continues.

### "Rate limit exceeded"

Wait until tomorrow (resets at midnight). The limit protects the Fargo server from overload.

### "Timeout" or "Page took too long"

Increase timeout in [fairmatch_scraper.py](Rankings-Bot/api/services/fairmatch_scraper.py):
```python
DEFAULT_TIMEOUT = 30  # Increase from 15 to 30 seconds
```

---

## 🔄 Recommended Schedule

**Run 3 times per day:**
1. **Morning** (8 AM): Enrich all new players from overnight
2. **Afternoon** (2 PM): Retry failed lookups
3. **Evening** (8 PM): Final cleanup

**Cron schedule:**
```cron
0 8 * * * cd /home/ansible/rankings-bot && python3 enrich_all_fargo.py --execute >> /var/log/fargo-enrich.log 2>&1
0 14 * * * cd /home/ansible/rankings-bot && python3 enrich_all_fargo.py --execute >> /var/log/fargo-enrich.log 2>&1
0 20 * * * cd /home/ansible/rankings-bot && python3 enrich_all_fargo.py --execute >> /var/log/fargo-enrich.log 2>&1
```

---

## 📝 Next Steps

1. **Install Selenium + Chrome** (see Step 1 above)
2. **Run dry-run** to verify everything works
3. **Execute first enrichment** for all 534 players (~16 minutes)
4. **Verify results** with database query
5. **Set up cron** for automatic daily enrichment

**Ready to start?**
```bash
cd /home/ansible/rankings-bot
python3 enrich_all_fargo.py  # Dry run first!
```

When you're confident:
```bash
python3 enrich_all_fargo.py --execute  # Actually scrape!
```
