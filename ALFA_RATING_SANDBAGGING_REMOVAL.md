# Alfa Rating System Update - Sandbagging Detection Removal

**Date:** February 17, 2026  
**Status:** ✅ Complete  
**Impact:** Breaking change for sandbagging detection features

---

## Executive Summary

Removed all sandbagging detection logic from the Alfa Rating system. Implemented Model A (Conservative) weighting that treats WPA/WPBA tournament variance as normal competitive variance rather than suspicious behavior.

**Key Principle:**  
WPA/WPBA tournaments are professional straight-up competition without handicapping. A high Fargo player finishing poorly in a single tournament is experiencing normal competitive variance, not sandbagging. Sandbagging detection is only applicable to handicapped league play (APA, BCA, etc.).

---

## Changes Implemented

### 1. Core Rating Engine (`api/services/alfa_engine.py`)

**Removed:**
- `_compute_sandbagger_score()` function
- `can_access_sandbagger_data()` function  
- Premium tier checks for sandbagging data
- All sandbagging score calculations

**Added:**
- Model A (Conservative) weighting implementation
- Sustained pattern analysis across 10+ tournaments
- Tournament strength multipliers (regional 0.8x, major 1.3x, elite 1.5x)
- Time decay support for recent tournament weighting
- Maximum ±15 point deviation constraint from Fargo

**New Calculation:**
```
Alfa = (Fargo × 85%) + ((Fargo + pattern_adj) × 12%) + ((Fargo + current_adj) × 3%)
```

Where:
- Pattern adjustment: Sustained deviation across 10+ tournaments (±10 max)
- Current adjustment: Single tournament impact (±5 max)
- Total deviation constrained to ±15 from Fargo

---

### 2. Constants Configuration (`api/services/alfa_constants.py`)

**Created new file with:**
- Model A weighting constants (85% / 12% / 3%)
- Tournament strength multipliers
- Pattern analysis parameters
- Deviation constraints
- Validation bounds
- Historical documentation about sandbagging removal

**Key Constants:**
```python
ALFA_BASE_WEIGHT = 0.85          # Fargo is primary
ALFA_PATTERN_WEIGHT = 0.12       # Sustained pattern matters
ALFA_CURRENT_WEIGHT = 0.03       # Single event minimal
ALFA_MAX_DEVIATION = 15.0        # ±15 constraint
MIN_TOURNAMENTS_FOR_PATTERN = 3  # Require 3+ tournaments
PATTERN_WINDOW_TOURNAMENTS = 10  # Analyze last 10 events
```

---

### 3. API Routes Updated

#### `api/routes/alfa.py`

**Removed:**
- `_strip_sandbagger()` helper
- `_strip_sandbagger_from_list()` helper  
- `can_access_sandbagger_data()` calls
- Premium tier checking logic
- Sandbagging fields from response models

**Updated Response Models:**
- `AlfaRatingItem`: Removed `sandbagger_score`, `sandbagger_flags`
- `AlfaPlayerResponse`: Removed `sandbagger_score`, `sandbagger_flags`  
- `AlfaSummaryResponse`: Removed `sandbagger_flagged_count`

**Added Fields:**
- `deviation_from_fargo`: Shows how much Alfa differs from Fargo (±15 max)
- `tournaments_analyzed`: Number of tournaments used in pattern calculation

---

#### `api/routes/alfa_ratings.py`

**Removed:**
- `/api/alfa/anomaly/check` endpoint (entire endpoint deleted)
- `_detect_anomalies()` function
- Anomaly detection from `/predict` responses
- Sandbagging detection from `/explain` responses

**Updated:**
- Set `anomaly_flags=[]` in prediction responses (with comment about removal)
- Removed `AlfaAnomalyCheckRequest`, `AlfaAnomalyCheckResponse` imports
- Updated docstring to document removal

---

### 4. Pydantic Schemas (`api/models/pydantic_schemas.py`)

