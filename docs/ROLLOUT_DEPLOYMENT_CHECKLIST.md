# Production Rollout Strategy - Integration Checklist

**Document Version:** 2.0.0  
**Last Updated:** 2026-02-16  
**Implementation Status:** READY FOR PRODUCTION  

---

## Pre-Deployment Checklist

All items must be checked before commencing Phase 1 deployment.

### Code & Configuration

- [x] Feature flag manager implemented (`models/feature_flag_manager.py`)
  - [x] Load/reload from JSON
  - [x] Thread-safe operations
  - [x] Update validation
  - [x] Change audit trail
  - [x] Phase prerequisites validation

- [x] Rollout manager implemented (`models/rollout_manager.py`)
  - [x] get_ratings_method() decision logic
  - [x] should_use_alfa() stratification algorithm
  - [x] record_rollout_metrics() for tracking
  - [x] set_user_preference() for opt-in (Phase 1-2)
  - [x] get_rollout_metrics() for dashboards

- [x] Feature flag middleware (`api/middleware/feature_flags.py`)
  - [x] Inject managers into request.state
  - [x] Extract user ID from auth
  - [x] Calculate use_alfa decision
  - [x] Log feature flag decisions

- [x] Feature flags configuration (`config/feature_flags.json`)
  - [x] alfa_rating_enabled (percentage)
  - [x] alfa_predictions_in_api (boolean)
  - [x] alfa_anomaly_detection_enabled (boolean)
  - [x] alfa_vs_fargo_comparison (percentage)
  - [x] alfa_admin_dashboard_enabled (boolean)
  - [x] Phase schedule metadata
  - [x] Prerequisites by phase

### Admin API

- [x] Admin endpoints in `api/routes/admin.py`
  - [x] GET /api/admin/rollout/status - Current phase and metrics
  - [x] PUT /api/admin/rollout/feature-flags/{flag_name} - Update flags
  - [x] GET /api/admin/rollout/all-flags - View all flags
  - [x] POST /api/admin/rollout/rollback - Emergency rollback
  - [x] GET /api/admin/rollout/change-log - Audit trail
  - [x] POST /api/admin/rollout/validate-phase - Validate prerequisites

### Database

- [x] Database migrations created (`database/migrations/rollout_tables.sql`)
  - [x] rollout_tracking table with proper schema
  - [x] Indexes for fast queries (timestamp, tournament_id, match_id, phase)
  - [x] v_rollout_metrics_by_percentage view
  - [x] v_rollout_metrics_hourly view
  - [x] v_rollout_anomalies view
  - [x] sp_calculate_phase_metrics stored procedure

- [x] Migration applied to target database
  - [x] Table created successfully
  - [x] Views created successfully
  - [x] Stored procedures created successfully
  - [x] Indexes created successfully
  - [ ] Data verified in production DB (after first deployment)

### Middleware Integration

- [x] Middleware registered in FastAPI app
  ```python
  from api.middleware.feature_flags import FeatureFlagMiddleware
  app.add_middleware(FeatureFlagMiddleware)
  ```

- [x] Request handlers use feature flag context
  - [ ] Rankings API uses request.state.use_alfa
  - [ ] Matches API uses request.state.rollout_manager
  - [ ] Other APIs check request.state features as needed

### Deployment Scripts

- [x] Deploy script (`scripts/rollout_alfa.sh`)
  - [x] deploy --phase X for phase transitions
  - [x] validate --phase X for prerequisites
  - [x] status for current phase
  - [x] schedule for timeline
  - [x] metrics for success criteria

- [x] Rollback script (`scripts/rollback_alfa.sh`)
  - [x] --phase X for targeted rollback
  - [x] --auto for automatic rollback
  - [x] --status for rollback history
  - [x] --list for previous checkpoints

### Documentation

- [x] Production Rollout Guide (`docs/PRODUCTION_ROLLOUT_GUIDE.md`)
  - [x] Complete timeline (Phases 0-5)
  - [x] Success criteria for each phase
  - [x] Detailed procedures
  - [x] Metrics and monitoring guidance
  - [x] Rollback procedures

- [x] Rollout Runbook (`docs/ROLLOUT_RUNBOOK.md`)
  - [x] Week-by-week checklist
  - [x] Daily monitoring procedures
  - [x] Escalation procedures

- [x] Feature Flags Reference (`docs/FEATURE_FLAGS_REFERENCE.md`)
  - [x] All flag definitions
  - [x] Enabled phases for each flag
  - [x] Dependencies between flags
  - [x] Usage examples

- [x] Rollout Implementation Guide (`docs/ROLLOUT_IMPLEMENTATION_GUIDE.md`)
  - [x] System architecture
  - [x] Component descriptions
  - [x] Admin endpoint reference
  - [x] Database schema
  - [x] Integration checklist

