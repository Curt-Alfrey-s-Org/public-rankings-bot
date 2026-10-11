# Fargo Scraper Quick Reference

## Run Scrapers via Admin Panel
1. Log in as admin
2. Go to Settings → Run Scrapers
3. Click "Run Fargo Scraper" button
4. Expected: "X updated / Y processed" where **X > 0** ✅

## Run Scrapers via API (CLI)

### Full Refresh (All Players)
```bash
# WPBA Women
curl -X POST "http://127.0.0.1:8003/api/fargo/sync?org=WPBA&wait=true&full_refresh=true"

# WPA Men
curl -X POST "http://127.0.0.1:8003/api/fargo/sync?org=WPA_Men&wait=true&full_refresh=true"

# WPA Women
curl -X POST "http://127.0.0.1:8003/api/fargo/sync?org=WPA_Women&wait=true&full_refresh=true"
```

### Quick Update (Missing Only)
```bash
curl -X POST "http://127.0.0.1:8003/api/fargo/sync?org=WPA_Men&wait=true&full_refresh=false"
```

## Check Accuracy Metrics

```bash
PGPASSWORD=rankings psql -U rankings -d rankings -h localhost << 'EOSQL'
SELECT 
  COUNT(*) FILTER (WHERE fargo_rating IS NOT NULL) as total_with_fargo,
  COUNT(*) FILTER (WHERE fargo_rating IS NOT NULL AND fargo_source_name IS NOT NULL) as tracked,
  ROUND(100.0 * COUNT(*) FILTER (WHERE fargo_rating IS NOT NULL AND fargo_source_name IS NOT NULL) / 
        NULLIF(COUNT(*) FILTER (WHERE fargo_rating IS NOT NULL), 0), 1) as percent_tracked
FROM rankings;
EOSQL
```

Expected output:
```
 total_with_fargo | tracked | percent_tracked 
------------------+---------+----------------
              768 |     613 |           79.8
```

## Check Recent Updates

```bash
PGPASSWORD=rankings psql -U rankings -d rankings -h localhost << 'EOSQL'
SELECT player_name, fargo_rating, fargo_source_name, fargo_last_updated
FROM rankings
WHERE fargo_last_updated > NOW() - INTERVAL '1 hour'
ORDER BY fargo_last_updated DESC
LIMIT 20;
EOSQL
```

## View Tier Breakdown in Logs

```bash
# Check application logs for tier execution
tail -100 /home/ansible/rankings-bot/Rankings-Bot/logs/app.log | grep -E "\[TIER[123]\]"
```

Expected output:
```
[TIER1] Fetched 291 unique players from Top-pool_opt_in lists
[TIER1] Updated 158/291 TIER1 players in database
[TIER2] Fuzzy match complete: 291 newly matched from TIER1
[TIER2] Updated 167/291 TIER2-fuzzy-matched players in database
[TIER3] Starting per-player lookups for 1 players using FairMatch
[TIER3] Complete: 0 successful, 1 failed
```

## Check Failed Players (Admin Messages)

```bash
PGPASSWORD=rankings psql -U rankings -d rankings -h localhost << 'EOSQL'
SELECT message_type, created_at, LEFT(message_text, 80) as message_preview
FROM admin_messages
WHERE message_type LIKE '%fargo%'
ORDER BY created_at DESC
LIMIT 10;
EOSQL
```

## Verify Alexander Kazakis Rating

```bash
PGPASSWORD=rankings psql -U rankings -d rankings -h localhost << 'EOSQL'
SELECT player_name, fargo_rating, fargo_source_name, fargo_last_updated
FROM rankings
WHERE player_name ILIKE '%kazaki%'
ORDER BY fargo_last_updated DESC;
EOSQL
```

Expected: `fargo_rating = 824` (not 860) ✅

## Run Integration Test

```bash
cd /home/ansible/rankings-bot/Rankings-Bot
python3 test_fargo_refactor.py
```

