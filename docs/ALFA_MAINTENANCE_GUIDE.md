# Alfa System Maintenance Guide

## Overview

This document defines routine maintenance procedures for the Alfa rating system. Scheduled tasks ensure optimal performance, data quality, and system reliability.

## Daily Maintenance (Morning Check)

**Time**: 06:00 UTC (or first thing in morning)  
**Duration**: 15-30 minutes  
**Owner**: On-call engineer

### 1. System Health Verification

```bash
#!/bin/bash
# Daily health check

PROJECT_ROOT="/home/ansible/rankings-bot/Rankings-Bot"
cd "$PROJECT_ROOT"

# 1. Service status
echo "=== Service Status ==="
systemctl status rankings-bot-api || echo "❌ Service down"

# 2. Health endpoint
echo "=== Health Check ==="
HEALTH=$(curl -s http://localhost:8003/api/health/alfa)
echo "$HEALTH" | jq .

# 3. Recent errors
echo "=== Error Count (Last 6 hours) ==="
tail -1000 rankings_bot.log | grep -c "ERROR\|CRITICAL" || echo "0"

# 4. Database connectivity
echo "=== Database Status ==="
psql -U alfadb -d alfadb -c "SELECT NOW()" > /dev/null && echo "✅ Connected" || echo "❌ Failed"
```

### 2. Metric Review

```python
# Daily metric summary
from backend.sla_tracking import SLATracker
from pathlib import Path

tracker = SLATracker()

# Last 24 hours
summary = tracker.get_breach_summary(hours=24)
print(f"""
Daily Summary:
- Total SLA breaches: {summary['total_breaches']}
- Critical: {summary['critical_count']}
- Warnings: {summary['warning_count']}
""")

# Check for alerts
if summary['critical_count'] > 0:
    print("⚠️ Critical breaches detected! Investigate immediately.")
if summary['warning_count'] > 3:
    print("⚠️ Multiple warnings. Review metrics for trends.")
```

### 3. Error Log Review

Check for patterns:
- Search for repeating ERROR entries
- Look for database connection errors
- Check for model loading failures
- Review authentication errors

```bash
tail -500 /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log | grep ERROR | sort | uniq -c | sort -rn | head -10
```

### 4. Disk Space Check

```bash
# Check log and data directories
du -sh /home/ansible/rankings-bot/Rankings-Bot/logs/
du -sh /home/ansible/rankings-bot/Rankings-Bot/data/
df -h /

# Alert if >80% usage
```

### 5. Action Items

If issues found:
- [ ] Critical alert → Follow incident response plan
- [ ] Warning alert → Monitor closely, prepare for action
- [ ] Error surge → Investigate logs, check recent changes
- [ ] Disk near full → Archive old logs/data

---

## Weekly Maintenance (Monday Morning)

**Time**: Monday 07:00 UTC  
**Duration**: 1-2 hours  
**Owner**: Data engineer or ML lead

### 1. Data Quality Analysis

```python
# Check for data drifts
from models.data_drift_detection import DriftDetector

detector = DriftDetector()

# Summary of past week
past_week = detector.get_drift_summary(hours=168)
print(f"Weekly Drift Summary:")
print(f"- Total events: {past_week['total_events']}")
print(f"- Severe: {past_week['by_severity'].get('severe', 0)}")
print(f"- Moderate: {past_week['by_severity'].get('moderate', 0)}")

# Check if retraining recommended
should_retrain, reason = detector.recommend_retraining()
if should_retrain:
    print(f"✅ Retraining recommended: {reason}")
else:
    print(f"✅ No retraining needed")
```

### 2. Performance Trend Analysis

```python
# Compare week-over-week metrics
from models.model_performance_tracking import PerformanceTracker

tracker = PerformanceTracker()
comparison = tracker.compare_to_baseline()

print("Performance vs Baseline:")
for metric, delta in comparison['deltas'].items():
    print(f"  {metric}: {delta['current']:.4f} (delta: {delta['delta_percent']:+.1f}%)")

# Review any alerts
for alert in comparison['alerts']:
    print(f"⚠️ {alert['level']}: {alert['message']}")
```

### 3. User Feedback Review

