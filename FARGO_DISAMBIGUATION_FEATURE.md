# Fargo Player Disambiguation Feature

**Date:** 2026-02-17  
**Status:** ✅ IMPLEMENTED & DEPLOYED

## Problem Solved

When multiple players have the same name (e.g., two "John Browns") in the Fargo database, the system needs a way to identify which player corresponds to which user account. Without disambiguation, users might see incorrect Fargo ratings in their stats.

## Solution Overview

Implemented a complete Fargo player disambiguation flow:
1. **Search Multiple Players**: FairMatch scraper now detects and returns ALL matching players
2. **User Selection**: Modal displays all matches with rating and location info
3. **Persistent Mapping**: User's selection is saved to `user_player_links` table
4. **Automatic Application**: Future queries use the mapped player automatically

## Architecture

### Backend Components

**1. FairMatch Scraper Enhancement**  
   File: `/api/services/fairmatch_scraper.py`
   - Added `search_players_list()` function
   - Returns list of matching players: `[{name, rating, info}, ...]`
   - Extracts multiple results from search results table
   - Falls back to HTML parsing if table extraction fails

**2. API Endpoint**  
   File: `/api/routes/fargo.py`
   - New endpoint: `GET /api/fargo/search?name={name}`
   - Requires authentication
   - Returns: `{ players: [{name, rating, info}, ...] }`
   - Timeout: 30 seconds (allows Selenium scraping)

### Frontend Components

**3. API Client**  
   File: `/frontend/src/api/fargo.ts`
   - `fargoApi.searchPlayers(name)` → returns `FargoPlayer[]`
   - Interface: `{ name: string, rating: number, info: string }`

**4. Disambiguation Modal**  
   File: `/frontend/src/components/PlayerDisambiguationModal.tsx`
   - Displays list of matching players
   - Shows name, rating (bold, large font), and additional info
   - Radio button selection
   - "Select & Save" button saves mapping to `user_player_links`
   - Invalidates relevant query caches on save

**5. Dashboard Integration**  
   File: `/frontend/src/pages/Dashboard.tsx`
   - **"Link Fargo" button** in My Ranking Snapshot card (top right)
   - Triggers `fargoApi.searchPlayers()` mutation
   - Opens modal when results found
   - Toast notifications for success/errors

## User Flow

### First Time Linking

1. User logs in and navigates to Dashboard (Home)
2. In "My Stats" section → "My Ranking Snapshot" card, click **"Link Fargo"** button
3. System searches FairMatch for all players matching the username
4. **Modal appears** showing all matching players:
   ```
   Multiple Players Found
   Found 3 players matching "John Brown". Select the correct one:
   
   ○ John Brown  755
     Phoenix, AZ • WPBA Member
   
   ○ John Brown  622
     Chicago, IL • Amateur
   
   ● John Brown  810
     Dallas, TX • WPA Men
   
   [Cancel]  [Select & Save]
   ```
5. User selects the correct player (matches location/org/rating)
6. Clicks "Select & Save"
7. Mapping saved to database: `user_player_links(user_id, player_name, ...)`
8. Success toast: "Linked to Fargo player: John Brown (810)"
9. Dashboard refreshes with correct Fargo rating

### After Linking

- Future Dashboard loads automatically use mapped player
- `/api/player-performance/me` returns mapped player name
- All "My Stats" queries use `effectivePlayerName` (mapped name or username)
- Mapping persists across sessions and reboots

### Changing Mapping

- Click "Link Fargo" button again
- Select different player
- New mapping replaces old (unique constraint on `user_id`)

## Database Schema

**Table: `user_player_links`** (created in migration 016)

| Column          | Type      | Description                          |
|-----------------|-----------|--------------------------------------|
| id              | SERIAL    | Primary key                          |
| user_id         | INTEGER   | FK to users.id (UNIQUE)              |
| player_id       | VARCHAR   | Internal UUID (optional)             |
| player_name     | VARCHAR   | Fargo player name (from search)      |
| license_number  | VARCHAR   | Pro license (optional, future use)   |
| created_at      | TIMESTAMPTZ | When link was created              |
| updated_at      | TIMESTAMPTZ | When link was last updated         |

**Indexes:**
- `UNIQUE(user_id)` - one mapping per user
- `INDEX(player_name)` - fast lookups by player name
- `INDEX(player_id)` - fast lookups by internal ID

## API Reference

### Search for Players

```
GET /api/fargo/search?name={playerName}
Authentication: Required (Bearer token)
```

**Response (Success):**
```json
{
  "players": [
    {"name": "John Brown", "rating": 755, "info": "Phoenix, AZ"},
    {"name": "John Brown", "rating": 622, "info": "Chicago, IL"}
  ]
}
```

**Response (No Results):**
```
404 Not Found
{"detail": "No players found for 'John Brown'"}
```

**Response (Chrome Not Available):**
```
503 Service Unavailable
{"detail": "Fargo search requires Chrome/Chromium. Install Chromium to use this feature."}
```

### Get My Player Info

```
GET /api/player-performance/me
Authentication: Required
```

**Response:**
```json
{
  "player_name": "John Brown",
  "source": "mapping"  // or "username" if no mapping
}
```

## Files Modified/Created

