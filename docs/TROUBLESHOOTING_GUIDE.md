# Troubleshooting Guide for Alfa Rating System

## Quick Diagnostics (1-2 minutes)

### Is the service running?
```bash
curl -s http://localhost:8003/api/health/alfa | jq '.status'
```
- If response: service is responding
- If no response: service may be down

### What's the overall health?
```bash
curl -s http://localhost:8003/api/health/alfa | jq '.components'
```
Output JSON shows status of: model, database, cache, system resources, error rate

### Which component is failing?
```bash
curl -s http://localhost:8003/api/health/alfa/detailed | jq '.'
```
Detailed output shows:
- `model`: Status, latency, error message
- `database`: Status, latency, error message
- `cache`: Status, latency, error message
- `system_resources`: CPU%, memory%, thread count
- `error_rate`: % errors in recent log

---

## Common Issues & Solutions

### 🔴 "Service Unavailable" / Connection Refused

**Symptom**: `curl: Failed to connect`

**Diagnosis**:
```bash
# Check if process running
ps aux | grep rankings-bot-api

# Check port is listening
netstat -tlnp | grep 8003

# Check service status
systemctl status rankings-bot-api
```

**Solutions**:

**1. Service not running**
```bash
systemctl start rankings-bot-api
sleep 5
curl http://localhost:8003/api/health/alfa
```

**2. Port in use**
```bash
# Find what's on port 8003
lsof -i :8003

# Kill it (if necessary)
kill -9 <PID>

# Restart service
systemctl restart rankings-bot-api
```

**3. Docker container issue**
```bash
docker ps | grep rankings-bot
docker logs rankings-bot-api | tail -50
docker restart rankings-bot-api
```

---

### 🔴 High Error Rate (>1%)

**Symptom**: Health endpoint shows error_rate > 1.0%

**Diagnosis**:
```bash
# See recent errors
tail -200 /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log | grep ERROR

# Count errors by type
tail -1000 rankings_bot.log | grep ERROR | awk -F': ' '{print $2}' | sort | uniq -c | sort -rn | head -10
```

**Common Causes & Solutions**:

**Case 1: Database connection errors**
```
Error: "DatabaseError: connection pool timeout"
```
→ Database unreachable or swamped

```bash
# Check database
psql -U alfadb -d alfadb -c "SELECT NOW()"

# If fails: restart docker container
docker-compose -f docker-compose.yml restart postgres

# If database slow: check query logs
psql -U alfadb -d alfadb -c "SELECT pid, query, query_start FROM pg_stat_activity WHERE state='active' AND query NOT LIKE '%idle%';"

# Kill long-running query if necessary
psql -U alfadb -d alfadb -c "SELECT pg_terminate_backend(123456)" -- Replace PID
```

**Case 2: Model loading errors**
```
Error: "Model not found" or "Failed to load model"
```
→ Model file missing or corrupted

```bash
# Check model exists
ls -la /home/ansible/rankings-bot/Rankings-Bot/models/alfa_logistic_regression.pkl

# Verify checksum
cd /home/ansible/rankings-bot/Rankings-Bot
sha256sum models/alfa_logistic_regression.pkl

# Restore from backup if needed
cp /archive/models/alfa_logistic_regression_backup.pkl models/alfa_logistic_regression.pkl
systemctl restart rankings-bot-api
```

**Case 3: Authentication/API errors**
```
Error: "Authentication failed" or "Invalid endpoint"
```
→ Recent code change or misconfiguration

```bash
# Check last deployment
git log --oneline -5 -- api/routes/

# Rollback if necessary
git revert <commit-hash>

# Or restore previous version
docker-compose pull rankings-bot-api
docker-compose up -d rankings-bot-api
```

**Case 4: Validation errors**
```
Error: "ValidationError: Invalid prediction input"
```
→ Input data format changed or model expects different features

```bash
# Check what model expects
python3 << 'EOF'
from models.alfa_logistic_regression import AlfaModel
model = AlfaModel()
print(f"Expected features: {model.feature_names}")
print(f"Feature count: {model.n_features}")
EOF

# Verify API is sending correct data
grep "prediction" /home/ansible/rankings-bot/Rankings-Bot/api/routes/rankings.py | head -20
```

---

### 🟊 High Latency (p99 > 2000ms)

**Symptom**: Predictions taking >2 seconds

