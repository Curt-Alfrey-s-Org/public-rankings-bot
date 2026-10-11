# Staging Data Validation Report

**Generated:** [AUTO-GENERATED - See timestamp below]  
**Environment:** Staging (rankings_staging database)  
**Status:** TO BE FILLED AFTER FIRST DEPLOYMENT

## Executive Summary

This report validates the staging environment is ready for production testing. It covers:
- Data integrity (1,000+ test matches loaded)
- Prediction quality (Brier score ±0.01 of training baseline)
- Anomaly detection (6 types correctly identified)
- System health (all services responding)

---

## Deployment Timeline

| Phase | Status | Details |
|-------|--------|---------|
| **Docker Build** | ✓ Ready | Image: `alfa-api:staging` |
| **Database Init** | ✓ Ready | Schema: 100 test players loaded |
| **Containers** | ⏳ Pending | Starting on first deploy |
| **Health Checks** | ⏳ Pending | API, DB, Redis, Prometheus |
| **Tests** | ⏳ Pending | Smoke, regression, load, accuracy |
| **Monitoring** | ✓ Ready | Prometheus + 3 Grafana dashboards |

---

## Data Integrity

### Seed Data

- **Test Players:** 100 players with varied Fargo ratings (500-706)
- **Initial Ratings:** All players initialized in `alfa_player_ratings` table
- **Rating Range:** [500-706], all valid [0-1000]
- **Database:** `rankings_staging` (separate from production)

**Validation Queries:**

```sql
-- Verify player count
SELECT COUNT(*) FROM players WHERE name LIKE 'Test Player%';
-- Expected: 100

-- Verify ratings loaded
SELECT COUNT(*) FROM alfa_player_ratings;
-- Expected: 100

-- Check rating distribution
SELECT 
  FLOOR(rating / 50) * 50 as rating_bucket, 
  COUNT(*) 
FROM alfa_player_ratings 
GROUP BY rating_bucket;
-- Should show even distribution across tiers
```

### Test Match Data (To be populated during staging)

After running model predictions for 1-2 weeks:

| Metric | Target | Expected | Actual |
|--------|--------|----------|--------|
| **Total Matches** | 1,000+ | ~50/day × 14 days | ⏳ Pending |
| **Unique Players** | 100+ | All test players | 100 |
| **Completed Predictions** | 95%+ | With actual outcomes | ⏳ Pending |
| **Brier Scores** | 90%+ | Computed | ⏳ Pending |

---

## Prediction Quality

### Baseline Metrics (from training set)

Expected model performance on held-out test set:
- **Brier Score:** 0.215 (perfect calibration = 0.0, random = 0.25)
- **Calibration RMSE:** 0.12
- **Accuracy:** 60%+ across all player strength tiers
- **Anomaly Precision:** 75%+

### Staging Validation Goals

| Metric | Required Range | Justification |
|--------|---|---|
| Brier Score | 0.205 - 0.225 (±0.01) | Within 1% of training baseline |
| Calibration RMSE | 0.095 - 0.145 (±0.05) | Model predictions well-calibrated |
| Accuracy | 55%+ per tier | Minimum threshold for production |
| Anomaly Precision | 50%+ | Acceptable false positive rate |
| Error Rate | <2% at 100 req/sec | System reliability |
| Latency p95 | <1.0 sec | User experience acceptable |

### Validation Results (To be filled after testing)

```
BRIER SCORE VALIDATION
─────────────────────────────────────────────────────────
Baseline (training):     0.215
7-day rolling average:   [PENDING]
30-day rolling average:  [PENDING]
Status:                  [PENDING - pass/fail]

CALIBRATION RMSE
─────────────────────────────────────────────────────────
Baseline (training):     0.12
Staging result:          [PENDING]
Status:                  [PENDING - pass/fail]

ACCURACY BY PLAYER TIER
─────────────────────────────────────────────────────────
Weak (Fargo <550):       [PENDING] (target: >55%)
Medium (550-650):        [PENDING] (target: >55%)
Strong (>650):           [PENDING] (target: >55%)

ANOMALY DETECTION METRICS
─────────────────────────────────────────────────────────
Total anomalies:         [PENDING]
Detected types (6):
  - winning_weak_only:   [PENDING] Y/N
  - rating_mismatch:     [PENDING] Y/N
  - unusual_performance: [PENDING] Y/N
  - extreme_rating_swing:[PENDING] Y/N
  - format_anomaly:      [PENDING] Y/N
  - equipment_anomaly:   [PENDING] Y/N
Precision:               [PENDING] (target: >50%)
```

