# Tournament Management System - Complete Guide

## Overview

This system provides comprehensive tournament management for pool/billiards competitions with:
- Full player profiles (license #, Fargo scores, avatars, Hall of Fame status)
- Tournament creation with custom point structures  
- Single and double elimination bracket generation
- Match score entry with automatic advancement
- Automated rankings calculation
- WPBA/WPA data import capability

## Architecture

### Database Schema
**7 New Tables:**
1. **players** (enhanced) - Full player profiles
2. **tournaments** - Tournament instances
3. **tournament_players** - Registration and results
4. **matches** - Bracket structure and scores
5. **games** - Individual game details
6. **tournament_templates** - Reusable configurations
7. **player_statistics** - Aggregated stats
8. **ranking_history** - Time-series rankings

### API Endpoints

#### Players (prefix: `/api/tournaments/players`)
- `POST /` - Create player
- `GET /` - List all players
- `GET /{player_id}` - Get player details
- `PUT /{player_id}` - Update player
- `DELETE /{player_id}` - Soft delete (set inactive)
- `GET /{player_id}/stats` - Get player statistics

#### Tournaments (prefix: `/api/tournaments`)
- `POST /` - Create tournament
- `GET /` - List tournaments (filterable by status)
- `GET /{tournament_id}` - Get tournament details
- `PUT /{tournament_id}` - Update tournament

#### Player Registration
- `POST /{tournament_id}/players` - Register single player
- `POST /{tournament_id}/players/bulk` - Register multiple players
- `DELETE /{tournament_id}/players/{player_id}` - Unregister player
- `GET /{tournament_id}/players` - List registered players

#### Bracket & Matches
- `POST /{tournament_id}/generate-bracket` - Generate bracket
- `GET /{tournament_id}/matches` - Get all matches
- `PUT /matches/{match_id}/score` - Update match score

#### Rankings
- `GET /rankings/current` - Get current rankings
- `POST /rankings/recalculate` - Recalculate all rankings

#### Templates
- `POST /templates` - Create reusable template
- `GET /templates` - List all templates
- `GET /templates/{template_id}` - Get template details

## Tournament Director Workflow

### 1. Setup Tournament
```json
POST /api/tournaments/
{
  "tournament_name": "Iron City Classic 2026",
  "tournament_date": "2026-03-15",
  "location": "Pittsburgh, PA",
  "elimination_type": "single",
  "max_players": 32,
  "points_structure": {
    "1": 2880,
    "2": 3600,
    "3": 2500,
    "4": 2500,
    "5": 1800,
    "6": 1800,
    "7": 1800,
    "8": 1800
  },
  "created_by": "Director Name",
  "notes": "Race to 7 all rounds"
}
```

**Response:** Returns `tournament_id` (e.g., "T000001")

### 2. Register Players
```json
POST /api/tournaments/{tournament_id}/players
{
  "player_id": "P000001",
  "seed_position": 1
}
```

Repeat for all players. Or use bulk registration:
```json
POST /api/tournaments/{tournament_id}/players/bulk
{
  "player_ids": ["P000001", "P000002", "P000003", "P000004"]
}
```

### 3. Generate Bracket
```json
POST /api/tournaments/{tournament_id}/generate-bracket
{
  "tournament_id": "T000001",
  "race_to": 7,
  "shuffle_seeds": false
}
```

This creates all matches for the tournament based on elimination type.

### 4. Enter Match Scores
As matches complete:
```json
PUT /api/tournaments/matches/{match_id}/score
{
  "operator_score": 7,
  "player2_score": 3,
  "status": "completed"
}
```

The system automatically:
- Determines winner (player who reaches `race_to` first)
- Updates player statistics
- Advances winner to next round match
- Updates tournament progress

### 5. Complete Tournament & Calculate Rankings
After all matches complete:
```json
PUT /api/tournaments/{tournament_id}
{
  "status": "completed"
}
```

Then recalculate rankings:
```json
POST /api/tournaments/rankings/recalculate
```

This aggregates all completed tournament results and updates player rankings.

## Player Profile Fields

```json
{
  "player_id": "P000001",
  "first_name": "Jennifer",
  "last_name": "Barretta",
  "nickname": "9-Ball Jen",
  "email": "player@example.com",
  "phone": "(555) 123-4567",
  "license_number": "WPBA001",
  "avatar_url": "/avatars/barretta.jpg",
  "fargo_score": 720,
  "nationality": "USA",
  "hometown": "Brooklyn",
  "state": "NY",
  "membership_status": "active",
  "hall_of_fame": true,
  "hot_streak_count": 3,
  "total_tournaments_played": 15,
  "total_points": 25000.0,
  "current_rank": 1
}
```

## Point Structure System

Each tournament has a custom `points_structure` JSON object mapping placement to points:

```json
{
  "1": 2880,    // 1st place
  "2": 3600,    // 2nd place
  "3": 2500,    // 3rd place
  "4": 2500,    // 4th place
  "5": 1800,    // 5th-8th place
  ...
}
```

**Key Features:**
- Fully customizable per tournament
- Can be saved as templates for reuse
- No weighting system - points only (as voted)
- Different tournaments can have completely different structures

## Bracket Generation

### Single Elimination
- Calculates bracket size (next power of 2)
- Creates all rounds and matches
- Assigns BYEs if player count < bracket size
- Winners automatically advance to next round

### Double Elimination
- Creates winners bracket (same as single elim)
- Creates losers bracket with feed-ins
- Handles complex losers bracket structure
- Finals includes potential bracket reset

## Rankings Calculation

Rankings are calculated by:
1. Summing all points from completed tournaments
2. Sorting players by total points (descending)
3. Assigning rank positions (1, 2, 3, ...)
4. Saving snapshot to `ranking_history` table

Players must have:
- `membership_status = 'active'`
- `total_points > 0`

## Statistics Tracked

### Per Player:
- Total tournaments played
- Total matches played/won
- Total games played/won
- Win percentages (matches & games)
- Break and runs
- Run outs
- 1st/2nd/3rd place finishes
- Average placement
- Best placement
- Current/longest win streak

### Per Tournament:
- Matches played/won/lost
- Games won/lost
- Final placement
- Points earned

## Testing the API

Run the test suite:
```bash
cd /home/ansible/rankings-bot
python3 test_tournament_api.py
```

This tests:
- Player CRUD operations
- Tournament creation
- Player registration
- Bracket generation
- Match score entry
- Rankings calculation

## Next Steps

### Frontend Components Needed:
1. **Tournament Wizard** - Multi-step tournament creation
2. **Player Management** - Add/edit/search players
3. **Visual Bracket** - Interactive tournament tree
4. **Match Entry** - Quick score entry interface
5. **Rankings Dashboard** - Leaderboard display
6. **Player Profile** - Detailed player view

### WPBA/WPA Integration:
1. **Web Scraper** - Fetch current rankings
2. **Data Mapper** - Convert to our schema
3. **Import Tool** - Bulk import historical data
4. **Sync Scheduler** - Periodic updates

### Mobile App Integration:
Future enhancement for directors to:
- Enter scores from mobile device
- View live bracket updates
- Push notifications for match calls
- QR code player check-in

## Migration & Deployment

### Initial Setup:
```bash
cd /home/ansible/rankings-bot/database
python3 migrate_tournament_management.py
```

This creates:
- ✅ 7 new tables
- ✅ 3 views for common queries
- ✅ 6 triggers for auto-updates
- ✅ 2 default tournament templates
- ✅ Database backup before migration

### Verify Migration:
```sql
psql $DATABASE_URL

-- Check tables created
.tables

-- Check sample data
SELECT * FROM tournament_templates;

-- Check enhanced players table
PRAGMA table_info(players);

-- Check views
SELECT * FROM v_current_rankings LIMIT 5;
```

## API Documentation

Once API is running, full interactive docs available at:
- Swagger UI: `http://localhost:8003/docs`
- ReDoc: `http://localhost:8003/redoc`

## Backup & Restore

### Backup:
```bash
pg_dump $DATABASE_URL > rankings_backup_$(date +%Y%m%d).sql
```

### Restore:
```bash
psql $DATABASE_URL < rankings_backup_YYYYMMDD.sql
```

## Troubleshooting

### API won't start:
```bash
# Check syntax
python3 -m py_compile api/routes/tournaments.py

# Check imports
python3 -c "from api.routes import tournaments"

# Check database
psql $DATABASE_URL "SELECT COUNT(*) FROM tournaments;"
```

### Bracket generation fails:
- Verify at least 2 players registered
- Check players have unique seed positions
- Verify tournament has valid elimination_type

### Rankings not updating:
- Ensure tournament status = 'completed'
- Check tournament_players have final_placement set
- Manually recalculate: `POST /api/tournaments/rankings/recalculate`

## Contact & Support

For issues or questions:
- Check API logs: `tail -f rankings_bot.log`
- Review test output: `python3 test_tournament_api.py`
- Check database: `psql $DATABASE_URL`
