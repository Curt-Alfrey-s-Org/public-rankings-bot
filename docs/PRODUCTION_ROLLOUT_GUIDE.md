# Production Rollout Guide - Alfa Rating System

**Document Version:** 1.0.0  
**Last Updated:** 2026-02-16  
**Status:** Ready for Deployment  

## Executive Summary

This guide covers the 9-week production rollout of the Alfa rating system for the Rankings Bot, replacing the legacy Fargo rating system. The rollout uses a gradual, risk-managed approach with feature flags, A/B testing, anomaly detection, and automated rollback capabilities.

**Key Principles:**
- **Safe:** Start at 0%, increase in measured steps
- **Observable:** Continuous metrics collection and dashboards
- **Reversible:** Automated rollback on failure conditions
- **Transparent:** Weekly phase completions with clear criteria
- **Data-Driven:** All decisions based on Brier score comparison

---

## Rollout Overview

### Timeline

| Phase | Duration | Coverage | Status | Primary Activity |
|-------|----------|----------|--------|------------------|
| 0 | Pre-launch | 0% | Planning | Infrastructure validation |
| 1 | Weeks 1-2 | 10% | Silent | Background computation |
| 2 | Weeks 3-4 | 25% | Shadow | API opt-in testing |
| 3 | Weeks 5-6 | 50% | Active | A/B testing in UI |
| 4 | Weeks 7-8 | 75% | Expanded | Anomaly detection |
| 5 | Week 9+ | 100% | Full | Production standard |

### Success Criteria by Phase

#### Phase 0: Pre-launch (Weeks before launch)
**Objective:** Validate infrastructure and deployment procedures.

**Success Criteria:**
- ✓ Feature flag system fully operational
- ✓ Rollout tracking database schema deployed
- ✓ Monitoring dashboards functional
- ✓ Rollback procedures tested (dry run)
- ✓ Admin training completed
- ✓ Stakeholder notifications configured

**Rollback Trigger:** Infrastructure not ready
**Timeline:** 1-2 weeks before Phase 1

#### Phase 1: Silent Canary - 10% (Weeks 1-2)
**Objective:** Run Alfa predictions alongside Fargo without user visibility.

**What Happens:**
- 10% of tournaments randomly assigned to Alfa
- Alfa predictions computed for all matches
- Predictions written to database but NOT shown in UI
- Stakeholders see Fargo only (no user perception of change)
- Baseline metrics collection begins

**Success Criteria:**
- ✓ 0 (zero) prediction errors
- ✓ Brier score < 0.30 (degradation acceptable at this stage)
- ✓ No anomalies detected or < 1% false positive rate
- ✓ Database queries responsive (< 200ms)
- ✓ No API response time regression

**Rollback Trigger:**
- Any unhandled exception in prediction pipeline
- Brier score > 0.32 (>5% degradation)
- Error rate > 1% (any exception type)
- Anomaly false positive rate > 10%

**Monitoring Focus:** Error rates, Brier curve, database performance

**Decision Point (End of Week 2):**
- Review collected metrics
- If all criteria met → Proceed to Phase 2
- If concerns → Extend Phase 1 OR rollback to Phase 0

#### Phase 2: Shadow Mode - 25% (Weeks 3-4)
**Objective:** Make Alfa predictions available via API with user opt-in.

**What Happens:**
- 25% of tournaments assigned to Alfa
- Alfa predictions available in API responses
- Users can opt-in via query parameter (`?use_alfa=true`)
- Track user opt-in rates and preferences
- UI still shows Fargo by default

**Database:** Both predictions stored for comparison

**Success Criteria:**
- ✓ Brier score < 0.27 (clear improvement over Fargo ~0.26)
- ✓ Fargo predictions unchanged (not affected by Alfa)
- ✓ No user complaints about Alfa predictions
- ✓ Opt-in rate tracking functional
- ✓ API response time < 300ms with Alfa computation
- ✓ Anomaly detection precision > 70%

**Rollback Trigger:**
- Brier score regression > 5% vs Fargo
- More than 3 user complaints
- API response time > 500ms
- Anomaly false positive rate > 15%

