# Emergency Procedures for Alfa Rating System

## Purpose

This document provides step-by-step procedures for handling service emergencies. Use this when normal troubleshooting isn't working or when you need to minimize downtime.

---

## 🔴 CRITICAL EMERGENCY: Service is Down

**Goal**: Restore service to ANY working state in <5 minutes

### Immediate (First 2 min)

1. **Confirm the problem**
   ```bash
   curl -s http://localhost:8003/api/health/alfa
   # Expected: Response with status
   # Actual: No response, 503, or 500 error
   ```

2. **Notify stakeholders**
   - Slack: Post to #incidents "🚨 CRITICAL: Alfa service down - investigating"
   - On-call pager
   - Leadership (if needed)

3. **Start incident clock**
   - Note exact time issue started
   - You have ~5 min to get service working

### Action Phase (Next 3 min)

**Try Option 1: Quick Restart (90% success rate)**
```bash
systemctl restart rankings-bot-api
sleep 10
curl -s http://localhost:8003/api/health/alfa | jq '.status'

# If healthy: Notify stakeholders of recovery
# If still down: Try Option 2
```

**Try Option 2: Force Stop & Clean Restart**
```bash
# Kill any hanging processes
pkill -9 -f ratings-bot-api || true
sleep 2

# Reset service
systemctl reset-failed rankings-bot-api || true
sleep 2

# Start service fresh
systemctl start rankings-bot-api
sleep 10
curl -s http://localhost:8003/api/health/alfa | jq '.status'
```

**Try Option 3: Docker Level Restart**
```bash
# Restart all containers
docker-compose restart rankings-bot-api
docker-compose restart postgres
docker-compose restart redis
sleep 15

# Check health
curl -s http://localhost:8003/api/health/alfa | jq '.status'
```

### Recovery Phase (If still down after 5 min)

**Execute Rollback to Last Known Good State**
```bash
# 1. Revert to Fargo ratings (always works)
cd /home/ansible/rankings-bot/Rankings-Bot
./scripts/rollback_alfa.sh

# 2. Verify
systemctl restart rankings-bot-api
sleep 5
curl http://localhost:8003/api/health/alfa
```

**Alert**: "Alfa rolled back to Fargo. System stable. RCA in progress."

### Post-Recovery

1. System is now running Fargo ratings
2. Investigate what broke ([TROUBLESHOOTING_GUIDE.md](TROUBLESHOOTING_GUIDE.md))
3. Plan redeployment only after root cause identified
4. Schedule status update for users

---

## 🔴 CRITICAL EMERGENCY: High Error Rate (>2%)

**Goal**: Reduce error rate to <1% in <10 minutes

### Diagnosis (1-2 min)

```bash
# Identify error type
tail -200 /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log | grep ERROR | head -10

# Count by type
tail -500 rankings_bot.log | grep ERROR | awk -F': ' '{print $2}' | sort | uniq -c | sort -rn | head -5
```

### Common Error Responses

| Error | Cause | Quick Fix |
|-------|-------|-----------|
| "Connection pool timeout" | DB overwhelmed | `docker-compose restart postgres` |
| "Model not found" | Model file missing | Restore from backup |
| "Cache connection failed" | Redis down | `docker-compose restart redis` |
| "Authentication failed" | Bad deployment | Rollback: `git revert` |
| "Memory error" | Out of memory | Restart: `systemctl restart` |

### Immediate Actions

**If Database Errors** (most common):
```bash
# 1. Increase pool timeout
# Edit environment or config, increase from 30 to 60 seconds
systemctl restart rankings-bot-api

# 2. If persists, restart database
docker-compose restart postgres
systemctl restart rankings-bot-api

# 3. If still persists, rollback
./scripts/rollback_alfa.sh
```

**If Model Errors**:
```bash
# 1. Check model exists
ls -la models/*.pkl

# 2. Restore backup
cp /archive/models/alfa_logistic_regression_BACKUP.pkl models/alfa_logistic_regression.pkl
systemctl restart rankings-bot-api

# 3. If no backup: Rollback to Fargo
./scripts/rollback_alfa.sh
```

**If Cache Errors**:
```bash
# 1. Restart Redis
docker-compose restart redis
sleep 5
systemctl restart rankings-bot-api

# 2. Clear cache
redis-cli FLUSHDB
```

**If Recent Deployment Error**:
```bash
# 1. Identify last change
git log --oneline -1

# 2. Rollback
git revert HEAD
docker-compose up -d

# 3. Or: Rollback state
./scripts/rollback_alfa.sh
```

### Verification

