# Incident Response Plan for Alfa Rating System

## Overview

This document defines the incident response procedures for the Alfa rating production system. It covers severity levels, response procedures, and post-incident analysis.

## Severity Levels

### 🔴 CRITICAL (P1)
**Response Time: 5 minutes**

Incidents that severely impact production or users.

#### Conditions
- Error rate > 2%
- Availability < 99% (>14.4 min outage/day)
- Brier score > 0.35 (model accuracy degraded significantly)
- Complete service unavailability
- Security breach or data loss

#### Response Procedures
1. **Immediate (0-2 min)**:
   - Page on-call team (SMS/phone/Slack)
   - Alert leadership and stakeholders
   - Initiate war room on Slack #incidents channel
   - Start incident timeline logging

2. **Assessment (2-5 min)**:
   - Identify root cause (check recent deployments, error logs)
   - Confirm impact scope (which users/features affected)
   - Review last successful deployment timestamp

3. **Action (5-15 min)**:
   - **Auto-rollback**: Revert to last stable Fargo model if Alfa issue
   - **Service restart**: If cache/database issue, attempt graceful restart
   - **Isolation**: Route traffic to healthy instance if applicable
   - Do NOT attempt complex fixes - rollback is safer

4. **Communication**:
   - Update incident status every 2 minutes
   - Post status to #incidents Slack
   - Notify users via status page if appropriate

5. **Recovery Steps**:
   ```bash
   # Rollback to Fargo ratings
   cd /home/ansible/rankings-bot/Rankings-Bot
   ./scripts/rollback_alfa.sh
   systemctl restart rankings-bot-api
   
   # Verify health
   curl http://localhost:8003/api/health/alfa
   ```

#### Post-Incident (Next 24 hours)
- Complete RCA (Root Cause Analysis) within 4 hours
- Identify 3-5 preventive measures
- Schedule follow-up meeting within 24 hours

---

### 🟊 MAJOR (P2)
**Response Time: 15 minutes**

Significant issues affecting functionality or performance.

#### Conditions
- Error rate 1-2%
- Availability 99-99.5% (14-43 min outage/month)
- Brier score 0.30-0.35 (accuracy degradation)
- Anomaly detection precision < 30% (many false positives)
- Latency p99 > 3 seconds consistently
- Data quality issues detected

#### Response Procedures
1. **Alert team** (within 5 min)
   - Post to #incidents channel
   - Notify on-call engineer via Slack
   - Prepare incident summary

2. **Investigate** (5-15 min)
   - Check recent changes/deployments
   - Review error logs and metrics
   - Compare current vs baseline performance

