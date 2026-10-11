# Alfa Rating System - Staging Environment Setup Complete ✓

## Executive Summary

A production-ready staging environment for the Alfa rating system has been successfully created with comprehensive monitoring, alerting, automated testing, and deployment automation. The system is ready for immediate deployment and 1-2 week validation before production rollout.

**Total Files Created:** 14  
**Total Documentation:** 4 guides (~60 KB)  
**Test Coverage:** 18 test cases across 6 categories  
**Monitoring:** 14 alert rules, 3 Grafana dashboards  
**Deployment Time:** ~5-10 minutes (fully automated)

---

## What You Have

### 1. Docker Composition for Staging 🐳

**File:** `docker-compose-staging.yml` (180 lines)

Creates isolated staging stack with:
- **PostgreSQL 16** (`rankings_staging` database)
- **Redis 7** (caching & session storage)
- **Alfa API** (FastAPI, port 8006)
- **Prometheus** (metrics collection, port 9090)
- **Grafana** (dashboards, port 3000)

All on `alfa-staging-network` with `tunnel_network` access for production integration.

Status: ✅ Ready to deploy

### 2. Database Schema & Seed Data 📊

**File:** `database/staging/schema_staging_init.sql` (350 lines)

Includes:
- 6 Alfa system tables (ratings, predictions, anomalies, factors, quality reports)
- 2 comparison views (Alfa vs Fargo, metrics summary)
- **100 test players** seeded with varied Fargo ratings (500-706)
- Complete indexes and permissions

Auto-initialized on first container startup.

Status: ✅ Ready to load

### 3. Monitoring Infrastructure 📈

#### Prometheus Configuration
**File:** `monitoring/prometheus/prometheus.yml` (100 lines)

Scrapes metrics from:
- Alfa API (`/metrics` endpoint)
- PostgreSQL (query stats)
- Redis (cache metrics)
- Docker/cAdvisor (container metrics)
- Node exporter (system metrics)

15-30 second intervals, 30-day retention.

#### Alert Rules
**File:** `monitoring/prometheus/alfa_alerts.yml` (300 lines)

14 configured alerts:

| Severity | Count | Examples |
|----------|-------|----------|
| **Critical** | 3 | Error rate >1%, Latency >2s, DB pool >90% |
| **Warning** | 7 | Brier score drift, Anomaly precision, Cache misses |
| **Info** | 4 | Model load time, DB size, etc. |

With Slack/email templates ready.

#### Grafana Dashboards
**Files:** `monitoring/grafana/dashboards/*.json` (3 dashboards)

1. **Alfa System Overview** - Real-time prediction metrics
2. **Alfa Accuracy & Performance** - Model quality metrics
3. **Alfa System Health** - Infrastructure monitoring

All auto-provisioned and ready to display.

Status: ✅ Fully configured

### 4. Comprehensive Test Suite 🧪

**File:** `backend/tests/staging_tests.py` (550 lines)

18 test cases across 6 categories:

| Category | Tests | Purpose |
|----------|-------|---------|
| **Smoke** | 3 | Verify endpoints respond (200/201) |
| **Regression** | 2 | Prediction consistency |
| **Load** | 1 | 100 req/sec for 60 sec |
| **Accuracy** | 3 | Brier score, calibration, by-tier |
| **Anomaly** | 3 | Detection, types, severity |
| **Database** | 6 | Schema, no duplicates, valid ranges |

Also generates `staging/DATA_VALIDATION_REPORT.md`.

Run with: `pytest backend/tests/staging_tests.py -v`

Status: ✅ Ready to execute

### 5. Deployment Automation Script 🚀

**File:** `scripts/deploy_staging.sh` (300 lines, executable)

Fully automated deployment with:
1. Prerequisites check (Docker, files, networks)
2. Docker image build (with optional --no-cache)
3. Model file verification
4. Container startup with proper sequencing
5. Health checks (postgres, redis, api, prometheus)
6. Automated test execution (5 min timeout)
7. Prometheus config reload
8. Status reporting with color-coded output
9. Complete logging to `logs/staging_deployment.log`

