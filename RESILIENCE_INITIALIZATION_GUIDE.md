# Rankings Bot Resilience - Initialization & Deployment Guide

**Date:** February 13, 2026  
**Component:** Rankings-Bot Data Persistence & Resilience  
**Status:** ✅ Ready for Deployment

---

## 📋 Overview

This guide documents the initialization and deployment steps for the Rankings Bot resilience features (Priority 1-4 from SCRAPER_PERSISTENCE_ANALYSIS.md). All components are implemented and integrated.

---

## ✅ Pre-Deployment Checklist

### 1. Database Schema Migration

The rankings-bot PostgreSQL database already includes all necessary tables. **No migrations required** if upgrading from recent versions.

**Verify tables exist:**

```bash
cd /home/ansible/rankings-bot/Rankings-Bot

python3 << 'EOF'
from database import get_database_manager
db = get_database_manager()

# Check tables exist
conn = db.get_connection()
cursor = conn.cursor()

required_tables = ['rankings', 'ranking_changes', 'rankings_archive']
for table in required_tables:
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_name = %s AND table_schema = 'public'
    """, (table,))
    exists = cursor.fetchone()[0] > 0
    status = "✓" if exists else "⚠"
    print(f"{status} Table '{table}': {'EXISTS' if exists else 'MISSING'}")

conn.close()
EOF
```

**If table is missing, run schema creation:**

```bash
cd /home/ansible/rankings-bot/Rankings-Bot
psql -U rankings -d rankings -h localhost < database/schema_postgres.sql
```

### 2. Environment Configuration

**File:** `Rankings-Bot/.env`

All resilience configuration variables have been added with sensible defaults:

- `SCRAPER_MAX_RETRIES=3` — Max retry attempts for scrapers
- `SCRAPER_RETRY_BACKOFF_SECONDS=2` — Initial backoff delay (exponential)
- `DATA_STALENESS_WARNING_DAYS=2` — Warning threshold for old data
- `DATA_STALENESS_CRITICAL_DAYS=7` — Critical threshold for old data
- `DATA_STALENESS_AUTO_REFRESH_HOURS=24` — Auto-refresh if data age > 24h
- `ENABLE_AUTO_REFRESH_ON_STARTUP=true` — Trigger refresh on API start
- `ENABLE_DATA_ARCHIVAL=true` — Archive old data before updates
- `ARCHIVE_RETENTION_DAYS=730` — Keep archives for 2 years
- `DB_CONNECTION_RETRY_MAX=3` — DB connection retry attempts
- `DB_CONNECTION_RETRY_DELAY=1` — Initial DB retry delay (seconds)
- `REFRESH_INTERVAL_HOURS=6` — Scheduled refresh interval

**Verify .env is loaded:**

```bash
cd /home/ansible/rankings-bot/Rankings-Bot
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('✓ .env loaded successfully')
print(f'  SCRAPER_MAX_RETRIES={os.getenv(\"SCRAPER_MAX_RETRIES\")}')
print(f'  ENABLE_DATA_ARCHIVAL={os.getenv(\"ENABLE_DATA_ARCHIVAL\")}')
"
```

### 3. Python Dependencies

All required packages are in `requirements-api.txt`:

- `requests` — HTTP library (scrapers)
- `beautifulsoup4` — HTML parsing (WPA scraper)
- `pdfplumber` — PDF parsing (WPBA scraper)
- `psycopg2` — PostgreSQL adapter
- `fastapi` — API framework
- `sqlalchemy` — ORM (database management)

**Verify installations:**

```bash
cd /home/ansible/rankings-bot/Rankings-Bot
pip3 check  # Verify no conflicts
```

### 4. Startup Services

**For systemd deployment:**

```ini
[Service]
Type=notify
ExecStart=/home/ansible/rankings-bot/Rankings-Bot/start_api.sh
Environment="ENABLE_AUTO_REFRESH_ON_STARTUP=true"
Environment="DATABASE_URL=postgresql://rankings:change-me@localhost:5432/rankings"
```

The startup process automatically:
1. Creates database tables (if missing)
2. Ensures rankings_archive table exists
3. Checks data freshness
4. Triggers auto-refresh if needed (async in background)

**Optional:** To **skip** startup refresh (for testing):

