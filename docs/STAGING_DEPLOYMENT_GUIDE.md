# Staging Deployment Guide for Alfa Rating System

## Overview

This guide provides step-by-step instructions for deploying and managing the Alfa rating system in the staging environment. The staging environment is designed for 1-2 week validation before production rollout.

**Key Features:**
- Independent staging database (`rankings_staging`)
- Fully isolated from production via separate Docker network (`alfa-staging-network`)
- Comprehensive monitoring with Prometheus and Grafana
- Automated testing suite with smoke, regression, load, and accuracy tests
- Model version pinning for reproducibility

## Architecture

```
Docker Compose Staging Stack:
├── postgres-staging (PostgreSQL 16, port 127.0.0.1:5433)
├── redis-staging (Redis 7, port 127.0.0.1:6380)
├── alfa-api-staging (FastAPI, port 127.0.0.1:8006)
├── prometheus-staging (Metrics collection, port 127.0.0.1:9090)
└── grafana-staging (Dashboards, port 127.0.0.1:3000)

All containers communicate on: alfa-staging-network (isolated)
API exposes to production tunnel via: tunnel_network
```

## Deployment Steps

### 1. Prerequisites

Ensure your system has:
- Docker 20.10+ with Docker Compose
- Python 3.11+ for test framework
- At least 8GB free disk space
- 4GB free RAM

Verify Docker is running:
```bash
docker ps
docker-compose --version
```

### 2. Quick Start Deployment

The automated deployment script handles all setup:

```bash
cd /home/ansible/rankings-bot/Rankings-Bot

# Standard deployment (builds image, starts containers, runs tests)
./scripts/deploy_staging.sh

# Deployment options:
./scripts/deploy_staging.sh --no-cache          # Rebuild without cache
./scripts/deploy_staging.sh --skip-tests        # Skip automated tests
./scripts/deploy_staging.sh --keep-data         # Reuse existing database
```

**What the script does:**
1. ✓ Checks prerequisites (Docker, files)
2. ✓ Builds `alfa-api:staging` Docker image
3. ✓ Verifies model files are available
4. ✓ Stops/removes previous staging containers
5. ✓ Starts all containers (postgres, redis, api, prometheus, grafana)
6. ✓ Waits for health checks to pass
7. ✓ Runs automated test suite
8. ✓ Reloads Prometheus configuration
9. ✓ Generates status report

**Expected output:**
```
✓ PostgreSQL is healthy
✓ Redis is healthy
✓ Alfa API is healthy
✓ Prometheus is healthy
✓ All tests passed
✓ STAGING ENVIRONMENT READY
```

### 3. Manual Deployment (Alternative)

If you prefer manual control:

#### 3.1 Build Docker Image

```bash
cd /home/ansible/rankings-bot/Rankings-Bot

docker build -f Dockerfile \
  -t alfa-api:staging \
  --build-arg LOG_LEVEL=DEBUG \
  .
```

#### 3.2 Ensure tunnel_network exists

```bash
docker network create tunnel_network || true
```

#### 3.3 Start Containers

```bash
docker-compose -f docker-compose-staging.yml up -d
```

#### 3.4 Verify Health

```bash
# Check PostgreSQL
docker exec alfa-staging-postgres pg_isready -U rankings -d rankings_staging

# Check Redis
docker exec alfa-staging-redis redis-cli ping

# Check API
curl http://localhost:8006/api/health

# Check Prometheus
curl http://localhost:9090/-/healthy
```

### 4. Database Initialization

The schema is automatically initialized on first startup via:
- `/database/staging/schema_staging_init.sql` - Creates tables, loads 100 test players
- `/database/schema_alfa_extends.sql` - Adds Alfa-specific columns

To manually reinitialize database:

```bash
# Stop containers
docker-compose -f docker-compose-staging.yml down -v

# Restart (will reinitialize)
docker-compose -f docker-compose-staging.yml up -d
```

To verify data was loaded:

```bash
docker exec -it alfa-staging-postgres psql -U rankings -d rankings_staging -c \
  "SELECT COUNT(*) as player_count FROM players WHERE name LIKE 'Test Player%';"

# Expected output: 100
```

## Testing

### Run All Tests

