# Alfa Rating Rollout - Week-by-Week Runbook

**Quick Reference for Daily Operations During 9-Week Rollout**

```
Phase 0: Pre-launch         [Weeks before launch]
Phase 1: Silent Canary 10%  [Weeks 1-2]
Phase 2: Shadow Mode 25%    [Weeks 3-4]
Phase 3: Experimentation 50% [Weeks 5-6]
Phase 4: Controlled Exp. 75% [Weeks 7-8]
Phase 5: Full Production 100% [Week 9+]
```

---

## PHASE 0: PRE-LAUNCH

### Pre-Launch Week: Infrastructure Setup

**Monday:**
- [ ] Verify feature flag system deployed: `./scripts/rollout_alfa.sh status`
- [ ] Check database migration: `psql rankings_db -c "SELECT * FROM rollout_tracking LIMIT 1;"`
- [ ] Verify Grafana dashboard accessible: http://grafana:3000/dashboards
- [ ] Check alert rules in Prometheus: http://prometheus:9090/alerts
- [ ] Run rollback dry-run: `./scripts/rollback_alfa.sh --status`
- [ ] Daily standup: Confirm all systems ready

**Tuesday:**
- [ ] Admin training session 1: Feature flag system overview
- [ ] Test manual flag update: `curl -X PUT /api/admin/feature-flags/alfa_rating_enabled`
- [ ] Verify notification channels: Email, Slack test messages
- [ ] Review rollout guide with team
- [ ] Check monitoring dashboard displays correct data

**Wednesday:**
- [ ] Admin training session 2: Rollback procedures
- [ ] Simulate rollback: Execute `./scripts/rollback_alfa.sh --phase 0` (in test env)
- [ ] Review rollover report generated
- [ ] Verify logging of all actions in `rollout.log`
- [ ] Test metric collection pipeline

**Thursday:**
- [ ] Admin training session 3: Anomaly detection (future phases)
- [ ] Review API endpoints for Alfa feature flag checks
- [ ] Validate error handling in prediction pipeline
- [ ] Check database performance: Query < 200ms at scale
- [ ] Brief stakeholders on launch plan

**Friday:**
- [ ] Final infrastructure validation
- [ ] Load test: Simulate Phase 1 load (10% of tournaments)
- [ ] Confirm all alerts are firing correctly
- [ ] Document any last-minute configuration changes
- [ ] Get final approval from product/engineering leads
- [ ] Schedule Week 1 daily standups: 9:00 AM

**Daily During Pre-Launch:**
- No monitoring required (system not yet in production)
- Focus on readiness verification
- Team availability confirmed for launch week

**Go/No-Go Decision (Friday 5 PM):**
- [ ] All infrastructure operational
- [ ] All staff trained and confident
- [ ] All monitoring and alerts ready
- [ ] Rollback procedures tested
- [ ] **Decision: Ready to launch Phase 1 on Monday**

---

## PHASE 1: SILENT CANARY (Weeks 1-2) - 10%

*Alfa predictions run in background, NOT shown in UI*

### Week 1

#### Monday (Day 1)

**Pre-Launch (6 AM):**
- [ ] Verify all systems operational
- [ ] Confirm database backups completed
- [ ] Check API servers ready and healthy
- [ ] Review alert thresholds one final time

**Launch (8 AM):**
- [ ] Execute: `./scripts/rollout_alfa.sh deploy --phase 1`
- [ ] Verify config updated: `jq .alfa_rating_enabled.percentage config/feature_flags.json`
- [ ] Check API logs for Alfa prediction initialization: `tail -50 rankings_bot.log | grep -i alfa`
- [ ] Post launch notification to Slack #rankings-bot

**Morning Monitoring (9 AM - 12 PM):** Every 30 minutes
- [ ] API response time: `curl -w "@curl_format.txt" -o /dev/null -s http://localhost:8003/api/health`
  - Expected: < 300ms
  - Alert if: > 500ms
- [ ] Error rate: Check logs for exceptions
  - Expected: 0-5 per hour
  - Alert if: > 10 per hour
- [ ] Database query performance
  - Expected: 95th percentile < 200ms
  - Alert if: > 400ms

**Afternoon Monitoring (12 PM - 6 PM):**
- [ ] Check prediction metrics dashboard
  - Count: Predictions computed
  - Brier score: Should appear (0.25-0.30 range expected)
