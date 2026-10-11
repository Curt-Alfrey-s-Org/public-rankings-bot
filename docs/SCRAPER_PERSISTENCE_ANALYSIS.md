 # Scraper Data Persistence Analysis - Rankings Bot

**Date:** February 12, 2026  
**Component:** Rankings-Bot Scrapers (WPA & WPBA)

## Executive Summary

The rankings-bot has two scrapers (WPA and WPBA) that fetch ranking data from external sources. While data **is persisted** in PostgreSQL, there are several gaps in resilience, archival, and recovery mechanisms that need to be addressed for production robustness.

---

## Current Architecture

### Scrapers

#### 1. **WPAScraper** (`scrapers/wpa_scraper.py`)
- **Source:** https://wpapool.com/rankings/
- **Method:** HTML scraping with BeautifulSoup
- **Data Extracted:** rank, name, points, country, license_number
- **Timeout:** 30 seconds
- **Retry Logic:** ❌ None

#### 2. **WPBAScraper** (`scrapers/wpba_scraper.py`)
- **Source:** PDF file from Squarespace (static URL)
- **Method:** PDF parsing with pdfplumber
- **Data Extracted:** rank, name, points
- **Timeout:** 30 seconds
- **Retry Logic:** ❌ None

### Database Persistence (PostgreSQL)

#### Tables
1. **`rankings`** - Current and historical snapshots
   - Primary key: `id`
   - Unique constraint: `(player_name, ranking_system, snapshot_date)`
   - Columns: `player_name`, `ranking_system`, `rank`, `points`, `country`, `snapshot_date`, `license_number`, `fargo_rating`, `created_at`

2. **`ranking_changes`** - Detected changes between snapshots
   - Tracks: old_rank → new_rank, old_points → new_points
   - Change types: `new_player`, `rank_up`, `rank_down`, `points_change`

#### Data Flow
```
Scraper → API Route (/api/rankings/refresh)
         ↓
    DatabaseManager.save_rankings()
         ↓
    UPSERT to rankings table (ON CONFLICT DO UPDATE)
         ↓
    _detect_and_save_changes() → ranking_changes table
```

### Scheduling

**Monitoring Daemon** (`Rankings-Bot/scripts/rankings_daemon.py`)
- **Frequency:** Every 6 hours (configurable via `REFRESH_INTERVAL_HOURS`)
- **Mechanism:** Calls `POST /api/rankings/refresh`
- **Health Check:** Monitors API status
- **Alerting:** Logs consecutive failures, sends alerts after 3 failures

---

## ✅ Current Strengths

1. **Data is Persisted:** All scraped data goes to PostgreSQL
2. **Historical Snapshots:** Each scrape creates a new snapshot (by date)
3. **Change Detection:** Automatic comparison between snapshots
4. **Unique Constraint:** Prevents duplicate entries per player/system/date
5. **Scheduled Refresh:** Automated scraping every 6 hours
6. **Monitoring:** Health checks and failure tracking

---

## ❌ Critical Gaps

### 1. **No Startup Recovery Check**
**Issue:** If the database is empty after reboot/restart, the bot doesn't automatically fetch initial data.

**Risk:** Bot may serve empty results until the next scheduled refresh (up to 6 hours).

**Solution Needed:**
- Add startup check in `api/main.py`
- If `rankings` table is empty or stale (>24 hours), trigger immediate refresh
- Log startup data status

### 2. **No Scraper Retry Logic**
**Issue:** Both scrapers fail immediately on network errors, timeouts, or parsing issues.

**Current Behavior:**
```python
try:
    response = self.session.get(url, timeout=30)
    # Parse and return
except Exception as e:
    logger.error(f"Error: {e}")
    return []  # ❌ Immediate failure
```

**Solution Needed:**
- Implement exponential backoff retry (3-5 attempts)
- Different retry strategies for network vs. parsing errors
- Detect transient failures (503, timeout) vs. permanent (404, 403)

### 3. **No Data Archival Strategy**
**Issue:** The `rankings` table uses UPSERT (`ON CONFLICT DO UPDATE`), which means:
- Old data for the same `(player, system, date)` is **overwritten**, not archived
- If scraper runs twice on the same day, first scrape is lost
- No separate historical archive table

**Current Behavior:**
```sql
INSERT INTO rankings (...) VALUES (...)
ON CONFLICT(player_name, ranking_system, snapshot_date) 
DO UPDATE SET rank = excluded.rank, points = excluded.points
-- ❌ Overwrites without archiving
```

**Solution Needed:**
- Create `rankings_archive` table for historical preservation
- Before UPDATE, move old row to archive
- Implement data retention policy (keep archives for N years)

### 4. **No Connection Loss Resilience**
**Issue:** If database connection is lost during operation:
- New scrapes will fail
- No fallback or queuing mechanism
- Data is lost until connection restores