**Deprecated (with notices):**
- `AlfaAnomalyCheckRequest` - Marked deprecated with explanation
- `AlfaAnomalyCheckResponse` - Marked deprecated with explanation
- All fields marked "DEPRECATED" in descriptions

**Rationale for keeping schemas:**  
Maintained for backward compatibility but documented as deprecated. Prevents breaking existing client code that may reference these types.

---

### 5. Database Changes

#### Schema Updates (`database/schema_nexus.sql`)

**Removed from `player_ratings` table:**
- `sandbagger_score DOUBLE PRECISION`
- `sandbagger_flags VARCHAR(32)`
- `idx_player_ratings_sandbagger` index

#### Migration Script (`database/migrations/remove_sandbagging_detection.sql`)

**Actions:**
- Drop `sandbagger_score` and `sandbagger_flags` columns
- Drop related indexes
- Drop `alfa_anomaly_flags` table (if exists)
- Drop `is_sandbagging_flagged` from `model_predictions`
- Clean up sandbagging anomaly records
- Add documentation comments

**To Apply Migration:**
```bash
psql -U rankings -d rankings -f database/migrations/remove_sandbagging_detection.sql
```

---

### 6. Test Files

Test files requiring updates (not modified in this implementation):

- `tests/test_alfa.py` - Remove sandbagging assertions
- `ab_test_comprehensive.py` - Remove sandbagging detection
- `optimize_anomaly_thresholds.py` - Deprecate anomaly detection
- `models/model_performance_tracking.py` - Remove sandbagging flags

**Action Required:** Update test expectations to match new rating calculations.

---

## Breaking Changes

### API Endpoints

**Removed:**
- `POST /api/alfa/anomaly/check` - Returns 404

**Changed Response Fields:**
- `GET /api/alfa/ratings` 
  - Removed: `sandbagger_score`, `sandbagger_flags`
  - Added: `deviation_from_fargo`, `tournaments_analyzed`

- `GET /api/alfa/player/{name}`
  - Removed: `sandbagger_score`, `sandbagger_flags`
  - Added: `deviation_from_fargo`, `tournaments_analyzed`

- `GET /api/alfa/summary`
  - Removed: `sandbagger_flagged_count`

### Database Schema

**Removed Columns:**
- `player_ratings.sandbagger_score`
- `player_ratings.sandbagger_flags`
- `model_predictions.is_sandbagging_flagged`

**Removed Tables:**
- `alfa_anomaly_flags`

---

## Migration Guide

### For API Consumers

**Before:**
```json
{
  "player_name": "Jane Doe",
  "alfa_rating": 685.2,
  "sandbagger_score": 0.0,
  "sandbagger_flags": []
}
```

**After:**
```json
{
  "player_name": "Jane Doe",
  "alfa_rating": 698.5,
  "deviation_from_fargo": -1.5,
  "tournaments_analyzed": 8,
  "fargo_rating": 700.0
}
```

### For Database Queries

**Before:**
```sql
SELECT player_name, alfa_rating, sandbagger_score 
FROM player_ratings 
WHERE sandbagger_score > 0.7;
```

**After:**
```sql
-- Sandbagging detection no longer supported
-- Use deviation_from_fargo for rating variance analysis
SELECT player_name, nexus_rating, 
       (SELECT alfa_rating FROM alfa_player_ratings 
        WHERE player_name = player_ratings.player_name LIMIT 1) as alfa
FROM player_ratings;
```

---

## Rationale

### Why Remove Sandbagging Detection?

1. **WPA/WPBA Context:**
   - Professional players competing without handicaps
   - All players at elite skill level
   - No incentive to intentionally underperform

2. **Normal Variance:**
   - High Fargo player finishing 10th in a 20-player field is just having a bad tournament
   - Bad days, injuries, equipment issues, mental state all affect performance
   - This is competitive variance, not strategic sandbagging

3. **Sandbagging Applies To:**
   - ✅ Handicapped league play (APA, BCA)
   - ✅ Amateur tournaments with handicap brackets
   - ❌ Professional straight-up competition (WPA/WPBA)