- [x] Admin Quick Reference (`docs/ROLLOUT_ADMIN_QUICK_REFERENCE.md`)
  - [x] Status checks
  - [x] Weekly checklist
  - [x] Emergency procedures
  - [x] Phase reference
  - [x] Communication templates

### Monitoring

- [x] Grafana dashboards created
  - [x] rollout_metrics.json - Main rollout dashboard
  - [x] alfa_health.json - System health
  - [x] alfa_accuracy.json - Prediction accuracy
  - [x] alfa_overview.json - High-level overview

- [x] Prometheus metrics configured
  - [x] Match count by phase
  - [x] Brier score comparison
  - [x] Error rate tracking
  - [x] Anomaly detection metrics

- [x] Alerting rules configured
  - [x] Brier > threshold alert
  - [x] Error rate > 1% alert
  - [x] Anomaly detection alerts
  - [x] Database connectivity alert

### Testing

- [ ] Unit tests for feature flag manager
  - [ ] Load/reload operations
  - [ ] Flag update validation
  - [ ] Phase validation logic
  - [ ] Change logging

- [ ] Unit tests for rollout manager
  - [ ] get_ratings_method() logic
  - [ ] Stratification algorithm
  - [ ] User preference handling
  - [ ] Metrics recording

- [ ] Integration tests
  - [ ] Middleware injects state correctly
  - [ ] API endpoints work with auth
  - [ ] Database writes/reads successful
  - [ ] Feature flag updates propagate

- [ ] Smoke tests in staging
  - [ ] Advance through all phases
  - [ ] Verify metrics collection
  - [ ] Test rollback procedures
  - [ ] Validate monitoring data

### Team Readiness

- [ ] Admin team trained
  - [ ] How to check status
  - [ ] How to advance phases
  - [ ] Emergency rollback procedures
  - [ ] Monitoring dashboard usage
  - [ ] Escalation procedures

- [ ] Support team briefed
  - [ ] Expected user impact per phase
  - [ ] Common issues and solutions
  - [ ] Escalation contacts
  - [ ] Communication templates

- [ ] DevOps team prepared
  - [ ] Canary/gradual rollout plan
  - [ ] Monitoring setup verified
  - [ ] Backup procedures ready
  - [ ] Runbook reviewed

---

## Phase 0: Pre-launch (Before deployment)

**Objective:** Final validation before public rollout

### Infrastructure Validation

- [ ] API service health check
  - [ ] Endpoints responding normally
  - [ ] Database connectivity confirmed
  - [ ] Feature flag file accessible
  - [ ] Middleware loads without errors

- [ ] Create rollout directory
  ```bash
  mkdir -p /path/to/project/rollout/checkpoints
  ```

- [ ] Create initial checkpoint
  ```bash
  ./scripts/rollout_alfa.sh checkpoint
  ```

### Dry Run - Test Phase 1 Deployment

- [ ] Execute dry-run deployment
  ```bash
  ./scripts/rollout_alfa.sh validate --phase 1
  ```
  Expected: "Phase 1 prerequisites met"

- [ ] Manually update feature flag to 10%
  ```bash
  curl -X PUT -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"flag_name": "alfa_rating_enabled", "value": 10}' \
    https://your-domain/api/admin/rollout/feature-flags/alfa_rating_enabled
  ```

- [ ] Verify status updated
  ```bash
  curl -H "Authorization: Bearer $TOKEN" \
    https://your-domain/api/admin/rollout/status
  ```
  Expected: Phase 1 (10%), Silent Canary

- [ ] Rollback to 0%
  ```bash
  curl -X POST -H "Authorization: Bearer $TOKEN" \
    https://your-domain/api/admin/rollout/rollback
  ```

- [ ] Verify rollback successful
  ```bash
  curl -H "Authorization: Bearer $TOKEN" \
    https://your-domain/api/admin/rollout/status
  ```
  Expected: Phase 0 (0%), Pre-launch

### Monitoring Setup

- [ ] Verify Grafana dashboards load
  - [ ] Navigate to rollout_metrics dashboard
  - [ ] Verify all panels load (no errors)
  - [ ] Test time range selectors

- [ ] Test alert notifications
  - [ ] Send test alert to on-call team
  - [ ] Verify Slack/PagerDuty notifications
  - [ ] Verify escalation path

### Admin Training

- [ ] Walk through admin dashboard
- [ ] Practice status checks
- [ ] Practice phase advancement
- [ ] Practice emergency rollback
- [ ] Review communication templates

---

## Phase 1: Silent Canary (Week 1-2)