**Solution Needed:**
- Add connection retry logic in DatabaseManager
- Implement write-ahead log or queue for failed writes
- Cache last successful scrape in memory/file as fallback

### 5. **No Data Staleness Verification**
**Issue:** If scrapers consistently fail, stale data remains in database with no warning to users.

**Current Behavior:**
- `/api/rankings/last-update` shows last snapshot date
- But frontend doesn't check staleness or warn users

**Solution Needed:**
- Add staleness check: if last snapshot > 48 hours, show warning
- Return staleness metadata in API responses
- Monitor and alert on data age

### 6. **No Unchanged Data Detection**
**Issue:** Requirement says "new scrape data will replace old data (unless no change in data)" but:
- Current implementation always writes (even if no change)
- No optimization to skip writes when data is identical

**Solution Needed:**
- Before UPSERT, check if new data differs from last snapshot
- Only write if changes detected
- Return metadata: `{skipped: X, updated: Y, new: Z}`

### 7. **No Manual Recovery Tools**
**Issue:** If data corruption occurs or needs restoration:
- No backup/restore scripts
- No way to replay historical scrapes
- No data validation tools

**Solution Needed:**
- Add database backup scripts
- Create data validation endpoint
- Build recovery tools for common scenarios

---

## 📊 Data Persistence Flow Analysis

### Current Flow
```
┌─────────────┐
│   Scraper   │ (WPA/WPBA)
└──────┬──────┘
       │ Returns List[Dict]
       ▼
┌─────────────────────┐
│  API Route Handler  │ (/api/rankings/refresh)
│  - Parallel scraping│
│  - Sequential save  │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ DatabaseManager     │
│ .save_rankings()    │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────────────┐
│ PostgreSQL (rankings table) │
│ UPSERT on conflict          │
└──────┬──────────────────────┘
       │
       ▼
┌──────────────────────────┐
│ _detect_and_save_changes │
│ (ranking_changes table)  │
└──────────────────────────┘
```

### Issues in Current Flow
1. **No validation step** before write
2. **No diff check** to skip unchanged data
3. **No transactional integrity** across both scrapers
4. **No rollback** on partial failure

---

## 🔧 Recommended Improvements

### Priority 1: Critical (Reboot/Connection Loss)

#### 1.1 Startup Data Check
**File:** `api/main.py` (in startup event)

```python
@app.on_event("startup")
async def startup_tasks():
    """Check data freshness and trigger refresh if needed."""
    db_manager = get_database_manager()
    
    # Check if rankings table is empty or stale
    wpba_last = db_manager.get_last_snapshot_date('WPBA_Women')
    wpa_last = db_manager.get_last_snapshot_date('WPA_Women')
    
    now = date.today()
    needs_refresh = False
    
    if not wpba_last or (now - wpba_last).days > 1:
        logger.warning(f"WPBA data stale or missing (last: {wpba_last})")
        needs_refresh = True
    
    if not wpa_last or (now - wpa_last).days > 1:
        logger.warning(f"WPA data stale or missing (last: {wpa_last})")
        needs_refresh = True
    
    if needs_refresh:
        logger.info("Triggering startup refresh...")
        # Trigger async refresh
        asyncio.create_task(trigger_startup_refresh())
```

#### 1.2 Add to DatabaseManager
```python
def get_last_snapshot_date(self, system: str) -> Optional[date]:
    """Get the most recent snapshot date for a system."""
    conn = self.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MAX(snapshot_date) FROM rankings 
        WHERE ranking_system = ?
    """, (system,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result and result[0] else None
```

### Priority 2: Scraper Resilience

#### 2.1 Add Retry Decorator
**File:** `scrapers/base.py` (new file)

```python
import time
import logging
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)

def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Retry decorator with exponential backoff."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(
                            f"{func.__name__} attempt {attempt}/{max_attempts} "
                            f"failed: {e}. Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts"
                        )
            
            raise last_exception
        return wrapper
    return decorator
```

#### 2.2 Update Scrapers
**File:** `scrapers/wpa_scraper.py`

```python
from scrapers.base import retry_with_backoff
import requests

class WPAScraper:
    @retry_with_backoff(
        max_attempts=3,
        initial_delay=2.0,
        exceptions=(requests.RequestException, ConnectionError)
    )
    def scrape_rankings(self) -> List[Dict]:
        """Scrape WPA rankings with retry logic."""
        # ... existing code
```

### Priority 3: Data Archival

#### 3.1 Create Archive Table
**File:** `database/schema_postgres.sql`

