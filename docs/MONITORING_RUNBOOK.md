# Monitoring Runbook for Alfa Rating System

## At a Glance

**Health Endpoint**: `GET /api/health/alfa` → JSON status report  
**Log File**: `/home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log`  
**Metrics DB**: PostgreSQL table `sla_metrics`, `drift_events`, `model_predictions`  
**Dashboard**: (Grafana ready in `monitoring/grafana/dashboards/`)  

---

## Morning Standup (5 min)

Start each day by checking these three things:

### 1. Is the service up?
```bash
curl -s http://localhost:8003/api/health/alfa | jq '.status'
# Expected: "healthy"

# If not healthy, check dashboard:
curl -s http://localhost:8003/api/health/alfa | jq '.components'
```

### 2. Any error spikes?
```bash
# Compare last 6 hours vs yesterday
TODAY_ERRORS=$(tail -1000 /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log | grep -c ERROR)
echo "Errors (last 1000 lines): $TODAY_ERRORS"

# If >20: Investigate immediately
```

### 3. Any SLA breaches?
```bash
# Check recent breaches
python3 << 'EOF'
from backend.sla_tracking import SLATracker
t = SLATracker()
summary = t.get_breach_summary(hours=6)
critical = summary['critical_count']
print(f"🔔 Critical breaches (6h): {critical}")
if critical > 0:
    print("⚠️ Investigate!")
    for b in summary['recent_breaches'][-3:]:
        print(f"  - {b['metric']}: {b['description']}")
EOF
```

---

## Metric Monitoring Tables

### sla_metrics
**Purpose**: Track hourly SLA compliance  
**Update Frequency**: Hourly  
**Retention**: 6 months

```sql
-- View last 24 hours
SELECT 
    metric_date, 
    hour,
    availability_percent,
    latency_p95_ms,
    latency_p99_ms,
    accuracy_brier,
    anomaly_precision
FROM sla_metrics
WHERE metric_date >= CURRENT_DATE - 1
ORDER BY metric_date DESC, hour DESC;
```

### drift_events
**Purpose**: Track data quality drifts  
**Update Frequency**: Real-time  
**Retention**: 3 months

```sql
-- View recent drift events
SELECT 
    drift_type,
    feature_name,
    severity,
    z_score,
    timestamp
FROM drift_events
WHERE timestamp > NOW() - INTERVAL '7 days'
ORDER BY timestamp DESC
LIMIT 20;

-- Drift summary by type
SELECT 
    drift_type,
    severity,
    COUNT(*) as count
FROM drift_events
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY drift_type, severity
ORDER BY count DESC;
```

### model_predictions
**Purpose**: Store all predictions for validation  
**Update Frequency**: Real-time (every prediction)  
**Retention**: 90 days

```sql
-- Daily prediction count
SELECT 
    DATE(prediction_timestamp) as date,
    COUNT(*) as predictions,
    SUM(CASE WHEN actual_outcome IS NOT NULL THEN 1 ELSE 0 END) as resolved,
    ROUND(AVG(brier_score)::numeric, 4) as avg_brier
FROM model_predictions
WHERE prediction_timestamp > NOW() - INTERVAL '30 days'
GROUP BY DATE(prediction_timestamp)
ORDER BY date DESC;

-- Sandbagging flag accuracy
SELECT 
    COUNT(*) as total_flagged,
    SUM(CASE WHEN flagged_correct THEN 1 ELSE 0 END) as correct,
    ROUND(SUM(CASE WHEN flagged_correct THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 1) as accuracy_percent
FROM model_predictions
WHERE is_sandbagging_flagged = TRUE
  AND flagged_correct IS NOT NULL;
```

### health_check_log
**Purpose**: Historical health status  
**Update Frequency**: Every 5 minutes  
**Retention**: 30 days

```sql
-- Find downtime windows
SELECT 
    DATE(timestamp),
    overall_status,
    COUNT(*) as occurrences,
    ROUND(COUNT(*) * 5.0 / 12 / 60, 1) as duration_hours
FROM health_check_log
WHERE overall_status != 'healthy'
  AND timestamp > NOW() - INTERVAL '7 days'
GROUP BY DATE(timestamp), overall_status
ORDER BY DATE(timestamp) DESC;
```

---

## Common Monitoring Queries

### Daily Performance Summary
```python
# Quick performance report
from models.model_performance_tracking import PerformanceTracker
from datetime import datetime, timedelta

tracker = PerformanceTracker()
date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
metrics = tracker.get_daily_metrics(date)

print(f"Performance for {date}:")
for metric, value in metrics.items():
    print(f"  {metric.value}: {value:.4f}")
```

### Drift Detection Status
```python
# Check if any drifts need attention
from models.data_drift_detection import DriftDetector

detector = DriftDetector()
recent = detector.get_drift_summary(hours=24)

if recent['total_events'] > 0:
    print(f"⚠️ {recent['total_events']} drift events in past 24h")
    for feat, count in recent['by_feature'].items():
        print(f"  {feat}: {count}")
else:
    print("✅ No drift detected in past 24h")
```

### Availability Calculation
```python
from backend.sla_tracking import SLATracker
from datetime import datetime, timedelta

tracker = SLATracker()

# Calculate availability from health checks (every 5 min)
healthy_checks = 287  # out of 288 checks (24h * 12 per hour)
availability = (healthy_checks / 288) * 100

print(f"Availability: {availability:.2f}%")
print(f"Downtime: {datetime.now() - timedelta(minutes=5)}")
```