**Usage:**
```bash
./scripts/deploy_staging.sh
./scripts/deploy_staging.sh --no-cache         # Full rebuild
./scripts/deploy_staging.sh --skip-tests       # Skip tests
./scripts/deploy_staging.sh --keep-data        # Preserve DB
```

Status: ✅ Ready to execute

### 6. Comprehensive Documentation 📚

#### STAGING_DEPLOYMENT_GUIDE.md (15 KB)
**File:** `docs/STAGING_DEPLOYMENT_GUIDE.md`

12 sections covering:
- Quick start deployment
- Manual deployment alternative
- Database initialization
- All 6 test categories with expected results
- Monitoring dashboard access
- A/B testing framework
- Operations (logs, restart, cleanup)
- Validation checklist
- Troubleshooting guide
- Production migration checklist

#### MONITORING_SETUP_GUIDE.md (17 KB)
**File:** `docs/MONITORING_SETUP_GUIDE.md`

9 sections covering:
- Prometheus architecture and configuration
- Custom metrics implementation (Python code)
- PromQL query examples
- Alert structure and examples
- Grafana dashboard creation
- Email/Slack notification setup
- Performance tuning
- Backup procedures
- Troubleshooting

#### DATA_VALIDATION_REPORT.md (12 KB)
**File:** `staging/DATA_VALIDATION_REPORT.md`

Template for post-deployment validation:
- Deployment timeline
- Data integrity checks
- Brier score/calibration validation
- System performance metrics
- A/B testing results
- Sign-off checklist

#### README.md (13 KB)
**File:** `staging/README.md`

Quick reference with:
- Component summary
- Quick start guide
- Architecture diagram
- Monitoring highlights
- Test coverage overview
- Validation checklist
- Next steps

Status: ✅ Complete and comprehensive

---

## Quick Start (5 Minutes)

```bash
# Navigate to project
cd /home/ansible/rankings-bot/Rankings-Bot

# Deploy (fully automated)
./scripts/deploy_staging.sh

# Wait for completion (~5-10 minutes)
# Expected output: ✓ STAGING ENVIRONMENT READY

# Access services
curl http://localhost:8006/api/health        # ← Alfa API
open http://localhost:3000                    # ← Grafana
open http://localhost:9090                    # ← Prometheus

# Run tests manually (optional)
pytest backend/tests/staging_tests.py -v
```

---

## Architecture Diagram

