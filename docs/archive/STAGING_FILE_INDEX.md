# Alfa Staging Environment - File Index & Quick Reference

## 📂 Files Created (18 Total)

### Configuration & Deployment (2)
| File | Size | Purpose |
|------|------|---------|
| `docker-compose-staging.yml` | 5.6 KB | Docker container orchestration for staging |
| `database/staging/schema_staging_init.sql` | 12 KB | Database schema with 100 test players |

### Monitoring Configuration (5)
| File | Size | Purpose |
|------|------|---------|
| `monitoring/prometheus/prometheus.yml` | 4.5 KB | Prometheus metrics scrape configuration |
| `monitoring/prometheus/alfa_alerts.yml` | 13 KB | 14 alert rules (critical, warning, info) |
| `monitoring/grafana/dashboards/alfa_overview.json` | 3.8 KB | System Overview dashboard |
| `monitoring/grafana/dashboards/alfa_accuracy.json` | 4.4 KB | Accuracy & Performance dashboard |
| `monitoring/grafana/dashboards/alfa_health.json` | 5.2 KB | System Health dashboard |

### Testing & Deployment (2)
| File | Size | Purpose |
|------|------|---------|
| `backend/tests/staging_tests.py` | 25 KB | 18 comprehensive test cases |
| `scripts/deploy_staging.sh` | 14 KB | Automated deployment script (executable) |

### Documentation (5)
| File | Size | Purpose |
|------|------|---------|
| `docs/STAGING_DEPLOYMENT_GUIDE.md` | 15 KB | Complete deployment guide (12 sections) |
| `docs/MONITORING_SETUP_GUIDE.md` | 17 KB | Monitoring setup guide (9 sections) |
| `staging/README.md` | 13 KB | Quick reference guide |
| `staging/DATA_VALIDATION_REPORT.md` | 12 KB | Validation report template |
| `STAGING_SETUP_COMPLETE.md` | 17 KB | Setup completion summary |

### Quick Reference (1)
| File | Size | Purpose |
|------|------|---------|
| `staging.env.sh` | 8 KB | Command aliases and helpers |

---

## 🚀 Getting Started

### Prerequisite Check
```bash
# Verify Docker is installed
docker --version
docker-compose --version

# Verify tunnel_network exists
docker network create tunnel_network
```

### Quick Deployment (One Command)
```bash
cd /home/ansible/rankings-bot/Rankings-Bot
./scripts/deploy_staging.sh
```

Expected output after 5-10 minutes:
```
✓ STAGING ENVIRONMENT READY
```

### Verify Deployment
```bash
# Check API health
curl http://localhost:8006/api/health

# Check containers
docker ps | grep alfa-staging

# Run tests
pytest backend/tests/staging_tests.py -v
```

### Access Services
```
Alfa API:       http://localhost:8006/api/health
Prometheus:     http://localhost:9090
Grafana:        http://localhost:3000 (admin/admin123)
PostgreSQL:     127.0.0.1:5433 (user: rankings)
Redis:          127.0.0.1:6380
```

---

## 📖 Documentation Structure

### 1. STAGING_DEPLOYMENT_GUIDE.md
Complete guide for deploying and operating the staging environment.
- Architecture overview
- Deployment procedures (automated & manual)
- Database initialization
- Testing procedures for all 6 test categories
- Monitoring dashboard setup
- A/B testing framework
- Operations procedures (restart, logs, cleanup)
- Validation checklist before production
- Troubleshooting guide

**Start here for:** Full deployment understanding

### 2. MONITORING_SETUP_GUIDE.md
Comprehensive guide for monitoring and alerting configuration.
- Monitoring architecture
- Prometheus configuration (scrape jobs, retention)
- Custom metrics implementation (Python code examples)
- PromQL query examples and syntax
- Alert rules structure and examples
- Grafana dashboard creation guide
- Email/Slack notification configuration
- Performance tuning tips
- Backup and recovery procedures
- Troubleshooting monitoring issues

**Start here for:** Understanding and configuring monitoring

### 3. staging/README.md
Quick reference with key information.
- Component summary
- Quick start commands
- Architecture diagram
- Monitoring highlights
- Test coverage overview
- Validation checklist
- Next steps

**Start here for:** Quick overview and common tasks