### Backend
- ✅ `/api/services/fairmatch_scraper.py` - Added `search_players_list()`
- ✅ `/api/routes/fargo.py` - Added `/api/fargo/search` endpoint
- ✅ `/api/routes/player_performance.py` - Already had `/me` endpoint (previous work)
- ✅ `/api/routes/users.py` - Already had player link endpoints (previous work)
- ✅ `/database/__init__.py` - Already created `user_player_links` table (previous work)

### Frontend
- ✅ `/frontend/src/api/fargo.ts` - NEW: Fargo API client
- ✅ `/frontend/src/components/PlayerDisambiguationModal.tsx` - NEW: Disambiguation modal
- ✅ `/frontend/src/pages/Dashboard.tsx` - Added "Link Fargo" button and modal integration

### Migrations
- ✅ Migration 016: `user_player_links` table (already applied)

## Dependencies

**Required:**
- Chrome/Chromium must be installed on server for FairMatch scraping
- Selenium Python package (already installed)
- Persistent Chrome driver (already implemented)

**Fallback:**
- If Chrome unavailable, API returns 503 with error message
- User can still manually create mappings via Settings → Admin (if admin/super_admin)

## Testing

### Manual Testing Steps

1. **Test Search (Single Result):**
   - Log in as user with unique name
   - Click "Link Fargo" button
   - Verify modal shows 1 player
   - Save and verify mapping works

2. **Test Search (Multiple Results):**
   - Log in as user with common name (e.g., "John Smith")
   - Click "Link Fargo" button
   - Verify modal shows multiple players
   - Select one → save
   - Verify My Stats uses correct player

3. **Test Persistence:**
   - Link player
   - Log out and log back in
   - Verify My Stats still uses linked player

4. **Test Change Mapping:**
   - Click "Link Fargo" again
   - Select different player → save
   - Verify new mapping replaces old

5. **Test Chrome Unavailable:**
   - Stop Chrome if running
   - Click "Link Fargo"
   - Verify 503 error toast appears

### Automated Testing

Selenium/Chrome scraping is complex to test. Consider:
- Unit tests with mocked `search_players_list()` responses
- Integration tests that call `/api/fargo/search` with mock scraper

**Example test (pseudo-code):**
```python
def test_fargo_search_returns_multiple_players(client, mock_scraper):
    mock_scraper.return_value = ([
        {"name": "John Brown", "rating": 755, "info": "Phoenix, AZ"},
        {"name": "John Brown", "rating": 622, "info": "Chicago, IL"}
    ], None)
    
    response = client.get("/api/fargo/search?name=John Brown", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["players"]) == 2
```

## Future Enhancements

**1. Auto-Linking on Registration**
- When user registers, automatically search Fargo and link if only 1 match

**2. License Number Extraction**
- Parse license number from `player.info` and save to `license_number` column
- Use license for more accurate matching

**3. Fargo Profile Deep Link**
- Add link to player's full Fargo profile on fairmatch.fargorate.com
- Click name in modal to open Fargo profile in new tab

**4. Location/Org Filtering**
- Add location filter to search: "Show players near me"
- Filter by organization (WPBA, WPA, APA, etc.)

**5. Admin Override**
- Allow admins to create/edit mappings for other users
- Bulk import mappings from CSV

**6. Confidence Score**
- Show confidence score based on:
  - Username similarity to player name
  - Location match (if user provided)
  - Historical tournament participation

## Troubleshooting

### "Link Fargo" Button Not Appearing
- Check if user is logged in (`currentPlayerName` must exist)
- Verify frontend built and deployed correctly

### Modal Shows No Players / 404
- Player may not exist in Fargo database
- Try searching with different name format (First Last vs Last, First)
- Use Settings → Admin → Player link mapping to manually create link

### 503 Error: Chrome Not Available
- Install Chrome/Chromium on server: `sudo apt-get install chromium-browser`
- Check Chrome path in environment: `CHROME_PATH=/usr/bin/chromium-browser`
- Verify Selenium can find Chrome: `python scripts/test_fairmatch_lookup.py "Test Player"`

### Mapping Not Persisting
- Check database: `SELECT * FROM user_player_links WHERE user_id = X;`
- Verify API logs for errors: `sudo journalctl -u rankings-bot-api -n 100 | grep player-links`
- Check migration 016 applied: `SELECT version_num FROM alembic_version;` should show "016"

### My Stats Still Wrong After Linking
- Hard refresh browser (Ctrl+Shift+R) to clear cache
- Check `/api/player-performance/me` returns correct `player_name`
- Verify mapping exists in database

## Deployment Checklist

✅ Database migration 016 applied (`user_player_links` table exists)  
✅ Backend changes deployed (fairmatch_scraper.py, fargo.py)  
✅ Frontend rebuilt (`npm run build`)  
✅ API restarted (`sudo systemctl restart rankings-bot-api`)  
✅ No TypeScript/Python errors  
✅ Chrome/Chromium installed on server  

## Summary

This feature solves the "multiple John Browns" problem by:
1. **Detecting** all matching Fargo players during search
2. **Displaying** them to the user with disambiguating info (rating, location)
3. **Saving** the user's selection to the database
4. **Applying** the mapping automatically to all future queries

Users can now confidently see their correct Fargo rating in My Stats, even when sharing a name with other players.

**User Impact:**
- ✅ Accurate Fargo ratings in My Stats
- ✅ One-click linking from Dashboard
- ✅ Persistent across sessions
- ✅ Easy to change if needed

**Technical Debt: None** - Clean implementation following existing patterns for modals, API clients, and database mappings.

