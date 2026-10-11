# Tournament Rankings Integration - Design Options

## Current Status

✅ **Stops Played Column:** Complete and ready for deployment
- Rankings page displays "Stops Played" column
- Backend queries updated to return stops_played field
- Database schema supports the new column

⏳ **Next Phase:** Link tournament results to ranking snapshots

## User Request (Clarified)

> "add all past tournaments rankings data to the tournaments...use existing db data if available...yes just dont scrape new data just use whats in the db right now, if nothing, thats ok for now"

**Interpretation:**
- Display ranking information (rank, points, stops_played) alongside tournament results
- Use only existing data from rankings table (no new scraping)
- Query rankings data for tournament date if available
- OK if some tournaments have no matching ranking data

## Current Data Structure

### Tournament History Table
```
tournament_history
├── tournament_id (PK)
├── name
├── date (tournament_date)
├── location
├── year
├── association
├── champion
├── runner_up
└── tournament_results (FK reference)
    ├── player_name
    ├── placement
    ├── points
    └── fargo_rating_at_scrape
```

### Rankings Table
```
rankings
├── id (PK)
├── player_name
├── ranking_system  (WPBA_Women, WPA_Men, etc.)
├── rank
├── points
├── country
├── snapshot_date
├── license_number
├── fargo_rating
└── stops_played (NEW)
```

## Design Options

### Option A: Store Rankings in tournament_results (Recommended for Simplicity)

**Approach:** Denormalize ranking data into tournament_results table

**Pros:**
- Fast queries (no joins needed)
- Complete history stored permanently
- Tournament view is self-contained
- Works offline (no external rankings lookup)