```sql
-- Historical archive (immutable records of every scrape)
CREATE TABLE IF NOT EXISTS rankings_archive (
    id SERIAL PRIMARY KEY,
    original_id INTEGER NOT NULL,  -- FK to rankings.id
    player_name VARCHAR(255) NOT NULL,
    ranking_system VARCHAR(32) NOT NULL,
    rank INTEGER NOT NULL,
    points DOUBLE PRECISION NOT NULL,
    country VARCHAR(255),
    snapshot_date DATE NOT NULL,
    license_number VARCHAR(255),
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archive_reason VARCHAR(64) DEFAULT 'update'  -- 'update', 'delete', 'correction'
);

CREATE INDEX idx_rankings_archive_player ON rankings_archive(player_name);
CREATE INDEX idx_rankings_archive_date ON rankings_archive(snapshot_date);
CREATE INDEX idx_rankings_archive_archived_at ON rankings_archive(archived_at DESC);
```

#### 3.2 Update Save Logic
**File:** `database/db_manager.py`

```python
def save_rankings(self, rankings: List[Dict], system: str, snapshot_date: date = None):
    """Save rankings with archival of old data."""
    if snapshot_date is None:
        snapshot_date = date.today()
    
    conn = self.get_connection()
    cursor = conn.cursor()
    saved_count = 0
    archived_count = 0
    
    for ranking in rankings:
        try:
            # Check if ranking exists
            cursor.execute("""
                SELECT id, rank, points, country, license_number
                FROM rankings
                WHERE player_name = ? AND ranking_system = ? AND snapshot_date = ?
            """, (ranking['name'], system, snapshot_date.isoformat()))
            
            existing = cursor.fetchone()
            
            if existing:
                # Archive old data before update
                cursor.execute("""
                    INSERT INTO rankings_archive 
                    (original_id, player_name, ranking_system, rank, points, 
                     country, snapshot_date, license_number, archive_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'update')
                """, (existing[0], ranking['name'], system, existing[1], 
                      existing[2], existing[3], snapshot_date.isoformat(), 
                      existing[4]))
                archived_count += 1
            
            # Upsert current data
            cursor.execute("""
                INSERT INTO rankings 
                (player_name, ranking_system, rank, points, country, 
                 snapshot_date, license_number)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(player_name, ranking_system, snapshot_date) 
                DO UPDATE SET
                    rank = excluded.rank,
                    points = excluded.points,
                    country = excluded.country,
                    license_number = excluded.license_number
            """, (ranking['name'], system, ranking['rank'], ranking['points'],
                  ranking.get('country'), snapshot_date.isoformat(),
                  ranking.get('license_number')))
            
            saved_count += 1
            
        except Exception as e:
            logger.error(f"Error saving ranking for {ranking.get('name')}: {e}")
    
    conn.commit()
    conn.close()
    
    logger.info(
        f"Saved {saved_count} {system} rankings "
        f"(archived {archived_count}) for {snapshot_date}"
    )
    
    self._detect_and_save_changes(system, snapshot_date)
    return saved_count
```

### Priority 4: Unchanged Data Detection

#### 4.1 Add Diff Check
**File:** `database/db_manager.py`

```python
def _has_data_changed(self, cursor, name: str, system: str, 
                      snapshot_date: date, new_data: Dict) -> bool:
    """Check if ranking data has changed."""
    cursor.execute("""
        SELECT rank, points, country, license_number
        FROM rankings
        WHERE player_name = ? AND ranking_system = ? AND snapshot_date = ?
    """, (name, system, snapshot_date.isoformat()))
    
    existing = cursor.fetchone()
    if not existing:
        return True  # New entry
    
    # Compare values
    old_rank, old_points, old_country, old_license = existing
    return (
        old_rank != new_data['rank'] or
        old_points != new_data['points'] or
        old_country != new_data.get('country') or
        old_license != new_data.get('license_number')
    )

def save_rankings(self, rankings: List[Dict], system: str, 
                  snapshot_date: date = None):
    """Save rankings, skipping unchanged data."""
    # ... (existing setup code)
    
    skipped_count = 0
    
    for ranking in rankings:
        # Check if data changed
        if not self._has_data_changed(cursor, ranking['name'], system, 
                                       snapshot_date, ranking):
            skipped_count += 1
            continue
        
        # ... (save logic)
    
    logger.info(
        f"Saved {saved_count}, skipped {skipped_count} unchanged, "
        f"archived {archived_count} for {system} on {snapshot_date}"
    )
```

### Priority 5: Connection Resilience

#### 5.1 Add Connection Retry to DatabaseManager
```python
from functools import wraps
import psycopg2

def with_connection_retry(max_attempts: int = 3):
    """Retry database operations on connection failure."""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(self, *args, **kwargs)
                except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                    if attempt < max_attempts:
                        logger.warning(
                            f"DB connection failed (attempt {attempt}): {e}. "
                            "Retrying..."
                        )
                        time.sleep(2 ** attempt)
                        # Reconnect
                        self._engine.dispose()
                    else:
                        logger.error(f"DB connection failed after {max_attempts} attempts")
                        raise
        return wrapper
    return decorator

@with_connection_retry(max_attempts=3)
def save_rankings(self, rankings: List[Dict], system: str, snapshot_date: date = None):
    """Save rankings with automatic retry on connection loss."""
    # ... existing code
```