```bash
export SKIP_STARTUP_REFRESH=1
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8003
```

---

## 🔧 Integrated Components

### Priority 1: Startup Recovery Check ✅

**Files:**
- `api/main.py` — Startup self-tests (linesounds 322–330)
- `database/db_manager.py` — `check_startup_refresh_needed()` method

**How it works:**
1. During startup, the lifespan checks if data is stale (>24 hours old)
2. If stale or missing, triggers async background refresh
3. Logs warning/status before serving requests

**Test startup behavior:**

```bash
cd /home/ansible/rankings-bot/Rankings-Bot
export DEBUG=true
python3 -m uvicorn api.main:app --host 127.0.0.1 --port 8003

# Watch for log: "[STARTUP] Background rankings refresh completed"
```

### Priority 2: Scraper Resilience ✅

**Files:**
- `scrapers/base.py` — `retry_with_backoff()` decorator
- `scrapers/wpa_scraper.py` — WPA scraper with retries
- `scrapers/wpba_scraper.py` — WPBA scraper with retries

**How it works:**
1. Both scrapers wrap `scrape_rankings()` with `@retry_with_backoff` decorator
2. On failure, retries with exponential backoff: 2s → 4s → 8s
3. Logs each retry attempt before raising final exception

**Configuration:**
- `SCRAPER_MAX_RETRIES=3` — Attempts 1, 2, 3 (total 6s + 4s = 10s wait)
- `SCRAPER_TIMEOUT_SECONDS=30` — Per-request timeout
- Retries on: `requests.RequestException`, `ConnectionError`, `TimeoutError`

**Test scraper resilience:**

```bash
cd /home/ansible/rankings-bot/Rankings-Bot
python3 << 'EOF'
from scrapers.wpa_scraper import WPAScraper
scraper = WPAScraper(timeout=30)
try:
    rankings = scraper.scrape_rankings()
    print(f"✓ Scraped {len(rankings)} WPA rankings with retry logic")
except Exception as e:
    print(f"✗ Final failure after retries: {e}")
EOF
```

### Priority 3: Data Archival ✅

**Files:**
- `database/schema_postgres.sql` — `rankings_archive` table (lines 30–46)
- `database/db_manager.py` — `save_rankings()` with archival (lines 367–455)
- `database/db_manager.py` — `_has_ranking_changed()` change detection

**How it works:**
1. Before UPSERT, checks if ranking data changed
2. If changed, archives old row to `rankings_archive` before update
3. Skips save if no changes detected (optimization)
4. Logs summary: "Saved X, skipped Y unchanged, archived Z"

**Archive table structure:**
```
rankings_archive
├── original_id (FK to rankings.id)
├── player_name, ranking_system, rank, points
├── archived_at (TIMESTAMP)
├── archive_reason (update, delete, correction, pre_update)
└── Indexes: player, date, archived_at, original_id
```

**Configuration:**
- `ENABLE_DATA_ARCHIVAL=true` — Enable archival
- `ARCHIVE_RETENTION_DAYS=730` — Keep archives for 2 years

**Test archival:**

```bash
cd /home/ansible/rankings-bot/Rankings-Bot
python3 << 'EOF'
from database import get_database_manager
db = get_database_manager()
archive_ok = db.ensure_archive_table_exists()
print(f"✓ Archive table: {'EXISTS' if archive_ok else 'FAILED'}")
EOF
```

### Priority 4: Connection Resilience ✅

**Files:**
- `database/db_manager.py` — `@with_db_retry()` decorator (lines 31–67)
- `database/db_manager.py` — `save_rankings()` wrapped with retry (line 361)

**How it works:**
1. Decorates database operations with connection retry logic
2. On `psycopg2.OperationalError` or `InterfaceError`, retries with backoff
3. Disposes engine connection pool between retries for fresh connect
4. Logs each retry attempt

**Configuration:**
- `DB_CONNECTION_RETRY_MAX=3` — Max retry attempts
- `DB_CONNECTION_RETRY_DELAY=1` — Initial delay (exponential: 1s → 2s → 4s)

---

## 🧪 Testing & Validation

### Import Verification ✅

```bash
cd /home/ansible/rankings-bot/Rankings-Bot
python3 << 'EOF'
from scrapers.base import retry_with_backoff
from scrapers.wpa_scraper import WPAScraper
from scrapers.wpba_scraper import WPBAScraper
from database import get_database_manager
print("✓ All imports verified")
EOF
```

