# Scraper Persistence Fixes - Quick Implementation Guide

**Priority:** Critical  
**Estimated Time:** 2-3 days for P1 fixes  

---

## 🚨 Critical Issues Summary

| Issue | Impact | Fix Effort |
|-------|--------|-----------|
| No startup data check | Empty database after reboot | 30 min |
| No scraper retry logic | Single network hiccup = failure | 1 hour |
| No data archival | Overwrites without history | 2 hours |
| No connection retry | DB disconnect = data loss | 1 hour |
| No unchanged data skip | Wasted writes | 1 hour |

---

## 🛠️ Quick Fixes (Priority 1)

### Fix 1: Startup Data Check (30 minutes)

**File:** `rankings-bot/api/main.py`

Add to startup event:
```python
from datetime import date, timedelta
import asyncio

@app.on_event("startup")
async def check_data_freshness():
    """Auto-refresh stale/missing data on startup."""
    try:
        db_manager = get_database_manager()
        
        # Check WPBA
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MAX(snapshot_date) FROM rankings 
            WHERE ranking_system = 'WPBA_Women'
        """)
        wpba_last = cursor.fetchone()[0] if cursor.fetchone() else None
        
        # Check WPA
        cursor.execute("""
            SELECT MAX(snapshot_date) FROM rankings 
            WHERE ranking_system = 'WPA_Women'
        """)
        wpa_last = cursor.fetchone()[0] if cursor.fetchone() else None
        conn.close()
        
        # Determine if refresh needed
        today = date.today()
        needs_refresh = False
        
        if not wpba_last or (today - wpba_last).days > 1:
            logger.warning(f"⚠️ WPBA data stale/missing (last: {wpba_last})")
            needs_refresh = True
        
        if not wpa_last or (today - wpa_last).days > 1:
            logger.warning(f"⚠️ WPA data stale/missing (last: {wpa_last})")
            needs_refresh = True
        
        if needs_refresh:
            logger.info("🔄 Triggering startup refresh...")
            # Trigger refresh asynchronously
            asyncio.create_task(trigger_startup_refresh())
        else:
            logger.info("✅ Rankings data fresh")
            
    except Exception as e:
        logger.error(f"Startup check failed: {e}")

async def trigger_startup_refresh():
    """Background refresh on startup."""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8003/api/rankings/refresh",
                timeout=300.0
            )
            if response.status_code == 200:
                logger.info("✅ Startup refresh completed")
            else:
                logger.error(f"❌ Startup refresh failed: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Startup refresh error: {e}")
```

---

### Fix 2: Scraper Retry Logic (1 hour)

**Step 1:** Create base retry decorator

**File:** `rankings-bot/scrapers/base_scraper.py` (NEW)

```python
import time
import logging
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)

def retry_with_backoff(max_attempts=3, initial_delay=2.0, backoff_factor=2.0):
    """Retry decorator with exponential backoff."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_error = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 1:
                        logger.info(f"✅ {func.__name__} succeeded on attempt {attempt}")
                    return result
                    
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts:
                        logger.warning(
                            f"⚠️ {func.__name__} attempt {attempt}/{max_attempts} "
                            f"failed: {e}. Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
                    else:
                        logger.error(
                            f"❌ {func.__name__} failed after {max_attempts} attempts: {e}"
                        )
            
            # Return empty list instead of raising (graceful degradation)
            logger.error(f"Returning empty result after all retries failed")
            return []
            
        return wrapper
    return decorator
```

**Step 2:** Update WPA Scraper

**File:** `rankings-bot/scrapers/wpa_scraper.py`

Add import at top:
```python
from scrapers.base_scraper import retry_with_backoff
```

Update scrape method:
```python
@retry_with_backoff(max_attempts=3, initial_delay=2.0)
def scrape_rankings(self) -> List[Dict]:
    """Scrape WPA rankings with retry logic."""
    # ... rest of existing code stays the same
```

**Step 3:** Update WPBA Scraper

**File:** `rankings-bot/scrapers/wpba_scraper.py`

Add same import and decorator to `scrape_rankings()` method.

---

### Fix 3: Database Connection Retry (1 hour)

**File:** `rankings-bot/Rankings-Bot/database/db_manager.py`

