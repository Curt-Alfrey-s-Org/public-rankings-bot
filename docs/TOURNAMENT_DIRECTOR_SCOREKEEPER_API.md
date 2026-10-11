# Tournament Director & Score Keeper API

This document outlines the API endpoints for tournament management, forfeit/DQ handling, and score keeper functionality.

**See also:** End-to-end tournament lifecycle (formats, registration, brackets, scoring, points, rankings) — [BILLIARDS_TOURNAMENT_LIFECYCLE.md](BILLIARDS_TOURNAMENT_LIFECYCLE.md). Production 4-step wizard and API sequence — [TOURNAMENT_WIZARD_VISUAL_OVERVIEW.md](TOURNAMENT_WIZARD_VISUAL_OVERVIEW.md). Test Center verification — [WPBA_TEST_CENTER_E2E.md](WPBA_TEST_CENTER_E2E.md).

**Base URL:** `/api/tournaments`

**Authentication:** All endpoints require JWT Bearer token with appropriate role.

---

## Role-Based Access Control

- **director**: Create/manage tournaments and matches, assign score keepers, enter scores
- **score_keeper**: View assigned matches, enter match scores, view timer state
- **admin**, **super_admin**: Full access

---

## Tour nament Configuration Endpoints

### Create Tournament
**POST** `/`

Creates a new tournament with optional timer configuration.

**Request:**
```json
{
  "tournament_name": "Q-School 2024",
  "tournament_date": "2024-09-15",
  "location": "Las Vegas, NV",
  "elimination_type": "single",
  "max_players": 32,
  "game_type": "9-ball",
  "tables_available": 8,
  "match_time_limit_minutes": 45,
  "shot_clock_seconds": 30,
  "points_structure": {
    "1": 2880,
    "2": 3600,
    "3": 2500,
    "4": 2500
  },
  "notes": "Optional tournament notes"
}
```

**Response:**
```json
{
  "tournament_id": "T000001",
  "tournament_name": "Q-School 2024",
  "status": "setup",
  "match_time_limit_minutes": 45,
  "shot_clock_seconds": 30,
  "created_at": "2024-09-01T10:00:00"
}
```

**Authorization:** director, admin, super_admin

---

### Update Tournament
**PUT** `/{tournament_id}`

Updates tournament details including timer configuration.

**Request:**
```json
{
  "tournament_name": "Q-School 2024 - Final",
  "status": "in_progress",
  "match_time_limit_minutes": 50,
  "shot_clock_seconds": 35
}
```

**Response:** Updated TournamentResponse

**Authorization:** director, admin, super_admin

---

## Match Management Endpoints

### Get All Matches
**GET** `/{tournament_id}/matches`

Retrieves all matches for a tournament.

**Response:**
```json
[
  {
    "match_id": "M000001",
    "tournament_id": "T000001",
    "round_number": 1,
    "match_number": 1,
    "bracket_type": "winners",
    "operator_id": "P000001",
    "player2_id": "P000002",
    "operator_name": "John Doe",
    "player2_name": "Jane Smith",
    "operator_score": 0,
    "player2_score": 0,
    "status": "pending",
    "race_to": 7,
    "table_number": 1,
    "is_forfeit": false,
    "forfeit_reason": null,
    "forfeit_notes": null,
    "scheduled_time": "2024-09-15T09:00:00",
    "completed_at": null
  }
]
```

---

### Get Match Timer State
**GET** `/{tournament_id}/matches/{match_id}/timer-state`

Gets match information needed for timer/score entry UI, including tournament timer configuration.

**Response:**
```json
{
  "match_id": "M000001",
  "tournament_id": "T000001",
  "round_number": 1,
  "match_number": 1,
  "operator_id": "P000001",
  "player2_id": "P000002",
  "operator_name": "John Doe",
  "player2_name": "Jane Smith",
  "operator_score": 3,
  "player2_score": 2,
  "status": "in_progress",
  "started_at": "2024-09-15T09:05:00",
  "race_to": 7,
  "table_number": 1,
  "match_time_limit_minutes": 45,
  "shot_clock_seconds": 30
}
```

**Authorization:** director, score_keeper, admin, super_admin

---

### Update Match
**PATCH** `/matches/{match_id}`

Updates match fields like table assignment, scheduled time, or notes.

**Request:**
```json
{
  "table_number": 3,
  "scheduled_time": "2024-09-15T10:00:00",
  "notes": "Delayed due to previous match running long",
  "status": "in_progress",
  "started_at": "2024-09-15T09:55:00"
}
```

**Response:**
```json
{
  "message": "Match updated",
  "match_id": "M000001"
}
```

**Authorization:** director, admin, super_admin

---

### Update Match Score
**PUT** `/matches/{match_id}/score`

Submits final match score and determines winner.

**Request:**
```json
{
  "operator_score": 7,
  "player2_score": 4,
  "status": "completed"
}
```

**Response:**
```json
{
  "message": "Match score updated successfully",
  "match_id": "M000001"
}
```

**Authorization:** Any authenticated user (director, score_keeper, admin, super_admin)

---

## Forfeit/Disqualification Endpoints

### Forfeit Match
**PUT** `/matches/{match_id}/forfeit`

Marks a match as forfeit, immediately sets winner, updates stats, and advances winner to next round.

**Request:**
```json
{
  "winner_id": "P000001",
  "reason": "player_no_show",
  "notes": "Player failed to arrive at scheduled time"
}
```