- [ ] Verify database records being written
  - `SELECT COUNT(*) FROM rollout_tracking WHERE timestamp > NOW() - INTERVAL 1 HOUR;`
- [ ] Check for any error patterns in logs
  - Search for: "ERROR", "EXCEPTION", "Brier exceeded"
- [ ] Confirm monitoring dashboards updating live

**Evening Debrief (4 PM):**
- Standup: "Systems operating normally, X tournaments using Alfa"
- Review any warnings/anomalies
- Plan for tomorrow

**Tuesday - Thursday (Days 2-4):** Simplified schedule

**Morning Check (8 AM):** 10 minutes
- [ ] Health check: All systems up
- [ ] Error rate: < 5 per hour
- [ ] Response time: < 300ms
- [ ] Database: Latest records within last hour

**Hourly Check (9 AM - 5 PM):** 5 minutes each
- [ ] Brier score hasn't degraded (< 0.30)
- [ ] No new error types appearing
- [ ] API still responsive
- [ ] Grafana dashboard updated

**Evening Debrief (4 PM):** 5 minutes
- Quick status: "All good" or "Worth monitoring"
- Daily log entry: Number of tournaments processed, key metrics

### Week 1 Success Criteria Check

**Friday (Day 5) - Data Review:**

```bash
# Check metrics collected in Week 1
./scripts/rollout_alfa.sh metrics

# Should show approximately:
# - Tournaments processed: 50-100 (10% of fleet)
# - Total matches: 1000-2000
# - Avg Brier (Alfa): ~0.27
# - Error rate: < 1%
# - Anomaly count: 0-5
```

**Friday Standup (3 PM):**
- [ ] Review collected metrics
- [ ] Check criteria:
  - ✓ Error rate: 0-1%?
  - ✓ Brier < 0.30?
  - ✓ No anomalies or < 1% false positive?
  - ✓ Database responsive?
- [ ] Decision: Continue to Week 2?
- [ ] No blockers found? → Continue normal monitoring

### Week 2

**Monday - Thursday (Days 8-11):** Same simplified schedule as Week 1

**Key Monitoring Focus:**
- Sustained performance over time
- Any patterns emerging in errors
- Brier score stability
- No unexpected behavior changes

**Friday Data Analysis (Day 12):**

```bash
# Full 2-week analysis
./scripts/rollout_alfa.sh metrics

# Phase 1 Success Criteria:
# ✓ Zero critical errors
# ✓ Brier score < 0.30 (with no trend toward 0.32):
#   - Week 1: 0.27
#   - Week 2: 0.26-0.27 (stable is good)
# ✓ No anomalies or < 1% false positive rate
# ✓ Database performance stable
```

### After Phase 1: Decision Point

**Friday 3 PM - Phase Review Meeting:**

Present metrics:
```
Phase 1 Results:
- Duration: 2 weeks (Feb 16-27)
- Coverage: 10% of tournaments (150-200 total)
- Matches evaluated: 3000-4000
- Avg Brier (Alfa): 0.266
- Avg Brier (Fargo): 0.268
- Error rate: 0.3%
- Critical incidents: 0
- Recommendation: PROCEED TO PHASE 2
```

**Voting/Approval:**
- [ ] Engineering Lead: ✓
- [ ] Product Manager: ✓
- [ ] Ops/DevOps: ✓

**Decision:** PROCEED to Phase 2 Monday (March 2)

---

## PHASE 2: SHADOW MODE (Weeks 3-4) - 25%

*Alfa predictions available via API, users can opt-in*

### Week 3 (Days 15-21)

**Monday 8 AM - Deploy Phase 2:**
```bash
./scripts/rollout_alfa.sh deploy --phase 2
```

**Deployment Validation:**
- [ ] Config updated to 25%: `jq .alfa_rating_enabled.percentage config/feature_flags.json`
- [ ] API predictions enabled: `jq .alfa_predictions_in_api.enabled config/feature_flags.json`
- [ ] Test opt-in: `curl http://localhost:8003/api/matches/123?use_alfa=true`
  - Should return both Alfa and Fargo predictions
- [ ] Post notification: "Phase 2 started, users can now opt-in to Alfa"

**Week 3 Monitoring Schedule:**