3. **Action** (15-30 min)
   - Prepare rollback plan (don't execute immediately)
   - Identify potential fixes
   - Decide: Fix or Rollback

4. **Escalation**
   - If fix takes >30 min: Execute rollback
   - If fix in progress: Provide updates every 10 min

#### Example Response Scenarios

**Scenario 1: High Error Rate**
```bash
# Check error logs
tail -f /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log | grep ERROR

# Monitor health endpoint
watch -n 5 'curl -s http://localhost:8003/api/health/alfa | jq .'

# If no improvement in 20 min: rollback
./scripts/rollback_alfa.sh
```

**Scenario 2: Accuracy Degradation**
```bash
# Compare recent predictions to baseline
python3 << 'EOF'
from backend.sla_tracking import SLATracker
tracker = SLATracker()
summary = tracker.get_breach_summary(hours=6)
print(f"Breaches: {summary['critical_count']} critical, {summary['warning_count']} warnings")
EOF

# If persistent: Trigger retraining
./scripts/retrain_alfa_pipeline.sh --dry-run
```

**Scenario 3: Database Connection Issues**
```bash
# Check database status
psql -U alfadb -d alfadb -c "SELECT 1"

# Check connections
psql -U alfadb -d alfadb -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"

# Restart connection pool
docker-compose restart rankings-bot-api
```

---

### 🟡 MINOR (P3)
**Response Time: 2 hours**

Issues that don't significantly impact service but should be monitored.

#### Conditions
- Latency p99 > 2 seconds (elevated but acceptable)
- Anomaly detection false positive rate > 20%
- New player convergence degraded by 5-10%
- Single component degraded (warning status)
- Non-critical features unavailable

#### Response Procedures
1. **Log incident** in #incidents
2. **Assess impact** - will this affect users?
3. **Investigate during business hours** - no page needed
4. **Schedule fix** within 1 week
5. **Document learnings**

#### Monitoring Response
- Increase monitoring frequency (every 5 min instead of 30 min)
- Alert if escalates to MAJOR
- Plan fix for next maintenance window

---

## Incident Response Procedures

### Immediate Actions (All Levels)

1. **Incident Acknowledgment**
   - Slack reaction to alert (✅ to acknowledge)
   - Create incident thread in #incidents
   - Post: "Acknowledged at HH:MM UTC"

2. **Impact Assessment**
   ```bash
   # Quick health check
   curl -s http://localhost:8003/api/health/alfa | jq .
   
   # Check error rate
   tail -100 /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log | grep ERROR | wc -l
   
   # Monitor metrics
   cd /home/ansible/rankings-bot/Rankings-Bot
   python3 -c "
   from backend.sla_tracking import SLATracker
   t = SLATracker()
   print(t.get_breach_summary(hours=1))
   "
   ```

3. **Severity Classification**
   - Is service completely down? → CRITICAL
   - Are errors > 1%? → MAJOR or CRITICAL
   - Is performance degraded? → MAJOR
   - Is there a warning alert? → MINOR

### Communication Template

**For Slack #incidents:**
```
:rotating_light: **INCIDENT: [TITLE]**
Severity: [CRITICAL|MAJOR|MINOR]
Time Started: [UTC]

**Impact**: [What's broken]
**Status**: Investigating...
**Next Update**: In 5 minutes

**On-Call**: @engineer-name
```

### Rollback Procedures

#### Rollback Alfa to Fargo
```bash
cd /home/ansible/rankings-bot/Rankings-Bot

# Verify rollback script exists
ls -la scripts/rollback_alfa.sh

# Execute rollback
./scripts/rollback_alfa.sh

# Verify health
curl -s http://localhost:8003/api/health/alfa | jq .status
```

#### Restart Service
```bash
# Check current status
systemctl status rankings-bot-api

# Restart API
systemctl restart rankings-bot-api

# Wait 10 seconds, then health check
sleep 10
curl http://localhost:8003/api/health/alfa

# Follow logs
journalctl -u rankings-bot-api -f
```

---

## Post-Incident Procedures

### RCA (Root Cause Analysis)

**Due**: Within 4 hours of critical, 24 hours of major

**Template**:
```markdown
# RCA: [Incident Title]

## Timeline
- HH:MM UTC - Issue started
- HH:MM UTC - Issue detected
- HH:MM UTC - Mitigation actions started
- HH:MM UTC - Service recovered

## Root Cause
[What actually caused this?]

## Contributing Factors
- [Factor 1]
- [Factor 2]

## Detection Gap
[Why wasn't this caught earlier?]

## Preventive Measures
1. [Action 1] - Owner: [Name] - Due: [Date]
2. [Action 2] - Owner: [Name] - Due: [Date]
3. [Action 3] - Owner: [Name] - Due: [Date]

## Learning
[Key insight from this incident]
```

### Incident Closure

- [ ] RCA complete and reviewed
- [ ] All preventive actions assigned
- [ ] No customer communication needed
- [ ] Incident logged in tracking system
- [ ] Follow-up meeting scheduled (if needed)

**Closure Template for Slack:**
```
:white_check_mark: **INCIDENT CLOSED**

Root Cause: [Brief summary]
Time to Detect: [Duration]
Time to Resolve: [Duration]

RCA: [Link to document]
Preventive Actions: [Link to issues/PRs]

Lessons learned: [Key takeaway]
```

---

## Runbook Quick Reference

### Command Quick Links

```bash
# Health & Status
curl http://localhost:8003/api/health/alfa              # Quick health
curl http://localhost:8003/api/health/alfa/detailed     # Detailed health

# Logs
tail -f /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log

# Database
psql -U alfadb -d alfadb -c "SELECT NOW()"

# Redis
redis-cli ping

# Metrics
docker stats rankings-bot-api

# Rollback
/home/ansible/rankings-bot/Rankings-Bot/scripts/rollback_alfa.sh

# Restart
systemctl restart rankings-bot-api
```

### On-Call Contact Tree

**Tier 1** (First Response): [Engineer name, phone, email]
**Tier 2** (Escalation): [Senior engineer, phone, email]
**Tier 3** (Leadership): [Manager, phone, email]

---

## Testing & Drills

- Monthly: Chaos engineering test (simulate failures)
- Quarterly: Full RCA drill (simulate incident, practice response)
- Annually: Update runbooks and test all recovery procedures

---

## Related Documents

- [ALFA_MAINTENANCE_GUIDE.md](ALFA_MAINTENANCE_GUIDE.md) - Routine maintenance
- [SLA_DEFINITIONS.md](SLA_DEFINITIONS.md) - SLA targets
- [MONITORING_RUNBOOK.md](MONITORING_RUNBOOK.md) - Day-to-day monitoring
- [TROUBLESHOOTING_GUIDE.md](TROUBLESHOOTING_GUIDE.md) - Common issues

---

**Last Updated**: 2026-02-16
**Next Review**: 2026-03-16