Add at top of class:
```python
import time
from functools import wraps

def with_db_retry(max_attempts=3):
    """Retry database operations on connection failure."""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            delay = 1.0
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(self, *args, **kwargs)
                except Exception as e:
                    # Check if it's a connection error
                    error_str = str(e).lower()
                    is_connection_error = any(x in error_str for x in [
                        'connection', 'operational', 'interface', 
                        'timeout', 'closed'
                    ])
                    
                    if is_connection_error and attempt < max_attempts:
                        logger.warning(
                            f"DB error (attempt {attempt}/{max_attempts}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        delay *= 2
                        
                        # Try to reset connection
                        try:
                            self._engine.dispose()
                        except:
                            pass
                    else:
                        raise
            
        return wrapper
    return decorator
```

Add decorator to critical methods:
```python
@with_db_retry(max_attempts=3)
def save_rankings(self, rankings: List[Dict], system: str, snapshot_date: date = None):
    """Save rankings with automatic retry on DB errors."""
    # ... existing code

@with_db_retry(max_attempts=3)
def get_latest_rankings(self, system: str) -> List[Dict]:
    """Get rankings with retry."""
    # ... existing code
```

---

### Fix 4: Data Archival (2 hours)

**Step 1:** Create archive table

**File:** `rankings-bot/Rankings-Bot/database/schema_postgres.sql`

Add at end of file:
```sql
-- Rankings archive (historical preservation)
CREATE TABLE IF NOT EXISTS rankings_archive (
    id SERIAL PRIMARY KEY,
    original_id INTEGER,
    player_name VARCHAR(255) NOT NULL,
    ranking_system VARCHAR(32) NOT NULL,
    rank INTEGER NOT NULL,
    points DOUBLE PRECISION NOT NULL,
    country VARCHAR(255),
    snapshot_date DATE NOT NULL,
    license_number VARCHAR(255),
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    archive_reason VARCHAR(64) DEFAULT 'update'
);

CREATE INDEX IF NOT EXISTS idx_rankings_archive_player 
    ON rankings_archive(player_name);
CREATE INDEX IF NOT EXISTS idx_rankings_archive_date 
    ON rankings_archive(snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_rankings_archive_archived_at 
    ON rankings_archive(archived_at DESC);
```

**Step 2:** Run migration

```bash
cd rankings-bot/Rankings-Bot
psql $DATABASE_URL -f database/schema_postgres.sql
```

**Step 3:** Update save logic

**File:** `rankings-bot/Rankings-Bot/database/db_manager.py`

In `save_rankings()` method, before the UPSERT, add archival:

```python
def save_rankings(self, rankings: List[Dict], system: str, snapshot_date: date = None):
    """Save rankings with archival."""
    if snapshot_date is None:
        snapshot_date = date.today()
    
    conn = self.get_connection()
    cursor = conn.cursor()
    
    # Check if archival table exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'rankings_archive'
        )
    """)
    has_archive = cursor.fetchone()[0]
    
    saved_count = 0
    archived_count = 0
    
    for ranking in rankings:
        try:
            # Archive existing data before UPSERT
            if has_archive:
                cursor.execute("""
                    INSERT INTO rankings_archive 
                    (original_id, player_name, ranking_system, rank, points, 
                     country, snapshot_date, license_number, archive_reason)
                    SELECT id, player_name, ranking_system, rank, points, 
                           country, snapshot_date, license_number, 'pre_update'
                    FROM rankings
                    WHERE player_name = ? 
                      AND ranking_system = ? 
                      AND snapshot_date = ?
                """, (ranking['name'], system, snapshot_date.isoformat()))
                
                if cursor.rowcount > 0:
                    archived_count += 1
            
            # Now do UPSERT
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
            """, (
                ranking['name'], system, ranking['rank'], ranking['points'],
                ranking.get('country'), snapshot_date.isoformat(),
                ranking.get('license_number')
            ))
            saved_count += 1
            
        except Exception as e:
            logger.error(f"Error saving {ranking.get('name')}: {e}")
    
    conn.commit()
    conn.close()
    
    logger.info(
        f"Saved {saved_count} {system} rankings "
        f"(archived {archived_count}) for {snapshot_date}"
    )
    
    self._detect_and_save_changes(system, snapshot_date)
    return saved_count
```

---

### Fix 5: Skip Unchanged Data (1 hour)

**File:** `rankings-bot/Rankings-Bot/database/db_manager.py`

