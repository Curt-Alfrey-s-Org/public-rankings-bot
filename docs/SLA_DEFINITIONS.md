# SLA Definitions for Alfa Rating System

## Overview

Service Level Agreements (SLAs) define the performance targets and commitments for the Alfa rating production system. These targets are measured continuously and breaches are tracked and reported.

---

## 1. AVAILABILITY SLA

**Target: 99.9% uptime** (max 43.2 minutes of downtime per month)

### Definition
- Measured by health check endpoint: `GET /api/health/alfa` → `status: healthy`
- Checks performed every 5 minutes
- Period: Calendar month

### Thresholds
- **Target Availability**: 99.9%
- **Warning Threshold**: 99.5% (7.2 hours downtime)
- **Critical Threshold**: 99.0% (14.4 hours downtime)

### Exclusions
- Maintenance windows (120 minutes/month pre-announced)
- DDoS attacks, network outages beyond our control
- Client-side issues (browser cache, network interruption)

### Calculation
```
Availability = (Healthy checks / Total checks) * 100
             = (287 / 288) * 100
             = 99.65%
```

### Alert Rules
- If availability drops below 99.0% for >30 consecutive minutes → CRITICAL alert
- If availability drops below 99.5% for >60 consecutive minutes → WARNING alert

---

## 2. LATENCY SLA

### Response Time Percentiles

| Percentile | Target | Warning | Critical |
|------------|--------|---------|----------|
| p50 (median) | <100ms | <200ms | <300ms |
| p95 | <500ms | <750ms | <1000ms |
| p99 | <2000ms | <3000ms | <5000ms |

### Definition
- Measured from API request received to response sent
- Includes database query time, model inference, serialization
- Excludes network transmission time
- Measured on prediction endpoint: `POST /api/predictions`

### Calculation
- Collect latency for all requests in 1-hour window
- Calculate percentiles using NIST method
- Report p50, p95, p99 for each hour

### Exclusions
- Client timeout settings
- Network latency to client
- Browser rendering time

### Alert Rules
- If p99 latency > 5 seconds for >10 consecutive minutes → CRITICAL
- If p99 latency > 3 seconds for >30 consecutive minutes → WARNING
- If p95 latency > 1 second consistently → Monitor closely

---

## 3. ACCURACY SLA

### Brier Score (Primary Metric)

**Target**: Brier score < 0.20 (within ±5% of training baseline)

**Definition**:
- Brier score = mean((predicted_prob - actual_outcome)^2)
- Measured on all predictions where outcome is known
- Lower is better (0 is perfect, 1 is worst)
- Baseline: 0.20 from model training on representative data

**Calculation**:
```
Daily Brier = mean([(p1 - o1)^2, (p2 - o2)^2, ...])

where p_i = predicted probability (0-1)
      o_i = actual outcome (0 or 1)
```

**Thresholds**:
- **Target**: Brier < 0.20
- **Warning**: Brier 0.20-0.25 (5-25% worse than baseline)
- **Critical**: Brier > 0.25 (>25% worse than baseline)

### Related Metrics