```bash
# Monitor error rate
for i in {1..10}; do
    ERROR_COUNT=$(tail -500 rankings_bot.log | grep -c ERROR)
    TOTAL=$(tail -500 rankings_bot.log | wc -l)
    RATE=$((ERROR_COUNT * 100 / TOTAL))
    echo "Error rate: ${RATE}%"
    sleep 5
done
```

---

## 🟊 MAJOR EMERGENCY: Service Degraded (Latency >3s, Error 1-2%)

**Goal**: Identify root cause and improve within 20 minutes

### Quick Diagnosis (3 min)

```bash
# 1. Check what's slow
curl -w "Time: %{time_total}s\n" http://localhost:8003/api/health/alfa

# 2. Component check
curl -s http://localhost:8003/api/health/alfa | jq '.components'

# 3. System resources
top -bn1 | head -20

# 4. Database queries
psql -U alfadb -d alfadb << SQL
SELECT pid, query, query_start, NOW() - query_start as duration
FROM pg_stat_activity 
WHERE query NOT LIKE '%idle%'
ORDER BY duration DESC;
SQL
```

### Performance Issues

| Symptom | Check | Fix |
|---------|-------|-----|
| Database slow | `psql` test | Kill long queries, restart DB |
| API slow | Model time | Check model is loaded |
| All endpoints slow | CPU/Memory | Increase resources or restart |
| Specific endpoint slow | Profile | Optimize query or add index |

### Quick Fixes

**1. Kill Long-Running Queries**
```bash
psql -U alfadb -d alfadb << SQL
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE state = 'active' 
  AND query NOT LIKE '%idle%'
  AND NOW() - query_start > INTERVAL '30 seconds';
SQL
```

**2. Restart Database Connection Pool**
```bash
docker-compose restart postgres
# or
systemctl restart rankings-bot-api
```

**3. Clear Cache**
```bash
redis-cli FLUSHDB
```

**4. Add Index if Missing**
```bash
# Check slow queries
psql -U alfadb -d alfadb -c "SELECT query FROM pg_stat_statements ORDER BY total_time DESC LIMIT 5"

# Add index
psql -U alfadb -d alfadb << SQL
CREATE INDEX CONCURRENTLY idx_matches_recent ON matches(created_at DESC);
ANALYZE matches;
SQL
```

---

## 🟡 PARTIAL OUTAGE: Some Users Affected

**Goal**: Isolate failing component and route around it

### Identify Affected Component (5 min)

```bash
# 1. Check health details
curl -s http://localhost:8003/api/health/alfa/detailed | jq '.components'

# 2. Test specific endpoints
curl -s http://localhost:8003/api/rankings | head -10
curl -s http://localhost:8003/api/predictions | head -10
curl -s http://localhost:8003/api/anomalies | head -10

# 3. Check specific error
tail -200 rankings_bot.log | grep "ENDPOINT" | tail -20
```

### Isolation Strategies

**If Predictions Endpoint Down**:
- Disable sandbagging detection (simpler model)
- Fall back to Fargo ratings
- Return cached results

**If Rankings Endpoint Down**:
- Return last cached rankings
- Show "data may be outdated" notice
- Continue background updates

**If Anomalies Endpoint Down**:
- Disable flagging temporarily
- Skip anomaly detection in predictions
- Return normal predictions

---

## 💥 CATASTROPHIC: Complete Infrastructure Failure

**Goal**: Minimize user impact, restore on best-effort basis

### Failover Procedures

**If Database Corrupted or Gone**:
```bash
# 1. Restore from backup
BACKUP_FILE="/backups/alfa-db/latest.sql"
dropdb -U alfadb alfadb
createdb -U alfadb alfadb
psql -U alfadb -d alfadb < "$BACKUP_FILE"

# 2. Restart services
docker-compose restart postgres
systemctl restart rankings-bot-api
```

**If Model Files Corrupted**:
```bash
# 1. Restore from archive
ARCHIVE="/archive/models/alfa_logistic_regression_$(date -d '1 day ago' +%Y%m%d).pkl"
cp "$ARCHIVE" models/alfa_logistic_regression.pkl

# 2. Or: Fall back to Fargo
./scripts/rollback_alfa.sh

# 3. Restart
systemctl restart rankings-bot-api
```

**If Entire Server Offline**:
```bash
# 1. Failover to backup server (if available)
# Point DNS to backup server IP
# (Requires pre-configured failover)

# 2. Or: Restore from image + last backup
docker-compose pull
docker-compose up -d
./restore_from_backup.sh
```

### User Communication

