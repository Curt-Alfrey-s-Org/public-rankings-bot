# Data Drift Monitoring for Alfa Rating System

## Overview

Data drift monitoring detects significant changes in input distributions, output distributions, and new player convergence rates. This guide explains how drift is detected, what it means, and what actions to take.

---

## Why Data Drift Matters

Data drift occurs when the distribution of data changes from what the model was trained on. This can lead to:

1. **Accuracy degradation**: Model was trained on different data
2. **Systematic bias**: Model predictions systematically off in one direction
3. **Anomaly detection failures**: Flags don't work on new player patterns
4. **Cold-start issues**: New player convergence rate decreases

**Example**: If the model was trained on 9-ball matches but production suddenly gets 50% 8-ball matches, the model will perform poorly because the match dynamics are different.

---

## Types of Drift Detected

### 1. Input Feature Drift

**What it is**: Distribution of match features changes

**Key Features Monitored**:
- **rating_diff**: Difference between player ratings (should be ~normal, mean=0, std=150)
- **race_to**: Match race-to value distribution (5, 7, 9, 11, etc.)
- **format**: Distribution by format (8-ball, 9-ball, 10-ball, etc.)

**Example**:
- Training: 80% 9-ball, 20% 8-ball
- Production: 40% 9-ball, 60% 8-ball
- Drift Detected: Yes, format distribution shifted 20+ percentage points

**Detection Method**: Compare production statistics to training baseline using z-score
- If z-score > 2.0: MODERATE drift
- If z-score > 3.0: SEVERE drift

**Alert Thresholds**:
- >2σ away from training = FLAG for investigation
- >3σ away from training = CRITICAL, recommend retraining

### 2. Output Distribution Drift

**What it is**: Distribution of actual match outcomes changes

**Measurement**:
- Track win rate distribution of all players
- Compare to training distribution
- Look for systematic shifts

**Example**:
- Training: Average win rate across all players = 50% (random outcomes)
- Production: Average win rate = 52% (systematic player skill showing)
- Assessment: Might be OK (skill matters) or might be sampling bias

**Detection Method**:
```python
# Get rolling 7-day win rate distribution
production_win_rates = [observed outcomes from past 7 days]
production_mean = mean(production_win_rates)
training_mean = 0.50  # 50% win rate baseline

# Calculate z-score
z = (production_mean - training_mean) / training_std

# Alert if z > 2.0
```

**Actions**:
- >2σ shift: Investigate player behavior changes
- Persistent >1σ shift: Consider retraining

### 3. Convergence Rate Drift

**What it is**: Speed at which new player ratings stabilize changes

**Target Baseline**:
- Training: 52% of new players converge within ±30 points by game 20

**Production Calculation**:
```python
# Track new players registered in past week
new_players = get_new_players(last_week=True)

# For each new player, check if converged by game 20
converged_count = 0
for player in new_players:
    if player.games_played >= 20:
        rating_variance = max(player.ratings[-5:]) - min(player.ratings[-5:])
        if rating_variance < 30:
            converged_count += 1

# Calculate convergence rate
convergence_rate = converged_count / len(new_players) * 100

# Compare to baseline (52%)
drift_percent = abs(convergence_rate - 52.0)
if drift_percent > 10.0:
    alert("Convergence degraded by {drift_percent}%")
```

**Actions**:
- If <45%: CRITICAL - New players can't stabilize, investigate
- If <50%: WARNING - Degradation trending
- If <52% for >2 weeks: Consider retraining or initial rating adjustment

---

## Drift Detection Algorithm

### Step 1: Collect Training Baseline

During model training, compute statistics for all features:

```python
training_stats = {
    "rating_diff": {
        "mean": 0.5,
        "std": 149.8,
        "min": -700,
        "max": 700,
        "count": 50000,
    },
    "race_to": {
        "5": 0.15,  # 15% of matches are race-to-5
        "7": 0.25,
        "9": 0.40,
        "11": 0.20,
    },
    # ... more features
}
```

### Step 2: Monitor Production

As predictions arrive, track observed feature distributions:

```python
production_observation = {
    "rating_diff": observed_rating_diff,
    "race_to": observed_race_to,
    # ... more features
}
```

### Step 3: Calculate Drift Score

For continuous features (rating_diff):
```
z_score = |observed_value - training_mean| / training_std
```