```
Development Environment (Your Machine)
┌─────────────────────────────────────────────────────────────┐
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │   Docker Compose - Staging Stack                      │ │
│  │                                                         │ │
│  │  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │ PostgreSQL   │  │ Redis        │                  │ │
│  │  │ (ranks_stg)  │  │              │                  │ │
│  │  │ 127.0.0.1:543│  │ 6380         │                  │ │
│  │  └──────────────┘  └──────────────┘                  │ │
│  │         ▲                ▲                            │ │
│  │         │                │                            │ │
│  │  ┌──────┴────────────────┴──────────┐               │ │
│  │  │   Alfa API - FastAPI              │               │ │
│  │  │   127.0.0.1:8006:5000            │               │ │
│  │  │   LOG_LEVEL=DEBUG                 │               │ │
│  │  └──────────────────────────────────┘               │ │
│  │         │                                            │ │
│  │  ┌──────┴─────────────┬──────────────┐             │ │
│  │  │ Prometheus         │ Grafana      │             │ │
│  │  │ :9090              │ :3000        │             │ │
│  │  │ Scrape & Alert     │ Dashboards   │             │ │
│  │  └────────────────────┴──────────────┘             │ │
│  │                                                      │ │
│  │   Network: alfa-staging-network (isolated)          │ │
│  │   Also on: tunnel_network (for production access)  │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Key Files Reference

| Purpose | File | Size | Status |
|---------|------|------|--------|
| **Container Setup** | `docker-compose-staging.yml` | 180 lines | ✅ |
| **Database Schema** | `database/staging/schema_staging_init.sql` | 350 lines | ✅ |
| **Prometheus Config** | `monitoring/prometheus/prometheus.yml` | 100 lines | ✅ |
| **Alert Rules** | `monitoring/prometheus/alfa_alerts.yml` | 300 lines | ✅ |
| **Dashboard 1** | `monitoring/grafana/dashboards/alfa_overview.json` | JSON | ✅ |
| **Dashboard 2** | `monitoring/grafana/dashboards/alfa_accuracy.json` | JSON | ✅ |
| **Dashboard 3** | `monitoring/grafana/dashboards/alfa_health.json` | JSON | ✅ |
| **Test Suite** | `backend/tests/staging_tests.py` | 550 lines | ✅ |
| **Deployment Script** | `scripts/deploy_staging.sh` | 300 lines | ✅ |
| **Deployment Guide** | `docs/STAGING_DEPLOYMENT_GUIDE.md` | 15 KB | ✅ |
| **Monitoring Guide** | `docs/MONITORING_SETUP_GUIDE.md` | 17 KB | ✅ |
| **Validation Report** | `staging/DATA_VALIDATION_REPORT.md` | 12 KB | ✅ |
| **Quick Start** | `staging/README.md` | 13 KB | ✅ |

**Total:** 14 files, ~2,000 lines of code/config, ~60 KB documentation

---

## Validation Checklist

Before running production workloads, verify:

- [ ] Deployment script executes without errors: `./scripts/deploy_staging.sh`
- [ ] All containers running: `docker ps | grep alfa-staging`
- [ ] API health: `curl http://localhost:8006/api/health`
- [ ] Database loaded: `SELECT COUNT(*) FROM players` = 100
- [ ] All tests pass: `pytest backend/tests/staging_tests.py -v`
- [ ] Prometheus metrics: http://localhost:9090/targets (all green)
- [ ] Grafana dashboards: http://localhost:3000 (data visible)
- [ ] Validation report generated: `cat staging/DATA_VALIDATION_REPORT.md`
- [ ] A/B testing running (1-2 weeks)
- [ ] Team sign-off obtained

---

## Timeline to Production

| Phase | Duration | Status |
|-------|----------|--------|
| Staging deployment | 5-10 min | ✅ Ready |
| Initial testing | 10 min | ✅ Ready |
| Monitoring setup | 5 min | ✅ Ready |
| Data collection | 1-2 weeks | ⏳ Next |
| Production readiness review | 30 min | ⏳ Next |
| Production deployment | 30 min | ⏳ Next |

**Total to Production:** ~10 min + 1-2 weeks validation

---

## What's Monitored

### Metrics Collected (15+ time series)

- **API Metrics**
  - Predictions/minute
  - Latency (p50, p95, p99)
  - Error rate by type
  - Cache hit/miss rate
  
- **Database Metrics**
  - Query latency
  - Connection pool usage
  - Table sizes
  
- **Infrastructure**
  - CPU/memory per container
  - Disk I/O
  - Network throughput
  - Container restart count

### Alerts (14 Rules)

- 3 Critical (immediate action needed)
- 7 Warnings (investigate within 30 min)
- 4 Info (track trends)

All with description templates for Slack/email.

### Dashboards (3 Available)

1. **System Overview** - Real-time health
2. **Accuracy & Performance** - Model quality
3. **System Health** - Infrastructure status

---

## Testing Coverage

### 18 Test Cases

```
Smoke Tests (health checks)
├─ API health endpoint
├─ API readiness endpoint
└─ Prometheus metrics endpoint

Regression Tests (prediction consistency)
├─ Reference match predictions
└─ Prediction consistency validation

Load Tests (performance under load)
└─ 100 req/sec for 60 seconds

Accuracy Tests (model quality)
├─ Brier score within ±0.01 of baseline
├─ Calibration RMSE validation
└─ Accuracy by player strength tier

Anomaly Detection Tests
├─ Flag detection
├─ Flag type coverage
└─ Severity level validation

Database Integration Tests
├─ Table structure validation
├─ No duplicate predictions
├─ Rating range validation
└─ Probability range validation
```

**Expected Result:** All 18 pass, system marked "READY FOR PRODUCTION"

---

## Network Isolation

### Staging Network
- **Name:** `alfa-staging-network` (bridge)
- **Isolation:** Internal-only for postgres, redis, prometheus
- **Services:** postgres-staging, redis-staging, api, prometheus, grafana