```
🚨 SERVICE ALERT 🚨

We're experiencing a service incident. Our team is working to restore service.

Current Status:
- Predictions: UNAVAILABLE (using cached data)
- Rankings: UNAVAILABLE (using previous days rankings)
- Estimates: UNAVAILABLE

Estimated Recovery Time: [30-60 minutes]

We'll post updates every 15 minutes.

Apologies for the inconvenience.
```

---

## Post-Emergency Checklist

After resolving emergency:

- [ ] Stop incident clock, note total downtime
- [ ] Document exact timeline of events
- [ ] Identify root cause (why did it happen?)
- [ ] Verify system is fully stable (run health check 5 times)
- [ ] Restore all monitoring and alerts
- [ ] Collect logs/data for analysis
- [ ] Schedule RCA meeting within 4 hours
- [ ] Notify stakeholders of resolution
- [ ] Plan preventive measures

### RCA Meeting (Next 4 hours)

Discuss:
- Timeline: When did issue start, when resolved?
- Root cause: Engineering failure? Infrastructure? Load?
- Preventive actions: What will prevent next time?
- Detection improvement: Why wasn't this caught sooner?
- Communication: How well did we inform users?

---

## Emergency Contact Information

**On-Call Engineer**: [Phone] [Slack: @on-call]
**Data Science Lead**: [Phone] [Email]
**DevOps Lead**: [Phone] [Email]
**Team Lead**: [Phone] [Email]
**CTO/Leadership**: [Phone] [Email alternate]

---

## Equipment & Access Needed

- [ ] SSH access to production servers
- [ ] Database credentials (saved in 1Password)
- [ ] Docker registry credentials
- [ ] GitHub access for code rollback
- [ ] Monitoring dashboard URL
- [ ] Backup storage location
- [ ] Slack access to #incidents channel
- [ ] PagerDuty/on-call rotation

---

## Testing Emergency Procedures

**Monthly**: Test rollback procedure
- Check backup exists and is recent
- Verify rollback script works
- Test with non-critical change

**Quarterly**: Full disaster recovery drill
- Architect joins as "incident commander"
- Simulate service outage
- Practice all procedures
- Document lessons learned

---

## Hardware Failure Recovery

### Lost Storage

```bash
# If /home is lost
# Restore from backup
rsync -av /backup/home /home

# If database storage lost
# Restore from database backup
psql -U alfadb -d alfadb < /backup/database/latest.sql

# If model storage lost
# Restore model from archive
cp /archive/models/alfa_logistic_regression.pkl /home/.../models/
```

### Lost Compute (CPU/Memory Overwhelmed)

```bash
# 1. Identify resource hog
ps aux | sort -nrk 3,3 | head -10  # CPU
ps aux | sort -nrk 4,4 | head -10  # Memory

# 2. Kill if necessary
kill -9 <PID>

# 3. Or: Migrate to different machine
# (Requires load balancer / Kubernetes setup)

# 4. Restart services
systemctl restart rankings-bot-api
```

### Network Isolation

```bash
# If can't reach database:
# 1. Check network connectivity
ping postgres-server
# 2. Check firewall rules
iptables -L -n
# 3. Check DNS
nslookup postgresql.service.consul
# 4. Use direct IP if needed
export DATABASE_URL="postgresql://user:pass@IP:5432/db"
systemctl restart rankings-bot-api
```

---

## Quick Reference Card

Print and keep at desk:

```
🚨 EMERGENCY PROCEDURE QUICK REFERENCE

1. CONFIRM SERVICE DOWN
   curl -s http://localhost:8003/api/health/alfa

2. NOTIFY TEAM
   Slack: #incidents
   Pager: [on-call number]

3. TRY RESTART
   systemctl restart rankings-bot-api
   Wait 10s, test health

4. IF STILL DOWN: ROLLBACK
   ./scripts/rollback_alfa.sh
   systemctl restart rankings-bot-api

5. VERIFY
   curl http://localhost:8003/api/health/alfa

6. INVESTIGATE LATER
   Logs: /home/.../rankings_bot.log
   Health DB: SELECT * FROM health_check_log ORDER BY timestamp DESC;

CRITICAL URLS
- Health: http://localhost:8003/api/health/alfa
- Logs: /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log
- Dashboard: [Grafana URL]

CRITICAL COMMANDS
- Restart API: systemctl restart rankings-bot-api
- Rollback: ./scripts/rollback_alfa.sh
- Full restart: docker-compose restart && systemctl restart
- Check status: curl http://localhost:8003/api/health/alfa

CONTACTS
- On-Call: [Name, Phone]
- Data Lead: [Name, Phone]
- DevOps: [Name, Phone]
```

---

**Last Updated**: 2026-02-16  
**Test Date**: [To be filled in after first test]
