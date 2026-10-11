# Feature Flags Reference Guide

Complete documentation of all feature flags for Alfa rating system rollout.

---

## Overview

Feature flags are stored in `config/feature_flags.json` and control how the Alfa rating system is deployed. They can be:
- Updated at runtime via API
- Validated before deployment
- Automatically triggered for rollback
- Organized by phase

---

## Flag: `alfa_rating_enabled`

**Type:** `percentage` (0-100)

**Current Value:** 0

**Purpose:** Controls what percentage of tournaments use Alfa rating system.

**Valid Range:** 0-100

**Update Method:** Runtime via API or direct JSON edit

**Rollback:** Yes (can revert to previous percentage)

### Usage

```bash
# Check current value
jq '.alfa_rating_enabled' config/feature_flags.json

# Update via API
curl -X PUT http://localhost:8003/api/admin/feature-flags/alfa_rating_enabled \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{"percentage": 50}'

# Update via Python
from models.feature_flag_manager import get_feature_flag_manager
mgr = get_feature_flag_manager()
success, msg = mgr.update_flag("alfa_rating_enabled", 50)
```

### Phase Mapping

```json
{
  "0%": "Phase 0 - Pre-launch (disabled)",
  "10%": "Phase 1 - Silent Canary",
  "25%": "Phase 2 - Shadow Mode",
  "50%": "Phase 3 - Experimentation",
  "75%": "Phase 4 - Controlled Expansion",
  "100%": "Phase 5 - Full Production"
}
```

### Decision Tree

When determining if tournament should use Alfa:

```
1. Is alfa_rating_enabled > 0%?
   No  → Use Fargo
   Yes → Continue

2. Is tournament in rollout percentage (stratified by type)?
   No  → Use Fargo
   Yes → Continue

3. Check user preference (phases 1-2)
   User opted out? → Use Fargo
   User opted in or no preference? → Continue

4. Return based on phase:
   Phase 1  → Return BOTH (background only)
   Phase 2+ → Return both if API enabled
   Phase 3+ → Return BOTH (for UI comparison)
   Phase 5  → Return ALFA only
```

**Example Implementation:**

```python
from models.rollout_manager import create_rollout_manager
from models.feature_flag_manager import get_feature_flag_manager

ffm = get_feature_flag_manager()
rm = create_rollout_manager(ffm)

# Determine method for a tournament
method = rm.get_ratings_method(
    tournament_id="tournament_12345",
    user_id="user_9876",
    tournament_type="league"
)

# Returns: RatingMethod.ALFA, RatingMethod.FARGO, or RatingMethod.BOTH
```

---

## Flag: `alfa_predictions_in_api`

**Type:** `boolean`

**Current Value:** `false`

**Purpose:** Allow Alfa predictions to be returned in API responses.

**Enabled At:** Phase 2+ (25%+ rollout)

**Dependencies:** `alfa_rating_enabled` >= 25%

**Update Method:** Direct JSON or API

### Behavior by Phase

| Phase | Enabled | Returned in API | Shown in UI |
|-------|---------|-----------------|------------|
| 0-1   | false   | No              | No         |
| 2     | true    | Yes (opt-in)    | Optional   |
| 3+    | true    | Yes (always)    | Comparison |

### API Response Example (Phase 2+)

```json
{
  "match_id": "match_12345",
  "tournament_id": "tournament_9876",
  "rating_method": "both",
  "fargo": {
    "prediction": "WIN",
    "confidence": 0.68,
    "rating_before": 580,
    "rating_after": 590
  },
  "alfa": {
    "prediction": "WIN",
    "confidence": 0.71,
    "rating_before": 575,
    "rating_after": 585
  }
}
```

### Usage

```python
# Check if Alfa predictions should be returned
from models.feature_flag_manager import get_feature_flag_manager

ffm = get_feature_flag_manager()
if ffm.is_enabled("alfa_predictions_in_api"):
    # Include Alfa predictions in response
    response["alfa"] = alfa_prediction
```

---

## Flag: `alfa_vs_fargo_comparison`

**Type:** `percentage` (0-100)

**Current Value:** 0

**Purpose:** Return both Alfa and Fargo scores for USER INTERFACE comparison.

**Synchronized With:** `alfa_rating_enabled` (follows same percentage)

**Update Method:** Automatic (synced), or manual override

### Behavior

```
Percentage | UI Display
-----------|-------------------------------------------
0%         | Fargo only (Alfa not shown)
10-25%     | Fargo only (Alfa in API if enabled)
50-75%     | Both scores shown (for comparison)
100%       | Alfa primary, Fargo as reference
```

