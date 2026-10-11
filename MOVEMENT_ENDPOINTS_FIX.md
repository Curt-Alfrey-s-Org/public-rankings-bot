# Movement & Snapshots Endpoints Fix - Complete Resolution

## Problem Description

Users reported a 500 error on the Movement page with the following error message in the browser console:
```
GET https://probilliardssoftware.com/api/rankings/movement?system=WPBA&limit=100 → 500
ERROR: name 'db_manager' is not defined
```

Additionally, the `/api/rankings/snapshots` endpoint had the same issue.

## Root Cause

During the SQLite-to-PostgreSQL migration cleanup phase:
1. All SQLite database files were deleted (`rankings.db`, `api/rankings.db`, etc.)
2. SQLite imports were removed from Python files
3. Main ranking endpoints (`/wpba-women`, `/wpa-men`, etc.) were successfully refactored to query PostgreSQL directly using SQLAlchemy
4. **However**, two analytics endpoints (`/movement`, `/snapshots`) still contained references to `db_manager.get_movement()` and `db_manager.get_snapshot_dates()` without initializing the `db_manager` variable
5. The `DatabaseManager` class itself still tried to use SQLite in its initialization, making it impossible to instantiate

## Solution Implemented

### 1. Refactored `/api/rankings/movement` Endpoint

**Before:**
```python
@router.get("/movement")
async def get_movement(system: str = Query(...), limit: int = Query(50, ...)):
    try:
        entries = db_manager.get_movement(system.upper(), limit=limit)  # ❌ db_manager undefined
        return {"system": system.upper(), "movement": entries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**After:**
```python
@router.get("/movement")
async def get_movement(system: str = Query(...), limit: int = Query(50, ...)):
    try:
        from sqlalchemy import text
        from database import engine
        
        with engine.connect() as conn:
            query = text("""
                SELECT player_name, ranking_system, old_rank, new_rank, 
                       old_points, new_points, change_date, change_type
                FROM ranking_changes
                WHERE ranking_system = :system
                ORDER BY change_date DESC, id DESC
                LIMIT :limit
            """)
            rows = conn.execute(query, {"system": system.upper(), "limit": limit}).fetchall()
            
            entries = [
                {
                    "player_name": r[0],
                    "ranking_system": r[1],
                    "old_rank": r[2],
                    "new_rank": r[3],
                    "old_points": r[4],
                    "new_points": r[5],
                    "change_date": str(r[6]),
                    "change_type": r[7],
                }
                for r in rows
            ]
        return {"system": system.upper(), "movement": entries}
    except Exception as e:
        logger.error(f"Error fetching movement: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 2. Refactored `/api/rankings/snapshots` Endpoint

**Before:**
```python
@router.get("/snapshots")
async def get_snapshot_dates(system: str = Query(...), limit: int = Query(30, ...)):
    try:
        dates = db_manager.get_snapshot_dates(system.upper(), limit=limit)  # ❌ db_manager undefined
        return {"system": system.upper(), "snapshot_dates": dates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**After:**
```python
@router.get("/snapshots")
async def get_snapshot_dates(system: str = Query(...), limit: int = Query(30, ...)):
    try:
        from sqlalchemy import text
        from database import engine
        
        with engine.connect() as conn:
            query = text("""
                SELECT DISTINCT snapshot_date
                FROM rankings
                WHERE ranking_system = :system
                ORDER BY snapshot_date DESC
                LIMIT :limit
            """)
            rows = conn.execute(query, {"system": system.upper(), "limit": limit}).fetchall()
            dates = [str(r[0]) for r in rows]
        
        return {"system": system.upper(), "snapshot_dates": dates}
    except Exception as e:
        logger.error(f"Error fetching snapshot dates: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 3. Fixed Database Schema

Added missing columns to the `rankings` table that the API expects:
```sql
ALTER TABLE rankings ADD COLUMN IF NOT EXISTS stops_played INTEGER;
ALTER TABLE rankings ADD COLUMN IF NOT EXISTS alfa_rating DOUBLE PRECISION;
```

## Testing Verification

All key endpoints now return valid responses:

### Movement Endpoint
```bash
$ curl 'http://127.0.0.1:8003/api/rankings/movement?system=WPBA&limit=1'
{"system":"WPBA","movement":[]}  # ✓ Empty but valid - no data yet
```

### Snapshots Endpoint
```bash
$ curl 'http://127.0.0.1:8003/api/rankings/snapshots?system=WPBA&limit=1'
{"system":"WPBA","snapshot_dates":[]}  # ✓ Empty but valid - no data yet
```

### Ranking Endpoints
```bash
$ curl 'http://127.0.0.1:8003/api/rankings/wpba-women?limit=1'
{"total":0,"limit":1,"offset":0,"count":0,"rankings":[],"association":"WPBA","division":"Women","ranking_type":"WPBA_Women"}  # ✓ Working
```

## Files Modified

- **api/routes/rankings.py** (lines 705-777)
  - Refactored `get_movement()` function to use PostgreSQL directly
  - Refactored `get_snapshot_dates()` function to use PostgreSQL directly

## Architecture

The fix completes the PostgreSQL migration by ensuring:
1. **All ranking endpoints** use SQLAlchemy with PostgreSQL
2. **All analytics endpoints** use SQLAlchemy with PostgreSQL  
3. **No dependencies** on the SQLite-based DatabaseManager class
4. **Single source of truth** is PostgreSQL exclusively

## Data Population

The endpoints are now functional but return empty results because the database was reset during the rebuild. To populate ranking data:

1. **Automated**: Run ranking refresh endpoints (requires scraper configuration)
2. **Manual**: Restore from a PostgreSQL backup file
3. **Frontend**: Use admin UI to import ranking data

## Next Steps

1. ✅ Endpoints fixed and verified working
2. ✅ Changes committed to GitHub (commit: 2253d8b)
3. ⏳ Restart frontend to refresh cached API responses
4. ⏳ Populate database with ranking data (via backup restoration or manual import)
5. ⏳ Verify Movement page loads with historical data

## Technical Notes

- The fix uses SQLAlchemy's `text()` function for raw SQL queries to PostgreSQL
- Connection pooling is managed by the `database.engine` instance
- Proper error logging is maintained for debugging
- The approach is consistent with other working endpoints (wpba-women, wpa-men, etc.)

---

**Status**: ✅ Fixed and deployed  
**Commit**: 2253d8b  
**Date**: 2026-02-23 04:30 UTC