For categorical features (race_to):
```
# Accumulate counts over time
production_counts = {"5": 100, "7": 200, "9": 300, "11": 150}
production_dist = {k: v / sum(production_counts.values()) for k, v in production_counts.items()}

# Compare distributions (Chi-square test)
chi_square = sum((obs - exp)^2 / exp for obs, exp in zip())
```

### Step 4: Alert if Drift Detected

```python
if z_score > 2.0:
    drift_event = {
        "timestamp": now(),
        "feature": "rating_diff",
        "severity": "MODERATE" if z_score < 3.0 else "SEVERE",
        "z_score": z_score,
        "observed": observed_value,
        "baseline_mean": training_mean,
        "baseline_std": training_std,
    }
    
    log_drift_event(drift_event)
    
    if severity == "SEVERE":
        notify_data_science_team(drift_event)
        recommend_retraining(drift_event)
```

---

## Interpreting Drift Events

### Example 1: Rating Difference Drift

**Event**:
```
Feature: rating_diff
Severity: SEVERE
Z-score: 2.8
Observed Mean: 15.2
Baseline Mean: 0.5
Baseline Std: 149.8
```

**Interpretation**: Player ratings are much more different than in training

**Likely Causes**:
- Match-making improved (better ratings now available)
- Skill gap tournament (tournaments pair disparate opponents)
- New player influx (high-rated vs low-rated matches)

**Action**:
- Review recent match data
- Check if tournament event happened
- Monitor if trend continues
- If persistent: Recommend retraining

### Example 2: Format Distribution Drift

**Event**:
```
Feature: race_to (format)
Type: Output Drift
9-ball training: 40%
9-ball production: 60% (+20%)
8-ball training: 20%
8-ball production: 5% (-15%)
```

**Interpretation**: Pool format popularity shifted

**Likely Causes**:
- Venue added 9-ball tables
- Tournament schedule changed
- Seasonal variation (different events)

**Action**:
- Verify with tournament director
- Check if 9-ball vs 8-ball models should be separate
- Monitor model performance by format
- Consider format-specific training

### Example 3: Convergence Rate Drift

**Event**:
```
New Player Convergence Rate (±30 pts by game 20)
Baseline: 52%
Current: 38% (-14%)
Trend: Declining over past 2 weeks
```

**Interpretation**: New players are taking longer to reach stable ratings

**Likely Causes**:
- Initial rating algorithm needs improvement
- Player pool is more heterogeneous
- Matchmaking is more random
- Fewer games played per player

**Action**:
- Analyze new player initial ratings vs actual skill
- Review rating update algorithm
- Check if initial rating seeding can be improved
- Recommend statistical review of model

---

## Dashboard & Monitoring

### Drift Summary Dashboard

```
DATA DRIFT SUMMARY (Past 7 Days)
└── 47 drift events detected
    ├── INPUT DRIFT: 32 events
    │   ├── rating_diff: 18 minor, 8 moderate, 6 severe
    │   └── race_to: 0 drift (stable)
    │
    ├── OUTPUT DRIFT: 12 events
    │   ├── player_win_rate: 12 warning level
    │   └── trend: Slightly elevated win rates (+0.8%)
    │
    └── CONVERGENCE DRIFT: 3 events
        └── convergence_rate: 48.5% (target: 52%, -3.5%)
```

### Query Examples

```sql
-- Recent drift events (past 7 days)
SELECT 
    drift_type,
    feature_name,
    severity,
    COUNT(*) as count,
    MAX(z_score) as max_z_score
FROM drift_events
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY drift_type, feature_name, severity
ORDER BY z_score DESC;

-- Severe drift events needing attention
SELECT 
    timestamp,
    feature_name,
    severity,
    z_score,
    observed_value,
    baseline_mean
FROM drift_events
WHERE severity = 'SEVERE'
  AND timestamp > NOW() - INTERVAL '24 hours'
ORDER BY timestamp DESC;

-- Trends in specific feature
SELECT 
    DATE(timestamp) as date,
    AVG(z_score) as avg_z_score,
    MAX(z_score) as max_z_score,
    COUNT(*) as event_count
FROM drift_events
WHERE feature_name = 'rating_diff'
  AND timestamp > NOW() - INTERVAL '30 days'
GROUP BY DATE(timestamp)
ORDER BY date DESC;
```

---

## Responding to Drift

### Decision Tree