### UI Examples

**At 0-25%:**
```
Player Rating: 580 (Fargo)
(Alfa predictions running in background)
```

**At 50-75%:**
```
Player Rating Comparison:
├─ Alfa:  575 (±2)
└─ Fargo: 580 (±3)

"Which rating system is more accurate? Help us improve!"
```

**At 100%:**
```
Player Rating: 575 (Alfa)
Fargo comparison: 580
```

### Usage

```python
# Frontend code
percentage = request.state.alfa_enabled_percentage

if percentage >= 50:
    # Show both ratings for comparison
    show_comparison_ui(alfa_rating, fargo_rating)
elif percentage >= 25 and request.query_params.get("use_alfa"):
    # Show Alfa if user opted in
    show_alfa_ui(alfa_rating)
else:
    # Show Fargo by default
    show_fargo_ui(fargo_rating)
```

---

## Flag: `alfa_anomaly_detection_enabled`

**Type:** `boolean`

**Current Value:** `false`

**Purpose:** Enable anomaly detection system for flagging suspicious activity.

**Enabled At:** Phase 4+ (75%+ rollout)

**Dependencies:**
- `alfa_rating_enabled` >= 75%
- Admin dashboard running
- Database schema initialized

### Anomaly Types Detected

| Type | Pattern | Action |
|------|---------|--------|
| Sandbagging | Intentionally losing to preserve rating | Flag for review |
| Skill Burst | Impossible rating improvement | Flag for review |
| Rating Collapse | Sudden unexplained drops | Flag for review |
| Betting Anomaly | Unusual match selection pattern | Alert |
| Time Exploit | Multiple matches in short timespan | Flag |

### Detection Algorithm

```
For each player in tournament:
  1. Calculate expected rating change (Alfa model)
  2. If actual ≠ expected by > threshold:
     - Flag as potential anomaly
     - Calculate confidence (0-1)
  3. If confidence > 0.7:
     - Add to admin review queue
     - Notify admin if auto-review enabled
  4. If confirmed by human:
     - Record in anomaly table
     - Update statistics
     - Offer rating adjustment option
```

### Admin Actions

```python
# Approve anomaly detection result
@app.post("/api/admin/anomalies/{anomaly_id}/approve")
async def approve_anomaly(
    anomaly_id: str,
    action: Literal["adjust_rating", "ignore", "investigate"]
):
    """
    Actions:
    - adjust_rating: Apply recommended rating change
    - ignore: Was false positive, don't flag again
    - investigate: Needs manual investigation
    """

# Adjust player rating
@app.post("/api/admin/players/{player_id}/rating-adjustment")
async def adjust_rating(
    player_id: str,
    adjustment: float,
    reason: str,
    evidence: str
):
    """Manually adjust Alfa rating for confirmed anomalies."""
```

### Admin Dashboard Display (Phase 4+)

```
Anomaly Detection Dashboard
├─ Flagged Matches (Today): 12
├─ Pending Review: 8
├─ Approved Anomalies: 42
├─ Precision: 85%
└─ False Positive Rate: 15%

[View Flagged Matches] [Configure Thresholds]

Flagged Match Details:
├─ Player: John Doe (rating 575)
├─ Tournament: Weekly League #12
├─ Type: Sandbagging
├─ Confidence: 92%
├─ Evidence: Lost to lower-rated player 3x
└─ [Approve] [Reject] [Adjust Rating]
```

### Usage

```python
# Check if anomaly detection active
annotate_if_anomaly(match, predictions):
    if get_feature_flag_manager().is_enabled("alfa_anomaly_detection_enabled"):
        # Run anomaly detection
        anomaly = detect_anomaly(match, predictions)
        if anomaly.confidence > 0.7:
            flag_for_admin_review(anomaly)
```

---

## Flag: `alfa_admin_dashboard_enabled`

**Type:** `boolean`

**Current Value:** `false`

**Purpose:** Enable admin dashboard for rollout monitoring and anomaly review.

**Enabled At:** Phase 4+ (75%+ rollout)

**Admin-Only:** Yes (requires special auth scope)

**Dependencies:** `alfa_anomaly_detection_enabled`

### Dashboard Components

1. **Rollout Metrics:**
   - Current percentage
   - Phase transition history
   - Brier score comparison
   - Error rate trends

2. **Anomaly Detection:**
   - Flagged matches list
   - Confidence distribution
   - Review queue stats
   - Precision/recall metrics