```bash
cd /home/ansible/rankings-bot/Rankings-Bot

pytest backend/tests/staging_tests.py -v
```

### Run Specific Test Categories

```bash
# Smoke tests only (5 min)
pytest backend/tests/staging_tests.py::TestSmokeHealthChecks -v

# Regression tests (2 min)
pytest backend/tests/staging_tests.py::TestRegressionPredictions -v

# Load test (1 min, 100 req/sec)
pytest backend/tests/staging_tests.py::TestLoadStaging::test_load_test_pool_opt_in_rps_1_minute -v

# Accuracy tests (1 min)
pytest backend/tests/staging_tests.py::TestAccuracyValidation -v

# Anomaly detection (30 sec)
pytest backend/tests/staging_tests.py::TestAnomalyDetection -v

# Database integration (30 sec)
pytest backend/tests/staging_tests.py::TestDatabaseIntegration -v
```

### Expected Test Results

After running the full staging tests:

1. **Smoke Tests** ✓
   - All API endpoints respond with 200/201
   - Health checks pass
   - Metrics endpoint available

2. **Regression Tests** ✓
   - Reference predictions consistent
   - Model probabilities in range [0, 1]

3. **Load Tests** ✓
   - 100 req/sec for 60 seconds
   - Error rate < 2%
   - Average latency < 1 second

4. **Accuracy Tests** ✓
   - Brier score within ±0.01 of training baseline (0.215)
   - Calibration RMSE within ±0.03 of baseline (0.12)
   - Accuracy > 55% for all player strength tiers

5. **Anomaly Detection** ✓
   - Detects at least 3 different anomaly types
   - Produces precision/recall metrics
   - Severity levels assigned correctly

6. **Database Integration** ✓
   - All required tables present
   - No duplicate predictions
   - Ratings in valid range [0-1000]
   - Probabilities in valid range [0-1]

### Test Output

The test suite generates a validation report at `staging/DATA_VALIDATION_REPORT.md`:

```markdown
# Staging Validation Report

Generated: 2026-02-16T19:24:00
Status: READY FOR PRODUCTION

## Metrics
- **total_predictions**: 1,847
- **unique_players**: 98
- **matches_with_brier_scores**: 1,823
- **avg_prediction_confidence**: 0.687
- **anomalies_detected**: 23
- **unresolved_anomalies**: 18
```

## Monitoring & Dashboards

### Prometheus Metrics

Prometheus automatically collects metrics from:
- **Alfa API** (`/metrics` endpoint)
  - Prediction rate (predictions/min)
  - Error rate by type (model, DB, validation)
  - Latency percentiles (p50, p95, p99)
  - Cache hit/miss rates
- **PostgreSQL** (via pg_stat_statements)
  - Query latency
  - Connection pool usage
  - Table sizes
- **Redis** (via redis-cli INFO)
  - Memory usage
  - Cache hit/miss stats
- **Docker/System** (via cAdvisor/node-exporter)
  - CPU, memory, disk I/O
  - Container metrics

Access Prometheus dashboard:
```
http://localhost:9090
```

### Grafana Dashboards

Three pre-configured dashboards visualize Alfa performance:

#### 1. Alfa System Overview
- Real-time prediction rate
- Error rate by type
- API latency distribution (heatmap)
- Cache hit rate
- Model load time
- Active players and total predictions

Access at: `http://localhost:3000/d/alfa-overview`

#### 2. Alfa Accuracy & Performance
- Brier score trend (7-day rolling)
- Calibration RMSE
- Anomaly detection precision/recall
- Rating convergence speed
- Alfa vs Fargo prediction comparison
- Model accuracy by match type

Access at: `http://localhost:3000/d/alfa-accuracy`

#### 3. Alfa System Health
- API response time percentiles (p50, p95, p99)
- Database connection pool usage
- Disk I/O and storage
- Memory usage trends
- Container restart count
- CPU usage and network I/O

Access at: `http://localhost:3000/d/alfa-health`

#### Configure Grafana:

1. Open http://localhost:3000
2. Login: `admin` / `admin123`
3. Navigate to **Configuration** > **Data Sources**
4. Select **Prometheus**
5. Verify URL: `http://prometheus-staging:9090`
6. Click **Test & Save**