**Forfeit Reasons (enum):**
- `player_no_show` - Player did not appear
- `retired` - Player retired from tournament
- `injured` - Player injured and cannot continue
- `disqualified` - Player disqualified for rules violation
- `rules_violation` - Other rules violation
- `unsportsmanlike_conduct` - Unsportsmanlike conduct
- `other` - Other reason

**Response:**
```json
{
  "message": "Match marked as forfeit",
  "match": {
    "match_id": "M000001",
    "tournament_id": "T000001",
    "winner_id": "P000001",
    "loser_id": "P000002",
    "status": "forfeit",
    "is_forfeit": true,
    "forfeit_reason": "player_no_show",
    "forfeit_notes": "Player failed to arrive at scheduled time",
    "completed_at": "2024-09-15T09:15:00"
  }
}
```

**Note:** 
- Automatically sets winner_id and loser_id
- Updates tournament_players statistics
- Advances winner to next round match
- No score is recorded (both remain 0)

**Authorization:** director, admin, super_admin

---

## Score Keeper Endpoints

### Get Score Keeper's Assigned Matches
**GET** `/{tournament_id}/score-keeper/matches`

Returns matches assigned to the current score keeper based on score_keeper_assignments table. If the score keeper is assigned to a specific table, only matches on that table are returned. If assigned to a round, only matches in that round are returned. Otherwise, all tournament matches are returned.

**Response:**
```json
[
  {
    "match_id": "M000001",
    "tournament_id": "T000001",
    "round_number": 1,
    "match_number": 1,
    "operator_id": "P000001",
    "player2_id": "P000002",
    "operator_name": "John Doe",
    "player2_name": "Jane Smith",
    "operator_score": 0,
    "player2_score": 0,
    "status": "pending",
    "race_to": 7,
    "table_number": 1,
    "scheduled_time": "2024-09-15T09:00:00"
  }
]
```

**Authorization:** director, score_keeper, admin, super_admin

---

### Get Matches by Table
**GET** `/{tournament_id}/matches/table/{table_number}`

Returns all matches assigned to a specific table.

**URL Parameters:**
- `table_number` (integer) - Table number

**Response:**
```json
[
  {
    "match_id": "M000001",
    "tournament_id": "T000001",
    "round_number": 1,
    "match_number": 1,
    "operator_name": "John Doe",
    "player2_name": "Jane Smith",
    "status": "pending",
    "table_number": 1,
    "scheduled_time": "2024-09-15T09:00:00"
  },
  {
    "match_id": "M000002",
    "tournament_id": "T000001",
    "round_number": 1,
    "match_number": 3,
    "operator_name": "Bob Johnson",
    "player2_name": "Alice Williams",
    "status": "pending",
    "table_number": 1,
    "scheduled_time": "2024-09-15T10:30:00"
  }
]
```

**Authorization:** director, score_keeper, admin, super_admin

---

## Database Schema Changes

### tournaments table
New columns:
- `match_time_limit_minutes` (INTEGER, nullable) - Match time limit in minutes
- `shot_clock_seconds` (INTEGER, nullable) - Shot clock duration in seconds

### matches table
New columns:
- `is_forfeit` (INTEGER, default 0) - Flag indicating match is forfeit/DQ
- `forfeit_reason` (VARCHAR(64), nullable) - Reason for forfeit (enum value)
- `forfeit_notes` (TEXT, nullable) - Additional notes about forfeit

### score_keeper_assignments table (NEW)
```sql
CREATE TABLE score_keeper_assignments (
  id SERIAL PRIMARY KEY,
  assignment_id VARCHAR(64) UNIQUE NOT NULL,
  tournament_id VARCHAR(32) NOT NULL REFERENCES tournaments(tournament_id),
  user_id VARCHAR(255) NOT NULL,
  table_number INTEGER,
  round_number INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Example Workflows

### Workflow 1: Normal Match Score Entry
```
1. Score keeper queries GET /{tournament_id}/score-keeper/matches
2. Score keeper views assigned match with GET /{tournament_id}/matches/{match_id}/timer-state
3. Score keeper submits scores with PUT /matches/{match_id}/score
4. Match is marked completed, winner advanced to next round
```

### Workflow 2: Player No-Shows
```
1. Director sees match scheduled time has passed
2. Director calls PUT /matches/{match_id}/forfeit with reason="player_no_show"
3. Forfeit is recorded, winner automatically advanced
4. Tournament continues with winner in next match
```

### Workflow 3: Disqualification Mid-Tournament
```
1. Director calls PUT /matches/{match_id}/forfeit with reason="disqualified"
2. Opponent is declared winner, advanced to next round
3. Disqualified player remains in tournament bracket but no more matches
```

---

## Error Responses

### 404 Not Found
```json
{
  "detail": "Match M000001 not found"
}
```

### 403 Forbidden
```json
{
  "detail": "Score keeper only"
}
```

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

---

## Migration Instructions

To apply the database changes:

1. Run Alembic migration 011 to add forfeit/timer columns
2. Run Alembic migration 012 to create score_keeper_assignments table
3. Restart the API service

```bash
cd /home/ansible/rankings-bot/Rankings-Bot
alembic upgrade head
```

---

## Notes

- Forfeit matches automatically set winner and loser, update statistics, and advance the winner
- Score keeper role is controlled by the JWT token's `role` claim
- Score keepers are assigned to tables or rounds via the `score_keeper_assignments` table
- Timer configuration is optional per tournament
- All timestamps are in UTC ISO format