3. **Player Management:**
   - Search player by name/ID
   - View rating history (Alfa vs Fargo)
   - Adjust rating if needed
   - Export audit trail

4. **Settings:**
   - Configure anomaly thresholds
   - Notification preferences
   - Feature flag overrides (if needed)
   - Bulk operations

### Access Control

```python
# Protect admin dashboard
@app.get("/admin/dashboard")
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    # Check auth
    user = get_current_user(request)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Check feature flag
    if not get_feature_flag_manager().is_enabled("alfa_admin_dashboard_enabled"):
        raise HTTPException(status_code=503, detail="Feature not yet enabled")
    
    return render_dashboard(user, db)
```

---

## Flag: `alfa_rollback_enabled`

**Type:** `boolean`

**Current Value:** `true`

**Purpose:** Enable automatic and manual rollback procedures.

**Should NOT be disabled** during rollout (critical safety feature)

**Dependencies:** None (always ready)

### Auto-Rollback Triggers

```json
{
  "enabled": true,
  "auto_rollback_triggers": {
    "brier_threshold": 0.32,
    "brier_check_interval_minutes": 30,
    "error_rate_threshold": 0.02,
    "error_rate_check_interval_minutes": 60,
    "consecutive_failures": 5
  }
}
```

**Trigger 1: Brier Score**
- If avg Brier > 0.32 for > 30 minutes
- Action: Rollback to Phase 0
- Override: Can be disabled (not recommended)

**Trigger 2: Error Rate**
- If error_rate > 2% for > 60 minutes
- Action: Rollback to previous phase
- Override: Can be disabled (not recommended)

**Trigger 3: Consecutive Failures**
- If 5+ prediction exceptions in sequence
- Action: Disable feature flag immediately
- Override: Automatic, no manual override

### Manual Rollback

```bash
# Rollback to specific phase
./scripts/rollback_alfa.sh --phase 0

# Auto-detect and rollback
./scripts/rollback_alpha.sh --auto

# Check status
./scripts/rollback_alfa.sh --status
```

---

## Flag: `alfa_stakeholder_notifications`

**Type:** `boolean`

**Current Value:** `true`

**Purpose:** Send notifications on phase transitions and critical events.

