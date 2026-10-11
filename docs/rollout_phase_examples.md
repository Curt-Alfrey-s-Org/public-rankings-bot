# Alfa Rating Rollout - Implementation Examples

Practical examples for integrating the Alfa rating system rollout into your API and frontend code.

---

## Table of Contents

1. [FastAPI Integration](#fastapi-integration)
2. [Frontend Implementation](#frontend-implementation)
3. [Database Integration](#database-integration)
4. [Monitoring and Metrics](#monitoring-and-metrics)
5. [Admin Operations](#admin-operations)

---

## FastAPI Integration

### Example 1: Basic Feature Flag Check

**Scenario:** Determine which rating system to use for a match.

```python
# In api/routes/matches.py
from fastapi import APIRouter, Request, Depends
from models.feature_flag_manager import get_feature_flag_manager
from models.rollout_manager import create_rollout_manager, RatingMethod
from database import SessionLocal

router = APIRouter()

@router.get("/api/matches/{match_id}")
async def get_match(
    match_id: str,
    request: Request,
    db: Session = Depends(SessionLocal)
):
    """Get match details with appropriate rating system."""
    
    # Get managers from request context
    ffm = request.state.feature_flag_manager
    rm = request.state.rollout_manager
    
    # Get match from database
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    # Determine which rating system to use
    rating_method = rm.get_ratings_method(
        tournament_id=match.tournament_id,
        user_id=request.state.user_id,
        tournament_type=match.tournament.type
    )
    
    # Build response based on rating method
    if rating_method == RatingMethod.BOTH:
        # Phase 1 or 2-3: Include both predictions
        response = {
            "match_id": match.id,
            "tournament_id": match.tournament_id,
            "player_1": match.player_1,
            "player_2": match.player_2,
            "rating_method": "both",
            "alfa": {
                "prediction": get_alfa_prediction(match),
                "confidence": 0.68,
                "rating_before": match.player_1_rating
            },
            "fargo": {
                "prediction": get_fargo_prediction(match),
                "confidence": 0.65,
                "rating_before": match.player_1_rating
            }
        }
    elif rating_method == RatingMethod.ALFA:
        # Phase 4-5: Alfa is primary
        response = {
            "match_id": match.id,
            "tournament_id": match.tournament_id,
            "player_1": match.player_1,
            "player_2": match.player_2,
            "rating_method": "alfa",
            "rating": {
                "prediction": get_alfa_prediction(match),
                "confidence": 0.68,
                "rating_before": match.player_1_rating
            }
        }
    else:  # FARGO
        # Phase 0-1 or user opted out: Fargo only
        response = {
            "match_id": match.id,
            "tournament_id": match.tournament_id,
            "player_1": match.player_1,
            "player_2": match.player_2,
            "rating_method": "fargo",
            "rating": {
                "prediction": get_fargo_prediction(match),
                "confidence": 0.65,
                "rating_before": match.player_1_rating
            }
        }
    
    return response
```

### Example 2: Middleware Usage

**Scenario:** Inject feature flag context into all requests.

```python
# In api/main.py
from api.middleware.feature_flags import FeatureFlagMiddleware
from models.feature_flag_manager import get_feature_flag_manager

# Create app
app = FastAPI()

# Initialize feature flag manager
ffm = get_feature_flag_manager("config/feature_flags.json")

# Add middleware
app.add_middleware(FeatureFlagMiddleware, feature_flag_manager=ffm)

# Now all routes have access to:
# - request.state.feature_flag_manager
# - request.state.rollout_manager
# - request.state.current_phase
# - request.state.alfa_enabled_percentage
# - request.state.user_id
# - request.state.use_alfa
```

### Example 3: Predictions Endpoint with Opt-in

**Scenario:** Phase 2 - Allow users to opt-in to Alfa predictions.

```python
@router.get("/api/rankings/predictions")
async def get_predictions(
    tournament_id: str,
    use_alfa: bool = Query(False),
    request: Request = None,
    db: Session = Depends(SessionLocal)
):
    """
    Get rating predictions for tournament.
    
    Query parameters:
    - tournament_id: Tournament to get predictions for
    - use_alfa: Set to 'true' to see Alfa predictions (Phase 2+)
    """
    
    rm = request.state.rollout_manager
    current_phase = request.state.current_phase
    user_id = request.state.user_id
    
    # Phase 0-1: Ignore use_alfa parameter
    if current_phase < 2:
        return get_fargo_predictions(tournament_id, db)
    
    # Phase 2: Honor opt-in preference
    if not use_alfa:
        # Check if user previously opted in
        user_pref = rm.get_user_preference(user_id)
        if user_pref is None:  # First time
            use_alfa = False  # Default to Fargo
        else:
            use_alfa = user_pref
    
    # Phase 2: User can opt-in
    if current_phase == 2 and use_alfa:
        # Check if feature flag allows API predictions
        if not request.state.feature_flag_manager.is_enabled(
            "alfa_predictions_in_api"
        ):
            raise HTTPException(
                status_code=503,
                detail="Alfa predictions not yet enabled in API"
            )
        
        # Save user preference
        rm.set_user_preference(user_id, True)
        
        return get_alfa_predictions(tournament_id, db)
    
    # Phase 3+: Return both
    if current_phase >= 3:
        return get_both_predictions(tournament_id, db)
    
    # Default to Fargo
    return get_fargo_predictions(tournament_id, db)
```

### Example 4: Record Rollout Metrics

**Scenario:** After a match completes, record predictions and outcomes for rollout tracking.

```python
@router.post("/api/matches/{match_id}/complete")
async def complete_match(
    match_id: str,
    outcome: str,  # "WIN" or "LOSS"
    request: Request = None,
    db: Session = Depends(SessionLocal)
):
    """Mark match as complete and record metrics."""
    
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404)
    
    # Get predictions
    alfa_pred = get_alfa_prediction(match)
    fargo_pred = get_fargo_prediction(match)
    
    # Calculate Brier scores
    actual = 1.0 if outcome == "WIN" else 0.0
    brier_alfa = (float(alfa_pred == outcome) - 1.0) ** 2  # Simplified
    brier_fargo = (float(fargo_pred == outcome) - 1.0) ** 2
    
    # Record rollout metrics
    rm = request.state.rollout_manager
    predictions_dict = {
        "outcome_actual": outcome,
        "outcome_predicted_alfa": alfa_pred,
        "outcome_predicted_fargo": fargo_pred,
        "brier_alfa": brier_alfa,
        "brier_fargo": brier_fargo,
        "confidence_alfa": 0.68,
        "confidence_fargo": 0.65
    }
    
    rm.record_rollout_metrics(
        match_id=match_id,
        tournament_id=match.tournament_id,
        predictions_dict=predictions_dict
    )
    
    # Update ratings
    update_ratings(match, outcome, db)
    
    # Commit transaction
    db.commit()
    
    return {"status": "completed", "match_id": match_id}
```

---

## Frontend Implementation

### Example 1: React Component - Display Rating with Feature Flags

**Scenario:** Show player rating, with comparison if Alfa/Fargo comparison enabled.

```jsx
// frontend/src/components/PlayerRatingCard.jsx
import React, { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';

export function PlayerRatingCard({ playerId, tournamentId }) {
  const { user } = useAuth();
  const [ratingData, setRatingData] = useState(null);
  const [showComparison, setShowComparison] = useState(false);
  const [useAlfa, setUseAlfa] = useState(false);
  const [phase, setPhase] = useState(0);

  useEffect(() => {
    fetchPlayerRating();
  }, [playerId, useAlfa]);

  const fetchPlayerRating = async () => {
    try {
      const response = await fetch(
        `/api/players/${playerId}/rating?` +
        `tournament_id=${tournamentId}&` +
        `use_alfa=${useAlfa}`,
        {
          headers: {
            'Authorization': `Bearer ${user?.token}`
          }
        }
      );
      
      const data = await response.json();
      setRatingData(data);
      
      // Determine if we should show comparison
      // (based on server response phase/percentage)
      if (data.alfa && data.fargo) {
        setShowComparison(true);
      }
    } catch (error) {
      console.error('Failed to fetch rating:', error);
    }
  };

  if (!ratingData) {
    return <div>Loading rating...</div>;
  }

  return (
    <div className="rating-card bg-slate-900 p-4 rounded">
      <div className="flex justify-between items-start">
        <h3 className="text-xl font-bold text-sky-400">
          {ratingData.player_name}
        </h3>
        
        {/* Main rating display */}
        <div className="text-right">
          <div className="text-4xl font-bold text-sky-300">
            {ratingData.rating?.current || ratingData.alfa?.rating}
          </div>
          <div className="text-xs text-slate-400">
            {ratingData.rating_method.toUpperCase()}
          </div>
        </div>
      </div>

      {/* Show comparison if enabled */}
      {showComparison && (
        <div className="mt-4 pt-4 border-t border-slate-700">
          <div className="text-sm text-slate-300 mb-2">
            Rating Comparison
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            {/* Alfa rating */}
            <div className="bg-slate-800 p-3 rounded">
              <div className="text-xs text-slate-400">Alfa</div>
              <div className="text-xl font-bold text-blue-400">
                {ratingData.alfa?.rating || '-'}
              </div>
              {ratingData.alfa?.confidence && (
                <div className="text-xs text-slate-500">
                  ±{Math.round(ratingData.alfa.confidence * 100)}
                </div>
              )}
            </div>

            {/* Fargo rating */}
            <div className="bg-slate-800 p-3 rounded">
              <div className="text-xs text-slate-400">Fargo</div>
              <div className="text-xl font-bold text-orange-400">
                {ratingData.fargo?.rating || '-'}
              </div>
              {ratingData.fargo?.confidence && (
                <div className="text-xs text-slate-500">
                  ±{Math.round(ratingData.fargo.confidence * 100)}
                </div>
              )}
            </div>
          </div>

          {/* Opt-in toggle for Phase 2 */}
          {phase === 2 && (
            <div className="mt-4">
              <label className="flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={useAlfa}
                  onChange={(e) => setUseAlfa(e.target.checked)}
                  className="mr-2"
                />
                <span className="text-sm text-slate-300">
                  Use Alfa predictions
                </span>
              </label>
            </div>
          )}
        </div>
      )}

      {/* Prediction display */}
      {ratingData.prediction && (
        <div className="mt-4 p-3 bg-slate-800 rounded">
          <div className="text-xs text-slate-400 mb-1">
            Expected Outcome
          </div>
          <div className="flex justify-between items-center">
            <div className="text-lg font-bold text-sky-300">
              {ratingData.prediction.toUpperCase()}
            </div>
            <div className="text-sm text-slate-400">
              {Math.round(ratingData.confidence * 100)}% confidence
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

### Example 2: Hook - Use Feature Flags

**Scenario:** Custom hook for accessing feature flag state in components.

```jsx
// frontend/src/hooks/useFeatureFlags.js
import { useEffect, useState, useContext } from 'react';
import { AuthContext } from '@/contexts/AuthContext';

export function useFeatureFlags() {
  const { user } = useContext(AuthContext);
  const [flags, setFlags] = useState({
    currentPhase: 0,
    alfaPercentage: 0,
    alfaEnabled: false,
    alfaInApi: false,
    alfaComparison: false,
    anomalyDetectionEnabled: false,
    adminDashboardEnabled: false
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchFeatureFlags();
    // Check every 5 minutes for updates
    const interval = setInterval(fetchFeatureFlags, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [user]);

  const fetchFeatureFlags = async () => {
    try {
      const response = await fetch(
        '/api/feature-flags',
        {
          headers: {
            'Authorization': `Bearer ${user?.token}`
          }
        }
      );
      
      if (response.ok) {
        const data = await response.json();
        setFlags({
          currentPhase: data.current_phase,
          alfaPercentage: data.alfa_rating_enabled?.percentage || 0,
          alfaEnabled: data.alfa_rating_enabled?.percentage > 0,
          alfaInApi: data.alfa_predictions_in_api?.enabled || false,
          alfaComparison: data.alfa_vs_fargo_comparison?.percentage > 0,
          anomalyDetectionEnabled: data.alfa_anomaly_detection_enabled?.enabled || false,
          adminDashboardEnabled: data.alfa_admin_dashboard_enabled?.enabled || false
        });
      }
    } catch (error) {
      console.error('Failed to fetch feature flags:', error);
    } finally {
      setLoading(false);
    }
  };

  return { flags, loading };
}

// Usage in component:
// const { flags, loading } = useFeatureFlags();
// if (flags.alfaComparison) {
//   return <RatingComparison />;
// }
```

### Example 3: Feedback Component - Collect User Feedback (Phase 3)

**Scenario:** Show feedback form during A/B testing phase.

```jsx
// frontend/src/components/PredictionFeedback.jsx
import React, { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';

export function PredictionFeedback({ matchId, prediction, outcome }) {
  const { user } = useAuth();
  const [sentiment, setSentiment] = useState(null);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async () => {
    try {
      await fetch('/api/feedback/predictions', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${user?.token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          match_id: matchId,
          prediction,
          outcome,
          sentiment,
          user_id: user?.id
        })
      });
      setSubmitted(true);
    } catch (error) {
      console.error('Failed to submit feedback:', error);
    }
  };

  if (submitted) {
    return (
      <div className="text-center text-green-400">
        ✓ Thanks for your feedback!
      </div>
    );
  }

  return (
    <div className="mt-4 p-3 bg-slate-800 rounded">
      <div className="text-sm text-slate-300 mb-3">
        Was this prediction accurate?
      </div>
      
      <div className="flex gap-2">
        <button
          onClick={() => {
            setSentiment('positive');
            handleSubmit();
          }}
          className="flex-1 px-3 py-2 bg-green-600 hover:bg-green-700 rounded text-sm"
        >
          Accurate ✓
        </button>
        
        <button
          onClick={() => {
            setSentiment('neutral');
            handleSubmit();
          }}
          className="flex-1 px-3 py-2 bg-slate-600 hover:bg-slate-700 rounded text-sm"
        >
          OK
        </button>
        
        <button
          onClick={() => {
            setSentiment('negative');
            handleSubmit();
          }}
          className="flex-1 px-3 py-2 bg-red-600 hover:bg-red-700 rounded text-sm"
        >
          Inaccurate ✗
        </button>
      </div>
    </div>
  );
}
```

---

## Database Integration

### Example 1: Query Rollout Metrics

**Scenario:** Get current rollout metrics for a specific phase.

```python
# In api/routes/admin.py
from sqlalchemy import func
from database import SessionLocal
from api.models.rollout import RolloutTracking

def get_phase_metrics(phase: int, db: Session):
    """Get aggregated metrics for a rollout phase."""
    
    metrics = db.query(
        func.count(RolloutTracking.id).label('total_matches'),
        func.count(
            func.distinct(RolloutTracking.tournament_id)
        ).label('tournaments'),
        func.avg(RolloutTracking.brier_alfa).label('avg_brier_alfa'),
        func.avg(RolloutTracking.brier_fargo).label('avg_brier_fargo'),
        func.sum(
            func.cast(RolloutTracking.correct_alfa, Integer)
        ).label('correct_alfa_count'),
        func.sum(
            func.cast(RolloutTracking.correct_fargo, Integer)
        ).label('correct_fargo_count'),
        func.sum(
            func.cast(RolloutTracking.anomaly_detected, Integer)
        ).label('anomalies_detected')
    ).filter(
        RolloutTracking.rollout_phase == phase
    ).first()
    
    if not metrics:
        return None
    
    # Calculate derived metrics
    accuracy_alfa = (metrics.correct_alfa_count / metrics.total_matches * 100
                     if metrics.total_matches > 0 else 0)
    accuracy_fargo = (metrics.correct_fargo_count / metrics.total_matches * 100
                      if metrics.total_matches > 0 else 0)
    
    improvement = ((metrics.avg_brier_fargo - metrics.avg_brier_alfa) /
                   metrics.avg_brier_fargo * 100
                   if metrics.avg_brier_fargo > 0 else 0)
    
    return {
        'phase': phase,
        'total_matches': metrics.total_matches,
        'tournaments': metrics.tournaments,
        'avg_brier_alfa': metrics.avg_brier_alfa,
        'avg_brier_fargo': metrics.avg_brier_fargo,
        'accuracy_alfa': accuracy_alfa,
        'accuracy_fargo': accuracy_fargo,
        'improvement_pct': improvement,
        'anomalies_detected': metrics.anomalies_detected
    }
```

### Example 2: Store Anomaly Detection Results

**Scenario:** Record anomalies in database for admin review (Phase 4).

```python
from api.models.rollout import RolloutTracking, Anomaly
from datetime import datetime

def record_anomaly_detection(
    match_id: str,
    tournament_id: str,
    user_id: str,
    anomaly_type: str,
    confidence: float,
    evidence: dict,
    db: Session
):
    """Record anomaly detection result."""
    
    # Create anomaly record
    anomaly = Anomaly(
        match_id=match_id,
        tournament_id=tournament_id,
        player_id=user_id,
        anomaly_type=anomaly_type,
        confidence=confidence,
        evidence=json.dumps(evidence),
        status='pending',  # Awaiting admin review
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(anomaly)
    
    # Also update rollout tracking record
    tracking = db.query(RolloutTracking).filter(
        RolloutTracking.match_id == match_id
    ).first()
    
    if tracking:
        tracking.anomaly_detected = True
        tracking.anomaly_type = anomaly_type
    
    db.commit()
    
    return anomaly
```

---

## Monitoring and Metrics

### Example 1: Expose Prometheus Metrics

**Scenario:** Export rollout metrics for Grafana monitoring.

```python
# In api/routes/metrics.py
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from fastapi import APIRouter
from models.feature_flag_manager import get_feature_flag_manager
from models.rollout_manager import create_rollout_manager

router = APIRouter()

# Define metrics
alfa_rollout_percentage = Gauge(
    'alfa_rating_rollout_percentage',
    'Current rollout percentage (0-100)',
    labelnames=['phase']
)

alfa_brier_score = Histogram(
    'alfa_brier_score',
    'Alfa Brier score (prediction accuracy)',
    buckets=(0.15, 0.20, 0.25, 0.26, 0.27, 0.30, 0.35, 0.40)
)

fargo_brier_score = Histogram(
    'fargo_brier_score',
    'Fargo Brier score (prediction accuracy)',
    buckets=(0.15, 0.20, 0.25, 0.26, 0.27, 0.30, 0.35, 0.40)
)

alfa_error_rate = Gauge(
    'alfa_error_rate',
    'Fraction of predictions that resulted in errors',
    labelnames=['phase']
)

anomaly_detection_precision = Gauge(
    'alfa_anomaly_detection_precision',
    'Precision of anomaly detection (TP/(TP+FP))',
    labelnames=['phase']
)

@router.get("/metrics")
async def prometheus_metrics():
    """Expose metrics for Prometheus scraping."""
    
    ffm = get_feature_flag_manager()
    phase = ffm.get_current_phase()
    percentage = ffm.get_percentage("alfa_rating_enabled")
    
    # Update gauge with current data
    alfa_rollout_percentage.labels(phase=phase).set(percentage)
    
    # Return metrics in Prometheus format
    return generate_latest()
```

### Example 2: Alert Configuration

**Scenario:** Define alerts for critical rollout conditions.

```yaml
# monitoring/prometheus/rules/alfa_rollout.yml
groups:
  - name: alfa_rollout_alerts
    interval: 30s
    rules:
      # Alert if Brier score degrades
      - alert: AlfaBrierDegradation
        expr: avg(alfa_brier_score) > 0.32
        for: 30m
        labels:
          severity: critical
          component: alfa_rollout
        annotations:
          summary: "Alfa Brier score exceeded threshold"
          description: "Alfa Brier={{ $value | humanize }}"
          action: "Check logs, consider rollback"

      # Alert if error rate spiked
      - alert: AlfaErrorRateHigh
        expr: alfa_error_rate > 0.02
        for: 60m
        labels:
          severity: critical
          component: alfa_rollout
        annotations:
          summary: "Alfa error rate > 2%"
          description: "Error rate={{ $value | humanizePercentage }}"
          action: "Page on-call engineer"

      # Alert if anomaly detection precision degraded
      - alert: AnomalyDetectionPrecisionLow
        expr: alfa_anomaly_detection_precision < 0.70
        for: 60m
        labels:
          severity: warning
          component: alfa_rollout
        annotations:
          summary: "Anomaly detection precision < 70%"
          description: "Precision={{ $value | humanizePercentage }}"
          action: "Review flagged matches, adjust thresholds"
```

---

## Admin Operations

### Example 1: Admin Endpoint - Update Feature Flags

**Scenario:** Allow admins to update feature flags at runtime.

```python
# In api/routes/admin.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from models.feature_flag_manager import get_feature_flag_manager

router = APIRouter(prefix="/api/admin")

class FlagUpdate(BaseModel):
    """Feature flag update request."""
    value: Union[bool, int]

@router.put("/feature-flags/{flag_name}")
async def update_feature_flag(
    flag_name: str,
    update: FlagUpdate,
    current_admin: User = Depends(get_current_admin)
):
    """
    Update a feature flag at runtime.
    
    Admin-only endpoint. Requires authentication.
    
    Example:
    PUT /api/admin/feature-flags/alfa_rating_enabled
    { "value": 50 }
    """
    
    ffm = get_feature_flag_manager()
    
    # Validate flag exists
    flag = ffm.get_flag(flag_name)
    if not flag:
        raise HTTPException(status_code=404, detail=f"Flag not found: {flag_name}")
    
    # Validate value type
    flag_type = flag.get("type")
    if flag_type == "percentage":
        if not isinstance(update.value, int) or not (0 <= update.value <= 100):
            raise HTTPException(
                status_code=400,
                detail="Percentage must be 0-100"
            )
    elif flag_type == "boolean":
        if not isinstance(update.value, bool):
            raise HTTPException(
                status_code=400,
                detail="Boolean value required"
            )
    
    # Check prerequisites
    current_phase = ffm.get_current_phase()
    if flag_name == "alfa_rating_enabled":
        # Calculate target phase from percentage
        value = update.value
        target_phase = 0
        if value > 0 and value <= 10:
            target_phase = 1
        elif value <= 25:
            target_phase = 2
        # ... etc
        
        valid, msg = ffm.validate_rollout_prerequisites(target_phase)
        if not valid:
            raise HTTPException(status_code=400, detail=msg)
    
    # Update flag
    success, msg = ffm.update_flag(flag_name, update.value)
    
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    
    # Log admin action
    log_admin_action(
        admin_id=current_admin.id,
        action="update_feature_flag",
        details={
            "flag": flag_name,
            "value": update.value,
            "previous_value": flag.get("enabled" if flag_type == "boolean" else "percentage")
        }
    )
    
    return {
        "success": True,
        "message": msg,
        "flag": flag_name,
        "value": update.value
    }
```

### Example 2: Admin Dashboard - Rollout Status

**Scenario:** Display current rollout status and metrics for admins.

```python
@router.get("/admin/rollout-status")
async def get_rollout_status(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(SessionLocal)
):
    """Get comprehensive rollout status for admin dashboard."""
    
    ffm = get_feature_flag_manager()
    rm = create_rollout_manager(ffm)
    
    phase = ffm.get_current_phase()
    percentage = ffm.get_percentage("alfa_rating_enabled")
    
    # Get metrics
    metrics = rm.get_rollout_metrics(db_session=db, weeks=4)
    
    # Get phase info
    phase_names = {
        0: "Pre-launch",
        1: "Silent Canary (10%)",
        2: "Shadow Mode (25%)",
        3: "Experimentation (50%)",
        4: "Controlled Expansion (75%)",
        5: "Full Production (100%)"
    }
    
    return {
        "current_phase": phase,
        "phase_name": phase_names.get(phase, "Unknown"),
        "rollout_percentage": percentage,
        "flags": {
            "alfa_rating_enabled": ffm.get_flag("alfa_rating_enabled"),
            "alfa_predictions_in_api": ffm.get_flag("alfa_predictions_in_api"),
            "alfa_anomaly_detection_enabled": ffm.get_flag(
                "alfa_anomaly_detection_enabled"
            )
        },
        "metrics": {
            "avg_brier_alfa": metrics.avg_brier_alfa if metrics else None,
            "avg_brier_fargo": metrics.avg_brier_fargo if metrics else None,
            "improvement_pct": metrics.improvement_pct if metrics else None,
            "tournaments_completed": metrics.tournaments_completed if metrics else 0,
            "matches_total": metrics.matches_total if metrics else 0,
            "error_rate": metrics.error_rate if metrics else 0,
            "anomalies_detected": metrics.anomalies_detected if metrics else 0
        },
        "timestamps": {
            "last_updated": datetime.utcnow().isoformat()
        }
    }
```

---

**For more examples and documentation, see:**
- [FEATURE_FLAGS_REFERENCE.md](FEATURE_FLAGS_REFERENCE.md)
- [PRODUCTION_ROLLOUT_GUIDE.md](PRODUCTION_ROLLOUT_GUIDE.md)
- [ROLLOUT_RUNBOOK.md](ROLLOUT_RUNBOOK.md)