**Monitoring Focus:** A/B comparison, user feedback, opt-in rates, API performance

**User Communication:**
- Opt-in users see message: "Alfa prediction available (experimental)"
- Emphasis on feedback: "Your input helps us improve"

**Decision Point (End of Week 4):**
- Compare Brier scores: Alfa vs Fargo
- If Alfa ≥ Fargo accuracy AND user satisfaction > 70% → Phase 3
- If concerns → Extend Phase 2 OR rollback

#### Phase 3: Experimentation - 50% (Weeks 5-6)
**Objective:** A/B test Alfa vs Fargo for primary rating system.

**What Happens:**
- 50% of tournaments randomly assigned to use Alfa or Fargo (stratified by tournament type)
- Both Alfa and Fargo displayed in UI side-by-side
- Users see "Currently using [Alfa/Fargo]" indicator
- Collect explicit feedback: "How accurate was this prediction?"
- Detailed logging of all prediction decisions

**Statistical Testing:**
- Null hypothesis: Brier(Alfa) = Brier(Fargo)
- Significance level: p < 0.05 (95% confidence)
- Calculate effect size (Cohen's d)

**Success Criteria:**
- ✓ Alfa Brier ≥ Fargo Brier (statistically significant, p < 0.05)
- ✓ Confidence intervals don't overlap
- ✓ Player satisfaction > 80% (survey after matches)
- ✓ Admin feedback positive (no requests to revert)
- ✓ No false positives in anomaly detection (spec < 20%)
- ✓ Server performance stable (99.9% uptime)

**Rollback Trigger:**
- Brier score significantly worse than Fargo (p > 0.05)
- Player satisfaction < 60%
- More than 5 admin complaints (other than feedback)
- False positive rate > 30% in anomaly detection
- Server downtime > 0.1%

**Monitoring Focus:** Statistical significance, player satisfaction, feedback themes

**Decision Point (End of Week 6):**
- Run statistical tests on Brier scores
- If Alfa superior (p < 0.05) AND satisfaction > 80% → Phase 4
- If marginal → Extend Phase 3 for more data
- If Alfa inferior → Rollback
- If equal → Continue to Phase 4 (no regression, ready for anomaly detection)

#### Phase 4: Controlled Expansion - 75% (Weeks 7-8)
**Objective:** Expand Alfa, enable anomaly detection for rating integrity.

**What Happens:**
- 75% of tournaments use Alfa as primary rating
- Admin dashboard enabled for anomaly review
- Anomaly detection system active:
  - Detects sandbagging (intentional loss to preserve rating)
  - Detects skill bursts (impossible rating improvement)
  - Manual override capability for admins
- Rating adjustments possible for confirmed anomalies
- Both Alfa and Fargo shown for comparison

**Admin Capabilities:**
- View flagged matches in admin dashboard
- Approve/reject anomaly detection results
- Manually adjust player ratings
- Export anomaly reports

**Success Criteria:**
- ✓ Anomaly detection precision > 80% (>80% of flagged matches are genuine anomalies)
- ✓ Anomaly detection recall > 70% (detect >70% of actual anomalies)
- ✓ False positive rate < 20% (< 20% of flags are incorrect)
- ✓ Admin workflow time < 5 min per anomaly
- ✓ Player acceptance of anomaly flags > 85% (after explanation)
- ✓ System performance stable (< 1% impact from anomaly detection)

**Rollback Trigger:**
- Precision < 60% (too many false alarms)
- False positive rate > 25%
- Players revolt against anomaly flags (satisfaction < 50%)
- Major system performance degradation
- More than 10 unresolved anomalies backlog

**Monitoring Focus:** Anomaly metrics, admin feedback, player acceptance

**Decision Point (End of Week 8):**
- Review anomaly detection performance metrics
- If precision > 80% AND false positive < 20% → Phase 5
- If marginal → Train model further with more data
- If poor → Rollback anomaly features (keep Alfa at 50%)

#### Phase 5: Full Production - 100% (Week 9+)
**Objective:** Make Alfa the standard rating system.

**What Happens:**
- 100% of tournaments use Alfa
- Fargo removed from public API (keep in backend for fallback)
- UI shows Alfa scores only
- Anomaly detection fully operational
- Admin dashboard becomes standard tool
- Archive rollout metrics and prepare public announcement

**Transition Details:**
- Historical ratings NOT converted (running parallel is acceptable)
- New players get Alfa estimates from the start
- Existing players see Alfa following next rated match
- Fargo available via admin API for troubleshooting

**Success Criteria:**
- ✓ All rollout phases completed successfully
- ✓ System performance meets SLAs
- ✓ 99.9%+ API availability
- ✓ Player satisfaction > 85%
- ✓ Admin confirmed stable operation for 1 week
- ✓ Documentation complete and published

**Post-Rollout Activities:**
- Publish results: "Alfa is now the standard rating system"
- Share lessons learned
- Retire Fargo from primary path (keep for fallback)
- Archive rollout data
- Plan for continuous improvement

---

## Feature Flags Reference

All feature flags are stored in `config/feature_flags.json` and can be updated at runtime.

### alfa_rating_enabled (Percentage)
- **Current Value:** 0%
- **Purpose:** Controls percentage of tournaments using Alfa
- **Valid Range:** 0-100
- **Rollback-enabled:** Yes
- **Update Method:** `PUT /api/admin/feature-flags/alfa_rating_enabled`

**Values:**
- 0% = Disabled (Phase 0)
- 10% = Phase 1 (Silent Canary)
- 25% = Phase 2 (Shadow Mode)
- 50% = Phase 3 (Experimentation)
- 75% = Phase 4 (Controlled Expansion)
- 100% = Phase 5 (Full Production)

### alfa_predictions_in_api (Boolean)
- **Current Value:** false
- **Purpose:** Return Alfa predictions in API responses
- **Enabled at:** Phase 2+
- **Prerequisites:** alfa_rating_enabled >= 25%

### alfa_anomaly_detection_enabled (Boolean)
- **Current Value:** false
- **Purpose:** Enable anomaly detection for rating integrity
- **Enabled at:** Phase 4+
- **Prerequisites:** alfa_rating_enabled >= 75%

### alfa_vs_fargo_comparison (Percentage)
- **Current Value:** 0%
- **Purpose:** Show both Alfa and Fargo scores for comparison
- **Follows:** alfa_rating_enabled percentage

### alfa_admin_dashboard_enabled (Boolean)
- **Current Value:** false
- **Purpose:** Enable admin dashboard for rollout monitoring
- **Enabled at:** Phase 4+
- **Admin-only:** Yes

### alfa_rollback_enabled (Boolean)
- **Current Value:** true
- **Purpose:** Allow automatic and manual rollback
- **Should NOT disable during rollout**

### Automatic Rollback Triggers

The system can automatically revert to previous phase if:

1. **Brier Score Degradation:**
   - Threshold: 0.32 (>5% worse than staging baseline of ~0.26)
   - Check interval: Every 30 minutes
   - Action: Rollback to previous phase

2. **Error Rate:**
   - Threshold: 2% (>2 errors per 100 predictions)
   - Check interval: Every 60 minutes
   - Action: Rollback to previous phase

3. **Consecutive Failures:**
   - Threshold: 5 consecutive unhandled exceptions
   - Check interval: Real-time
   - Action: Disable feature flag

---

## Monitoring and Observability

### Key Metrics

**Accuracy Metrics:**
- Brier score (0 = perfect, 1 = worst)
  - Target: < 0.26 (better than Fargo ~0.26)
  - Alert threshold: > 0.32
- Prediction accuracy (% correct)
- Confidence distribution

**Operational Metrics:**
- API response time (target: < 300ms with Alfa)
- Error rate (target: < 0.5%)
- Database query performance
- Feature flag update latency

**Rollout Metrics:**
- Current percentage
- Current phase
- Tournaments using Alfa
- Matches evaluated
- User opt-in rate (Phases 2-3)

**Anomaly Detection Metrics:**
- True positive rate (recall)
- False positive rate
- Precision (TPs / all flagged)
- Anomalies per tournament
- Admin review completion rate

### Dashboards

**Main Rollout Dashboard** (`monitoring/grafana/dashboards/rollout_metrics.json`):
1. Current rollout percentage (gauge, color-coded by phase)
2. Alfa vs Fargo Brier score trend (time series, with band for confidence interval)
3. Prediction accuracy comparison (bar chart)
4. Error rate by phase (bar chart with alert threshold)
5. User adoption rate (line chart for Phase 2+)
6. Anomaly detection performance (5 metrics: TP, FP, TN, FN, precision)
7. Difference in ratings (histogram: Alfa - Fargo)

**Admin Monitoring Dashboard** (Phase 4+):
- Anomaly detection flagged matches
- Manual override history
- Rating adjustment impact
- Player feedback on anomalies

---

## Rollback Procedures

### Manual Rollback

**Command:**
```bash
./scripts/rollback_alfa.sh --phase 0    # Disable Alfa completely
./scripts/rollback_alfa.sh --phase 2    # Revert to Phase 2
```

**What Happens:**
1. Creates checkpoint of current configuration
2. Updates `config/feature_flags.json` to target phase
3. Disables Alfa prediction endpoints
4. Reverts API to return Fargo only
5. Generates rollback report
6. Sends notifications to admin team

**Rollback Report** (`rollout/ROLLBACK_REPORT_{timestamp}.md`):
- Timestamp and trigger reason
- Status before/after
- List of actions taken
- Checkpoint locations
- Next steps for investigation

### Automatic Rollback

**Triggers (Automatically Activated):**
1. **Brier Score:** If avg > 0.32 for > 30 min
   - Action: Rollback to Phase 0 (disable Alfa)
   - Alert: Critical, requires investigation

2. **Error Rate:** If > 2% for > 60 min
   - Action: Disable prediction endpoint
   - Alert: Critical, page on-call engineer

3. **Consecutive Failures:** If 5+ exceptions
   - Action: Disable feature flag immediately
   - Alert: Critical, block further rollout

**Response SLA:**
- Critical alerts: Response within 30 minutes
- Investigation: Complete within 4 hours
- Resolution: Deploy fix or confirm safe to retry

### Investigation After Rollback

1. **Immediate (< 10 min):**
   - Check `rankings_bot.log` for error patterns
   - Review rollout metrics from last hour
   - Verify rollback completed successfully

2. **Short-term (< 2 hours):**
   - Analyze which tournaments/users affected
   - Identify specific failure patterns
   - Check for upstream service issues

3. **Medium-term (< 24 hours):**
   - Root cause analysis
   - Implement fix
   - Test fix in staging
   - Plan re-deployment

### Re-deployment After Rollback

1. **Fix validation** (required):
   - Run full test suite
   - Validate in staging for 1 hour
   - Get approval from 2 team members

2. **Staged re-deployment**:
   ```bash
   # Start at lower percentage
   ./scripts/rollout_alfa.sh deploy --phase 1    # 10%
   # Monitor for 24 hours
   # Gradually increase
   ./scripts/rollout_alfa.sh deploy --phase 2    # 25%
   ```

3. **Enhanced monitoring**:
   - Check metrics every 5 minutes (vs normal 30 min)
   - Shorter automatic rollback threshold (0.30 instead of 0.32)
   - Lower error rate trigger (1% instead of 2%)

---

## Admin Guide

### Feature Flag Updates

**Update flag via API:**
```bash
# Enable API predictions in Phase 2
curl -X PUT http://localhost:8003/api/admin/feature-flags/alfa_predictions_in_api \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'

# Increase rollout percentage
curl -X PUT http://localhost:8003/api/admin/feature-flags/alfa_rating_enabled \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{"percentage": 50}'
```

**Response:**
```json
{
  "flag": "alfa_rating_enabled",
  "old_value": 25,
  "new_value": 50,
  "timestamp": "2026-02-16T12:34:56Z",
  "success": true
}
```

### Checking Rollout Status

**Current status:**
```bash
./scripts/rollout_alfa.sh status
```

**Metrics:**
```bash
./scripts/rollout_alfa.sh metrics
```

**Rollout schedule:**
```bash
./scripts/rollout_alfa.sh schedule
```

### Anomaly Detection (Phase 4+)

**View flagged matches:**
- Admin Dashboard → Anomaly Detection tab
- Filter by: Date, Tournament, Player, Type
- Status: Pending, Approved, Rejected, Resolved

**Review process:**
1. Admin sees flagged player
2. Analyzes recent match history
3. Checks for rating inconsistencies
4. Approves or rejects flag
5. If approved, can adjust rating or leave as-is

**Manual override:**
```bash
# If necessary, adjust player Alfa rating
curl -X POST http://localhost:8003/api/admin/players/{player_id}/rating-adjustment \
  -H "Authorization: Bearer {admin_token}" \
  -d '{
    "adjustment": -10,
    "reason": "Sandbagging detected in tournament 12345",
    "evidence": "Lost to lower-rated player 3 times"
  }'
```

### Notifications Configuration

**Email notifications:**
- Phase transitions (to admin list)
- Rollback events (critical)
- Weekly metrics summary
- Monthly results report

**Slack notifications:**
- Daily status updates in #rankings-bot channel
- Alert on anomalies
- Summary in #deployments channel

Configure in admin panel:
- Admin Dashboard → Settings → Notifications
- Recipient list: Add/edit email addresses
- Frequency: Daily/weekly/on-event

---

## Timeline and Checklist

### Pre-Launch (1-2 weeks before Phase 1)

- [ ] Feature flag system deployed and tested
- [ ] Database schema created and migrated
- [ ] Monitoring dashboards configured
- [ ] Rollback procedures tested (dry run)
- [ ] Alert rules configured
- [ ] Admin team trained on procedures
- [ ] Stakeholder notification system ready
- [ ] Documentation reviewed and approved

### Phase 1 Checklist (Week 1-2)

**Week 1:**
- [ ] Deploy Phase 1 (10% rollout)
- [ ] Monitor metrics every hour
- [ ] Check error rate (target: 0%)
- [ ] Verify database records created
- [ ] Team standup: Daily status

**Week 2:**
- [ ] Review Phase 1 metrics
- [ ] Verify Brier < 0.30
- [ ] Check anomaly detection baseline
- [ ] Decision: Proceed to Phase 2?
- [ ] Get stakeholder approval

### Phase 2 Checklist (Week 3-4)

**Week 3:**
- [ ] Deploy Phase 2 (25% rollout, API enabled)
- [ ] Monitor opt-in rates
- [ ] Track user feedback
- [ ] Check API performance (< 300ms)
- [ ] Daily standup

**Week 4:**
- [ ] Statistical analysis: Alfa vs Fargo
- [ ] User feedback summary
- [ ] Opt-in rate analysis
- [ ] Decision: Proceed to Phase 3?
- [ ] Get stakeholder approval

### Phase 3 Checklist (Week 5-6)

**Week 5:**
- [ ] Deploy Phase 3 (50% A/B test)
- [ ] Randomize tournament assignments
- [ ] Collect explicit user feedback
- [ ] Monitor statistical significance
- [ ] Daily standup

**Week 6:**
- [ ] Analyze A/B test results
- [ ] Calculate p-values, effect size
- [ ] Summarize player feedback (>80% satisfied?)
- [ ] Decision: Proceed to Phase 4?
- [ ] Get stakeholder approval

### Phase 4 Checklist (Week 7-8)

**Week 7:**
- [ ] Deploy Phase 4 (75% rollout, anomaly detection)
- [ ] Enable admin dashboard
- [ ] Monitor anomaly detection metrics
- [ ] Train admins on review process
- [ ] Daily standup

**Week 8:**
- [ ] Analyze anomaly detection precision/recall
- [ ] Review admin feedback
- [ ] Check false positive rate (<20%?)
- [ ] Decision: Proceed to Phase 5?
- [ ] Get stakeholder approval

### Phase 5 Launch (Week 9)

**Week 9:**
- [ ] Deploy Phase 5 (100% production)
- [ ] Run full test suite
- [ ] Verify both versions running correctly
- [ ] Monitor during launch (every 5 min)
- [ ] PR: Announce Alfa is now standard
- [ ] Blog post: Technical details and results

**Post-Launch:**
- [ ] Maintain elevated monitoring for 1 week
- [ ] Address any user feedback
- [ ] Publish final metrics and lessons learned
- [ ] Plan Fargo deprecation timeline
- [ ] Schedule retrospective meeting

---

## Escalation Procedures

### Level 1: Monitoring Alert (10 min response)

**Triggers:**
- Brier score warning (> 0.28)
- Error rate warning (> 0.5%)
- API response time > 300ms

**Action:**
- Check metrics dashboards
- Verify no ongoing deployments
- Check upstream services
- No action needed if temporary

### Level 2: Critical Alert (5 min response)

**Triggers:**
- Brier score > 0.32 (auto-trigger rollback)
- Error rate > 2%
- API response time > 500ms
- Database connection issues

**Action:**
1. Page on-call engineer immediately
2. Initiate rollback if not automatic
3. Create incident in Slack #incidents
4. Start root cause analysis
5. Brief team within 30 min

### Level 3: Major Incident (Immediate)

**Triggers:**
- API completely unavailable
- Database corruption
- Data loss detected
- Security breach

**Action:**
1. Declare SEV-1 incident
2. Page on-call manager + engineers
3. Initiate incident commander role
4. Establish war room (Zoom)
5. Begin immediate rollback
6. Post-mortem after stabilization

---

## Post-Deployment Assessment

### 1-Week Post-Launch (Week 10)

**Metrics to Review:**
- Brier score stability (no regressions)
- Error rate (maintained < 0.5%)
- API performance (consistent < 200ms)
- Player satisfaction (surveys)
- Admin feedback (no critical issues)

**Decision:**
- System stable? → Discontinue elevated monitoring
- Issues found? → Extend Phase 5 focused fixes
- Proceed to deprecation planning

### 30-Day Post-Launch

**Analysis:**
- Compare against Fargo baseline (week 1 vs week 4)
- Identify edge cases (tournament types, player levels)
- Measure specific improvements (juniors, seniors, women)
- Calculate ROI if applicable

**Actions:**
- Publish blog post with results
- Archive rollout metrics to database
- Update internal documentation
- Plan continuous improvements

### Public Results Publication

**Blog Post Template:**
```markdown
# Alfa Rating System Launch: Results and Lessons

## Executive Summary
- Alfa deployed to 100% of tournaments Week 9
- Improved prediction accuracy by X% vs Fargo
- Deployed safely with zero critical incidents

## Metrics
- Brier score improved from 0.26 → 0.25
- Anomaly detection identified X cheaters
- Player satisfaction: 87%

## Process
- 9-week gradual rollout
- 5 phases with clear success criteria
- Automated rollback on failure

## Lessons Learned
1. [Key insight from Phase 1]
2. [Key insight from Phase 2]
...

## Next Steps
- Monitor $/value metrics
- Plan A/B test for [next feature]
- Deprecate Fargo in public API (timeline)
```

---

## Appendices

### Appendix A: Contacts and Escalation

**Primary On-Call:** [Name, Phone]
**Manager:** [Name, Email]
**Product Owner:** [Name]
**Infrastructure Team:** [Slack channel]

### Appendix B: Alert Rules Configuration

See `monitoring/alert_rules.yaml`

### Appendix C: Database Backup Procedures

Before each phase:
```bash
./scripts/backup_database.sh --before-phase 2
```

### Appendix D: Glossary

- **Brier Score:** Accuracy metric (0=perfect, 1=worst)
- **False Positive:** Anomaly flagged but not genuine
- **Precision:** Accuracy of flagged matches (TP/(TP+FP))
- **Recall:** Coverage of actual anomalies (TP/(TP+FN))
- **Stratification:** Ensuring equal distribution across types
- **Phase Transition:** Moving to next percentage tier

---

**Document Complete**

Next: Review [ROLLOUT_RUNBOOK.md](ROLLOUT_RUNBOOK.md) for week-by-week detailed tasks.