### Configuration Validation ✅

```bash
cd /home/ansible/rankings-bot/Rankings-Bot
python3 << 'EOF'
import os
from dotenv import load_dotenv

load_dotenv()

# Check all resilience variables
vars_to_check = [
    'SCRAPER_MAX_RETRIES',
    'SCRAPER_RETRY_BACKOFF_SECONDS',
    'DATA_STALENESS_WARNING_DAYS',
    'DATA_STALENESS_CRITICAL_DAYS',
    'DATA_STALENESS_AUTO_REFRESH_HOURS',
    'ENABLE_AUTO_REFRESH_ON_STARTUP',
    'ENABLE_DATA_ARCHIVAL',
    'ARCHIVE_RETENTION_DAYS',
    'DB_CONNECTION_RETRY_MAX',
]

for var in vars_to_check:
    value = os.getenv(var)
    status = "✓" if value is not None else "⚠"
    print(f"{status} {var}={value}")
EOF
```

### Database Schema Validation ✅

```bash
cd /home/ansible/rankings-bot/Rankings-Bot
python3 << 'EOF'
from database import get_database_manager

db = get_database_manager()
conn = db.get_connection()
cursor = conn.cursor()

# Check tables
tables = ['rankings', 'ranking_changes', 'rankings_archive']
for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table} LIMIT 1")
    try:
        count = cursor.fetchone()[0]
        print(f"✓ {table} accessible (rows: {count})")
    except Exception as e:
        print(f"✗ {table} error: {e}")

# Check ranks
cursor.execute("SELECT COUNT(*) FROM rankings_archive")
archive_count = cursor.fetchone()[0]
print(f"✓ Archive has {archive_count} historical records")

conn.close()
EOF
```

### Startup Test ✅

```bash
cd /home/ansible/rankings-bot/Rankings-Bot

# Run with fresh startup (will trigger refresh check)
timeout 30 python3 -m uvicorn api.main:app --host 127.0.0.1 --port 8001 2>&1 | grep -E "\[STARTUP\]|\[SELFTEST\]"

# Expected output:
# [STARTUP] API startup began at ...
# [STARTUP] Running startup self-tests...
# [SELFTEST] ✓ Rankings Freshness - all data fresh
# [STARTUP] Background rankings refresh completed
```

---

## 📊 Monitoring & Verification

### Health Endpoint Usage

Once deployed, check data freshness:

```bash
curl -s http://localhost:8003/api/rankings/health | python3 -m json.tool
```

Expected response:
```json
{
  "status": "healthy",
  "wpba": {
    "last_update": "2026-02-13",
    "age_days": 0,
    "stale": false
  },
  "wpa": {
    "last_update": "2026-02-13",
    "age_days": 0,
    "stale": false
  }
}
```

### Logs Inspection

Check startup behavior:

```bash
tail -100f /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log | grep -E "\[STARTUP\]|\[SELFTEST\]|\[RESILIENCE\]"
```

Check scraper retries:

```bash
grep -i "retry\|backoff" /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log
```

Check archival:

```bash
grep "archived" /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log
```

---

## 🚀 Deployment Steps

### 1. Backup Current Database (Recommended)

```bash
cd /home/ansible/rankings-bot/Rankings-Bot
pg_dump -U rankings -d rankings -h localhost > backups/pre-resilience-backup.sql
```

### 2. Update .env

✅ **Already done** — New variables added with defaults.

Verify in `/home/ansible/rankings-bot/Rankings-Bot/.env`:
```dotenv
SCRAPER_MAX_RETRIES=3
ENABLE_DATA_ARCHIVAL=true
DATA_STALENESS_AUTO_REFRESH_HOURS=24
# ... etc
```

### 3. Ensure Archive Table

```bash
cd /home/ansible/rankings-bot/Rankings-Bot
python3 << 'EOF'
from database import get_database_manager
db = get_database_manager()
result = db.ensure_archive_table_exists()
print(f"✓ Archive table ready: {result}")
EOF
```

### 4. Restart API Service

```bash
# If running as systemd service:
sudo systemctl restart rankings-bot

# Or if running in terminal:
cd /home/ansible/rankings-bot/Rankings-Bot
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8003
```

