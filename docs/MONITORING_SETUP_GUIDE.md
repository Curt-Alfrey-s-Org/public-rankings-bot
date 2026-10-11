# Monitoring & Alerting Setup Guide for Alfa Rating System

> **DEPRECATED reference (staging only).** Sections below ("Overview" onward)
> describe the old self-contained **alfa staging** stack (`alfa-api-staging`,
> `docker-compose-staging.yml`, `alfa_*.json`). They are kept for historical
> reference and PromQL/alert examples — they are **not** the production path.
>
> **Rankings Bot production monitoring** is the **central stack** in the separate
> `monitoring` repo on `192.0.2.20`. See the authoritative guide:
> **[MONITORING_RANKINGS_BOT.md](MONITORING_RANKINGS_BOT.md)**.

## Rankings Bot Production Addendum

Rankings Bot does **not** run its own Prometheus/Grafana in production. The central
`monitoring` stack scrapes the API `/metrics` over the shared `rankings-bot-network`.

Authoritative config (in the `monitoring` repo):

- Scrape config: `monitoring/prometheus/prometheus.yml` (job `rankings-bot-api`)
- Alert rules: `monitoring/prometheus/rules/rankings_alerts.yml`
- Dashboards: `monitoring/grafana/dashboards/rankings_bot_overview.json`,
  `monitoring/grafana/dashboards/rankings_bot_api.json` (Grafana folder **Homelab**)

URLs for Rankings Bot production monitoring (central stack):

- Grafana: `http://192.0.2.20:3000`
- Prometheus: `http://192.0.2.20:9092` (UI; internal scrape/eval on container `:9090`)

Frontend admin integration for Rankings Bot uses:
- `VITE_GRAFANA_BASE_URL` (Grafana links)
- `VITE_PROMETHEUS_BASE_URL` (Prometheus link)

Both are documented in `docs/ENV_VARS.md` and should point at the central URLs above.

## Overview

> The remainder of this document describes the **deprecated alfa staging** stack.

This guide explains how to configure, customize, and operate the monitoring and alerting infrastructure for Alfa rating system staging and production environments.

The monitoring stack consists of:
- **Prometheus** - Metrics collection and alert evaluation
- **Grafana** - Visualization dashboards
- **AlertManager** (optional) - Alert routing and notifications

## Architecture

```
Metrics Flow:
┌──────────────────────────────────────────────────────────────────┐
│  Data Sources                                                    │
├──────────────────────────────────────────────────────────────────┤
│  • Alfa API (/metrics)                                           │
│  • PostgreSQL (pg_stat_*)                                        │
│  • Redis (redis-cli INFO)                                        │
│  • Docker/cAdvisor (container metrics)                           │
│  • Node Exporter (system metrics)                                │
└────────────────────────┬─────────────────────────────────────────┘
                         │ (scrape every 15-30s)
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  Prometheus (storage)                                            │
│  • Time series database                                          │
│  • Rule evaluation (alerts)                                      │
│  • Data retention: 30 days                                       │
└────────────────────────┬─────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
    Grafana          Alerts          API (queries)
  (visualization)   (evaluate)
        │                │
        │                ▼
        │          AlertManager → Slack/Email
        │
        ▼
    Dashboards
    (visualize metrics)
```

## Prometheus Configuration

### Setup

Prometheus configuration file: `monitoring/prometheus/prometheus.yml`

Key sections:

#### 1. Global Configuration

```yaml
global:
  scrape_interval: 15s           # Default scrape interval
  evaluation_interval: 15s       # How often to evaluate alert rules
  external_labels:               # Apply to all time series
    monitor: 'alfa-staging'      
    environment: 'staging'
```

#### 2. Data Sources (Scrape Configs)

Four main job configurations:

**a) Alfa API Metrics**
```yaml
- job_name: 'alfa-api'
  static_configs:
    - targets: ['alfa-api-staging:5000']
  metrics_path: '/metrics'
  scrape_interval: 10s
```

Metrics exposed by Alfa API:
- `alfa_predictions_total{model, outcome}` - Counter of predictions
- `alfa_prediction_latency_seconds_bucket` - Histogram of latencies
- `alfa_prediction_errors_total{error_type}` - Counter of errors
- `alfa_cache_hits_total` - Cache hit counter
- `alfa_cache_misses_total` - Cache miss counter
- `alfa_model_load_time_seconds{model}` - Model load time gauge
- `alfa_brier_score{rolling_window}` - Brier score gauge
- `alfa_anomaly_detections{outcome}` - Anomaly detection counter