**Notification Channels:**
- Email (to user9@example.com)
- Slack (#rankings-bot, #incidents)
- PagerDuty (for critical)

### Events Triggering Notifications

| Event | Severity | Recipients |
|-------|----------|------------|
| Phase transition | Info | All stakeholders |
| Brier degradation | Warning | Tech team |
| Rollback triggered | Critical | All + on-call |
| Anomaly precision < 70% | Warning | Admins |
| API error rate spike | Critical | Ops + on-call |

### Notification Templates

**Phase Transition (Info):**
```
Subject: Alfa Rating - Phase X Deployment

Alfa rating system has transitioned to Phase X (YY% rollout).

Details:
- Start time: [timestamp]
- Tournaments affected: [count]
- Initial metrics: [summary]
- Next phase: Phase X+1 (target date)

Dashboard: [link]
Status: [green/yellow/red]
```

**Rollback Alert (Critical):**
```
CRITICAL: Alfa Rating Rollback Triggered

Details:
- Trigger: [Brier exceeded / Error rate exceeded / etc]
- Rollback from: Phase X → Phase Y
- Affected systems: [count] tournaments
- Action taken: [Automatic / Manual]

Investigation started. More details in 30 minutes.

Slack: #incidents
Dashboard: [link]
```

---

## Managing Feature Flags

### Load Flags at Startup

```python
# In api/main.py or similar
from models.feature_flag_manager import get_feature_flag_manager

# Load flags on app startup
@app.on_event("startup")
async def load_feature_flags():
    ffm = get_feature_flag_manager("config/feature_flags.json")
    app.state.feature_flag_manager = ffm
    logger.info(f"Feature flags loaded - Current phase: {ffm.get_current_phase()}")
```

### Inject into Requests

```python
# Use middleware to add to request context
from api.middleware.feature_flags import FeatureFlagMiddleware

app.add_middleware(FeatureFlagMiddleware)

# Now available in routes
@app.get("/api/matches/{match_id}")
async def get_match(match_id: str, request: Request):
    current_phase = request.state.current_phase
    use_alfa = request.state.use_alfa
    # ... build response based on flags
```

### Update at Runtime

```python
# Via API endpoint
@app.put("/api/admin/feature-flags/{flag_name}")
async def update_feature_flag(
    flag_name: str,
    value: Union[bool, int],
    request: Request
):
    ffm = get_feature_flag_manager()
    success, msg = ffm.update_flag(flag_name, value)
    return {"success": success, "message": msg}

# Validate before update
valid, msg = ffm.validate_rollout_prerequisites(target_phase)
if not valid:
    raise HTTPException(status_code=400, detail=msg)
```

### Monitor Flag Changes

```python
# Get audit trail
ffm = get_feature_flag_manager()
changes = ffm.get_change_log(limit=20)

for change in changes:
    print(f"{change['timestamp']}: {change['flag']} "
          f"{change['old_value']} → {change['new_value']}")
```

---

## Troubleshooting

### Flags Not Updating

**Symptom:** Feature flag update returns success but behavior doesn't change

**Check:**
```bash
# 1. Verify file updated
jq '.' config/feature_flags.json | grep -A5 alfa_rating_enabled

# 2. Check if manager cached old value
# Solution: Restart API server to reload flags
systemctl restart rankings-bot-api

# 3. Check for duplicate flag managers
# Solution: Ensure using singleton pattern (get_feature_flag_manager())
```

### Flag Validation Failing

**Symptom:** Can't update flag, validation error

**Check:**
```python
# Get validation error details
from models.feature_flag_manager import get_feature_flag_manager

ffm = get_feature_flag_manager()
valid, msg = ffm.validate_rollout_prerequisites(target_phase)
print(f"Valid: {valid}, Message: {msg}")

# Common issues:
# - Phase 2 requires alfa_predictions_in_api flag
# - Phase 4 requires both anomaly detection & admin dashboard
# - Percentage out of range (0-100)
```

### Wrong Phase Detected

**Symptom:** System says Phase 2 but metrics show Phase 1 behavior

**Check:**
```python
# Verify percentage mapping
ffm = get_feature_flag_manager()
percentage = ffm.get_percentage("alfa_rating_enabled")  # e.g., 25
phase = ffm.get_current_phase()  # Should be 2

# Phase mapping:
# 0%: phase=0
# 1-10%: phase=1
# 11-25%: phase=2
# 26-50%: phase=3
# 51-75%: phase=4
# 76-100%: phase=5
```

---

## Examples and Use Cases

### Example 1: Phase 1 Deployment

```bash
# Update config
jq '.alfa_rating_enabled.percentage = 10' config/feature_flags.json > /tmp/ff.json && \
  mv /tmp/ff.json config/feature_flags.json

# Restart API
systemctl restart rankings-bot-api

# Verify
./scripts/rollout_alfa.sh status
# Output: Current Phase: 1 (Silent Canary), Rollout Percentage: 10%

# Monitor
watch './scripts/rollout_alfa.sh metrics'
```

### Example 2: Toggle Feature for Single Tournament

```python
# In API route handler
async def get_tournament_matches(tournament_id: str, request: Request):
    ffm = request.state.feature_flag_manager
    rm = request.state.rollout_manager
    
    # Check if tournament should use Alfa
    method = rm.get_ratings_method(
        tournament_id=tournament_id,
        tournament_type="league"
    )
    
    # Build response based on method
    if method in [RatingMethod.ALFA, RatingMethod.BOTH]:
        # Include Alfa prediction
        matches = get_matches_with_alfa(tournament_id)
    else:
        # Fargo only
        matches = get_matches_with_fargo(tournament_id)
    
    return matches
```

### Example 3: Opt-In Query Parameter

```python
# User can opt-in to Alfa in Phase 2
@app.get("/api/players/{player_id}/rating")
async def get_player_rating(
    player_id: str,
    request: Request,
    use_alfa: bool = Query(False)
):
    phase = request.state.current_phase
    
    # Phase 2: Allow opt-in
    if phase == 2 and use_alfa:
        # Save user preference
        rm = request.state.rollout_manager
        rm.set_user_preference(player_id, True)
        rating_method = RatingMethod.ALFA
    else:
        rating_method = RatingMethod.FARGO
    
    rating = get_rating(player_id, method=rating_method)
    return {"rating": rating, "method": rating_method}
```

---

**For more details, see:**
- [PRODUCTION_ROLLOUT_GUIDE.md](PRODUCTION_ROLLOUT_GUIDE.md) - Complete 9-week strategy
- [ROLLOUT_RUNBOOK.md](ROLLOUT_RUNBOOK.md) - Week-by-week operational checklist