Expected output:
```
✅ All tests passed!
✓ TIER1 fetched 291 players
✓ Database connection successful
✓ TIER2 fuzzy-matched 291 players
✓ Sync complete!
  Updated: 325
```

## Restart API (After Changes)

```bash
sudo systemctl restart rankings-bot-api
sleep 5
sudo systemctl status rankings-bot-api --no-pager | head -20
```

## Check API Health

```bash
curl http://127.0.0.1:8003/api/system/health
```

Expected: `{"status":"ok",...}`

## Rollback (If Needed)

```bash
cd /home/ansible/rankings-bot/Rankings-Bot
mv api/services/fargo_client.py api/services/fargo_client_refactored.py
mv api/services/fargo_client_old.py api/services/fargo_client.py
sudo systemctl restart rankings-bot-api
```

## Environment Variables (Optional Tuning)

Add to `/etc/systemd/system/rankings-bot-api.service`:

```ini
# Batch processing
Environment="FARGO_BATCH_SIZE=25"
Environment="FARGO_BATCH_DELAY_SECONDS=0.5"
Environment="FARGO_MAX_CONCURRENT_LOOKUPS=10"

# Retry logic
Environment="FARGO_LOOKUP_RETRIES=2"
Environment="FARGO_LOOKUP_RETRY_DELAY=2.0"

# FairMatch toggle
Environment="USE_FAIRMATCH_SCRAPE=true"
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl restart rankings-bot-api
```

## Troubleshooting

### Problem: "0 updated" still appearing
**Check:**
1. API logs: `journalctl -u rankings-bot-api -n 100 | grep -i tier`
2. Database columns: `\d rankings` — should show `fargo_source_name`
3. Test script: `python3 test_fargo_refactor.py`

### Problem: "Internal Server Error"
**Check:**
1. Import errors: `python3 -c "from api.services.fargo_client import sync_fargo_ratings_rate_limited"`
2. Recent errors: `journalctl -u rankings-bot-api -n 50 | grep -A5 Traceback`
3. Database connection: `PGPASSWORD=rankings psql -U rankings -h localhost rankings -c "SELECT 1"`

### Problem: TIER3 failing with "Chrome not available"
**Solution:**
```bash
# Install Chromium
sudo apt-get update
sudo apt-get install chromium-browser chromium-chromedriver

# Or disable FairMatch and use manual CSV import
export USE_FAIRMATCH_SCRAPE=false
```

### Problem: Too many TIER3 lookups
**Solution:** Expand NICKNAME_MAP in `api/services/fargo_client.py`:
```python
NICKNAME_MAP = {
    "alex": ["alexander", "alexandra", "alexis"],
    "rob": ["robert"],
    "bill": ["william"],
    # Add more nicknames as needed
}
```

## Performance Tuning

### Increase Parallelism (Faster but more load)
```bash
export FARGO_MAX_CONCURRENT_LOOKUPS=20
export FARGO_BATCH_SIZE=50
```

### Decrease Rate (Slower but safer)
```bash
export FARGO_BATCH_DELAY_SECONDS=1.0
export FARGO_MAX_CONCURRENT_LOOKUPS=5
```

## Success Indicators

✅ **Sync output shows**: "Updated: X" where X > 0  
✅ **Logs show**: `[TIER1]`, `[TIER2]`, `[TIER3]` prefixes  
✅ **Database query**: `percent_tracked` increasing toward 90%+  
✅ **Admin panel**: "X updated / Y processed" where X > 0  
✅ **Test script**: "✅ All tests passed!"  

## Key Files

- **Main code**: `api/services/fargo_client.py`
- **Tests**: `test_fargo_refactor.py`, `tests/test_fargo_client_refactored.py`
- **Documentation**: `FARGO_SCRAPER_REFACTOR_SUMMARY.md`, `FARGO_ARCHITECTURE_DIAGRAM.md`
- **Backup**: `api/services/fargo_client_old.py`
- **Logs**: `/home/ansible/rankings-bot/Rankings-Bot/logs/app.log`