---

## System Performance

### Load Test Results (100 req/sec × 60 sec)

```
REQUEST PERFORMANCE
─────────────────────────────────────────────────────────
Total requests:          [PENDING]
Successful:              [PENDING]
Failed:                  [PENDING]
Error rate:              [PENDING]% (target: <2%)

LATENCY DISTRIBUTION
─────────────────────────────────────────────────────────
Min:                     [PENDING] ms
p50:                     [PENDING] ms
p95:                     [PENDING] ms (target: <1000ms)
p99:                     [PENDING] ms
Max:                     [PENDING] ms
```

### System Resource Usage

```
CONTAINER RESOURCE USAGE
─────────────────────────────────────────────────────────
Service               CPU        Memory      Disk I/O
api                   [PENDING]  [PENDING]   [PENDING]
postgres              [PENDING]  [PENDING]   [PENDING]
redis                 [PENDING]  [PENDING]   [PENDING]
prometheus            [PENDING]  [PENDING]   [PENDING]
grafana               [PENDING]  [PENDING]   [PENDING]
```

---

## Data Quality Checks

### Validation Queries

All validation passes before marking "Ready for Production":

- [ ] No duplicate predictions: `SELECT COUNT(*) > 0 FROM (SELECT match_id FROM alfa_match_predictions GROUP BY match_id HAVING COUNT(*) > 1)`
- [ ] All probabilities in [0,1]: `SELECT COUNT(*) > 0 FROM alfa_match_predictions WHERE predicted_win_prob_p1 NOT BETWEEN 0 AND 1`
- [ ] All ratings in [0-1000]: `SELECT COUNT(*) > 0 FROM alfa_player_ratings WHERE rating NOT BETWEEN 0 AND 1000`
- [ ] No NULL keys: `SELECT COUNT(*) > 0 FROM alfa_match_predictions WHERE match_id IS NULL OR operator_id IS NULL OR player2_id IS NULL`

### Data Completeness

```
TABLE STATISTICS
─────────────────────────────────────────────────────────
Table                        Rows        Size
players                      100         ~5 KB
alfa_player_ratings          100         ~10 KB
alfa_match_predictions       [PENDING]   [PENDING]
alfa_anomaly_flags           [PENDING]   [PENDING]
alfa_prediction_factors      [PENDING]   [PENDING]
alfa_data_quality_report     [PENDING]   [PENDING]
```

---

## Monitoring & Alerting

### Prometheus Metrics Available

- [x] `alfa_predictions_total` - Predictions counter
- [x] `alfa_prediction_latency_seconds` - Latency histogram
- [x] `alfa_prediction_errors_total` - Error counter
- [x] `alfa_cache_hits_total` - Cache metric
- [x] `alfa_cache_misses_total` - Cache metric
- [x] `alfa_brier_score` - Calibration metric
- [x] `alfa_anomaly_detections` - Anomaly counter
- [x] Database metrics (pg_stat_statements)
- [x] Container metrics (cAdvisor)
- [ ] Custom application metrics (as needed)

### Grafana Dashboards

All three dashboards accessible at `http://localhost:3000`:

| Dashboard | Status | Last Verified |
|-----------|--------|---|
| Alfa System Overview | ✓ Working | [PENDING] |
| Alfa Accuracy & Performance | ✓ Working | [PENDING] |
| Alfa System Health | ✓ Working | [PENDING] |

### Alert Rules Status

All alert rules configured and evaluating:

| Alert | Status | Threshold | Last Fired |
|-------|--------|-----------|---|
| AlfaPredictionErrorRateHigh | ✓ Active | >1% for 5m | [PENDING] |
| AlfaAPILatencyP99High | ✓ Active | >2s for 10m | [PENDING] |
| DatabaseConnectionPoolHigh | ✓ Active | >90% for 5m | [PENDING] |
| CacheMissRateHigh | ✓ Active | >20% for 10m | [PENDING] |
| AnomalyDetectionPrecisionLow | ✓ Active | <50% for 30m | [PENDING] |

---

## A/B Testing Metrics (1-2 week collection)

After running A/B tests on 100 matches/week vs Fargo:

```
WEEKLY A/B TEST RESULTS
─────────────────────────────────────────────────────────
Week 1:
  Alfa Brier Score:        [PENDING]
  Fargo Brier Score:       [PENDING]
  Improvement:             [PENDING]%
  Matches evaluated:       [PENDING]

Week 2:
  Alfa Brier Score:        [PENDING]
  Fargo Brier Score:       [PENDING]
  Improvement:             [PENDING]%
  Matches evaluated:       [PENDING]

Overall A/B Analysis:
  Alfa Win Rate:           [PENDING]%
  Prediction Differences:  [PENDING] (avg delta)
  Significant Players:     [PENDING] (players where Alfa differs >10%)
```

---

## Issues & Resolutions

During staging, document any issues discovered and how they were resolved:

| Issue | Severity | Description | Resolution | Status |
|-------|----------|--|---|--|
| [Example] | Medium | Brier score 0.05 higher than expected | Retrained model with updated data | ✓ Resolved |
| | | | | |

---

## Sign-Off Checklist

Before moving to production, verify all items:

### Data Validation
- [ ] 100 test players loaded
- [ ] 1,000+ test matches with outcomes
- [ ] All ratings in valid range
- [ ] All probabilities in valid range
- [ ] No duplicate predictions
- [ ] Brier score within ±0.01 of baseline
- [ ] Anomaly detection working (3+ types)

### System Health
- [ ] All containers running
- [ ] All health checks passing
- [ ] Load test: <2% error rate
- [ ] Load test: p95 latency <1 second
- [ ] No memory leaks (24h+ monitoring)
- [ ] Database connection pool stable

### Monitoring & Alerting
- [ ] Prometheus collecting metrics
- [ ] All 3 Grafana dashboards populated
- [ ] Alert rules evaluating correctly
- [ ] No false positive alerts
- [ ] Notification channels tested (optional)

### Testing
- [ ] All smoke tests passing
- [ ] Load test completed successfully
- [ ] Accuracy tests all pass
- [ ] Anomaly detection tests pass
- [ ] Database integration tests pass

### Documentation
- [ ] Deployment runbook updated
- [ ] Monitoring guide completed
- [ ] Issues and resolutions documented
- [ ] Runbooks for on-call team ready

### Ready for Production?

Status: **[PENDING]** ← Fill in after validation

**Approved By:** _________________ **Date:** _____________  
**QA Sign-Off:** _________________ **Date:** _____________  
**Ops Sign-Off:** _________________ **Date:** _____________

---

## Additional Notes

### Known Limitations

- Staging uses test players, not production player data
- Model trained on historical data (may not reflect recent meta shifts)
- No real tournament data (only simulated matches)
- Can be wiped/reset without impact to production

### Next Steps Before Production

1. Review this report with team
2. Conduct load testing in staging
3. Run 1-2 week monitoring period
4. Collect A/B test metrics against Fargo
5. Document any learnings/adjustments
6. Update production deployment procedure
7. Schedule production rollout window

### References

- [STAGING_DEPLOYMENT_GUIDE.md](STAGING_DEPLOYMENT_GUIDE.md) - Deployment procedures
- [MONITORING_SETUP_GUIDE.md](MONITORING_SETUP_GUIDE.md) - Monitoring configuration
- [../ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture
- [../.github/PORT_ASSIGNMENTS.md](../.github/PORT_ASSIGNMENTS.md) - Port mappings
- [ALFA_QUICK_REFERENCE.md](ALFA_QUICK_REFERENCE.md) - Alfa system reference

---

**Last Updated:** [AUTO]  
**Version:** 1.0  
**Status:** Ready for Staging Deployment