**Cons:**
- Data duplication
- Rankings become static snapshots (don't update if rankings change)
- Larger table size

**Implementation:**
```sql
ALTER TABLE tournament_results ADD COLUMN IF NOT EXISTS 
  player_rank_on_tournament_date INTEGER,
  player_points_on_tournament_date NUMERIC,
  player_stops_on_tournament_date INTEGER,
  ranking_system_used VARCHAR(50);
```

**Data Population:**
```python
# For each tournament_results record:
# 1. Get rankings for player_name on or near tournament_date
# 2. Store rank, points, stops_played from that ranking snapshot
# 3. Can run as one-time backfill script
```

**Frontend Changes:**
- TournamentHistory.tsx displays new columns from tournament_results
- TournamentCard shows ranking context alongside placement
- Minimal changes to queries

---

### Option B: Query Rankings On-Demand (Recommended for Currency)

**Approach:** Query rankings table when displaying tournaments, match by date proximity

**Pros:**
- No data duplication
- Rankings reflect current state (if data updated)
- Flexible date range matching
- Clean schema

**Cons:**
- Slower queries (requires JOIN + date filtering)
- May not find exact match if ranking snapshots sparse
- More complex query logic

**Implementation:**
```python
# New API endpoint: GET /api/tournaments/{id}/with-rankings
def get_tournament_with_rankings(tournament_id):
    tournament = get_tournament(tournament_id)
    rankings = {}
    
    for result in tournament.results:
        # Find latest rankings on/before tournament date
        ranking = db.query(rankings)\
            .filter_by(player_name=result.player_name)\
            .filter(snapshot_date <= tournament.date)\
            .order_by(snapshot_date.desc())\
            .first()
        rankings[result.player_name] = ranking
    
    return {**tournament, rankings_by_player: rankings}
```

**Frontend Changes:**
- TournamentHistory fetches from new endpoint
- Displays ranking data without changing schema
- Handles missing data gracefully

---

### Option C: Hybrid - Cache with TTL

**Approach:** Store rankings in tournament_results, but regenerate on demand

**Pros:**
- Fast reads (cached)
- Fresh data (can refresh)
- Maintains history

**Cons:**
- Most complex implementation
- Requires background job or manual refresh

**Implementation:**
- Store rankings in tournament_results (like Option A)
- Provide refresh endpoint to update from rankings table
- Call refresh when viewing tournaments or on schedule

---

## Recommendation: **Option A (Denormalization)**

**Rationale:**
1. **User specified:** "use existing db data if available...OK if nothing" — suggests one-time backfill
2. **Performance:** Tournament views are read-heavy; denormalization makes sense
3. **Simplicity:** Minimal schema changes, straightforward data flow
4. **Scope:** Fits "don't scrape new data" requirement perfectly
5. **Frontend:** Simplest implementation (no complex queries)

## Implementation Plan (Option A)

### Step 1: Add Columns to tournament_results

```sql
ALTER TABLE tournament_results 
ADD COLUMN IF NOT EXISTS player_rank_on_tournament_date INTEGER DEFAULT NULL,
ADD COLUMN IF NOT EXISTS player_points_on_tournament_date NUMERIC DEFAULT NULL,
ADD COLUMN IF NOT EXISTS player_stops_on_tournament_date INTEGER DEFAULT NULL,
ADD COLUMN IF NOT EXISTS ranking_system_used VARCHAR(50) DEFAULT NULL;

CREATE INDEX idx_tournament_results_ranking 
ON tournament_results(player_name, player_rank_on_tournament_date);
```

### Step 2: Create Backfill Script

```python
# backfill_tournament_rankings.py
import datetime
from database import get_connection

def backfill_tournament_rankings():
    """Populate ranking data in tournament_results from existing rankings"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get all tournament_results without ranking data
    cursor.execute("""
        SELECT tournament_id, player_name, tournament_results.id
        FROM tournament_results
        WHERE player_rank_on_tournament_date IS NULL
        ORDER BY tournament_id
    """)
    
    results = cursor.fetchall()
    updated = 0
    
    for tournament_id, player_name, result_id in results:
        # Get tournament date
        cursor.execute("SELECT date FROM tournament_history WHERE id = ?", (tournament_id,))
        tournament_date = cursor.fetchone()[0]
        
        # Find rankings on/before tournament date (latest)
        cursor.execute("""
            SELECT rank, points, stops_played, ranking_system
            FROM rankings
            WHERE player_name = ? AND snapshot_date <= ?
            ORDER BY snapshot_date DESC
            LIMIT 1
        """, (player_name, tournament_date))
        
        row = cursor.fetchone()
        if row:
            rank, points, stops, system = row
            cursor.execute("""
                UPDATE tournament_results
                SET player_rank_on_tournament_date = ?,
                    player_points_on_tournament_date = ?,
                    player_stops_on_tournament_date = ?,
                    ranking_system_used = ?
                WHERE id = ?
            """, (rank, points, stops, system, result_id))
            updated += 1
            conn.commit()
    
    print(f"Updated {updated} tournament results with ranking data")
    conn.close()

if __name__ == '__main__':
    backfill_tournament_rankings()
```

### Step 3: Update API Endpoints

```python
# api/routes/tournaments.py
@router.get("/tournaments/{tournament_id}")
def get_tournament_with_rankings(tournament_id: int):
    """Get tournament with historical ranking context"""
    tournament = get_tournament_by_id(tournament_id)
    
    cur = conn.cursor()
    cur.execute("""
        SELECT player_name, placement, points, 
               player_rank_on_tournament_date, 
               player_points_on_tournament_date,
               player_stops_on_tournament_date,
               ranking_system_used
        FROM tournament_results
        WHERE tournament_id = ?
        ORDER BY placement ASC
    """, (tournament_id,))
    
    results = cur.fetchall()
    # Transform to response format
    return {
        **tournament,
        results: results
    }
```

### Step 4: Update Frontend

```typescript
// frontend/src/pages/TournamentHistory.tsx
// Display ranking columns in tournament detail view

// TournamentCard component enhancement:
interface TournamentResult {
  player_name: string
  placement: number
  points: number
  // NEW: ranking context
  player_rank_on_tournament_date?: number
  player_points_on_tournament_date?: number
  player_stops_on_tournament_date?: number
  ranking_system_used?: string
}

// In render:
<td className="text-sm">
  {result.player_rank_on_tournament_date 
    ? `#${result.player_rank_on_tournament_date}` 
    : '—'}
</td>
<td className="text-sm">
  {result.player_stops_on_tournament_date ?? '—'}
</td>
```

## Decision Required

Which approach would you prefer?

1. **Option A (Recommended):** Denormalize rankings into tournament_results
   - Simplest implementation
   - Best for one-time backfill
   - Fastest queries
   - **Next step:** Confirm to proceed with schema migration + backfill script

2. **Option B:** Query rankings on-demand
   - More complex but no duplication
   - Better if rankings data frequently updated
   - **Next step:** Design API endpoint structure

3. **Option C (If both):** Implement hybrid caching
   - Most flexible but complex
   - **Next step:** Design cache invalidation strategy

**My Recommendation:** Proceed with **Option A**. It aligns with user's "use existing data" requirement and minimizes implementation complexity.

Please confirm which option you'd like to proceed with, and I'll implement it immediately.