**Accuracy (Classification)**
- Target: >68% (same as training)
- Calculated: (# correct predictions) / (# total predictions)

**Calibration RMSE**
- Target: <0.10
- Measures: How well predicted probabilities match actual probabilities
- Calculated by comparing predicted prob to bin accuracy

**AUC-ROC (Discrimination)**
- Target: >0.72
- Measures: Model's ability to distinguish winners from losers
- Calculation: Area under ROC curve

### Comparison to Baseline
All accuracy metrics are compared to training set performance:

| Metric | Training Baseline | Production Target | Warning | Critical |
|--------|------------------|------------------|---------|----------|
| Brier | 0.200 | <0.200 | 0.200-0.250 | >0.250 |
| Accuracy | 0.681 | >0.681 | 0.64-0.681 | <0.640 |
| AUC-ROC | 0.720 | >0.720 | 0.70-0.720 | <0.700 |
| Calibration RMSE | 0.085 | <0.085 | 0.085-0.100 | >0.100 |

### Monitoring
- Daily calculation of all metrics
- Weekly comparison to baseline
- Monthly SLA report generation
- Alert if metrics degrade >5% for >24 hours

---

## 4. ANOMALY DETECTION SLA

### Sandbagging Detection

**Purpose**: Identify players exhibiting sandbagging behavior (intentionally losing rated matches)

**Metrics**:

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| Precision | >50% | 40-50% | <40% |
| Recall | >70% | 60-70% | <60% |
| F1-Score | >0.58 | 0.52-0.58 | <0.52 |
| False Positive Rate | <20% | 20-25% | >25% |

### Definitions

**Precision**: Of all players flagged as sandbagging, % that actually exhibited behavior
- Formula: TP / (TP + FP)
- Target: 50% (1 in 2 flagged players is correct)

**Recall**: Of all players actually sandbagging, % that were flagged
- Formula: TP / (TP + FN)
- Target: 70% (catch 7 out of 10 sandbagging players)

**F1-Score**: Harmonic mean of Precision and Recall
- Formula: 2 * (P * R) / (P + R)
- Balances precision and recall

### Measurement
- Collect all predictions flagged as anomalous
- Track actual outcome (did player sandbagging behavior occur?)
- Validate after 30 days (sufficient time to observe outcome)
- Calculate metrics daily, report weekly

### Alert Rules
- If precision < 30% → CRITICAL (too many false flags)
- If recall < 50% → WARNING (missing too many actual incidents)
- If false positive rate > 25% → WARNING (bothering innocent players)

---

## 5. COLD-START PERFORMANCE SLA

### New Player Rating Convergence

**Target**: 52% of new players converge to stable rating within ±30 points by game 20

### Definitions

**Convergence**: Rating stabilizes (variance < 30 points over last 5 games)

**Metrics**:

| Threshold | Target % | Warning % | Critical % |
|-----------|----------|-----------|-----------|
| ±20 points | 40% | 30-40% | <30% |
| ±30 points | 52% | 45-52% | <45% |
| ±50 points | 80% | 75-80% | <75% |

**Games Measured**: First 20 rated games for each new player

### Calculation
```
Convergence rate = (# players converged within threshold) / (# total new players)

Example:
- 100 new players tracked
- 45 converged within ±30 pts by game 20
- Convergence rate = 45% (target: 52%)
```

### Monitoring
- Continuous tracking in `cold_start_tracking` table
- Report weekly convergence rates
- Alert if <50% for >2 consecutive weeks

### Implications
- Shows how well the rating system works for new players
- Affects user experience (new players should feel ratings are fair)
- If degraded: May need initial rating adjustment algorithm

---

## 6. ERROR RATE SLA

**Target**: <0.1% error rate (99.9% success)

### Definition
- Errors = HTTP 5xx responses + exceptions logged as ERROR
- Success = HTTP 2xx responses without exceptions
- Measured: Hourly averaging over 1-month window

### Thresholds
- **Target**: <0.1% (1 error per 1000 requests)
- **Warning**: 0.5% (5 errors per 1000 requests)
- **Critical**: 1.0% (10 errors per 1000 requests)

### Exclusions
- 4xx errors (client fault, not server fault)
- Errors in background jobs (cached/retried)
- Rate-limited requests

### Calculation
```
Error rate = (# errors) / (# total requests) * 100
           = (75 errors) / (100,000 requests) * 100
           = 0.075%
```

### Alert Rules
- If error rate > 1.0% for >continuous 10 minutes → CRITICAL
- If error rate > 0.5% for >continuous 30 minutes → WARNING
- If specific endpoint error > 5% → Investigate endpoint

---

## 7. DATA QUALITY SLA

### Data Drift Detection

**Target**: <2 standard deviations drift in key feature distributions

### Key Features Monitored
1. **rating_diff** (difference in player ratings)
   - Should have normal distribution
   - Mean ~0, std ~150

2. **race_to** (match race-to value)
   - Categorical: 5, 7, 9, 11, ...
   - Distribution by format should remain stable

3. **player_win_rate** (actual outcome distribution)
   - Should match training distribution
   - If shifted: May indicate data quality or format change

### Alert Actions
- If drift detected → Auto-flag for investigation
- Notify data science team
- Check for format/rule changes
- Consider triggering model retraining

---

## SLA Reporting

### Monthly Report Format
```
# SLA Report for [MONTH]

## Summary
- Availability: [%] (Target: 99.9%)
- Latency p95: [ms] (Target: <500ms)
- Brier Score: [value] (Target: <0.20)
- Anomaly Precision: [%] (Target: >50%)

## Breaches
[List of all SLA breaches]

## Trends
[Month-over-month comparison]

## Recommendations
[Actions for next month]
```

### Escalation

| Metric | Action |
|--------|--------|
| Critical threshold breached | Immediate alert + incident response |
| Warning threshold breached for >30 min | Escalate to team lead |
| Trend degrading over 2+ weeks | Schedule strategy meeting |
| Repeated breach >2x/month | Investigate root cause, plan fix |

---

## SLA Review & Adjustment

### Quarterly Review
- Compare actual performance to targets
- Are targets realistic?
- Have service characteristics changed?
- Update community if needed

### Annual Review (Q4)
- Full SLA audit
- Compare to industry standards
- Review tool/process for measurement
- Update documentation

### Adjustment Criteria
- If consistently exceeding target → May keep higher bar
- If consistently missing target → Investigate why (need investment?)
- If target no longer relevant → Update standards
- If new metrics needed → Add to tracking

---

## Related Documents

- [MONITORING_RUNBOOK.md](MONITORING_RUNBOOK.md) - How to monitor SLAs daily
- [INCIDENT_RESPONSE_PLAN.md](INCIDENT_RESPONSE_PLAN.md) - How to respond to breaches
- [ALFA_MAINTENANCE_GUIDE.md](ALFA_MAINTENANCE_GUIDE.md) - Maintenance procedures
- [backend/sla_tracking.py](/backend/sla_tracking.py) - SLA tracking code

---

**Last Updated**: 2026-02-16  
**Next Review**: 2026-05-16 (Quarterly)  
**Owner**: Data Science Lead  
**Approval**: CTO