### 4. staging/DATA_VALIDATION_REPORT.md
Template for tracking validation results.
- Data integrity checks
- Prediction quality metrics (Brier score, etc.)
- System performance (load test results)
- Resource usage monitoring
- A/B testing metrics
- Sign-off checklist
- Issues and resolutions

**Fill this in during:** Staging validation period (1-2 weeks)

### 5. STAGING_SETUP_COMPLETE.md
Executive summary of what was created.
- Component descriptions
- Architecture diagram
- File reference table
- Timeline estimates
- Success criteria
- Next steps

**Read this for:** Understanding overall setup

---

## 🧪 Test Categories Reference

### Smoke Tests (3 tests)
Health checks and basic endpoint availability.
```bash
pytest backend/tests/staging_tests.py::TestSmokeHealthChecks -v
```
Tests: Health endpoint, readiness, metrics

### Regression Tests (2 tests)
Model prediction consistency validation.
```bash
pytest backend/tests/staging_tests.py::TestRegressionPredictions -v
```
Tests: Reference predictions, consistency

### Load Tests (1 test)
Performance under sustained load (100 req/sec).
```bash
pytest backend/tests/staging_tests.py::TestLoadStaging -v
```
Tests: 100 req/sec for 60 seconds, error rate <2%

### Accuracy Tests (3 tests)
Model quality validation.
```bash
pytest backend/tests/staging_tests.py::TestAccuracyValidation -v
```
Tests: Brier score (±0.01), calibration, by-tier accuracy

### Anomaly Detection Tests (3 tests)
Anomaly detection validation.
```bash
pytest backend/tests/staging_tests.py::TestAnomalyDetection -v
```
Tests: Flag detection, types, severity levels

### Database Integration Tests (6 tests)
Data integrity and schema validation.
```bash
pytest backend/tests/staging_tests.py::TestDatabaseIntegration -v
```
Tests: Schema, duplicates, ranges, permissions

**Run all tests:**
```bash
pytest backend/tests/staging_tests.py -v
```

---

## 🔍 Key Commands

### Deployment
```bash
./scripts/deploy_staging.sh                    # Full deployment
./scripts/deploy_staging.sh --no-cache         # Rebuild without cache
./scripts/deploy_staging.sh --skip-tests       # Skip tests
./scripts/deploy_staging.sh --keep-data        # Preserve database
```

### Testing
```bash
pytest backend/tests/staging_tests.py -v       # All tests
pytest backend/tests/staging_tests.py::TestSmokeHealthChecks -v  # Smoke tests only
```

### Docker Operations
```bash
docker-compose -f docker-compose-staging.yml up -d      # Start containers
docker-compose -f docker-compose-staging.yml down       # Stop containers
docker-compose -f docker-compose-staging.yml down -v    # Stop & remove volumes
docker-compose -f docker-compose-staging.yml logs -f    # View all logs
```

### View Logs
```bash
tail -f logs/staging_deployment.log           # Deployment log
docker logs -f alfa-api-staging               # API logs
docker logs -f alfa-staging-postgres          # Database logs
docker logs -f alfa-prometheus-staging        # Prometheus logs
```

### Database Access
```bash
docker exec -it alfa-staging-postgres psql -U rankings -d rankings_staging
SELECT COUNT(*) FROM players;                 # Count test players
SELECT COUNT(*) FROM alfa_match_predictions;  # Count predictions
SELECT AVG(brier_score) FROM alfa_match_predictions;  # Avg Brier score
```

### Quick Commands (if sourced staging.env.sh)
```bash
deploy                    # Full deployment
test_all                  # Run all tests
test_load                 # Load test only
prometheus                # Open Prometheus
grafana                   # Open Grafana
health                    # Check API health
containers_status         # Show container status
logs_api                  # Show API logs
db_connect                # Connect to database
db_brier_score            # Show Brier score
staging_help              # Show all commands
```

---

## 📊 Architecture Overview

```
Host Machine (127.0.0.1)
├── Port 5433 ──→ PostgreSQL (staging database)
├── Port 6380 ──→ Redis (caching)
├── Port 8006 ──→ Alfa API (FastAPI)
├── Port 9090 ──→ Prometheus (metrics/alerts)
└── Port 3000 ──→ Grafana (dashboards)

Docker Networks:
├── alfa-staging-network (internal, isolated)
│   └── All staging containers communicate here
└── tunnel_network (external, shared)
    └── Alfa API accessible for production integration
```