Dashboards are auto-provisioned from `/monitoring/grafana/dashboards/*.json`

## Alerting

Prometheus alerts are configured in `/monitoring/prometheus/alfa_alerts.yml`.

### Critical Alerts

Alert when:
| Condition | Threshold | Duration | Action |
|-----------|-----------|----------|--------|
| Prediction error rate | > 1% | 5 min | Restart API, check logs |
| API latency p99 | > 2 sec | 10 min | Check DB performance |
| DB connection pool | > 90% | 5 min | Kill idle connections |
| Service down | No response | 2 min | Restart container |

### Warning Alerts

Alert when:
| Condition | Threshold | Duration |
|-----------|-----------|----------|
| Brier score deviation | > 5% from baseline | 15 min |
| Anomaly precision | < 50% | 30 min |
| Cache miss rate | > 20% | 10 min |
| Query latency p95 | > 500 ms | 15 min |

### Alert Notification Setup (Optional)

To enable Slack notifications:

1. Create a Slack webhook: https://api.slack.com/messaging/webhooks
2. Add to `monitoring/prometheus/alertmanager.yml`:

```yaml
global:
  slack_api_url: 'YOUR_WEBHOOK_URL'

route:
  receiver: 'slack'

receivers:
  - name: 'slack'
    slack_configs:
      - channel: '#alfa-alerts'
        title: 'Alfa Staging Alert'
```

3. Restart Prometheus:
```bash
docker-compose -f docker-compose-staging.yml restart prometheus-staging
```

## Operations

### View Logs

**API logs:**
```bash
docker logs -f alfa-api-staging | tail -50

# Or read file directly
tail -f logs/alfa_staging.log
```

**Database logs:**
```bash
docker logs -f alfa-staging-postgres | tail -50
```

**Prometheus logs:**
```bash
docker logs -f alfa-prometheus-staging
```

**Test logs:**
```bash
tail -f logs/staging_deployment.log
```

### Restart Services

```bash
# Restart entire staging stack
docker-compose -f docker-compose-staging.yml restart

# Restart specific service
docker-compose -f docker-compose-staging.yml restart alfa-api-staging

# Restart with clean database
docker-compose -f docker-compose-staging.yml down -v
docker-compose -f docker-compose-staging.yml up -d
```

### Database Access

**Direct PostgreSQL access:**
```bash
docker exec -it alfa-staging-postgres psql -U rankings -d rankings_staging

# Useful queries inside psql:
SELECT COUNT(*) FROM alfa_match_predictions;
SELECT AVG(brier_score) FROM alfa_match_predictions;
SELECT COUNT(*) FROM alfa_anomaly_flags WHERE resolved_at IS NULL;
SELECT * FROM v_staging_metrics_summary;
```

**Redis access:**
```bash
docker exec -it alfa-staging-redis redis-cli

# Useful commands:
INFO memory
KEYS *
DEL cache:*  # Clear cache
```

### Monitor Resource Usage

```bash
docker stats --no-stream

# Watch container memory in real-time
watch 'docker stats --no-stream | grep alfa-'
```

### Clean Up

**Remove containers but keep data:**
```bash
docker-compose -f docker-compose-staging.yml down
```

**Full cleanup (remove containers + volumes):**
```bash
docker-compose -f docker-compose-staging.yml down -v
```

**Prune everything (careful!):**
```bash
docker system prune -a
```

## A/B Testing

### Generate A/B Test Matches

```bash
# Get 100 random test matches with both Alfa and Fargo predictions
curl http://localhost:8006/api/staging/ab-test-matches | jq '.[] | {p1_id, p2_id, alfa_prob_p1, fargo_prob_p1, outcome}'
```

### Weekly Comparison

Run every Monday to collect weekly metrics:

```bash
# Script: scripts/collect_ab_test_metrics.sh
./scripts/collect_ab_test_metrics.sh

# Generates: staging/ab_test_metrics_YYYY-WW.json with:
# - Brier score (Alfa vs Fargo)
# - Accuracy (Alfa vs Fargo)
# - Calibration RMSE
# - Top prediction differences
```

## Validation Checklist (Before Production)

Use this checklist to validate staging is ready for production:

- [ ] All containers running: `docker ps | grep staging`
- [ ] All health checks passing
- [ ] API responds to health: `curl http://localhost:8006/api/health`
- [ ] Database has 100+ test players
- [ ] Smoke tests all pass
- [ ] Load test: < 2% error rate at 100 req/sec
- [ ] Accuracy tests: Brier score within ±0.01 of baseline
- [ ] Anomaly detection: At least 3 types detected
- [ ] No critical Prometheus alerts firing
- [ ] Grafana dashboards displaying data
- [ ] Test report generated: `staging/DATA_VALIDATION_REPORT.md`
- [ ] A/B test data collected for at least 3 days
- [ ] Model versions pinned correctly
- [ ] No data quality issues reported

## Troubleshooting

### API Container Won't Start

```bash
# Check logs
docker logs alfa-api-staging

# Check if port 8006 is in use
lsof -i :8006

# Rebuild image
docker-compose -f docker-compose-staging.yml build --no-cache alfa-api-staging

# Restart
docker-compose -f docker-compose-staging.yml up -d alfa-api-staging
```

### Database Connection Fails

```bash
# Check if postgres is running
docker ps | grep postgres-staging

# Check postgres logs
docker logs alfa-staging-postgres

# Verify database exists
docker exec alfa-staging-postgres psql -U rankings -l

# Reinitialize
docker-compose -f docker-compose-staging.yml down -v
docker-compose -f docker-compose-staging.yml up -d
```

### Tests Fail

```bash
# Run tests with verbose output
pytest backend/tests/staging_tests.py -vv --tb=long

# Run specific failing test
pytest backend/tests/staging_tests.py::TestSmokeHealthChecks::test_api_health_endpoint -vv

# Check test report
cat staging/DATA_VALIDATION_REPORT.md
```

### High Error Rate on Load Test

```bash
# Check API logs for errors
docker logs alfa-api-staging | grep ERROR

# Check database connection pool
docker exec alfa-staging-postgres psql -U rankings -d rankings_staging -c \
  "SELECT count(*) FROM pg_stat_activity;"

# Check Redis connection
docker exec alfa-staging-redis redis-cli INFO | grep connected_clients

# Reduce load test RPS in tests or increase container resources
```

### Metrics Not Appearing in Prometheus

```bash
# Verify prometheus can scrape API
curl http://localhost:9090/api/v1/targets

# Check if metrics endpoint is responding
curl http://localhost:8006/metrics | head -20

# Reload prometheus config
curl -X POST http://localhost:9090/-/reload

# Check prometheus logs
docker logs alfa-prometheus-staging | grep -i "error"
```

## Production Migration

When ready to move to production:

1. **Validate all staging tests pass**
   ```bash
   pytest backend/tests/staging_tests.py -v
   ```

2. **Collect final A/B comparison metrics**
   ```bash
   ./scripts/collect_ab_test_metrics.sh
   ```

3. **Review Prometheus alerts and dashboards**
   - No critical alerts for 24+ hours
   - Metrics stable and predictable

4. **Document any issues/learnings**
   - Update `docs/PRODUCTION_DEPLOYMENT.md`
   - Note any threshold adjustments needed
   - Record any data quality issues found

5. **Deploy to production**
   ```bash
   cd /home/ansible/rankings-bot/Rankings-Bot
   ./scripts/deploy_production.sh
   ```

6. **Monitor production rollout**
   - 1-2 week monitoring period
   - Gradual traffic shift (if A/B testing)
   - Ready to rollback if needed

## Support & References

- **Prometheus Setup**: [monitoring/MONITORING_SETUP_GUIDE.md](MONITORING_SETUP_GUIDE.md)
- **Architecture**: [../ARCHITECTURE.md](../ARCHITECTURE.md)
- **Docker Networking**: [../NETWORKING_STANDARDS.md](../NETWORKING_STANDARDS.md)
- **Port Assignments**: [../.github/PORT_ASSIGNMENTS.md](../.github/PORT_ASSIGNMENTS.md)
- **Alfa Systems**: [ALFA_QUICK_REFERENCE.md](ALFA_QUICK_REFERENCE.md)

---

**Last Updated:** February 16, 2026  
**Maintained By:** Development Team  
**Status:** Ready for Staging Deployment
