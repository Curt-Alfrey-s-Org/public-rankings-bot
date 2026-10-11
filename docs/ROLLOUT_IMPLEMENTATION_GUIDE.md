# Alfa Rating System - Production Rollout Implementation Guide

**Document Version:** 2.0.0  
**Last Updated:** 2026-02-16  
**Status:** Complete Implementation Ready  

---

## Overview

This document provides a comprehensive guide to the complete production rollout infrastructure for the Alfa rating system. All components are implemented, tested, and ready for deployment.

### Key Deliverables

✅ **Feature Flag System** - Runtime configuration without code deployment  
✅ **Rollout Manager** - Gradual deployment logic with stratification  
✅ **Admin API Endpoints** - Control and monitoring via REST  
✅ **Database Schema** - Tracking and metrics collection  
✅ **Deployment Scripts** - Automated phase transitions  
✅ **Documentation** - Complete runbooks and guides  
✅ **Monitoring Dashboards** - Real-time rollout visibility  

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Application                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Feature Flag Middleware                                 │   │
│  │  - Injects feature flag context into requests            │   │
│  │  - Determines rating method (Alfa vs Fargo)              │   │
│  │  - Tracks user preferences                               │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↓                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Request Handlers (Rankings, Matches, etc.)              │   │
│  │  - Use feature_flag_manager from request.state           │   │
│  │  - Use rollout_manager from request.state                │   │
│  │  - Return Alfa or Fargo based on phase                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↓                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Admin Endpoints (/api/admin/rollout/*)                  │   │
│  │  - Get/update feature flags at runtime                   │   │
│  │  - View rollout status and metrics                       │   │
│  │  - Emergency rollback                                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↓                                      │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Database                                                │   │
│  │  - rollout_tracking: Match-level metrics                │  │
│  │  - v_rollout_metrics_*: Aggregated views                │  │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Feature Flag Manager (`models/feature_flag_manager.py`)

**Purpose:** Load, validate, and update feature flags at runtime.

**Key Methods:**

```python
# Load/reload flags from config
ffm.reload()

# Check boolean flag
ffm.is_enabled("alfa_predictions_in_api")

# Get percentage rollout
ffm.get_percentage("alfa_rating_enabled")  # Returns 0-100

# Update flag at runtime
success, msg = ffm.update_flag("alfa_rating_enabled", 25)

# Get current phase (auto-calculated from percentage)
phase = ffm.get_current_phase()  # 0-5

# Validate prerequisites for phase transition
valid, msg = ffm.validate_rollout_prerequisites(target_phase)

# Get audit trail
changes = ffm.get_change_log(limit=50)
```

**Configuration File:** `config/feature_flags.json`

**Flags:**

| Flag | Type | Purpose | Enabled At |
|------|------|---------|------------|
| `alfa_rating_enabled` | percentage | Main rollout percentage | Phase 1+ |
| `alfa_predictions_in_api` | boolean | Return predictions in API | Phase 2+ |
| `alfa_anomaly_detection_enabled` | boolean | Flag suspicious activity | Phase 4+ |
| `alfa_vs_fargo_comparison` | percentage | Show both in UI | Phase 2+ |
| `alfa_admin_dashboard_enabled` | boolean | Admin monitoring tools | Phase 4+ |
| `alfa_rollback_enabled` | boolean | Allow emergency rollback | Always |

---

### 2. Rollout Manager (`models/rollout_manager.py`)

**Purpose:** Decision logic for Alfa deployment with stratification.

**Key Methods:**

```python
from models.rollout_manager import create_rollout_manager

rm = create_rollout_manager(ffm)

# Determine which rating method to use for a tournament
method = rm.get_ratings_method(
    tournament_id="t123",
    user_id="user456",
    tournament_type="league"
)
# Returns: RatingMethod.ALFA, FARGO, or BOTH

# Check if tournament should get Alfa
should_use = rm.should_use_alfa(
    tournament_id="t123",
    tournament_type="league",
    percentage=25
)

# Record metrics after match
rm.record_rollout_metrics(
    match_id="m456",
    tournament_id="t123",
    predictions_dict={
        "outcome_actual": 1.0,
        "outcome_predicted_alfa": 0.45,
        "outcome_predicted_fargo": 0.48,
        "brier_alfa": 0.3025,
        "brier_fargo": 0.2704
    }
)

# User opt-in/out (Phase 1-2)
rm.set_user_preference(user_id="user456", use_alfa=True)

# Get current metrics
metrics = rm.get_rollout_metrics(db_session=db, weeks=4)
```

**Stratification Algorithm:**

The `should_use_alfa()` method uses consistent hashing for even distribution:

```
hash = MD5(f"{tournament_id}:{tournament_type}")
decision_value = (hash % 100) + 1  # 1-100
use_alfa = decision_value <= percentage
```

This ensures:
- Same tournament always gets same treatment
- Even distribution across tournament types
- No per-request randomness

---

### 3. Feature Flag Middleware (`api/middleware/feature_flags.py`)

**Purpose:** Inject feature flag context into every request.

**Request State Injection:**

```python
@app.get("/api/matches/{match_id}")
async def get_match(match_id: str, request: Request):
    ffm = request.state.feature_flag_manager
    rm = request.state.rollout_manager
    current_phase = request.state.current_phase
    alfa_pct = request.state.alfa_enabled_percentage
    user_id = request.state.user_id
    use_alfa = request.state.use_alfa
    
    if use_alfa:
        # Return Alfa predictions
    else:
        # Return Fargo predictions
```

---

### 4. Admin API Endpoints (`api/routes/admin.py`)

**Base Path:** `/api/admin/rollout/`

All endpoints require `admin` or `super_admin` role.

#### Get Rollout Status
```
GET /api/admin/rollout/status

Response:
{
  "current_phase": 2,
  "phase_name": "Shadow Mode (25%)",
  "alfa_percentage": 25,
  "predictions_in_api": true,
  "anomaly_detection_enabled": false,
  "comparisons_shown": true,
  "last_updated": "2026-02-16T14:30:00Z",
  "metrics": {...}
}
```

#### Update Feature Flag
```
PUT /api/admin/rollout/feature-flags/{flag_name}

Request:
{
  "flag_name": "alfa_rating_enabled",
  "value": 50,
  "reason": "Advancing to Phase 3 - metrics approved"
}

Response:
{
  "flag_name": "alfa_rating_enabled",
  "type": "percentage",
  "value": 50,
  "phase": 3,
  "phase_name": "Experimentation (50%)",
  "message": "Flag alfa_rating_enabled updated successfully to 50"
}
```

#### Get All Flags
```
GET /api/admin/rollout/all-flags

Response:
{
  "current_phase": 2,
  "phase_name": "Shadow Mode (25%)",
  "flags": {
    "alfa_rating_enabled": {...},
    "alfa_predictions_in_api": {...},
    ...
  },
  "timestamp": "2026-02-16T14:30:00Z"
}
```

#### Emergency Rollback
```
POST /api/admin/rollout/rollback

Response:
{
  "status": "rolled_back",
  "message": "Alfa rating system has been rolled back to Phase 0",
  "timestamp": "2026-02-16T14:35:00Z",
  "user": "admin@example.com",
  "alfa_percentage": 0,
  "current_phase": 0
}
```

#### Get Change Log
```
GET /api/admin/rollout/change-log?limit=50

Response:
[
  {
    "timestamp": "2026-02-16T14:30:00Z",
    "flag": "alfa_rating_enabled",
    "attribute": "percentage",
    "old_value": 10,
    "new_value": 25
  },
  ...
]
```

#### Validate Phase
```
POST /api/admin/rollout/validate-phase

Request:
{
  "phase": 3
}

Response:
{
  "phase": 3,
  "valid": true,
  "message": "Phase 3 prerequisites met",
  "phase_name": "Experimentation (50%)",
  "timestamp": "2026-02-16T14:30:00Z"
}
```

---

## Database Schema

### Table: `rollout_tracking`

Tracks every match during rollout for analysis.

```sql
CREATE TABLE rollout_tracking (
    id INT AUTO_INCREMENT PRIMARY KEY,
    match_id VARCHAR(255) UNIQUE NOT NULL,
    tournament_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- Rating predictions
    outcome_actual FLOAT NOT NULL,           -- 0.0 or 1.0
    outcome_predicted_alfa FLOAT,            -- Alfa prediction
    outcome_predicted_fargo FLOAT,           -- Fargo prediction
    
    -- Accuracy metrics
    brier_alfa FLOAT,                        -- (pred - actual)^2
    brier_fargo FLOAT,
    
    -- Rollout context
    rollout_phase INT DEFAULT 0,             -- Phase 0-5
    alfa_enabled_percentage INT DEFAULT 0,  -- Percentage at time of match
    anomaly_detected BOOLEAN DEFAULT FALSE,
    
    -- Indexes for fast queries
    INDEX idx_tournament (tournament_id),
    INDEX idx_timestamp (timestamp),
    INDEX idx_rollout_phase (rollout_phase)
);
```

### Views

**`v_rollout_metrics_by_percentage`**
- Aggregates metrics by rollout percentage
- Shows Brier score comparison
- Useful for phase advancement decisions

**`v_rollout_metrics_hourly`**
- Time-series metrics aggregated hourly
- Detects performance degradation
- Powers Grafana dashboards

**`v_rollout_anomalies`**
- Anomalies detected during rollout
- False positive rate tracking
- Validates anomaly detection effectiveness

---

## Deployment Scripts

### Deploy to Phase
```bash
./scripts/rollout_alfa.sh deploy --phase 1    # 10% Silent Canary
./scripts/rollout_alfa.sh deploy --phase 2    # 25% Shadow Mode
./scripts/rollout_alfa.sh deploy --phase 3    # 50% Experimentation
./scripts/rollout_alfa.sh deploy --phase 4    # 75% Controlled Expansion
./scripts/rollout_alfa.sh deploy --phase 5    # 100% Full Production
```

### Check Status
```bash
./scripts/rollout_alfa.sh status               # Show current phase
./scripts/rollout_alfa.sh schedule             # Show rollout timeline
./scripts/rollout_alfa.sh metrics              # Show success metrics
```

### Rollback
```bash
./scripts/rollback_alfa.sh --phase 0           # Rollback to disabled
./scripts/rollback_alfa.sh --auto              # Auto-rollback on failure
./scripts/rollback_alfa.sh --status            # Show rollback history
```

---

## Rollout Phases

### Phase 0: Pre-launch (Before deployment)
**Percentage:** 0%  
**Duration:** 1-2 weeks  
**Activities:**
- Final testing on staging
- Admin training
- Monitoring dashboard setup
- Rollback procedure dry-run

**Success Criteria:**
- ✓ All systems functional
- ✓ Admin team trained
- ✓ Monitoring configured
- ✓ Communication plan ready

---

### Phase 1: Silent Canary (Weeks 1-2)
**Percentage:** 10%  
**Feature:** Alfa runs in background, not shown to users  
**Activities:**
- Compute Alfa predictions for 10% of tournaments
- Record metrics (Brier scores, errors)
- Monitor for anomalies
- No user-facing changes

**Success Criteria:**
- ✓ Brier score < 0.30
- ✓ No critical errors
- ✓ No anomalies
- ✓ System stable

**Advance If:** All criteria met  
**Rollback If:** Brier > 0.32 or error rate > 2%

---

### Phase 2: Shadow Mode (Weeks 3-4)
**Percentage:** 25%  
**Feature:** API returns both Alfa & Fargo, users can opt-in  
**Activities:**
- Extend Alfa to 25% of tournaments
- Users can request Alfa via API (`?show_alfa=true`)
- Compare predictions side-by-side
- Gather user feedback

**Success Criteria:**
- ✓ Brier score < 0.27
- ✓ Fargo unchanged
- ✓ No user complaints
- ✓ Adoption rate > 5%

**Advance If:** All criteria met  
**Rollback If:** Brier > 0.30 or negative feedback

---

### Phase 3: Experimentation (Weeks 5-6)
**Percentage:** 50%  
**Feature:** A/B test in UI, both ratings shown  
**Activities:**
- 50% tournaments use Alfa
- Display both Alfa and Fargo predictions
- Run A/B test in UI
- Analyze user satisfaction

**Success Criteria:**
- ✓ Brier ≥ Fargo (equal or better)
- ✓ User satisfaction > 80%
- ✓ Statistically significant difference
- ✓ No operational issues

**Advance If:** All criteria met  
**Rollback If:** Brier degradation or low satisfaction

---

### Phase 4: Controlled Expansion (Weeks 7-8)
**Percentage:** 75%  
**Feature:** Enable anomaly detection, admin dashboard  
**Activities:**
- 75% tournaments use Alfa
- Activate anomaly detection
- Enable admin dashboard
- Monitor false positives

**Success Criteria:**
- ✓ Anomaly detection precision > 80%
- ✓ False positive rate < 20%
- ✓ Admin review complete
- ✓ No escalations

**Advance If:** All criteria met  
**Rollback If:** High false positive rate

---

### Phase 5: Full Production (Week 9+)
**Percentage:** 100%  
**Feature:** Alfa becomes standard, Fargo as fallback  
**Activities:**
- All tournaments use Alfa
- Archive rollout data
- Public announcement
- Sunset Fargo scoring

**Success Criteria:**
- ✓ All tests pass
- ✓ Performance stable
- ✓ Documentation complete
- ✓ Support trained

---

## Monitoring and Rollout Metrics

### Key Performance Indicators

| KPI | Target | Phase | Monitoring |
|-----|--------|-------|-----------|
| **Brier Score** | < Fargo baseline | All | Real-time |
| **Error Rate** | < 1% | All | Alerts |
| **Anomaly Precision** | > 80% | 4+ | Dashboard |
| **False Positives** | < 20% | 4+ | Dashboard |
| **User Satisfaction** | > 80% | 3+ | Surveys |
| **System Stability** | 99.9% uptime | All | Grafana |

### Grafana Dashboards

**Main Rollout Dashboard** (`monitoring/grafana/dashboards/rollout_metrics.json`)
- Current phase gauge
- Alfa vs Fargo Brier comparison
- Match count by phase
- Error rate trend
- Anomaly detection metrics

**Alfa Health Dashboard** (`monitoring/grafana/dashboards/alfa_health.json`)
- System health metrics
- API response times
- Database performance
- Error logs and alerts

**Alfa Accuracy Dashboard** (`monitoring/grafana/dashboards/alfa_accuracy.json`)
- Prediction accuracy comparison
- Calibration curves
- Win probability analysis
- Player rating changes

---

## Integration Checklist

- [ ] ✓ Feature flag system configured
- [ ] ✓ Rollout manager integrated with rankings API
- [ ] ✓ Middleware installed in FastAPI app
- [ ] ✓ Admin endpoints added to `/api/admin`
- [ ] ✓ Database schema migrated (rollout_tracking table)
- [ ] ✓ Grafana dashboards created
- [ ] ✓ Deployment scripts tested
- [ ] ✓ Monitoring alerts configured
- [ ] ✓ Admin team trained
- [ ] ✓ Rollback procedure tested

---

## Usage Examples

### 1. Get Current Rollout Status

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://your-domain.com/api/admin/rollout/status
```

### 2. Advance to Next Phase

```bash
# Validate prerequisites
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"phase": 3}' \
  https://your-domain.com/api/admin/rollout/validate-phase

# Update flag
curl -X PUT -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "flag_name": "alfa_rating_enabled",
    "value": 50,
    "reason": "Phase 3 - All criteria met"
  }' \
  https://your-domain.com/api/admin/rollout/feature-flags/alfa_rating_enabled
```

### 3. Emergency Rollback

```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  https://your-domain.com/api/admin/rollout/rollback
```

### 4. View Change History

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://your-domain.com/api/admin/rollout/change-log?limit=100
```

---

## Troubleshooting

### Issue: Flag not updating
1. Verify admin permissions
2. Check feature_flags.json is writable
3. Verify JSON format is valid
4. Check application logs

### Issue: Requests still using old values
1. Middleware cache may need to clear
2. Restart API service: `./scripts/restart_api.sh`
3. Force reload: `./scripts/rollout_alfa.sh reload`

### Issue: Rollout percentage not applied
1. Check database connectivity
2. Verify rollout_tracking table exists
3. Check API logs for errors
4. Validate feature flags JSON format

---

## References

- [Production Rollout Guide](PRODUCTION_ROLLOUT_GUIDE.md)
- [Rollout Runbook](ROLLOUT_RUNBOOK.md)
- [Feature Flags Reference](FEATURE_FLAGS_REFERENCE.md)
- [Deployment Scripts](../scripts/rollout_alfa.sh)
- [Admin Routes](../api/routes/admin.py)

---

## Support

For questions or issues:
1. Check the [Rollout Runbook](ROLLOUT_RUNBOOK.md) for week-by-week procedures
2. Review monitoring dashboards in Grafana
3. Check application logs: `tail -f rankings_bot.log`
4. Contact DevOps team for infrastructure support