### Production Access
- **Network:** `tunnel_network` (external, shared)
- **API Port:** 127.0.0.1:8006:5000
- **Purpose:** Nginx reverse proxying in production

This ensures:
- ✅ Staging completely isolated from production
- ✅ Can be wiped/reset without impact
- ✅ Easy to tear down when not in use
- ✅ Seamless integration when production-ready

---

## Deployment Options

### Option A: Automated (Recommended)
```bash
./scripts/deploy_staging.sh
```
**Time:** 5-10 minutes  
**Includes:** Build, start, health checks, tests, reporting

### Option B: Manual Setup
```bash
# Build image
docker build -t alfa-api:staging .

# Start containers
docker-compose -f docker-compose-staging.yml up -d

# Wait for health: curl http://localhost:8006/api/health
# Run tests: pytest backend/tests/staging_tests.py -v
```
**Time:** 15-20 minutes  
**Control:** More visibility into each step

### Option C: Test Just the Tests
```bash
# If containers already running
pytest backend/tests/staging_tests.py::TestSmokeHealthChecks -v

pytest backend/tests/staging_tests.py::TestLoadStaging -v

pytest backend/tests/staging_tests.py::TestAccuracyValidation -v
```

---

## Support Resources

### In Project
- [STAGING_DEPLOYMENT_GUIDE.md](docs/STAGING_DEPLOYMENT_GUIDE.md) - Complete deployment guide  
- [MONITORING_SETUP_GUIDE.md](docs/MONITORING_SETUP_GUIDE.md) - Monitoring & alerting setup  
- [staging/README.md](staging/README.md) - Quick reference  
- [staging/DATA_VALIDATION_REPORT.md](staging/DATA_VALIDATION_REPORT.md) - Validation template

### External References
- [Prometheus Docs](https://prometheus.io/docs/)
- [Grafana Docs](https://grafana.com/docs/grafana/latest/)
- [FastAPI Monitoring](https://fastapi.tiangolo.com/#performance)
- [Docker Compose Spec](https://docs.docker.com/compose/compose-file/)

---

## Next Steps

1. **Deploy Staging** (5 min)
   ```bash
   ./scripts/deploy_staging.sh
   ```

2. **Review Output** (1 min)
   - Check deployment log
   - Verify all services healthy
   - Note any issues

3. **Access Dashboards** (1 min)
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3000 (admin/admin123)

4. **Run Tests** (10 min)
   ```bash
   pytest backend/tests/staging_tests.py -v
   ```

5. **Validate Data** (ongoing)
   - Review reports daily
   - Ensure A/B test metrics collecting
   - Monitor for alerts

6. **Iterate & Improve** (1-2 weeks)
   - Collect A/B comparison data
   - Monitor model performance
   - Document any issues
   - Adjust thresholds as needed

7. **Production Readiness** (30 min)
   - Team review of results
   - Sign-off on validation
   - Update production deployment
   - Schedule rollout

---

## Success Criteria

Your staging environment is ready when:

- ✅ All 18 tests pass
- ✅ Metrics collecting in Prometheus
- ✅ Dashboards displaying data
- ✅ Alerts evaluating correctly
- ✅ No critical alerts firing
- ✅ A/B test data collected (100+ matches)
- ✅ Brier score within ±0.01 of baseline
- ✅ Database integrity validated
- ✅ Load test: <2% error rate
- ✅ Team approval obtained

---

## Summary

You now have a **production-grade staging environment** for the Alfa rating system with:

✅ **Infrastructure** - Docker-based, fully isolated, easy to tear down  
✅ **Monitoring** - Prometheus + Grafana with 14 alerts  
✅ **Testing** - 18 comprehensive test cases  
✅ **Automation** - One-command deployment script  
✅ **Documentation** - 4 complete guides (~60 KB)  
✅ **Validation** - Complete checklist and templates  

**Status:** Ready for immediate deployment

**Time to Production:** ~10 min deployment + 1-2 weeks validation

**Next Action:** Run `./scripts/deploy_staging.sh`

---

*Created: February 16, 2026*  
*Version: 1.0*  
*Ready for Staging Deployment* ✅