**Rollout:** 10% of tournaments  
**Duration:** 2 weeks  

### Week 1: Days 1-3 - Initial Deployment

- [ ] **Day 1: Deploy to Production**
  ```bash
  ./scripts/rollout_alfa.sh deploy --phase 1
  # Or via API:
  curl -X PUT ... -d '{"flag_name": "alfa_rating_enabled", "value": 10}' ...
  ```

  Actions:
  - [ ] Update feature flag to 10%
  - [ ] Send notification to team
  - [ ] Monitor dashboard for 1 hour
  - [ ] No user-facing changes

- [ ] **Day 1-3: Monitor Base Metrics**
  - [ ] Check Grafana rollout_metrics dashboard
  - [ ] Verify match count increasing
  - [ ] Confirm no errors in logs
  - [ ] Monitor Brier score trend
  - [ ] Check anomaly detection metrics

### Week 1: Days 4-7 - Stability Validation

- [ ] **Daily checks:**
  - [ ] Morning: Check dashboard status
  - [ ] Check error logs
  - [ ] Verify database size growth
  - [ ] Confirm predictions being recorded

- [ ] **Check success criteria (Day 7):**
  - [ ] Brier(Alfa) < 0.30? ✓
  - [ ] Error rate < 1%? ✓
  - [ ] No critical anomalies? ✓
  - [ ] System stable? ✓

### Week 2: Days 8-14 - Extended Monitoring

- [ ] **Continue daily monitoring**
  - [ ] Focus on Brier score stability
  - [ ] Monitor error rates
  - [ ] Track anomaly patterns

- [ ] **End of Week 2 Decision:**
  - [ ] Review all success criteria
  - [ ] Get approval from stakeholders
  - [ ] Plan Phase 2 deployment

---

## Phase 2: Shadow Mode (Week 3-4)

**Rollout:** 25% of tournaments  
**Duration:** 2 weeks  

### Prerequisite: Validate Phase 2

```bash
curl -X POST ... -d '{"phase": 2}' .../validate-phase
# Expected: "Phase 2 prerequisites met"
```

### Week 3: Deploy to 25%

- [ ] **Day 1: Deploy Phase 2**
  ```bash
  ./scripts/rollout_alfa.sh deploy --phase 2
  # Or:
  curl -X PUT ... -d '{"flag_name": "alfa_rating_enabled", "value": 25}' ...
  # Enable predictions in API:
  curl -X PUT ... -d '{"flag_name": "alfa_predictions_in_api", "value": true}' ...
  ```

  Actions:
  - [ ] Update feature flag to 25%
  - [ ] Enable predictions API flag
  - [ ] Send notification
  - [ ] Monitor for 1 hour

- [ ] **Week 3: Monitor Stability**
  - [ ] Daily dashboard checks
  - [ ] Verify API returning both predictions
  - [ ] Check user opt-in rate (via logs)
  - [ ] Monitor Brier score trend

### Week 4: Evaluate Phase 2

- [ ] **End of Week 4 Decision Point:**
  - [ ] Brier(Alfa) < 0.27? ✓
  - [ ] No degradation of Fargo? ✓
  - [ ] User feedback positive? ✓
  - [ ] Ready to advance? ✓

- [ ] **If issues found:**
  - [ ] Analyze failure cause
  - [ ] Determine if rollback needed
  - [ ] Execute rollback if necessary
  - [ ] Investigate root cause

---

## Phase 3: Experimentation (Week 5-6)

**Rollout:** 50% of tournaments  
**Duration:** 2 weeks  
**New Feature:** Display both in UI  

### Prerequisites

```bash
curl -X POST ... -d '{"phase": 3}' .../validate-phase
```

### Week 5: Deploy to 50%

- [ ] **Day 1: Deploy Phase 3**
  ```bash
  curl -X PUT ... -d '{"flag_name": "alfa_rating_enabled", "value": 50}' ...
  curl -X PUT ... -d '{"flag_name": "alfa_vs_fargo_comparison", "value": 50}' ...
  ```

  Actions:
  - [ ] Update feature flag to 50%
  - [ ] Enable comparison flag
  - [ ] Update frontend to show both ratings
  - [ ] Send communication

- [ ] **Week 5: Monitor A/B Test**
  - [ ] Daily dashboard checks
  - [ ] Monitor user reactions
  - [ ] Track satisfaction surveys
  - [ ] Watch Brier score movements

### Week 6: A/B Test Results

- [ ] **End of Week 6 Analysis:**
  - [ ] Brier(Alfa) ≥ Brier(Fargo)? ✓
  - [ ] User satisfaction > 80%? ✓
  - [ ] Statistically significant improvement? ✓
  - [ ] Safe to expand? ✓

---

