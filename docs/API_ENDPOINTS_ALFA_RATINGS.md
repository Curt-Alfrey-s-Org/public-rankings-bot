# Alfa Rating Prediction API Endpoints

## Overview

The Alfa Rating API provides machine learning-powered predictions for pool match outcomes, with comprehensive explainability, anomaly detection, and player rating tracking. All predictions are logged to PostgreSQL for audit trails and model validation.

**Base URL:** `/api/alfa`  
**Authentication:** Optional (some features enhancement)  
**Rate Limit:** 100 requests/minute per IP

---

## Table of Contents

1. [Core Endpoints](#core-endpoints)
2. [Request/Response Models](#requestresponse-models)
3. [Error Handling](#error-handling)
4. [Caching Behavior](#caching-behavior)
5. [Database Integration](#database-integration)
6. [Examples](#examples)
7. [Implementation Notes](#implementation-notes)

---

## Core Endpoints

### 1. POST /api/alfa/predict

**Predict match outcome with explainable factors.**

Computes win probability for a match using logistic regression model, featuring:
- Rating gap analysis
- Table size comfort metrics
- Game format specialization
- Race-to length impact
- Confidence scoring based on player robustness

#### Request

```json
{
  "operator_id": 123,
  "player2_id": 456,
  "race_to": 11,
  "table_size": "9ft",
  "format": "9-ball",
  "location": "silk_city_billiards",
  "match_id": "match_20260216_001"  // optional
}
```

**Parameters:**
- `operator_id` (int, required): Player 1 ID (>0)
- `player2_id` (int, required): Player 2 ID (>0, must differ from operator_id)
- `race_to` (int, required): Race-to value (2-15)
- `table_size` (string, required): One of: `7ft`, `8ft`, `9ft`, `10ft`, `8.5ft`
- `format` (string, required): One of: `9-ball`, `10-ball`, `8-ball`, `mixed`
- `location` (string, required): Venue location code
- `match_id` (string, optional): Match identifier for tracking (auto-generated if omitted)

#### Response

```json
{
  "match_id": "match_20260216_001",
  "predicted_win_prob_p1": 0.65,
  "predicted_win_prob_p2": 0.35,
  "factors": [
    {
      "name": "rating_gap",
      "contribution": 0.15,
      "weight": 0.35,
      "direction": "favors_p1"
    },
    {
      "name": "table_size_comfort",
      "contribution": 0.08,
      "weight": 0.15,
      "direction": "favors_p1"
    },
    {
      "name": "format_specialty",
      "contribution": 0.05,
      "weight": 0.15,
      "direction": "favors_p1"
    },
    {
      "name": "race_length_factor",
      "contribution": 0.02,
      "weight": 0.10,
      "direction": "favors_p1"
    }
  ],
  "confidence": 0.82,
  "predicted_race_length": null,
  "model_version": "alfa_logistic_v1",
  "timestamp": "2026-02-16T10:30:00Z"
}
```

**Response Fields:**
- `match_id`: Match identifier for future reference
- `predicted_win_prob_p1`: Player 1 win probability (0-1)
- `predicted_win_prob_p2`: Player 2 win probability (0-1, always = 1 - prob_p1)
- `factors`: Array of contributing factors with impact scores
- `confidence`: Model confidence level (0-1, based on player robustness)
- `model_version`: Version of prediction model used
- `timestamp`: When prediction was made

**HTTP Status Codes:**
- `200 OK`: Prediction successful
- `400 Bad Request`: Invalid parameters (race_to out of range, invalid table_size, etc.)
- `404 Not Found`: One or both players not in rating system
- `503 Service Unavailable`: Model loading failure

**Example cURL:**
```bash
curl -X POST http://localhost:8000/api/alfa/predict \
  -H "Content-Type: application/json" \
  -d '{
    "operator_id": 123,
    "player2_id": 456,
    "race_to": 11,
    "table_size": "9ft",
    "format": "9-ball",
    "location": "silk_city_billiards"
  }'
```

---

### 2. POST /api/alfa/explain

**Get detailed explanation of a prediction.**

Retrieves stored prediction with full factor breakdown, anomaly context, and calibration metrics (if match was played).

#### Request

```json
{
  "match_id": "match_20260216_001"
}
```

**Parameters:**
- `match_id` (string, required): Match identifier from prediction endpoint

#### Response

```json
{
  "match_id": "match_20260216_001",
  "match_details": {
    "operator_id": 123,
    "player2_id": 456
  },
  "predicted_prob_p1": 0.65,
  "predicted_prob_p2": 0.35,
  "actual_winner_id": 123,
  "actual_result": "win",
  "prediction_error": 0.1225,
  "factors_breakdown": [
    {
      "name": "rating_gap",
      "contribution": 0.15,
      "weight": 0.35,
      "direction": "favors_p1"
    }
  ],
  "anomaly_flags": [
    {
      "flag_name": "winning_weak_only",
      "description": "Player wins primarily against weaker opponents",
      "severity": "medium",
      "severity_score": 0.65,
      "explanation": "Player's win rate drops 45% against rated players"
    }
  ],
  "confidence": 0.82
}
```

**Response Fields:**
- `match_details`: Original match parameters
- `predicted_prob_p1`: Originally predicted probability
- `actual_winner_id`: Winner (null if not yet played)
- `actual_result`: "win"/"loss" (null if not played)
- `prediction_error`: Brier score calibration metric (only if played)
- `factors_breakdown`: Original factors that influenced prediction
- `anomaly_flags`: Any suspicious patterns detected
- `confidence`: Model confidence

**HTTP Status Codes:**
- `200 OK`: Explanation retrieved
- `404 Not Found`: Match prediction not found
- `500 Internal Server Error`: Database error

---

### 3. POST /api/alfa/anomaly/check

**Detect sandbagging and suspicious patterns.**

Analyzes player's entire match history to detect patterns inconsistent with skill:
- Win rate disparity (weak vs. strong opponents)
- Rating gaps vs. actual performance
- Format/location specialization
- Sudden rating changes

#### Request

```json
{
  "player_id": 123
}
```

**Parameters:**
- `player_id` (int, required): Player ID (>0)

#### Response

```json
{
  "player_id": 123,
  "anomaly_score": 0.72,
  "anomaly_level": "suspicious",
  "flags": [
    {
      "flag_name": "winning_weak_only",
      "description": "Player wins primarily against weaker opponents",
      "severity": "high",
      "severity_score": 0.85,
      "explanation": "85% of wins against rated players below 500"
    }
  ],
  "sandbagging_probability": 0.68,
  "games_analyzed": 45,
  "recommendation": "REVIEW: Player shows patterns consistent with skill sandbagging",
  "last_analyzed": "2026-02-16T10:30:00Z"
}
```

**Response Fields:**
- `anomaly_score`: Overall anomaly score (0-1, 0=clean, 1=highly suspicious)
- `anomaly_level`: Categorical level ("clean", "suspicious", "flagged")
- `flags`: Array of specific anomaly indicators
- `sandbagging_probability`: Likelihood of intentional skill hiding (0-1)
- `games_analyzed`: Number of games evaluated
- `recommendation`: Action recommendation for tournament directors
- `last_analyzed`: When analysis was performed

**Anomaly Levels:**
- `clean` (score < 0.3): No concerns detected
- `suspicious` (score 0.3-0.7): Monitor next games, possible pattern
- `flagged` (score > 0.7): Strong indicators, recommend director review

**HTTP Status Codes:**
- `200 OK`: Analysis complete
- `404 Not Found`: Player not in system
- `500 Internal Server Error`: Analysis error

---

### 4. GET /api/alfa/player/{player_id}

**Get player Alfa rating and statistics.**

Retrieves comprehensive player data including current rating, confidence, history, and cold-start progress.

#### Parameters

- `player_id` (int, required, path): Player ID

#### Response

```json
{
  "player_id": 123,
  "player_name": "John Doe",
  "current_rating": 675.5,
  "rating_confidence": 0.92,
  "games_played": 45,
  "anomaly_score": 0.15,
  "rating_history": [
    {
      "date": "2026-02-16",
      "rating": 675.5,
      "confidence": 0.92
    },
    {
      "date": "2026-02-15",
      "rating": 672.1,
      "confidence": 0.91
    }
  ],
  "cold_start_progress": null,
  "last_update": "2026-02-16T10:30:00Z",
  "robustness": 45
}
```

**Response Fields:**
- `current_rating`: Latest Alfa rating
- `rating_confidence`: Confidence in rating (0-1, based on sample size)
- `games_played`: Total games in system
- `rating_history`: Last 30 days of ratings
- `cold_start_progress`: For new players (<20 games), convergence timeline
- `robustness`: Number of validated games (confidence measure)
- `anomaly_score`: Current anomaly score (0-1)

**HTTP Status Codes:**
- `200 OK`: Player data retrieved
- `404 Not Found`: Player not found
- `500 Internal Server Error`: Database error

**Caching:** Results cached for 1 hour

---

### 5. GET /api/alfa/comparison/{operator_id}/{player2_id}

**Compare two players across multiple dimensions.**

Head-to-head analysis including rating differences, match history, tournament results, and predicted matchups.

#### Parameters

- `operator_id` (int, required, path): First player ID
- `player2_id` (int, required, path): Second player ID

#### Response

```json
{
  "comparison": {
    "operator_id": 123,
    "player2_id": 456,
    "operator_name": "John Doe",
    "player2_name": "Jane Smith",
    "fargo_diff": 25.0,
    "alfa_diff": 45.5,
    "head_to_head": {
      "total_matches": 12,
      "operator_wins": 7,
      "player2_wins": 5,
      "win_rate_p1": 0.583
    },
    "tournament_history": {
      "tournaments_together": 3,
      "operator_avg_placement": 2.5,
      "player2_avg_placement": 5.2
    },
    "predicted_matchup_prob_p1": 0.62
  },
  "timestamp": "2026-02-16T10:30:00Z"
}
```

**Response Fields:**
- `fargo_diff`: Fargo rating difference (null if Fargo data unavailable)
- `alfa_diff`: Alfa rating difference
- `head_to_head`: Match history statistics
- `tournament_history`: Tournament appearance data
- `predicted_matchup_prob_p1`: If played 1v1 match, predicted win probability

**HTTP Status Codes:**
- `200 OK`: Comparison retrieved
- `404 Not Found`: One or both players not found
- `500 Internal Server Error`: Database error

---

### 6. GET /api/alfa/health

**System health check.**

Verifies model availability and system readiness.

#### Response

```json
{
  "status": "healthy",
  "models": [
    "logistic_regression",
    "anomaly_detection",
    "cold_start_engine"
  ],
  "timestamp": "2026-02-16T10:30:00Z"
}
```

**HTTP Status Codes:**
- `200 OK`: System healthy
- `503 Service Unavailable`: Model loading issues

---

## Request/Response Models

### Prediction Factor

Explains how a factor influenced prediction:

```typescript
{
  name: string          // "rating_gap", "table_size", etc.
  contribution: number  // -1 to 1, impact on probability
  weight: number       // 0-1, importance of this factor
  direction?: string   // "favors_p1" or "favors_p2"
}
```

### Anomaly Flag

Describes a detected suspicious pattern:

```typescript
{
  flag_name: string        // "winning_weak_only", etc.
  description?: string     // Human-readable explanation
  severity: string         // "low", "medium", "high"
  severity_score: number   // 0-1 numeric severity
  explanation?: string     // Detailed explanation
}
```

### Rating History Entry

Historical rating snapshot:

```typescript
{
  date: string   // ISO format: "2026-02-16"
  rating: number // Alfa rating on that date
  confidence: number // 0-1
}
```

### Cold Start Progress

For new players (< 20 games):

```typescript
{
  games_played: number        // Games so far
  confidence_estimate: number // Current confidence (0-1)
  target_confidence: number   // Target for convergence (0.85)
  games_to_convergence: number // Estimated games needed
}
```

---

## Error Handling

### Standard Error Response

```json
{
  "status_code": 400,
  "detail": "Invalid input: race_to must be between 2 and 15",
  "error_type": "validation_error",
  "timestamp": "2026-02-16T10:30:00Z",
  "validation_errors": [
    {
      "field": "race_to",
      "message": "must be >= 2 and <= 15"
    }
  ]
}
```

### Common Errors

| Status | Reason | Solution |
|--------|--------|----------|
| 400 | Invalid input | Check parameter ranges (race_to 2-15, valid table sizes) |
| 404 | Player/match not found | Verify player ID exists in rating system |
| 503 | Model loading failed | Server restarting or configuration issue |
| 500 | Database connection | Retry after 5-10 seconds |

### Error Types

- `validation_error`: Input validation failed (4xx)
- `not_found_error`: Resource not found (404)
- `model_error`: ML model unavailable (503)
- `database_error`: Database connection issue (500)

---

## Caching Behavior

### Cached Endpoints

| Endpoint | TTL | Key Pattern |
|----------|-----|-------------|
| POST /predict | 5 min | `predict_{p1}_{p2}_{race_to}` |
| GET /player/{id} | 1 hour | `player_{id}` |

### Cache Invalidation

- **Manual:** Delete player cache when rating updates occur
- **Automatic:** TTL expiration
- **Health:** All caches cleared on model reload

### Backend Cache

Cache is in-memory (SimpleCache class). For production distributed systems, consider:
- Redis backend (drop-in replacement)
- Memcached integration
- Database result caching

---

## Database Integration

### Tables Used

#### alfa_player_ratings
Stores player rating snapshots:
- `player_id`: Player identifier
- `rating`: Alfa rating value
- `robustness`: Game count (confidence measure)
- `rating_confidence`: 0-1 confidence score
- `updated_at`: Last update timestamp

#### alfa_match_predictions
Logs all predictions:
- `match_id`: Unique match identifier
- `operator_id, player2_id`: Players involved
- `predicted_win_prob_p1`: Probability prediction
- `prediction_confidence`: Model confidence
- `actual_winner_id`: Filled when match completes
- `brier_score`: Calibration metric (after match)

#### alfa_prediction_factors
Stores factor breakdowns (one per factor per match):
- `match_id`: Link to prediction
- `factor_name`: Factor type
- `contribution`: Impact on probability
- `weight`: Importance (0-1)

#### alfa_anomaly_flags
Anomaly detections (one per flag per player):
- `player_id`: Player with anomaly
- `flag_type`: Type of anomaly
- `severity`: low/medium/high
- `description`: Details
- `resolved_at`: When addressed (null = active)

### Audit Trail

All predictions are logged for:
- Model validation (track Brier scores)
- Accountability (director review)
- Performance monitoring
- System learning

### Retention

- **Predictions:** Indefinite for audit
- **Ratings:** Keep last 30 days active, archive older
- **Anomalies:** Keep 90 days, then mark resolved

---

## Examples

### Example 1: Predict Match with Cache Hit

```bash
# First call (cache miss, 750ms)
curl -X POST http://localhost:8000/api/alfa/predict \
  -H "Content-Type: application/json" \
  -d '{
    "operator_id": 123,
    "player2_id": 456,
    "race_to": 11,
    "table_size": "9ft",
    "format": "9-ball",
    "location": "silk_city"
  }'

# Response: 200 OK with prediction

# Second call within 5 minutes (cache hit, <10ms)
curl -X POST http://localhost:8000/api/alfa/predict \
  -H "Content-Type: application/json" \
  -d '{
    "operator_id": 123,
    "player2_id": 456,
    "race_to": 11,
    "table_size": "9ft",
    "format": "9-ball",
    "location": "silk_city"
  }'

# Response: Same result from cache
```

### Example 2: Detect Sandbagging

```bash
curl -X POST http://localhost:8000/api/alfa/anomaly/check \
  -H "Content-Type: application/json" \
  -d '{"player_id": 789}'

# Response: High anomaly score with specific flags
```

### Example 3: Compare Tournament Rivals

```bash
curl -X GET http://localhost:8000/api/alfa/comparison/123/456

# Response: H2H history, rating gap, tournament appearance data
```

---

## Implementation Notes

### Cold Start Handling

New players (< 20 games) have lower confidence. Use `cold_start_progress` field to communicate:
- How many more games needed
- Current convergence rate
- Expected final rating range (±30 points)

### Confidence Interpretation

- `0.90-1.00`: High confidence (50+ games, stable rating)
- `0.70-0.90`: Good confidence (20-50 games)
- `0.50-0.70`: Fair confidence (5-20 games)
- `<0.50`: Low confidence (< 5 games, use with caution)

### Factor Weights

Factor weights sum to ~0.75 (allowing ~0.25 for other unmeasured factors):
- Rating gap: 0.35 (dominant)
- Table size + Format + Race: 0.40 combined
- Other (field conditions, psychology): ~0.25

### Probability Interpretation

- `0.5`: Even match (equal skill)
- `0.65`: Moderate advantage (expected to win ~2-1)
- `0.75`: Strong advantage (expected to win 3-1)
- `0.9+`: Dominant (rare, only for large skill gaps)

### Rate Limiting

All endpoints subject to:
- **Global:** 100 requests/minute per IP
- **Per endpoint:** 1000 requests/hour
- **Burst:** Max 5 concurrent requests

### Monitoring

Log all predictions with:
- Player IDs, timestamp
- Prediction values and confidence
- Anomaly flags triggered
- Brier score (if match result known)

Use for:
- Model performance tracking
- Anomaly detection validation
- System audit trail