**Diagnosis**:
```bash
# Check database latency
time psql -U alfadb -d alfadb -c "SELECT 1"

# Check model inference time
python3 << 'EOF'
import time
from models.alfa_logistic_regression import AlfaModel

model = AlfaModel()
start = time.perf_counter()
pred = model.predict(1200, 1300)
elapsed = (time.perf_counter() - start) * 1000
print(f"Model inference: {elapsed:.1f}ms")
EOF

# Check API response time
time curl -s http://localhost:8003/api/alfa_ratings/compare
```

**Solutions**:

**1. Database is slow**
```bash
# Profile queries
psql -U alfadb -d alfadb -c "EXPLAIN ANALYZE SELECT * FROM matches LIMIT 10"

# Add index if missing
psql -U alfadb -d alfadb -c "CREATE INDEX idx_matches_recent ON matches(created_at DESC)"

# Increase connection pool
# Edit docker-compose or config file, increase max_connections
docker-compose restart postgres
```

**2. Cache not working**
```bash
# Check Redis
redis-cli ping
# Expected: PONG

# Check hit rate
redis-cli INFO stats | grep hit_ratio

# Clear cache if corrupted
redis-cli FLUSHDB

# Restart Redis
docker-compose restart redis
```

**3. Model inference slow**
- Model may be too large
- Check if using CPU instead of GPU
- Consider model optimization
- Profile code: `python3 -m cProfile -s cumtime script.py`

---

### 🟊 Accuracy Degradation (Brier >0.25)

**Symptom**: Model predictions less accurate than baseline

**Diagnosis**:
```python
# Check recent predictions
import pandas as pd
from models.model_performance_tracking import PerformanceTracker

tracker = PerformanceTracker()
recent = tracker.compare_to_baseline()
print(f"Brier score: {recent['current']['brier']}")
print(f"Vs baseline: {recent['baseline']['brier']}")
```

**Solutions**:

**1. Data distribution changed**
```python
# Check for data drift
from models.data_drift_detection import DriftDetector

detector = DriftDetector()
drift_summary = detector.get_drift_summary(hours=24)
print(f"Drift events: {drift_summary['total_events']}")

if drift_summary['total_events'] > 5:
    print("⚠️ Significant drift detected - may need retraining")
```

**2. Model needs retraining**
```bash
# Start retraining pipeline
./scripts/retrain_alfa_pipeline.sh

# Or dry-run to test
./scripts/retrain_alfa_pipeline.sh --dry-run
```

**3. Check for data quality issues**
```sql
-- Check for missing values
SELECT COUNT(*) as missing_ratings
FROM matches
WHERE operator_rating IS NULL OR player2_rating IS NULL;

-- Check for outliers
SELECT PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY rating)
FROM (
    SELECT operator_rating as rating FROM matches
    UNION ALL
    SELECT player2_rating FROM matches
) t;
```

---

### 🟡 False Positives (Sandbagging Detection >20%)

**Symptom**: Too many players flagged as sandbagging who aren't

**Diagnosis**:
```python
# Check anomaly validation metrics
from models.model_performance_tracking import PerformanceTracker

tracker = PerformanceTracker()
validation = tracker.anomaly_validation.compute_metrics()
print(f"Precision: {validation['precision']:.2%}")
print(f"False positives: {validation['false_positives']}")
```

**Solutions**:

**1. Adjust detection threshold**
```python
# For now, edit thresholds in models/alfa_anomaly_detection.py
# Increase threshold to reduce false positives
SANDBAGGING_THRESHOLD = 0.65  # was 0.50
```

**2. Retrain with different parameters**
```bash
./scripts/retrain_alfa_pipeline.sh --force
```

**3. Collect domain expert feedback**
- Have experts review flagged players
- Adjust features if patterns emerge
- Update training data labels

---

### 🟡 New Player Convergence Slow

**Symptom**: New players not converging within expected games

**Diagnosis**:
```python
# Check cold-start performance
from models.model_performance_tracking import PerformanceTracker

tracker = PerformanceTracker()
convergence = tracker.cold_start.get_convergence_stats(num_games=20)
print(f"% converged by game 20: {convergence['convergence_by_threshold']['±30pts']}")
```

**Solutions**:

**1. Initial rating algorithm issue**
```python
# Check if initial ratings are good
# Review cold_start_tracking table
sql = "SELECT AVG(final_rating - initial_rating) FROM cold_start_tracking"

# If initial rating is very far off: may need better seeding algorithm
```