**b) PostgreSQL Metrics**
```yaml
- job_name: 'postgres-staging'
  static_configs:
    - targets: ['postgres-staging:5432']
  metrics_path: '/metrics'
  scrape_interval: 30s
```

Requires postgres_exporter for these metrics:
- `pg_stat_statements_total_time` - Query execution time
- `pg_stat_activity_count` - Active connections
- `pg_database_size_bytes` - Database size
- `pg_table_size_bytes{table}` - Per-table sizing

**c) Redis Metrics**
```yaml
- job_name: 'redis-staging'
  static_configs:
    - targets: ['redis-staging:6379']
  metrics_path: '/metrics'
```

Requires redis_exporter:
- `redis_memory_used_bytes` - Used memory
- `redis_keys_total` - Total keys
- `redis_commands_processed_total` - Command count

**d) Docker Metrics (cAdvisor)**
```yaml
- job_name: 'docker-staging'
  static_configs:
    - targets: ['localhost:8080']
  metrics_path: '/metrics'
```

Metrics:
- `container_cpu_usage_seconds_total` - CPU usage
- `container_memory_usage_bytes` - Memory usage
- `container_fs_usage_bytes` - Disk usage
- `container_network_io_bytes_total` - Network I/O

### Custom Metrics Implementation

To expose custom metrics from Alfa API, add to `api/main.py`:

```python
from prometheus_client import Counter, Histogram, Gauge
import time

# Define metrics
predictions_total = Counter(
    'alfa_predictions_total',
    'Total predictions made',
    ['model', 'outcome']  # Labels: alfa_v1, fargo_baseline, etc.
)

prediction_latency = Histogram(
    'alfa_prediction_latency_seconds',
    'Prediction latency in seconds',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0],  # Histogram buckets
    labelnames=['model']
)

brier_score = Gauge(
    'alfa_brier_score',
    'Rolling 7-day average Brier score',
    labelnames=['rolling_window']
)

cache_hits = Counter('alfa_cache_hits_total', 'Cache hits')
cache_misses = Counter('alfa_cache_misses_total', 'Cache misses')

# Use in code
@app.post("/predict")
async def predict(request: PredictionRequest):
    start = time.time()
    try:
        result = model.predict(request.operator_id, request.player2_id)
        predictions_total.labels(model='alfa_v1', outcome='success').inc()
        prediction_latency.labels(model='alfa_v1').observe(time.time() - start)
        return result
    except Exception as e:
        predictions_total.labels(model='alfa_v1', outcome='failure').inc()
        raise

# Expose metrics endpoint
from prometheus_client import make_wsgi_app
from werkzeug.middleware.dispatcher import DispatcherMiddleware

app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    "/metrics": make_wsgi_app()
})
```

### Metric Queries

Common Prometheus query syntax:

```promql
# Current rate of predictions
rate(alfa_predictions_total[5m])

# Prediction error rate (last 5 minutes)
rate(alfa_prediction_errors_total[5m]) / rate(alfa_predictions_total[5m])

# Latency percentiles
histogram_quantile(0.95, rate(alfa_prediction_latency_seconds_bucket[5m]))

# Cache hit rate
rate(alfa_cache_hits_total[5m]) / (rate(alfa_cache_hits_total[5m]) + rate(alfa_cache_misses_total[5m]))

# Database size
pg_database_size_bytes

# Container memory usage
container_memory_usage_bytes{container_name="alfa-api-staging"}

# Combine multiple metrics with JOIN
- Query 1: rate(alfa_predictions_total[5m])
- Query 2: rate(alfa_prediction_errors_total[5m])
- Combined: errors / predictions
```

### View Prometheus Dashboard

Open: `http://localhost:9090`

Key pages:
- **Graph** - Write and execute custom PromQL queries
- **Alerts** - View active alerts and rules
- **Status** - Configuration and service health
- **Targets** - View scrape targets and health

## Alert Rules Configuration

Alert rules file: `monitoring/prometheus/alfa_alerts.yml`

### Alert Structure

```yaml
groups:
  - name: group_name
    interval: 30s  # Evaluation frequency
    rules:
      - alert: AlertName
        expr: 'PromQL expression'  # When true, alert fires
        for: 5m                     # Duration before firing
        labels:
          severity: critical
          service: alfa-api
        annotations:
          summary: "Human-readable summary"
          description: |
            Detailed description with {{ $labels.instance }}
            and {{ $value }} substitution
```

### Example: Create Custom Alert