**Daily (8 AM):** 10 minutes
- [ ] API health check
- [ ] Error rate < 1%
- [ ] Response time < 300ms (with Alfa computation)
- [ ] Database size check: Storage growing as expected

**Twice daily (12 PM, 4 PM):** 10 minutes
- [ ] Opt-in rate: How many users choosing Alfa?
  - Target: 20-30% try it
  - Track in: `SELECT COUNT(*) FROM user_preferences WHERE use_alfa=true`
- [ ] User feedback: Any complaints or issues?
  - Check: Slack channel, email
  - Act: Respond within 2 hours
- [ ] Comparison metrics: Alfa vs Fargo on same matches
  - Check: Brier score for both
  - Both should be ~0.26-0.27

**Statistical Analysis (Friday):**
```bash
# Phase 2 so far - Week 3 analysis
SELECT
  AVG(brier_alfa) as alfa_brier,
  AVG(brier_fargo) as fargo_brier,
  (AVG(brier_fargo) - AVG(brier_alfa)) / AVG(brier_fargo) * 100 as improvement_pct,
  COUNT(*) as total_matches
FROM rollout_tracking
WHERE timestamp > NOW() - INTERVAL 7 DAYS;

# Expected:
# alfa_brier: 0.26-0.27
# fargo_brier: 0.26-0.27
# improvement_pct: -5% to +5% (either direction OK at this point)
```

### Week 4 (Days 22-28)

**Same monitoring as Week 3**

**Thursday - Prepare Phase 2 Summary:**
```bash
# Full 2-week Phase 2 analysis
./scripts/rollout_alfa.sh metrics

# Phase 2 Success Criteria:
# ✓ Brier < 0.27 (Alfa vs Fargo)?
# ✓ User opt-in rate 20-40%?
# ✓ No user complaints (or < 3)?
# ✓ Error rate stable < 1%?
# ✓ API response time < 300ms with Alfa?
```

### After Phase 2: Decision Point

**Friday 3 PM - Phase 2 Review:**

Present metrics:
```
Phase 2 Results:
- Duration: 2 weeks (Mar 2-13)
- Coverage: 25% of tournaments (375-500 total)
- Matches evaluated: 7500-10000
- Opt-in rate: 28% (good!)
- Alfa Brier: 0.263
- Fargo Brier: 0.265
- Improvement: +0.76% in Alfa's favor
- User feedback: Positive (2 minor complaints, resolved)
- Error rate: 0.4%
- Critical incidents: 0
- Recommendation: PROCEED TO PHASE 3
```

**Decision:** PROCEED to Phase 3 Monday (March 16)

---

## PHASE 3: EXPERIMENTATION (Weeks 5-6) - 50%

*A/B test Alfa vs Fargo with 50% of tournaments*

### Week 5 (Days 29-35)

**Monday 8 AM - Deploy Phase 3:**
```bash
./scripts/rollout_alfa.sh deploy --phase 3
```

**Deployment:**
- [ ] Config: 50% (stratified by tournament type)
- [ ] UI shows both Alfa and Fargo for comparison
- [ ] Feedback system enabled: "Rate this prediction"
- [ ] Post: "A/B testing Alfa - feedback needed!"

**Week 5 Monitoring:**

**Daily (8 AM):** 15 minutes
- [ ] Strat split verified: ~50% Alfa, ~50% Fargo
  - Query: Count tournaments by method
  - Both should be ~300-400 each
- [ ] Error rate < 1%
- [ ] Response time < 350ms (A/B test adds minor overhead)

**Daily (4 PM):** 15 minutes
- [ ] User feedback volume
  - Expected: 50-100 feedback entries
  - Track sentiment: Positive/neutral/negative
- [ ] Brier score comparison
  - Alfa: Expected 0.26-0.27
  - Fargo: Expected 0.26-0.27
  - Both should be similar (no clear winner yet)
- [ ] Statistical test setup
  - Confirm data collection for significance testing

**End of Week 5 (Friday):**
```
Week 5 Midpoint:
- Tournaments processing: ~700 (50% of fleet)
- Daily feedback: ~80 entries
- Alfa sentiment: 72% positive (good start)
- Brier convergence: Both ~0.266
```

### Week 6 (Days 36-42)

**Same monitoring as Week 5**

**Thursday - Statistical Analysis:**