## Phase 4: Controlled Expansion (Week 7-8)

**Rollout:** 75% of tournaments  
**Duration:** 2 weeks  
**New Feature:** Enable anomaly detection  

### Prerequisites

```bash
curl -X POST ... -d '{"phase": 4}' .../validate-phase
```

### Week 7: Deploy to 75%

- [ ] **Day 1: Deploy Phase 4**
  ```bash
  curl -X PUT ... -d '{"flag_name": "alfa_rating_enabled", "value": 75}' ...
  curl -X PUT ... -d '{"flag_name": "alfa_anomaly_detection_enabled", "value": true}' ...
  curl -X PUT ... -d '{"flag_name": "alfa_admin_dashboard_enabled", "value": true}' ...
  ```

  Actions:
  - [ ] Update feature flag to 75%
  - [ ] Enable anomaly detection
  - [ ] Enable admin dashboard
  - [ ] Send notification

- [ ] **Week 7: Monitor Anomalies**
  - [ ] Daily dashboard checks
  - [ ] Review detected anomalies
  - [ ] Check false positive rate
  - [ ] Admin review of flags

### Week 8: Anomaly Detection Review

- [ ] **End of Week 8 Evaluation:**
  - [ ] Anomaly precision > 80%? ✓
  - [ ] False positive rate < 20%? ✓
  - [ ] Admin review complete? ✓
  - [ ] Ready for full production? ✓

---

## Phase 5: Full Production (Week 9+)

**Rollout:** 100% of tournaments  
**Duration:** Ongoing  
**Status:** Alfa becomes standard  

### Week 9: Deploy to 100%

- [ ] **Day 1: Deploy Full Production**
  ```bash
  curl -X PUT ... -d '{"flag_name": "alfa_rating_enabled", "value": 100}' ...
  curl -X PUT ... -d '{"flag_name": "alfa_vs_fargo_comparison", "value": 100}' ...
  ```

  Actions:
  - [ ] Update feature flag to 100%
  - [ ] All tournaments use Alfa
  - [ ] Fargo available as fallback
  - [ ] Send announcement

### Ongoing Monitoring

- [ ] Daily health checks
- [ ] Weekly metrics review
- [ ] Monthly trend analysis
- [ ] Continue anomaly monitoring

### Post-Rollout Activities

- [ ] Archive rollout_tracking data
- [ ] Publish final performance report
- [ ] Update documentation
- [ ] Plan for future improvements

---

## Emergency Procedures

### If Critical Issue Detected at Any Time

1. **Immediate Action:**
   ```bash
   ./scripts/rollback_alfa.sh --phase 0
   # Or via API:
   curl -X POST ... https://your-domain/api/admin/rollout/rollback
   ```

2. **Communication:**
   - Notify team immediately
   - Send "Rollback Notice" to stakeholders
   - Status: "Investigating incident"

3. **Investigation:**
   - Analyze logs for error patterns
   - Review metrics/dashboard
   - Identify root cause
   - Document findings

4. **Resolution:**
   - Fix identified issue
   - Test in staging
   - Plan re-deployment
   - Schedule next attempt

---

## Success Metrics Summary

| Phase | Duration | Success Criteria | Decision Point |
|-------|----------|------------------|-----------------|
| 0 | 1-2w | Infrastructure ready | Proceed to Phase 1 |
| 1 | 2w | Brier < 0.30, no errors | Advance to Phase 2 |
| 2 | 2w | Brier < 0.27, Fargo stable | Advance to Phase 3 |
| 3 | 2w | Brier ≥ Fargo, satisfaction > 80% | Advance to Phase 4 |
| 4 | 2w | Anomaly precision > 80% | Advance to Phase 5 |
| 5 | ∞ | All tests pass, stable | Monitor & maintain |

---

## Sign-Off

- [ ] **CTO/Technical Lead:** Reviewed and approved
- [ ] **DevOps Lead:** Infrastructure ready
- [ ] **Product Manager:** Timeline approved
- [ ] **Support Lead:** Team trained
- [ ] **Analytics Lead:** Monitoring configured

---

## Notes & Issues Log

```
Date      | Issue | Status | Resolution
----------|-------|--------|----------
2026-02-16| [Log any issues here for reference]
```

---

## References

- [Production Rollout Guide](PRODUCTION_ROLLOUT_GUIDE.md)
- [Rollout Runbook](ROLLOUT_RUNBOOK.md)
- [Feature Flags Reference](FEATURE_FLAGS_REFERENCE.md)
- [Rollout Implementation Guide](ROLLOUT_IMPLEMENTATION_GUIDE.md)
- [Admin Quick Reference](ROLLOUT_ADMIN_QUICK_REFERENCE.md)