---

## Alert Interpretation Guide

### Error Rate Alerts

**If Error Rate > 1.0% (CRITICAL)**
1. Check recent deployment: `git log --oneline -5`
2. Review error logs: `tail -50 rankings_bot.log | grep ERROR`
3. Check if specific feature affected (auth, predictions, etc.)
4. If not obvious → Rollback last deployment

**If Error Rate 0.5-1.0% (WARNING)**
1. Monitor closely (check every 5 min, not 30)
2. Identify which endpoint has errors
3. Check database/cache status
4. Investigate root cause, plan fix

### Latency Alerts

**If p99 > 2000ms (CRITICAL)**
1. Check database query performance
2. Review cache hit rate
3. Check for locked database connections
4. Look for N+1 queries in logs
5. If persistent → restart API service

**If p95 > 500ms or p99 > 1500ms (WARNING)**
1. Profile recent requests
2. Check if specific endpoints are slow
3. Review database connections
4. Monitor for improvement

### Accuracy/Brier Score Drift

**If Brier increases >5% from baseline (CRITICAL)**
1. Review recent match data quality
2. Check for format/player demographic shifts
3. Investigate anomaly detection (false flagging?)
4. Consider triggering retraining
5. Alert data science team

**If Precision <50% or Recall <70% (WARNING)**
1. Review sandbagging detection logic
2. Check if thresholds need adjustment
3. Investigate false positive spike
4. Is player behavior changing?

### Database Alerts

**If DB Latency > 1000ms (CRITICAL)**
1. Check active connections: `SELECT count(*) FROM pg_stat_activity WHERE state = 'active'`
2. Kill long-running queries if needed
3. Check for locks: `SELECT * FROM pg_locks WHERE NOT granted`
4. Restart database if necessary
5. Review query logs for inefficient queries

### Cache Alerts

**If Cache Unavailable (CRITICAL)**
1. Check Redis: `redis-cli ping`
2. Check Redis memory: `redis-cli INFO memory`
3. If full → flush old data: `redis-cli FLUSHDB ASYNC`
4. Restart Redis if needed
5. Monitor prediction latency (may increase)

---

## Useful Commands

### Quick Health Check
```bash
curl -s http://localhost:8003/api/health/alfa | jq '.'
```

### View Recent Errors
```bash
tail -100 /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log | grep -i error
```

### Database Connection Check
```bash
psql -U alfadb -d alfadb -c "\l"
```

### Redis Status
```bash
redis-cli INFO | grep -E "used_memory|connected_clients|keys_expired"
```

### Process Status
```bash
systemctl status rankings-bot-api
docker ps | grep rankings-bot
```

### Metric Query Template
```sql
SELECT * FROM sla_metrics
WHERE metric_date = CURRENT_DATE
ORDER BY hour DESC
LIMIT 24;
```

---

## Shift Handoff Template

When handing off to next shift:

```
=== ALFA SYSTEM HANDOFF ===

Current Status: [HEALTHY|DEGRADED|UNHEALTHY]

Uptime (24h):
- [%] availability

Recent Issues:
- [Issue 1]: [Status - Investigated | Resolved | Pending]
- [Issue 2]: [Status]

Metrics:
- Error Rate: [%]
- Avg Latency: [ms]
- Brier: [value] (baseline: [value])

Actions Needed:
- [ ] Item 1 - Priority: [HIGH|MEDIUM|LOW]
- [ ] Item 2

Notes:
[Anything else important]

Time: [UTC]
Previous Engineer: [Name]
Current Engineer: [Name]
```

---

## Escalation Flowchart

```
Is service healthy?
├─ YES → Check metrics/alerts, look for trends
└─ NO → Is error rate >1%?
    ├─ YES → CRITICAL: Page on-call, prepare rollback
    └─ NO → Is availability <99%?
        ├─ YES → MAJOR: Alert team, investigate
        └─ NO → MINOR: Log, monitor, fix during business hours
```

---

## Key Metrics to Track Daily

| Metric | Target | Warning | Critical | Check |
|--------|--------|---------|----------|-------|
| Availability | 99.9% | <99.5% | <99.0% | Health endpoint |
| Error Rate | <0.1% | >0.5% | >1.0% | Log analysis |
| p95 Latency | <500ms | >750ms | >1000ms | Monitoring table |
| p99 Latency | <2000ms | >3000ms | >5000ms | Monitoring table |
| Brier Score | <0.20 | >0.25 | >0.30 | Daily metrics |
| Anomaly Precision | >50% | <40% | <30% | Validation table |

---

## Related Documents

- [INCIDENT_RESPONSE_PLAN.md](INCIDENT_RESPONSE_PLAN.md) - How to respond to issues
- [ALFA_MAINTENANCE_GUIDE.md](ALFA_MAINTENANCE_GUIDE.md) - Routine maintenance
- [TROUBLESHOOTING_GUIDE.md](TROUBLESHOOTING_GUIDE.md) - Common problems & fixes
- [EMERGENCY_PROCEDURES.md](EMERGENCY_PROCEDURES.md) - Crisis response

---

**Last Updated**: 2026-02-16  
**Quick Reference Card**: Print and post at desk