### Why Model A (Conservative)?

1. **Fargo is Reliable:** 85% weight on Fargo because it's the most comprehensive skill metric
2. **Sustained Patterns Matter:** 12% weight on 10+ tournament average identifies genuine skill changes
3. **Single Tournament Minimal:** 3% weight prevents overreaction to normal variance
4. **Constrained Deviation:** ±15 max ensures rating stability

---

## Testing Requirements

### Unit Tests
- [ ] Test `_compute_alfa_rating()` with various scenarios
- [ ] Test pattern analysis with 3, 10, 20 tournaments
- [ ] Test deviation constraints (verify ±15 max)
- [ ] Test tournament strength multipliers
- [ ] Test Fargo validation bounds

### Integration Tests
- [ ] Test `/api/alfa/ratings` endpoint response format
- [ ] Test `/api/alfa/player/{name}` endpoint response format
- [ ] Test `/api/alfa/summary` endpoint response format
- [ ] Verify removed `/api/alfa/anomaly/check` returns 404

### Database Tests
- [ ] Verify migration removes sandbagging columns
- [ ] Verify no sandbagging indexes remain
- [ ] Test alfa rating calculation queries

---

## Rollback Plan

If rollback is needed:

1. **Revert Code Changes:**
   ```bash
   git revert HEAD  # Or specific commit
   ```

2. **Restore Database Schema:**
   ```sql
   ALTER TABLE player_ratings ADD COLUMN sandbagger_score DOUBLE PRECISION DEFAULT 0;
   ALTER TABLE player_ratings ADD COLUMN sandbagger_flags VARCHAR(32) DEFAULT 'none';
   CREATE INDEX idx_player_ratings_sandbagger ON player_ratings(sandbagger_score DESC);
   ```

3. **Restore API Endpoints:**
   - Restore `POST /api/alfa/anomaly/check`
   - Restore sandbagging calculations in `alfa_engine.py`

---

## Performance Impact

**Expected:**
- ✅ **Faster rating calculations** (no sandbagging heuristics)
- ✅ **Reduced database queries** (no anomaly flag lookups)
- ✅ **Smaller response payloads** (fewer fields)
- ✅ **Simpler API** (one less endpoint)

**Monitoring:**
- Watch `/api/alfa/ratings` response times
- Monitor database query performance
- Track API error rates

---

## Documentation Updates

Files to update:
- [ ] `docs/ALFA_RATING_GUIDE.md` - Explain new Model A weighting
- [ ] `docs/API_REFERENCE.md` - Update endpoint documentation
- [ ] `README.md` - Update Alfa rating description
- [ ] `CHANGELOG.md` - Add breaking changes notice

---

## Future Enhancements

Possible additions to Model A implementation:

1. **Tournament Result Tracking:**
   - Store tournament finishes in database
   - Enable pattern analysis from actual data (not just history stats)

2. **Adaptive Weighting:**
   - Adjust weights based on tournament count
   - New players: 95% Fargo, 5% pattern
   - Established players: 85% Fargo, 12% pattern, 3% current

3. **Field Strength Calculation:**
   - Compute tournament strength from opponent Fargo ratings
   - Auto-detect elite vs. regional fields

4. **Rating Confidence:**
   - Add confidence score based on data quality
   - Show how many tournaments support the Alfa rating

---

## Contact

For questions or issues:
- Code: Review [alfa_engine.py](api/services/alfa_engine.py)
- Constants: Review [alfa_constants.py](api/services/alfa_constants.py)  
- Migration: Review [remove_sandbagging_detection.sql](database/migrations/remove_sandbagging_detection.sql)

---

## Sign-off

- [x] Core logic implemented (Model A weighting)
- [x] API routes updated (sandbagging removed)
- [x] Database migration created
- [x] Schemas updated with deprecation notices
- [x] Documentation created
- [ ] Tests updated (pending)
- [ ] Migration applied to production (pending)
- [ ] API documentation updated (pending)