### 5. Monitor Startup

```bash
# Watch logs for successful startup
tail -f /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log | grep -E "\[STARTUP\]|\[SELFTEST\]"
```

---

## 🔍 Configuration Reference

### Environment Variables Summary

| Variable | Default | Purpose | Tuning |
|----------|---------|---------|--------|
| `SCRAPER_MAX_RETRIES` | 3 | Retry attempts for scrapers | Inc to 5 if unstable network |
| `SCRAPER_RETRY_BACKOFF_SECONDS` | 2.0 | Initial retry delay (sec) | Inc to 3.0 for rate limits |
| `SCRAPER_TIMEOUT_SECONDS` | 30 | Request timeout (sec) | Inc for slow networks |
| `DATA_STALENESS_WARNING_DAYS` | 2 | Warning threshold (days) | Adjust per SLA |
| `DATA_STALENESS_CRITICAL_DAYS` | 7 | Critical threshold (days) | Adjust per SLA |
| `DATA_STALENESS_AUTO_REFRESH_HOURS` | 24 | Auto-refresh if older | Keep < WARNING_DAYS*24 |
| `ENABLE_AUTO_REFRESH_ON_STARTUP` | true | Refresh on API start | Set false to disable |
| `ENABLE_DATA_ARCHIVAL` | true | Archive old data | Set false to disable archival |
| `ARCHIVE_RETENTION_DAYS` | 730 | Keep archives (days) | Adjust per compliance needs |
| `DB_CONNECTION_RETRY_MAX` | 3 | DB retry attempts | Keep at 3 |
| `DB_CONNECTION_RETRY_DELAY` | 1 | Initial DB retry delay | Keep at 1 |
| `REFRESH_INTERVAL_HOURS` | 6 | Scheduled refresh interval | Adjust per freshness needs |

---

## ⚠️ Known Limitations & Notes

1. **Archive Table Not Auto-Purged** — Set a cron job to clean old archives:
   ```bash
   # Purge archives older than retention period
   psql -U rankings -d rankings -h localhost -c \
     "DELETE FROM rankings_archive WHERE archived_at < (NOW() - INTERVAL '730 days')"
   ```

2. **Startup Refresh is Async** — If API receives requests before refresh completes, stale cache may be served briefly. This is acceptable for resilience (API stays up).

3. **Manual Recovery** — For corrupted data, restore from `rankings_archive`:
   ```sql
   -- Example (consult DBA before running)
   SELECT * FROM rankings_archive WHERE player_name = 'Player Name' 
   ORDER BY archived_at DESC LIMIT 1;
   ```

---

## 📞 Support & Troubleshooting

### Issue: Startup refresh never completes

**Solution:** Check logs for scraper errors:
```bash
grep -i "scrape\|refresh" /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log | tail -20
```

### Issue: Data showing as stale despite recent scrape

**Solution:** Check DATA_STALENESS_WARNING_DAYS threshold:
```bash
cd /home/ansible/rankings-bot/Rankings-Bot
grep DATA_STALENESS .env
```

### Issue: Archive table not growing

**Solution:** Verify ENABLE_DATA_ARCHIVAL=true and check disk space:
```bash
df -h /var/lib/postgresql  # Check PostgreSQL disk
```

---

## ✅ Final Deployment Checklist

- [ ] Database schema verified (rankings, ranking_changes, rankings_archive tables exist)
- [ ] .env updated with resilience variables
- [ ] Python imports verified (scrapers, database, decorators)
- [ ] Configuration consistency validated (thresholds, backoff, retention)
- [ ] Backup created before deployment
- [ ] Archive table exists and is accessible
- [ ] API service restarted with new config
- [ ] Startup logs reviewed (no errors in [STARTUP] / [SELFTEST] sections)
- [ ] Health endpoint accessible (`/api/rankings/health`)
- [ ] Scraper retry logic confirmed (check logs for retry attempts)
- [ ] Monitoring configured (cron job for archive cleanup)
- [ ] Team notified of resilience improvements

---

**Status:** ✅ **READY FOR PRODUCTION DEPLOYMENT**

All 4 Priorities (Startup Recovery, Scraper Resilience, Data Archival, Connection Resilience) are implemented, integrated, and tested.