```sql
-- Get weekly feedback summary
SELECT 
    feedback_type,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) as percent
FROM user_feedback
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY feedback_type
ORDER BY count DESC;

-- Look for negative feedback patterns
SELECT comment, COUNT(*) as occurrences
FROM user_feedback
WHERE feedback_type = 'thumbs_down' 
  AND created_at > NOW() - INTERVAL '7 days'
  AND comment IS NOT NULL
GROUP BY comment
ORDER BY occurrences DESC
LIMIT 10;
```

### 4. System Resource Audit

```bash
# Check CPU/Memory trends over week
grep "cpu_percent\|memory_percent" /home/ansible/rankings-bot/Rankings-Bot/logs/health_check.log \
    | tail -168 | \
    awk '{sum+=$NF; count++} END {print "Average: "sum/count"%"}'

# Check disk usage growth
du -s /home/ansible/rankings-bot/Rankings-Bot/data/* | sort -rn | head -10
```

### 5. Dependency & Security Updates

```bash
# Check for available updates
cd /home/ansible/rankings-bot/Rankings-Bot
pip list --outdated > /tmp/outdated_packages.txt

# Review for critical security patches
cat /tmp/outdated_packages.txt | grep -E "Django|sqlalchemy|fastapi" || echo "✅ Core deps up to date"
```

### 6. Weekly Report

Save summary for records:

```python
from pathlib import Path
from datetime import datetime

report = f"""
# Weekly Maintenance Report - {datetime.now().strftime('%Y-%m-%d')}

## System Health
- Uptime: [from daily checks]
- Error Rate: [percentage]
- Avg Response Time: [ms]

## Performance
[From weekly analysis above]

## Data Quality
[Drift summary]

## Recommendations
- [Action 1]
- [Action 2]

**Next Steps**: [Tasks for next week]
"""

Path("/home/ansible/rankings-bot/Rankings-Bot/reports/WEEKLY_REPORT.md").write_text(report)
```

---

## Monthly Maintenance (First Friday of Month)

**Time**: First Friday, 08:00 UTC  
**Duration**: 2-4 hours  
**Owner**: ML lead / Data scientist

### 1. SLA Report Generation

```python
from backend.sla_tracking import SLATracker
from datetime import datetime
from dateutil.relativedelta import relativedelta

tracker = SLATracker()

# Generate for last month
last_month = (datetime.now() - relativedelta(months=1)).strftime("%Y-%m")
report = tracker.generate_monthly_report(last_month)

print(f"SLA Report for {last_month} generated and saved")
print(report)
```

### 2. Performance Report

```python
from models.model_performance_tracking import PerformanceTracker

tracker = PerformanceTracker()
comparison = tracker.compare_to_baseline()

report = f"""
# Monthly Performance Report

## Model Metrics
{comparison['current']}

## Baseline Comparison
{comparison['baseline']}

## Alerts
{comparison['alerts']}
"""

print(report)
```

### 3. Data Quality Audit

```python
from models.data_drift_detection import DriftDetector

detector = DriftDetector()
month_drift = detector.get_drift_summary(hours=730)  # ~30 days

print(f"""
Data Drift Summary (30 days):
- Total events: {month_drift['total_events']}
- By severity: {month_drift['by_severity']}
- By type: {month_drift['by_type']}
- Affected features: {list(month_drift['by_feature'].keys())}
""")
```

### 4. Model Audit

- [ ] Compare training metrics vs production metrics
- [ ] Verify model file integrity (checksums)
- [ ] Check model version tracking
- [ ] Review any failed predictions
- [ ] Assess cold-start performance

```bash
# Model integrity check
cd /home/ansible/rankings-bot/Rankings-Bot/models
ls -lah *.pkl *.json
sha256sum *.pkl > /tmp/model_checksums.txt
```

### 5. Database Maintenance

```sql
-- Monthly database cleanup and optimization

-- Archive old predictions (>90 days)
DELETE FROM model_predictions 
WHERE prediction_timestamp < NOW() - INTERVAL '90 days'
  AND outcome_timestamp IS NOT NULL;

-- Vacuum and analyze
VACUUM ANALYZE sla_metrics;
VACUUM ANALYZE drift_events;
VACUUM ANALYZE model_predictions;

-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Replace indexes with no usage (>90 days)
SELECT indexname FROM pg_stat_user_indexes WHERE idx_scan = 0 AND idx_created < NOW() - INTERVAL '90 days';
```

### 6. Documentation Update

- [ ] Update [MONITORING_RUNBOOK.md](MONITORING_RUNBOOK.md) if procedures changed
- [ ] Update thresholds/alerts based on learnings
- [ ] Review and update SLA targets if needed
- [ ] Document any incidents and resolutions