---

## ✅ Validation Checklist

Before moving to production:

- [ ] Deployment completes without errors
- [ ] All containers running: `docker ps | grep alfa-staging`
- [ ] API health: `curl http://localhost:8006/api/health`
- [ ] Database loaded: SELECT COUNT(*) FROM players (expect 100)
- [ ] All tests pass: `pytest backend/tests/staging_tests.py -v`
- [ ] Prometheus targets healthy: http://localhost:9090/targets
- [ ] Grafana dashboards populated: http://localhost:3000
- [ ] No critical alerts firing
- [ ] Validation report generated
- [ ] A/B testing data collected (1-2 weeks)
- [ ] Team sign-off obtained

---

## 🔗 Related Documentation

**In Project:**
- [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture
- [NETWORKING_STANDARDS.md](../NETWORKING_STANDARDS.md) - Network design
- [.github/PORT_ASSIGNMENTS.md](../.github/PORT_ASSIGNMENTS.md) - Port configuration

**Database:**
- `database/staging/schema_staging_init.sql` - Staging schema
- `database/schema_alfa_extends.sql` - Alfa extensions
- `database/schema_postgres.sql` - Main schema

**API:**
- `api/main.py` - FastAPI application (add /metrics endpoint)
- `requirements-api.txt` - Python dependencies

---

## 📈 Monitoring Summary

### Metrics Collected
| Source | Metric | Interval |
|--------|--------|----------|
| Alfa API | Prediction rate, latency, errors | 10s |
| PostgreSQL | Query time, connections | 30s |
| Redis | Memory, cache hits/misses | 30s |
| Docker | CPU, memory, disk I/O | 30s |

### 3 Grafana Dashboards
1. **System Overview** - Real-time prediction metrics
2. **Accuracy & Performance** - Model quality metrics
3. **System Health** - Infrastructure monitoring

### 14 Alert Rules
- 3 Critical (requires immediate action)
- 7 Warning (investigate within 30 min)
- 4 Info (track trends)

---

## ⏰ Timeline Estimates

| Task | Duration | Notes |
|------|----------|-------|
| Deployment | 5-10 min | Fully automated |
| Initial Tests | 10 min | All 18 tests |
| Monitoring Setup | 5 min | Auto-provisioned |
| Staging Validation | 1-2 weeks | Collect A/B data |
| Production Readiness | 30 min | Team review |
| Production Rollout | 30 min | Once approved |

**Total to Production:** ~10 min + 1-2 weeks validation

---

## 🆘 Troubleshooting

### API Won't Start
```bash
docker logs alfa-api-staging
```
Check for: database connection, model loading, port binding

### Tests Fail
```bash
pytest backend/tests/staging_tests.py::TestName -vv
```
Check logs, verify containers healthy, check database

### Metrics Not Appearing
```bash
curl http://localhost:9090/api/v1/targets
```
Verify Prometheus can reach API metrics endpoint

### High Error Rate
```bash
docker logs -f alfa-api-staging | grep ERROR
```
Check API logs, database, and model status

For detailed troubleshooting, see:
- [STAGING_DEPLOYMENT_GUIDE.md](docs/STAGING_DEPLOYMENT_GUIDE.md#troubleshooting)
- [MONITORING_SETUP_GUIDE.md](docs/MONITORING_SETUP_GUIDE.md#troubleshooting)

---

## 📝 Notes

- **Network:** All staging services isolated; API only accessible via 127.0.0.1:8006
- **Data:** Completely separate from production; can be safely reset
- **Models:** Versions pinned for reproducibility
- **Logs:** All comprehensive logging for debugging; see logs/ directory
- **Tests:** Require running staging environment; not for CI/CD
- **Monitoring:** Full metrics collection; requires Prometheus + Grafana

---

## 🎯 Success Criteria

Your staging environment is ready when:
1. ✅ Deployment completes
2. ✅ All 18 tests pass
3. ✅ Metrics displaying in Prometheus/Grafana
4. ✅ No critical alerts
5. ✅ Validation report generated
6. ✅ A/B testing data collected
7. ✅ Team approval obtained

---

**Created:** February 16, 2026  
**Status:** ✅ Ready for Deployment  
**Version:** 1.0  

**Next Action:** Run `./scripts/deploy_staging.sh`
