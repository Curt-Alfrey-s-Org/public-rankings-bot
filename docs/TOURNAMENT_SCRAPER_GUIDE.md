# Tournament Scraper - Monitoring and Operations Guide

## Overview

The enhanced tournament scraper automatically discovers and scrapes tournament data from WPBA and WPA websites every hour with the following features:

- **Rate Limiting**: 2-second delay between requests to avoid overwhelming sources
- **Incremental Scraping**: Only processes new or updated tournaments (past tournaments re-scraped every 7 days)
- **Future Tournaments**: Tracks upcoming tournaments and updates them on every run
- **Robust Error Handling**: Automatic retries with exponential backoff
- **Health Monitoring**: Detailed metrics and logging for each run
- **Fargo Integration**: Automatically attaches current Fargo ratings to player results

## Files

### Core Components

- `scrapers/tournament_scraper_improved.py` - Enhanced scraper with all improvements
- `scripts/run_tournament_scraper_hourly.py` - Scheduler wrapper for hourly execution
- `scripts/setup_tournament_scraper_cron.sh` - Cron job installation script

### Logs and Monitoring

- `logs/tournament_scraper.log` - Main scraper log (rotated automatically)
- `logs/tournament_scraper_last_run.json` - Last run summary (for monitoring)
- `logs/tournament_scraper_cron.log` - Cron execution log

## Installation

### 1. Install Cron Job (Hourly Execution)

```bash
cd /home/ansible/rankings-bot/Rankings-Bot
chmod +x scripts/setup_tournament_scraper_cron.sh
./scripts/setup_tournament_scraper_cron.sh
```

This will install a cron job that runs every hour at minute 0.

### 2. Verify Cron Installation

```bash
crontab -l | grep tournament_scraper
```

You should see:
```
0 * * * * cd /home/ansible/rankings-bot/Rankings-Bot && python3 scripts/run_tournament_scraper_hourly.py >> logs/tournament_scraper_cron.log 2>&1
```

## Manual Execution

### Run Full Scrape

```bash
cd /home/ansible/rankings-bot/Rankings-Bot
python3 scrapers/tournament_scraper_improved.py
```

### Run with Options

```bash
# WPBA only
python3 scrapers/tournament_scraper_improved.py --wpba-only

# WPA only
python3 scrapers/tournament_scraper_improved.py --wpa-only

# Skip future tournaments
python3 scrapers/tournament_scraper_improved.py --no-future

# Force re-scrape all tournaments (ignores last scrape time)
python3 scrapers/tournament_scraper_improved.py --force

# Test with limited number of tournaments
python3 scrapers/tournament_scraper_improved.py --limit 5

# Adjust rate limiting (default 2.0 seconds)
python3 scrapers/tournament_scraper_improved.py --rate-limit 3.0
```

## Monitoring

### View Recent Logs

```bash
# Last 50 lines
tail -n 50 logs/tournament_scraper.log

# Follow live
tail -f logs/tournament_scraper.log

# Search for errors
grep -i error logs/tournament_scraper.log

# Last run summary
cat logs/tournament_scraper_last_run.json | python3 -m json.tool
```

### Check Last Run Status

```bash
python3 << 'EOF'
import json
from pathlib import Path

summary_file = Path("logs/tournament_scraper_last_run.json")
if summary_file.exists():
    with open(summary_file) as f:
        data = json.load(f)
    print(f"Last Run: {data.get('start_time', 'N/A')}")
    print(f"Duration: {data.get('duration_seconds', 0):.2f}s")
    print(f"Discovered: {data.get('events_discovered', 0)}")
    print(f"Processed: {data.get('events_processed', 0)}")
    print(f"New: {data.get('events_new', 0)}")
    print(f"Updated: {data.get('events_updated', 0)}")
    print(f"Errors: {data.get('error_count', 0)}")
else:
    print("No run data available")
EOF
```

### Database Monitoring Queries