```yaml
- alert: ModelDataQualityDegraded
  expr: |
    (count(alfa_anomaly_detections) by (type)) / 
    (sum(rate(alfa_predictions_total[1d]))) > 0.15
  for: 30m
  labels:
    severity: warning
    service: alfa-models
  annotations:
    summary: "Model data quality degraded (>15% anomalies)"
    description: |
      Anomaly rate is {{ $value | humanizePercentage }}.
      Review data sources and model drift.
      Action: Check logs, validate training data
```

### Alert Evaluation

Prometheus evaluates alert rules every `evaluation_interval` (default 15s):

1. **Evaluation** - PromQL expression evaluated against current data
2. **Comparison** - Result compared to threshold
3. **Duration** - Alert fires only if condition persists for `for:` duration
4. **Routing** - Fired alerts sent to AlertManager (if configured)

## Grafana Dashboards

### Access Grafana

Open: `http://localhost:3000`
- **Default user:** admin
- **Default password:** admin123 (set during deployment with `GRAFANA_ADMIN_PASSWORD`)

### Dashboard Provisioning

Grafana auto-loads dashboards from JSON files in:
```
monitoring/grafana/dashboards/
├── alfa_overview.json      # System overview dashboard
├── alfa_accuracy.json      # Accuracy & performance metrics
└── alfa_health.json        # Infrastructure health
```

Dashboards are read-only if provisioned automatically.

### Create Custom Dashboard

1. Click **+** → **Dashboard**
2. Click **Add panel**
3. Configure query:
   - **Data source:** Prometheus
   - **Metrics:** Write PromQL expression
4. Configure visualization:
   - **Type:** Graph, Gauge, Stat, Table, etc.
   - **Axes:** Names, units, thresholds
   - **Legend:** Format and position
5. Save dashboard: **Save** button

### Share Dashboards

1. Click dashboard title
2. **Settings** → **Edit JSON**
3. Copy JSON
4. Place in `monitoring/grafana/dashboards/my_dashboard.json`
5. Restart Grafana: `docker-compose restart grafana-staging`

## Alerting Notifications

### Email Alerts

Configure in AlertManager (`monitoring/prometheus/alertmanager.yml`):

```yaml
global:
  resolve_timeout: 5m
  smtp_smarthost: 'smtp.example.com:587'
  smtp_auth_username: 'user8@example.com'
  smtp_auth_password: 'your-app-password'
  from: 'alerts@alfasystem.local'

route:
  receiver: 'email'
  group_by: ['alertname', 'instance']

receivers:
  - name: 'email'
    email_configs:
      - to: 'ops-team@example.com'
        headers:
          Subject: 'Alfa Alert: {{ .GroupLabels.alertname }}'
```

### Slack Alerts

```yaml
global:
  slack_api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'

route:
  receiver: 'slack'

receivers:
  - name: 'slack'
    slack_configs:
      - channel: '#alfa-alerts'
        title: '{{ .GroupLabels.severity | upper }}: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
        send_resolved: true
```

### Enable AlertManager

1. Create `monitoring/prometheus/alertmanager.yml`
2. Start AlertManager container (add to docker-compose-staging.yml):

```yaml
alertmanager:
  image: prom/alertmanager:latest
  container_name: alertmanager
  ports:
    - '127.0.0.1:9093:9093'
  volumes:
    - ./monitoring/prometheus/alertmanager.yml:/etc/alertmanager/config.yml
    - alertmanager_data:/alertmanager
  networks:
    - alfa-staging-network
```

3. Configure Prometheus to use it (already configured in `prometheus.yml`)

## Performance Tuning

### Optimize Prometheus Storage

Edit `docker-compose-staging.yml`:

```yaml
prometheus:
  command:
    - '--storage.tsdb.retention.time=7d'      # Keep only 7 days
    - '--storage.tsdb.max-block-duration=2h'  # Block size
    - '--query.lookback-delta=5m'              # Query optimization
```

### Optimize Scrape Intervals

Adjust in `monitoring/prometheus/prometheus.yml`:

```yaml
# For high-volume metrics, use longer intervals
- job_name: 'docker-staging'
  scrape_interval: 60s   # Instead of 30s
  scrape_timeout: 10s

# For critical metrics, use shorter intervals
- job_name: 'alfa-api'
  scrape_interval: 5s    # More frequent
```

### Optimize Dashboard Queries

Avoid expensive queries:
```promql
# Bad: Queries all labels
rate(container_cpu_usage_seconds_total[5m])

# Good: Filter by container
rate(container_cpu_usage_seconds_total{container_name=~"alfa-.*"}[5m])
```