**2. Insufficient early game data**
- Some players may not have enough match data
- This is expected behavior
- Ensure system collects matches

**3. Model may not handle new players well**
- Review model training on new player subset
- Consider special handling for cold-start users
- Implement rating adjustment algorithm

---

### Database Issues

#### Can't Connect to Database

```bash
# Test connection
psql -U alfadb -d alfadb -c "SELECT NOW()"

# If fails:
# 1. Check if PostgreSQL running
docker ps | grep postgres

# 2. Check logs
docker logs rankings-bot-postgres

# 3. Check credentials
echo $DATABASE_URL  # Verify URL is correct

# 4. Restart container
docker-compose restart postgres
sleep 5
```

#### Database Locked

```bash
# High number of "waiting for..."
psql -U alfadb -d alfadb -c "
SELECT 
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
"

# Kill blocking query
psql -U alfadb -d alfadb -c "SELECT pg_terminate_backend(<PID>)"
```

#### Disk Space Full

```bash
# Check usage
df -h /var/lib/postgresql

# Find large tables
psql -U alfadb -d alfadb << SQL
SELECT schemaname, tablename, 
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
SQL

# Archive old predictions
psql -U alfadb -d alfadb -c "
DELETE FROM model_predictions
WHERE prediction_timestamp < NOW() - INTERVAL '60 days'
  AND outcome_timestamp IS NOT NULL;
"

# Vacuum database
psql -U alfadb -d alfadb -c "VACUUM FULL"
```

---

### Cache (Redis) Issues

#### Redis Not Available

```bash
# Test connection
redis-cli ping

# If no response:
# 1. Check if running
docker ps | grep redis

# 2. Check logs
docker logs rankings-bot-redis

# 3. Restart
docker-compose restart redis

# 4. Test again
redis-cli ping  # Should return PONG
```

#### Redis Out of Memory

```bash
# Check memory
redis-cli INFO memory | grep used_memory_human

# Check current usage
redis-cli MEMORY STATS

# Clear cache
redis-cli FLUSHDB

# Or: Set eviction policy
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

---

## Diagnostic Scripts

### Health Check Script
```bash
#!/bin/bash
echo "=== ALFA SYSTEM DIAGNOSTICS ==="
echo ""
echo "1. Service Status"
systemctl status rankings-bot-api --no-pager | head -5

echo ""
echo "2. Health Endpoint"
curl -s http://localhost:8003/api/health/alfa | jq '.status'

echo ""
echo "3. Error Count (Last Hour)"
tail -500 /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log | grep -c ERROR || echo "0"

echo ""
echo "4. Database"
psql -U alfadb -d alfadb -c "SELECT NOW()" && echo "✅ Connected" || echo "❌ Failed"

echo ""
echo "5. Redis"
redis-cli ping && echo "✅ Connected" || echo "❌ Failed"

echo ""
echo "=== END DIAGNOSTICS ==="
```

### System Resource Check
```bash
#!/bin/bash
echo "=== SYSTEM RESOURCES ==="
echo "CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)%"
echo "Memory: $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
echo "Disk: $(df -h / | awk 'NR==2 {print $5}')"
echo "=== END ==="
```

---

## When All Else Fails: Full Restart

```bash
#!/bin/bash
# Nuclear option - restarts everything

set -e

echo "Starting full system restart..."

# 1. Stop API
systemctl stop rankings-bot-api
sleep 2

# 2. Stop containers
docker-compose down
sleep 2

# 3. Start containers
docker-compose up -d
sleep 5

# 4. Start API
systemctl start rankings-bot-api
sleep 5

# 5. Verify
curl -s http://localhost:8003/api/health/alfa | jq '.status'

echo "System restart complete"
```

---

## Getting Help

If issue persists after trying above:

1. **Collect diagnostics**:
```bash
curl -s http://localhost:8003/api/health/alfa > /tmp/health.json
tail -500 /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log > /tmp/recent_logs.txt
docker logs rankings-bot-api > /tmp/docker_logs.txt
psql -U alfadb -d alfadb -c "SELECT * FROM sla_breaches ORDER BY timestamp DESC LIMIT 10" > /tmp/breaches.txt
```

2. **Contact**:
   - Data Science Lead: [Name, contact]
   - DevOps Engineer: [Name, contact]
   - On-Call: [Number from on-call rotation]

3. **Provide**:
   - What you tried
   - Files from step 1
   - Exact error message
   - When issue started

---

**Last Updated**: 2026-02-16