Add helper method:
```python
def _has_ranking_changed(self, cursor, name: str, system: str, 
                         snapshot_date: date, new_data: Dict) -> bool:
    """Check if ranking data differs from existing."""
    cursor.execute("""
        SELECT rank, points, country, license_number
        FROM rankings
        WHERE player_name = ? AND ranking_system = ? AND snapshot_date = ?
    """, (name, system, snapshot_date.isoformat()))
    
    result = cursor.fetchone()
    if not result:
        return True  # New entry = changed
    
    old_rank, old_points, old_country, old_license = result
    
    return (
        old_rank != new_data['rank'] or
        abs(old_points - new_data['points']) > 0.01 or  # Float comparison
        old_country != new_data.get('country') or
        old_license != new_data.get('license_number')
    )
```

Update `save_rankings()` loop:
```python
    skipped_count = 0
    
    for ranking in rankings:
        try:
            # Check if data changed
            if not self._has_ranking_changed(
                cursor, ranking['name'], system, snapshot_date, ranking
            ):
                skipped_count += 1
                continue
            
            # ... rest of save logic (archive + upsert)
```

Update final log:
```python
    logger.info(
        f"Saved {saved_count}, skipped {skipped_count} unchanged, "
        f"archived {archived_count} | {system} {snapshot_date}"
    )
```

---

## 🧪 Testing Checklist

After implementing fixes, test:

### Manual Tests
```bash
# Test 1: Startup with empty/stale data
docker-compose restart rankings-bot-api
# Watch logs for auto-refresh

# Test 2: Scraper retry
# Temporarily break WPA URL in wpa_scraper.py
# Run refresh, should see 3 retry attempts

# Test 3: Connection loss recovery
# Kill postgres mid-scrape, restart it
# Should see retry and recovery

# Test 4: Archive verification
psql $DATABASE_URL -c "SELECT COUNT(*) FROM rankings_archive;"
# Should show archived entries

# Test 5: Unchanged data skip
# Run refresh twice in same day
# Second run should skip most entries
```

### Automated Tests
```bash
cd rankings-bot
pytest tests/ -k "scraper or database" -v
```

---

## 📊 Verification Metrics

After deployment, monitor:

1. **Startup behavior:** Check logs for auto-refresh trigger
2. **Retry success rate:** Count retry attempts vs. successes
3. **Archive growth:** `SELECT COUNT(*) FROM rankings_archive`
4. **Skip rate:** Check logs for "skipped N unchanged"
5. **Connection resilience:** Monitor DB error recovery

---

## 🚀 Deployment Steps

1. **Backup database:**
   ```bash
   pg_dump $DATABASE_URL > rankings_backup_$(date +%Y%m%d).sql
   ```

2. **Create archive table:**
   ```bash
   psql $DATABASE_URL -f Rankings-Bot/database/schema_postgres.sql
   ```

3. **Deploy code changes:**
   ```bash
   git pull origin main
   docker-compose down
   docker-compose up -d --build
   ```

4. **Verify startup:**
   ```bash
   docker-compose logs -f rankings-bot-api | grep -E "startup|refresh|archive"
   ```

5. **Test manual refresh:**
   ```bash
   curl -X POST http://localhost:8003/api/rankings/refresh \
     -H "Authorization: Bearer $ADMIN_TOKEN"
   ```

---

## ⏱️ Implementation Time Estimate

- Fix 1 (Startup check): **30 minutes**
- Fix 2 (Retry logic): **1 hour**
- Fix 3 (Connection retry): **1 hour**
- Fix 4 (Archival): **2 hours**
- Fix 5 (Skip unchanged): **1 hour**
- Testing: **1 hour**
- Documentation: **30 minutes**

**Total:** ~7 hours (1 full day of focused work)

---

## 🆘 Rollback Plan

If issues occur:

1. **Restore database:**
   ```bash
   psql $DATABASE_URL < rankings_backup_YYYYMMDD.sql
   ```

2. **Revert code:**
   ```bash
   git revert HEAD
   docker-compose up -d --build
   ```

3. **Quick fix:**
   - Remove `@retry_with_backoff` decorators
   - Remove archive logic
   - Keep startup check (low risk)

---

## 📞 Support

If you encounter issues:
- Check logs: `docker-compose logs rankings-bot-api`
- Verify DB: `psql $DATABASE_URL -c "SELECT COUNT(*) FROM rankings;"`
- Test scrapers: `python rankings-bot/test_scrapers_manual.py`