```python
# Run significance test after 2 weeks of Phase 3 data
from scipy import stats

alfa_briers = [...]  # From database
fargo_briers = [...]  # From database

# T-test
t_stat, p_value = stats.ttest_rel(alfa_briers, fargo_briers)

print(f"Alfa mean Brier: {np.mean(alfa_briers):.4f}")
print(f"Fargo mean Brier: {np.mean(fargo_briers):.4f}")
print(f"P-value: {p_value:.4f}")
print(f"Significant? {p_value < 0.05}")

# Effect size (Cohen's d)
cohens_d = (np.mean(alfa_briers) - np.mean(fargo_briers)) / np.sqrt(...)
print(f"Effect size (d): {cohens_d:.4f}")
```

### After Phase 3: Decision Point

**Friday 3 PM - Phase 3 Review:**

Present metrics:
```
Phase 3 Results:
- Duration: 2 weeks (Mar 16-27)
- Coverage: 50% of tournaments (750-1000 total)
- Matches evaluated: 15000-20000
- User feedback volume: 800 entries
- User satisfaction: 81% (target: >80%)
- Alfa Brier: 0.261
- Fargo Brier: 0.264
- Improvement: +1.14% statistically significant
- P-value: 0.032 (significant, p < 0.05)
- Effect size: 0.15 (Cohen's d, small-medium)
- Recommendation: PROCEED TO PHASE 4
```

**Decision:** PROCEED to Phase 4 Monday (Mar 30)

---

## PHASE 4: CONTROLLED EXPANSION (Weeks 7-8) - 75%

*Enable anomaly detection, 75% of tournaments use Alfa*

### Week 7 (Days 43-49)

**Monday 8 AM - Deploy Phase 4:**
```bash
./scripts/rollout_alfa.sh deploy --phase 4
```

**Deployment:**
- [ ] Config: 75% rollout
- [ ] Anomaly detection enabled
- [ ] Admin dashboard accessible
- [ ] Post: "Anomaly detection now active - review sandbagging flagged"

**Week 7 Monitoring:**

**Daily (8 AM):** 20 minutes
- [ ] Anomaly detection metrics
  - Anomalies flagged: Expected 5-10
  - False positive rate: < 20%
  - Precision: > 70%
- [ ] Admin dashboard working
  - Can view flagged matches?
  - Can review and approve/reject?
- [ ] Performance impact
  - Anomaly detection latency < 100ms
  - No API slowdown from new feature

**Daily (12 PM, 4 PM):** 10 minutes
- [ ] Player feedback on anomaly flags
  - Any complaints about false positives?
  - Are flagged players accepting explanations?
- [ ] Admin workload
  - Backlog of anomalies to review?
  - Time to approve/reject: < 5 min/anomaly?

**Weekly (Friday):**
```
Week 7 Summary:
- Anomalies detected: 42
- Confirmed true positives: 34 (81% precision)
- False positives: 8 (19%)
- Player acceptance: 83%
- Admin review time: avg 3.2 min
```

### Week 8 (Days 50-56)

**Same monitoring as Week 7**

**Focus:** Anomaly detection tuning
- If precision > 85%: Consider stricter thresholds
- If precision < 70%: Review flagging logic, possibly adjust
- If false positive rate > 25%: Increase threshold

**Friday - Full Phase 4 Analysis:**

```
Phase 4 Results:
- Duration: 2 weeks (Mar 30 - Apr 10)
- Coverage: 75% of tournaments (1125-1500 total)
- Anomalies detected: 85
- True anomalies (confirmed): 72 (85% precision - EXCELLENT)
- False positives: 13 (15% - acceptable, < 20%)
- Recall: 82% (detected 82% of actual anomalies)
- Player acceptance: 84% (target: >85%)
- Admin satisfaction: High (no complaints)
- Recommendation: PROCEED TO PHASE 5
```

**Decision:** PROCEED to Phase 5 Monday (Apr 13)

---

## PHASE 5: FULL PRODUCTION (Week 9+) - 100%

*All tournaments use Alfa, Fargo deprecated from public API*

### Week 9 (Days 57-63) - Launch Week

**Monday 8 AM - Deploy Phase 5:**
```bash
./scripts/rollout_alfa.sh deploy --phase 5
```

**Deployment:**
- [ ] Config: 100% rollout
- [ ] UI updated to show only Alfa ratings
- [ ] Fargo removed from public API
- [ ] Post: "🎉 Alfa rating system is now the standard!"