## Maintenance

### Backup Prometheus Data

```bash
# Stop Prometheus
docker-compose -f docker-compose-staging.yml stop prometheus-staging

# Backup storage
tar -czf prometheus_backup_$(date +%Y%m%d).tar.gz monitoring/

# Restart
docker-compose -f docker-compose-staging.yml start prometheus-staging
```

### Backup Grafana Dashboards

```bash
# Export all dashboards
curl http://localhost:3000/api/search | jq '.[] | .id' | \
  xargs -I {} curl http://localhost:3000/api/dashboards/uid/{} > all_dashboards.json

# Or use API key (create in Grafana UI first)
curl -H "Authorization: Bearer YOUR_API_TOKEN" \
  http://localhost:3000/api/dashboards > all_dashboards.json
```

### Clean Old Metrics

Prometheus automatically removes series older than `storage.tsdb.retention.time`.

To manually delete old data:

```bash
curl -X POST http://localhost:9090/api/v1/admin/tsdb/delete_series?match[]={}
```

## Troubleshooting

### Prometheus Won't Start

```bash
# Check logs
docker logs prometheus-staging

# Validate config syntax
docker run -v $(pwd)/monitoring/prometheus:/config \
  prom/prometheus --config.file=/config/prometheus.yml --dry-run

# Common issues:
# - YAML indentation
# - Invalid PromQL in alert rules
# - Target hosts not resolvable
```

### Metrics Not Appearing

```bash
# Check targets in Prometheus UI
http://localhost:9090/targets

# Manually test scrape endpoint
curl http://localhost:8006/metrics | grep alfa_predictions

# Check Prometheus logs for scrape errors
docker logs prometheus-staging | grep -i "error"
```

### Alerts Not Firing

```bash
# Check alert rules in Prometheus UI
http://localhost:9090/alerts

# Verify rule conditions
- Navigate to Graph tab
- Execute the alert's PromQL expression
- Check if condition evaluates to true

# Check alert state
curl http://localhost:9090/api/v1/rules | jq '.data.groups[0].rules'

# Common issues:
# - Label names misspelled
# - Threshold value incorrect
# - Metric not available from that data source
```

### Grafana Dashboards Blank

```bash
# Check data source configuration
http://localhost:3000/datasources

# Verify Prometheus is reachable from Grafana
curl -X POST http://localhost:3000/api/datasources/proxy/1/api/v1/query?query=up

# Check panel queries
- Edit panel
- Check PromQL expression
- Run query manually in Prometheus

# Rebuild dashboards
docker-compose -f docker-compose-staging.yml restart grafana-staging
```

### High Memory Usage in Prometheus

```bash
# Check tsdb disk usage
du -sh monitoring/

# Reduce retention
# Edit docker-compose-staging.yml, set shorter retention:
command:
  - '--storage.tsdb.retention.time=7d'    # Was 30d

# Reduce scrape frequency
# Edit monitoring/prometheus/prometheus.yml:
global:
  scrape_interval: 30s    # Was 15s

# Restart
docker-compose -f docker-compose-staging.yml restart prometheus-staging
```

## Best Practices

1. **Alert Naming** - Use descriptive, action-oriented names
   - ✓ `AlfaPredictionErrorRateHigh`
   - ✗ `error_rate_alert`

2. **Alert Thresholds** - Based on operational experience
   - Test thresholds during staging
   - Adjust based on observed anomalies
   - Document reasoning

3. **Label Consistency** - Use same labels across all metrics
   - `service: "alfa-api"`
   - `severity: "critical"`
   - `environment: "staging"`

4. **Metric Naming** - Follow Prometheus conventions
   - `unit_base` (e.g., `latency_seconds`, `size_bytes`)
   - `total` suffix for counters
   - `_bucket` for histograms

5. **Dashboard Organization**
   - One dashboard per major system component
   - Start with high-level metrics, drill down
   - Include context and runbooks

6. **Query Efficiency**
   - Use appropriate time ranges
   - Filter by labels to reduce cardinality
   - Avoid expensive joins

## References

- [Prometheus Official Docs](https://prometheus.io/docs/)
- [PromQL Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Documentation](https://grafana.com/docs/grafana/latest/)
- [Alert Rules Syntax](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)
- [Slack Integration](https://prometheus.io/docs/alerting/latest/configuration/#slack_config)

---

**Last Updated:** February 16, 2026  
**Maintained By:** DevOps Team  
**Status:** Staging Environment Ready