```sql
-- View scraper run history
SELECT 
    run_timestamp,
    duration_seconds,
    events_discovered,
    events_processed,
    events_new,
    events_updated,
    error_count
FROM tournament_scraper_runs
ORDER BY run_timestamp DESC
LIMIT 10;

-- View tournament scrape metadata
SELECT 
    tournament_id,
    last_scraped_at,
    scrape_count,
    last_scrape_status,
    last_error
FROM tournament_scraper_metadata
ORDER BY last_scraped_at DESC
LIMIT 20;

-- Find tournaments with errors
SELECT 
    tournament_id,
    last_scraped_at,
    last_error
FROM tournament_scraper_metadata
WHERE last_scrape_status = 'error'
ORDER BY last_scraped_at DESC;

-- View recent tournaments
SELECT 
    tournament_id,
    name,
    date,
    status,
    champion,
    updated_at
FROM tournament_history
ORDER BY updated_at DESC
LIMIT 10;

-- View future tournaments
SELECT 
    tournament_id,
    name,
    date,
    location,
    association
FROM tournament_history
WHERE status = 'upcoming'
ORDER BY date ASC;
```

## Troubleshooting

### Scraper Not Running

1. **Check cron is active:**
   ```bash
   systemctl status cron
   # or
   service cron status
   ```

2. **Check crontab entry:**
   ```bash
   crontab -l
   ```

3. **Check cron log:**
   ```bash
   tail -n 50 logs/tournament_scraper_cron.log
   ```

### High Error Rate

1. **Check network connectivity:**
   ```bash
   ping -c 3 wpba.com
   ping -c 3 wpapool.com
   ```

2. **Check source website status:**
   ```bash
   curl -I https://wpba.com/events-official
   curl -I https://wpapool.com/calendar-2/
   ```

3. **Increase rate limit if being blocked:**
   ```bash
   # Edit cron job or manual run
   python3 scrapers/tournament_scraper_improved.py --rate-limit 5.0
   ```

### Database Issues

1. **Check database connection:**
   ```bash
   cd /home/ansible/rankings-bot/Rankings-Bot
   python3 -c "from database import engine; print('DB OK' if engine else 'DB FAIL')"
   ```

2. **Verify tables exist:**
   ```bash
   python3 << 'EOF'
   from database import engine
   from sqlalchemy import text
   with engine.connect() as conn:
       result = conn.execute(text("""
           SELECT table_name FROM information_schema.tables 
           WHERE table_name LIKE 'tournament%'
       """))
       for row in result:
           print(row[0])
EOF
   ```

### Reset Scraper Metadata

If you want to force a complete re-scrape:

```bash
cd /home/ansible/rankings-bot/Rankings-Bot
python3 << 'EOF'
from database import engine
from sqlalchemy import text
with engine.connect() as conn:
    conn.execute(text("DELETE FROM tournament_scraper_metadata"))
    conn.commit()
    print("✅ Metadata cleared - next run will re-scrape all tournaments")
EOF
```

## Maintenance

### Disable Cron Job Temporarily

```bash
# Comment out the line
crontab -e
# Add # at the beginning of the tournament_scraper line
```

### Remove Cron Job

```bash
crontab -e
# Delete the line containing 'run_tournament_scraper_hourly.py'
```

### Log Rotation

Logs are automatically managed by Python's logging system. For manual log rotation:

```bash
# Archive old logs
cd /home/ansible/rankings-bot/Rankings-Bot/logs
tar -czf tournament_scraper_logs_$(date +%Y%m%d).tar.gz tournament_scraper.log
> tournament_scraper.log  # Truncate
```

## Performance Metrics

Expected performance for a typical hourly run:

- **Duration**: 30-120 seconds (depending on events discovered)
- **Discovery**: 50-200 events total
- **Processing**: 0-20 events (incremental)
- **Rate Limit**: ~2s per request = ~30 requests/minute
- **Memory**: < 200MB
- **Storage**: ~1MB per 100 tournaments

## API Endpoints

The scraped data is available through the Rankings Bot API:

- `GET /api/tournament-history` - List all tournaments
- `GET /api/tournament-history?year=2025` - Filter by year
- `GET /api/tournament-history?association=WPBA` - Filter by association
- `GET /api/tournament-history/{tournament_id}` - Get specific tournament
- `GET /api/tournament-history/{tournament_id}/results` - Get tournament results with player placements

## Notes

- **Incremental Scraping**: Past tournaments are only re-scraped every 7 days to reduce load
- **Future Tournaments**: Scraped on every run to capture updates
- **Rate Limiting**: 2-second delay between requests (adjustable)
- **Fargo Ratings**: Attached to player results when available (current rating at scrape time)
- **Error Handling**: 3 retry attempts with 5-second delays
- **Monitoring**: All runs tracked in `tournament_scraper_runs` table

## Support

For issues or questions:
1. Check logs in `logs/tournament_scraper.log`
2. Review database monitoring queries above
3. Check source websites are accessible
4. Verify database connectivity