```
Drift Detected?
├─ NO → Continue normal monitoring
├─ YES → Is severity SEVERE?
    ├─ NO (MINOR/MODERATE)
    │   ├─ Log event
    │   ├─ Monitor for trends
    │   └─ Continue normal retraining schedule
    │
    └─ YES (SEVERE)
        ├─ Alert data science team
        ├─ Is it a known event? (tournament, format change)
        │   ├─ YES → Document and track
        │   └─ NO → Investigate root cause
        │
        ├─ Check model performance
        │   ├─ Accuracy degraded? → Recommend retraining
        │   └─ Performance OK? → Monitor closely
        │
        └─ Check if persistent (>2 severe events in 24h)
            ├─ YES → Trigger immediate retraining
            └─ NO → Continue monitoring
```

---

## Drift Mitigation Strategies

### Short-term (No retraining)
1. Adjust prediction thresholds
2. Add feature engineering for new patterns
3. Manually weight predictions by feature distribution
4. Increase monitoring frequency

### Medium-term (Scheduled retraining)
1. Add retraining trigger: "If drift >3σ for >24 hours"
2. Collect new data subset reflecting current distribution
3. Retrain model on recent data
4. A/B test new model vs production

### Long-term (Architecture)
1. Implement online learning (continuously update model)
2. Build separate models for subgroups (8-ball vs 9-ball)
3. Improve initial rating seeding algorithm
4. Implement robust feature processing

---

## Advanced Monitoring

### Drift Prediction

Monitor leading indicators of drift:
- New tournament announcements (format changes)
- Player pool changes (new members, skill level)
- Rule changes that affect outcomes
- Venue openings/closings

### Anomaly Cascading

Link multiple drift events:
```
Tournament announced (9-ball)
  ↓
Format distribution shifts (+9-ball)
  ↓
Rating distribution changes (more disparate)
  ↓
Win rate distribution shifts
  ↓
Model accuracy may degrade
```

Plan interventions ahead of cascade.

### Seasonal Patterns

Store historical data to identify expected drift:
- Summer tournaments (different formats)
- Tournament season vs casual play
- New vs returning players at different times
- Skill level variations by season

---

## Implementation in Code

See:
- **Module**: `models/data_drift_detection.py`
- **Class**: `DriftDetector`
- **Method**: `analyze_input_feature()`, `analyze_output_distribution()`, `analyze_convergence_drift()`

```python
# Example usage
from models.data_drift_detection import DriftDetector

detector = DriftDetector(baseline=training_baseline)

# Check input feature
drift_event = detector.analyze_input_feature("rating_diff", 200.5)
if drift_event:
    print(f"Drift detected: {drift_event}")

# Check output distribution
win_rates = [0.45, 0.52, 0.48, 0.51, ...]
drift_event = detector.analyze_output_distribution(
    win_rates,
    training_win_rate_mean=0.50,
    training_win_rate_std=0.10
)

# Check convergence
drift_event = detector.analyze_convergence_drift(
    current_convergence=48.5,
    expected_convergence=52.0
)
```

---

## Alerts & Notifications

### Slack Message Format

```
🚨 DATA DRIFT DETECTED

Feature: rating_diff
Severity: SEVERE
Z-Score: 2.85

Observed Mean: 25.4
Expected Mean: 0.5 (std: 149.8)

Action Required:
- [ ] Investigate root cause
- [ ] Check model performance
- [ ] Consider immediate retraining

Data: https://[dashboard]/drift/latest
```

### Escalation

- **MINOR**: Log only, no alert
- **MODERATE**: Slack notification to #monitoring
- **SEVERE**: Page data science on-call + Slack notification

---

## Training for Team

### Monthly Drift Review

```
AGENDA:
1. Summary of drift events (5 min)
   - Total events: ?
   - Any SEVERE events? What were they?
   - Any trends?

2. Discussion of major drifts (10 min)
   - Why did they occur?
   - Was response adequate?
   - Any preventive measures?

3. System health (5 min)
   - Model accuracy: stable?
   - Convergence rate: stable?
   - Player satisfaction: any complaints?

4. Retraining assessment (5 min)
   - Do we need to retrain?
   - When should we schedule it?
```

---

## Related Documents

- [SLA_DEFINITIONS.md](SLA_DEFINITIONS.md) - Data drift SLA targets
- [models/data_drift_detection.py](/models/data_drift_detection.py) - Implementation code
- [backend/sla_tracking.py](/backend/sla_tracking.py) - SLA tracking (includes drift alerting)
- [MONITORING_RUNBOOK.md](MONITORING_RUNBOOK.md) - Day-to-day monitoring

---

**Last Updated**: 2026-02-16  
**Owner**: Data Science Team  
**Review Frequency**: Quarterly