### Priority 6: Monitoring & Alerting

#### 6.1 Add Data Staleness Check
**File:** `api/routes/rankings.py`

```python
@router.get("/health")
async def get_rankings_health():
    """Check rankings data health and staleness."""
    db_manager = get_db_manager()
    
    wpba_last = db_manager.get_last_snapshot_date('WPBA_Women')
    wpa_last = db_manager.get_last_snapshot_date('WPA_Women')
    
    now = date.today()
    
    wpba_age_days = (now - wpba_last).days if wpba_last else 999
    wpa_age_days = (now - wpa_last).days if wpa_last else 999
    
    health_status = {
        "status": "healthy",
        "wpba": {
            "last_update": wpba_last.isoformat() if wpba_last else None,
            "age_days": wpba_age_days,
            "stale": wpba_age_days > 2
        },
        "wpa": {
            "last_update": wpa_last.isoformat() if wpa_last else None,
            "age_days": wpa_age_days,
            "stale": wpa_age_days > 2
        }
    }
    
    # Overall health
    if wpba_age_days > 7 or wpa_age_days > 7:
        health_status["status"] = "critical"
    elif wpba_age_days > 2 or wpa_age_days > 2:
        health_status["status"] = "warning"
    
    return health_status
```

---

## 🎯 Implementation Roadmap

### Phase 1: Critical Fixes (Week 1)
- [ ] Add startup data check and auto-refresh
- [ ] Implement scraper retry logic with exponential backoff
- [ ] Add connection retry to DatabaseManager
- [ ] Create data staleness monitoring endpoint

### Phase 2: Data Integrity (Week 2)
- [ ] Create rankings_archive table
- [ ] Update save_rankings with archival logic
- [ ] Implement unchanged data detection (skip logic)
- [ ] Add data validation tools

### Phase 3: Resilience & Monitoring (Week 3)
- [ ] Build recovery scripts for common failure scenarios
- [ ] Add comprehensive logging and metrics
- [ ] Create database backup automation
- [ ] Implement alerting for prolonged staleness

### Phase 4: Performance & Optimization (Week 4)
- [ ] Add caching layer for frequent queries
- [ ] Optimize database indexes
- [ ] Implement data retention/cleanup policies
- [ ] Load testing and performance tuning

---

## 📝 Configuration Changes Needed

### Environment Variables (add to `.env`)
```bash
# Scraper Configuration
SCRAPER_MAX_RETRIES=3
SCRAPER_RETRY_DELAY=2.0
SCRAPER_TIMEOUT=30

# Data Freshness
DATA_STALENESS_WARNING_DAYS=2
DATA_STALENESS_CRITICAL_DAYS=7

# Startup Behavior
AUTO_REFRESH_ON_STARTUP=true
STARTUP_STALENESS_THRESHOLD_HOURS=24

# Archival
ENABLE_DATA_ARCHIVAL=true
ARCHIVE_RETENTION_DAYS=730  # 2 years

# Connection Resilience
DB_CONNECTION_RETRY_MAX=3
DB_CONNECTION_RETRY_DELAY=2
```

---

## 🧪 Testing Requirements

### Unit Tests Needed
1. Scraper retry logic with mock failures
2. Database archival (verify archive table population)
3. Unchanged data detection (skip logic)
4. Staleness calculation
5. Connection retry behavior

### Integration Tests Needed
1. Full refresh cycle with failures
2. Startup recovery from empty database
3. Connection loss during scrape
4. Archival and retrieval flow

### Manual Testing Scenarios
1. Reboot server → verify auto-refresh
2. Disconnect network → verify retry and recovery
3. Run multiple refreshes same day → verify archival
4. Simulate stale data → verify health endpoint warnings

---

## 📊 Success Metrics

1. **Zero Data Loss:** All scraped data persisted (even on retries)
2. **Auto-Recovery:** System recovers from reboot/connection loss in <5 minutes
3. **Change Detection:** 100% of ranking changes captured in `ranking_changes`
4. **Staleness Alerts:** Warnings triggered within 1 hour of threshold breach
5. **Archive Integrity:** All updates archived before overwrite

---

## Summary

**Current State:** ✅ Data persists, ⚠️ but lacks resilience  
**Gaps Found:** 7 critical issues  
**Priority Focus:** Startup recovery, retry logic, archival  
**Estimated Effort:** 3-4 weeks for complete implementation  

This analysis provides a roadmap to make the rankings-bot fully production-ready with robust data persistence, archival, and recovery mechanisms.