### 7. Team Review Meeting

Schedule meeting to discuss:
- Performance trends
- Data quality issues
- System reliability
- Plans for next month

---

## Quarterly Review (Every 90 Days)

**Time**: Every 3 months on 15th  
**Duration**: 4-6 hours  
**Owner**: Team lead + data scientist

### 1. Full Model Audit

Compare training vs production:
- Brier score drift
- Accuracy preservation
- Cold-start convergence
- Anomaly detection effectiveness

### 2. Meet with Domain Experts

Review with billiards domain experts:
- Are predictions accurate from player perspective?
- Any gaming patterns that violate model assumptions?
- New rule changes that affect ratings?

### 3. System Architecture Review

- Database scaling needs
- API performance bottlenecks
- Cache effectiveness
- Monitoring alert tuning

### 4. Retraining Assessment

Decide on next training schedule:
- Is retraining needed soon?
- What new data will be available?
- Are there model improvements to explore?

### 5. Strategic Planning

Document for next quarter:
- Major improvements needed
- Infrastructure upgrades
- Research directions
- Risk mitigation

---

## Backup & Archive Procedures

### Daily Backup

```bash
#!/bin/bash
# Daily database backup (run at 03:00 UTC)

BACKUP_DIR="/backups/alfa-db/daily"
mkdir -p "$BACKUP_DIR"

pg_dump -U alfadb -d alfadb > "$BACKUP_DIR/alfa_$(date +%Y%m%d_%H%M%S).sql"

# Keep last 30 days
find "$BACKUP_DIR" -name "*.sql" -mtime +30 -delete
```

### Weekly Archive

```bash
#!/bin/bash
# Archive old model predictions to cold storage

ARCHIVE_DIR="/archive/model_predictions"
mkdir -p "$ARCHIVE_DIR"

psql -U alfadb -d alfadb << SQL
COPY (
  SELECT * FROM model_predictions 
  WHERE prediction_timestamp < NOW() - INTERVAL '30 days'
    AND outcome_timestamp IS NOT NULL
) TO STDIN CSV;
SQL > "$ARCHIVE_DIR/predictions_$(date +%Y%m%d).csv"

# Compress
gzip "$ARCHIVE_DIR/predictions_$(date +%Y%m%d).csv"
```

### Monthly Model Backup

```bash
#!/bin/bash
# Archive current model version

ARCHIVE_DIR="/archive/models"
mkdir -p "$ARCHIVE_DIR"

cp /home/ansible/rankings-bot/Rankings-Bot/models/alfa_logistic_regression.pkl \
   "$ARCHIVE_DIR/alfa_$(date +%Y%m%d_%H%M%S).pkl"
```

---

## Alert Threshold Tuning

Review and adjust thresholds monthly:

| Metric | Current | Min | Max | Last Adjusted |
|--------|---------|-----|-----|---------------|
| Error Rate Warning | 0.5% | 0.1% | 2.0% | 2026-01-15 |
| Error Rate Critical | 1.0% | 0.5% | 5.0% | 2026-01-15 |
| Latency p99 Warning | 1500ms | 1000ms | 3000ms | 2026-01-15 |
| Latency p99 Critical | 2000ms | 1500ms | 5000ms | 2026-01-15 |
| Brier Drift Warning | ±5% | ±3% | ±10% | 2026-01-15 |
| Anomaly Precision Min | 50% | 30% | 70% | 2026-01-15 |

---

## Escalation Procedures

For unresolved maintenance items:

1. **Low Priority** (1-2 weeks): Add to backlog
2. **Medium Priority** (3-5 days): Schedule with team
3. **High Priority** (1-3 days): Escalate to manager
4. **Urgent** (same day): Follow incident response plan

---

## Related Documents

- [MONITORING_RUNBOOK.md](MONITORING_RUNBOOK.md) - Daily operations
- [INCIDENT_RESPONSE_PLAN.md](INCIDENT_RESPONSE_PLAN.md) - Crisis procedures
- [TROUBLESHOOTING_GUIDE.md](TROUBLESHOOTING_GUIDE.md) - Common issues
- [SLA_DEFINITIONS.md](SLA_DEFINITIONS.md) - Performance targets

---

**Last Updated**: 2026-02-16  
**Next Review**: 2026-03-16