**Enhanced Monitoring (First 3 Days):**

**Every 5 minutes (Mon-Wed, 8 AM - 10 PM):**
- [ ] API health check
- [ ] Error rate (should be near-zero)
- [ ] Response time (< 300ms)
- [ ] Database connectivity

**Every 30 minutes (Mon-Wed, 8 PM - 8 AM):**
- [ ] Same checks as above
- [ ] Check for unusual patterns in logs

**Every hour (Thursday-Friday):**
- [ ] API health
- [ ] Error rate
- [ ] Response time
- [ ] Brier score (stability check)

**Daily (Friday):**
```
First 5 Days of Phase 5:
- Coverage: 100% of tournaments
- Tournaments assigned: 1500-2000
- Total matches: 30000+ 
- API uptime: 99.97%
- Error rate: 0.08%
- Avg response time: 248ms
- Anomalies detected: 12
- Zero critical incidents
- ✓ SYSTEM STABLE, MONITORING NORMAL
```

### Day 6 Onwards (Friday - Normal Operations)

**Daily Checklist (8 AM):** 15 minutes
- [ ] Overnight anomalies: Any flagged?
- [ ] Error rate: Normalized?
- [ ] Response time: Stable?
- [ ] Stakeholder feedback: Any issues?

**Weekly Review (Friday 3 PM):** 30 minutes
- [ ] Metrics summary
- [ ] Anomaly detection performance
- [ ] Player satisfaction (continue surveys)
- [ ] Plan for next week

**Monthly Review:** Comprehensive analysis

---

## EMERGENCY RESPONSE

### Automatic Rollback Triggers

**These happen automatically - monitor for:**

```
1. Brier Score Alert (check every 30 min)
   If avg Brier > 0.32 for > 30 minutes
   → AUTO ROLLBACK to previous phase
   → Alert: "CRITICAL: Brier exceeded threshold"

2. Error Rate Alert (check every 60 min)
   If error_rate > 2% for > 60 minutes
   → AUTO ROLLBACK to previous phase
   → Alert: "CRITICAL: Error rate exceeded"

3. Consecutive Failures (real-time)
   If 5+ consecutive prediction exceptions
   → Disable feature flag
   → Alert: "CRITICAL: Feature flag disabled"
```

### If Automatic Rollback Occurs

**Immediate (Within 10 min):**
1. [ ] Acknowledge alert in Slack
2. [ ] Check rollout/ROLLBACK_REPORT_{timestamp}.md
3. [ ] Verify rollback completed
4. [ ] Read initial error summary

**Short-term (Within 2 hours):**
1. [ ] Full root cause analysis
2. [ ] Review error logs in detail
3. [ ] Identify affected tournaments/users
4. [ ] Brief team in Slack #incidents

**Medium-term (Within 24 hours):**
1. [ ] Implement fix
2. [ ] Test in staging thoroughly
3. [ ] Get 2 approvals for re-deployment
4. [ ] Plan phased re-deployment

**Long-term (Next week):**
1. [ ] Publish post-mortem
2. [ ] Implement preventive measures
3. [ ] Re-plan rollout starting at earlier phase
4. [ ] Conduct blameless retrospective

---

## Daily Standup Template

**Time:** 9:00 AM (5 minutes)

**Report:**
```
Phase [N] - Day [X/42]  
Status: GREEN / YELLOW / RED

Overnight Results:
- Tournaments processed: XXX
- Total matches: XXX
- Avg Brier: 0.XXX
- Errors: X (rate: X%)

Key Metrics:
- API uptime: 99.9%+?
- Response time: < 300ms?
- Database: Healthy?

Issues/Blockers:
- None / [List if any]

Next 24 Hours:
- Standard monitoring / [Special focus area]

Owner: [Name]
Time to full report: [minutes]
```

---

## Key Contacts & Escalation

```
On-Call Engineer:     [Name] [Phone]
Engineering Lead:     [Name] [Phone]  
Ops/DevOps Lead:      [Name] [Phone]
Product Manager:      [Name] [Email]

Slack Channels:
#rankings-bot         - Main channel
#incidents            - Critical issues
#deployments          - Deployment records

Escalation:
5 min  → Page on-call
15 min → Page lead + manager
30 min → Full team all-hands
```

---

**This is a living document - update as you learn during rollout!**
