# Head-to-Head Match History

## Overview

The Head-to-Head feature displays detailed match history between two players, including tournament information, scores, and venues.

## API Endpoint

**GET** `/api/players/{player_id}/head-to-head/{opponent_id}`

Returns comprehensive comparison data including historical match records.

### Response Structure

```json
{
  "operator": {
    "id": "Alice Smith",
    "name": "Alice Smith",
    "rank": 1,
    "fargo_rating": 720,
    ...
  },
  "player2": {
    "id": "Bob Jones",
    "name": "Bob Jones",
    "rank": 2,
    "fargo_rating": 710,
    ...
  },
  "head_to_head": {
    "direct_wins_p1": 2,
    "direct_losses_p1": 1,
    "common_opponents": [],
    "matches": [
      {
        "id": 123,
        "tournament_id": "2025-us-open",
        "tournament_name": "US Open 2025",
        "date": "2025-03-15",
        "location": "Las Vegas, NV",
        "year": 2025,
        "round": 3,
        "operator_name": "Alice Smith",
        "player2_name": "Bob Jones",
        "operator_score": 9,
        "player2_score": 7,
        "winner": "Alice Smith",
        "notes": "Semi-final match"
      }
    ]
  }
}
```

## Database Schema

### Required Tables

#### tournament_history
Stores tournament metadata:
- **tournament_id** (VARCHAR, PRIMARY KEY): Unique tournament identifier
- **name** (VARCHAR): Tournament name
- **year** (INTEGER): Tournament year
- **date** (VARCHAR): Tournament date
- **location** (VARCHAR): Venue/city (nullable)
- **association** (VARCHAR): WPBA, WPA, etc.
- **championship** (VARCHAR): Championship type
- **status** (VARCHAR): completed, ongoing, cancelled

#### tournament_history_matches
Stores individual match results:
- **id** (SERIAL, PRIMARY KEY): Match ID
- **tournament_id** (VARCHAR, FK): References tournament_history
- **round_num** (INTEGER): Round number (nullable)
- **match_num** (INTEGER): Match number within round (nullable)
- **operator_name** (VARCHAR): First player name
- **player2_name** (VARCHAR): Second player name
- **operator_score** (INTEGER): Player 1 score (nullable)
- **player2_score** (INTEGER): Player 2 score (nullable)
- **winner_name** (VARCHAR): Name of winner
- **notes** (TEXT): Additional match notes (nullable)

## Data Requirements

### Required Fields
- `tournament_id`: Must be unique across all tournaments
- `name`: Tournament name for display
- `year`: Used for chronological sorting
- `operator_name`, `player2_name`: Must match player names in rankings table
- `winner_name`: Should match one of operator_name or player2_name

### Optional Fields with Fallbacks
- **location**: Falls back to `"Unknown location"` if NULL
- **date**: Can be NULL; will display year only
- **round_num**: Can be NULL; won't display round info
- **operator_score**, **player2_score**: Can be NULL; displays `?` in UI
- **notes**: Can be NULL; won't display additional info

## Frontend Components

### ComparisonStats Component
Located at: `/frontend/src/features/head-to-head/components/ComparisonStats.tsx`

Displays:
1. **Summary section**: Win/loss record
2. **Match history list**: Individual matches with:
   - Tournament name
   - Date and location
   - Round (if available)
   - Score
   - Winner highlight (blue for operator, gray for player2)
   - Additional notes (if available)

### Visual Indicators
- **Border color**: Blue (sky-400) for operator wins, gray (slate-600) for player2 wins
- **Score formatting**: Handles null scores by displaying `?`
- **Empty state**: Shows "No direct match history found" message

## Implementation Notes

### Match Counting Logic
The backend counts direct wins/losses for operator:
- Queries all matches where either player appears
- Counts matches where `winner_name = operator_name` as wins
- Counts matches where `winner_name = player2_name` as losses
- Handles player order independence (player can be operator or player2 in match record)

### Match Ordering
Matches are ordered by:
1. Year (descending)
2. Date (descending)
3. Round number (descending)

This ensures most recent matches appear first.

### Score Display Logic
Frontend handles player order:
- Determines which player is operator in the match record
- Swaps scores if necessary to always show requesting player first
- Example: If Bob Jones is operator in DB but Alice is operator in UI, scores are swapped

## Testing

See `/tests/test_head_to_head.py` for comprehensive test suite:
- ✅ Basic comparison data
- ✅ Match history inclusion
- ✅ Location fallback for NULL values
- ✅ Match ordering verification
- ✅ Win/loss calculation accuracy
- ✅ Empty match list handling
- ✅ Player not found (404)
- ✅ Database unavailable (503)

### Running Tests

```bash
# From Rankings-Bot directory
pytest tests/test_head_to_head.py -v

# Or run all tests
pytest tests/ -v
```

## Future Enhancements

Potential improvements:
1. Filter matches by year/tournament type
2. Add pagination for players with extensive history
3. Include match statistics (average score, win rate by venue)
4. Display common opponent records
5. Add match video/highlight links
6. Support for doubles matches

## Troubleshooting

### No matches showing
- Verify `tournament_history` and `tournament_history_matches` tables exist
- Check player names match exactly (case-sensitive)
- Ensure `winner_name` is properly set in match records

### Location showing "Unknown location"
- This is expected behavior when `location` is NULL in database
- Update tournament records with location data to improve display

### Incorrect win/loss counts
- Verify `winner_name` matches player names exactly
- Check for duplicate match records
- Ensure match queries include both player orders (operator/player2 swaps)
