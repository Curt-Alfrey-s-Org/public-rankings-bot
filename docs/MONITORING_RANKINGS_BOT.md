# Rankings Bot Monitoring Guide

## Overview

Rankings Bot production monitoring is provided by the **central monitoring stack**
on the apps host (`192.0.2.20`), defined in the separate repo
[`/home/ansible/monitoring`](../../monitoring/README.md). Rankings Bot does **not**
run its own Prometheus/Grafana in production; the central stack scrapes the API
over the shared `rankings-bot-network` Docker network.

Covered signals:
- API performance (request rates, latency, errors) via the API `/metrics` endpoint
- Container metrics (CPU, memory, network per service) via cAdvisor
- Database health (PostgreSQL connections, query performance) via postgres-exporter
- Redis metrics (memory, connections, operations) via redis-exporter
- System resources (host CPU, memory, disk, network) via node_exporter

> Note: a self-contained Prometheus/Grafana exists only in
> `docker-compose-staging.yml` (the deprecated alfa staging stack). It is **not**
> the production path and is not described here.

## Quick Start

### Access dashboards (central stack on `192.0.2.20`)

| Service | URL | Notes |
|---------|-----|-------|
| **Grafana** | `http://192.0.2.20:3000` | Datasources `prometheus` + `loki` provisioned |
| **Prometheus** | `http://192.0.2.20:9092` | UI; internal scrape/eval runs on container `:9090` |
| **Alertmanager** | `http://192.0.2.20:9093` | Alert routing |

Rankings Bot dashboards (Grafana folder **Homelab**):
- **Rankings Bot - API Performance** (`monitoring/grafana/dashboards/rankings_bot_api.json`)
- **Rankings Bot - System Overview** (`monitoring/grafana/dashboards/rankings_bot_overview.json`)

### Frontend integration

Monitoring links are available in **Settings > Admin > Health & logs**
(`/settings/admin/health-logs`).
- Grafana links appear when `VITE_GRAFANA_BASE_URL` is configured.
- Prometheus link appears when `VITE_PROMETHEUS_BASE_URL` is configured.

Add to `.env` (point at the central stack):
```bash
VITE_GRAFANA_BASE_URL=http://192.0.2.20:3000
VITE_PROMETHEUS_BASE_URL=http://192.0.2.20:9092
```

Grafana admin credentials are managed in the `monitoring` repo
(`GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` in its `.env`), not in this repo.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Metrics sources (scraped by the central Prometheus)         │
├─────────────────────────────────────────────────────────────┤
│  • Rankings Bot API        rankings-bot-api:8003/metrics      │
│  • PostgreSQL              postgres-exporter-rankings:9187     │
│  • Redis                   redis-exporter-rankings:9121        │
│  • Docker containers       cadvisor:8080 (host :8081)         │
│  • System/host             host.docker.internal:9100          │
└────────────────────────┬────────────────────────────────────┘
                         │ reachable via rankings-bot-network (Docker DNS)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Prometheus (container :9090, host :9092)                    │
│  • Time series storage + alert rule evaluation                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Grafana (host :3000)  ·  Alertmanager (host :9093)          │
└─────────────────────────────────────────────────────────────┘
```

## Prometheus configuration

Lives in the `monitoring` repo:
- Scrape config: `monitoring/prometheus/prometheus.yml`
- Alert rules: `monitoring/prometheus/rules/rankings_alerts.yml`

### Scrape targets (jobs in `prometheus.yml`)

1. **`rankings-bot-api`** — `rankings-bot-api:8003/metrics`
   - HTTP request metrics (rate, latency, errors), request/response sizes,
     status-class distribution
2. **`postgres`** — `postgres-exporter-rankings:9187` (connections, query perf, size)
3. **`redis`** — `redis-exporter-rankings:9121` (memory, clients, ops)
4. **`cadvisor`** — `cadvisor:8080` (per-container CPU, memory, network, restarts)
5. **`node`** — `host.docker.internal:9100` (host CPU, memory, disk, network)

Prometheus reaches `rankings-bot-api` because the monitoring stack joins
`rankings-bot-network`; the API itself binds `127.0.0.1:8003` on the host.

## Grafana dashboards

Provisioned from files in `monitoring/grafana/dashboards/` (folder **Homelab**):

- **Rankings Bot - System Overview** (`rankings_bot_overview.json`): API request rate
  by method/status, error rate (4xx/5xx), response time (p50/p95/p99), container
  CPU/memory, PostgreSQL connections, Redis memory/clients, system CPU/memory,
  network and disk I/O.
- **Rankings Bot - API Performance** (`rankings_bot_api.json`): request rate and p95
  latency by endpoint, error rate by endpoint, request/response size distributions,
  HTTP status-class and method distributions.

## Alert rules

File: `monitoring/prometheus/rules/rankings_alerts.yml`. Active alerts:

1. **RankingsBotAPIDown** — `up{job="rankings-bot-api"} == 0` for >1m (critical)
2. **HighAPIErrorRate** — 5xx rate >0.1/s for 5m (warning)
3. **HighAPILatency** — p95 latency >2s for 5m (warning)
4. **PostgresDown** — database unavailable (critical)
5. **HighPostgresConnections** — >80 active connections (warning)
6. **SlowPostgresQueries** — query time >10 s/s (warning)
7. **RedisDown** — Redis unavailable (critical)
8. **HighRedisMemory** — memory usage >90% (warning)
9. **ContainerHighCPU** — container CPU >80% (warning)
10. **ContainerHighMemory** — container memory >90% (warning)
11. **ContainerRestarting** — frequent restarts (warning)
12. **HighSystemCPU** — system CPU >80% (warning)
13. **HighSystemMemory** — system memory >85% (warning)
14. **LowDiskSpace** — disk space <15% (warning)

View in Prometheus UI: `http://192.0.2.20:9092/alerts`.

## API metrics endpoint

The API exposes Prometheus metrics at `/metrics` (host loopback):

```bash
curl http://127.0.0.1:8003/metrics
```

### Available metrics

- `http_requests_total{method, endpoint, status}` — total HTTP requests.
  The `status` label is a **status class** (`2xx`, `3xx`, `4xx`, `5xx`), not a raw
  3-digit code. Alert/dashboard selectors must match the class exactly
  (e.g. `status="5xx"`).
- `http_request_duration_seconds{method, endpoint}` — request latency histogram
- `http_request_size_bytes{method, endpoint}` — request size histogram
- `http_response_size_bytes{method, endpoint}` — response size histogram

### Metrics middleware

`PrometheusMiddleware` (`api/middleware/prometheus.py`) tracks all HTTP requests:
normalizes paths (replaces IDs with `{id}`), records request/response sizes, and
tracks latency and status class.

## Troubleshooting

### Prometheus target down

```bash
# From the monitoring host, check rankings-bot-api target health
curl -s 'http://192.0.2.20:9092/api/v1/targets' \
  | jq '.data.activeTargets[] | select(.labels.job=="rankings-bot-api")'
```

Common causes:
- API container not running (`docker compose ps` in this repo)
- Monitoring stack not joined to `rankings-bot-network`
- API `/metrics` disabled (verify `prometheus-client` installed)

### Metrics not appearing

```bash
# Verify API metrics endpoint (host loopback)
curl -s http://127.0.0.1:8003/metrics | grep http_requests_total

# From the Prometheus container, confirm it can reach the API by Docker DNS
docker exec prometheus wget -qO- http://rankings-bot-api:8003/metrics | head -5
```

### Grafana dashboards empty

```bash
# Confirm the Prometheus datasource is provisioned
curl -s http://192.0.2.20:3000/api/datasources \
  | jq '.[] | select(.type=="prometheus") | {name, url}'
```

If panels are empty, confirm the `rankings-bot-api` target is `up` in Prometheus
(Status → Targets) and that the dashboard JSON files are present under
`monitoring/grafana/dashboards/`.

## Maintenance

Prometheus retention, Grafana provisioning, and backups are owned by the
`monitoring` repo. See:
- `monitoring/README.md` — stack overview and operations
- `monitoring/PORTS.md` — authoritative host/container port map
- `monitoring/SERVER_STACKS.md` — which container belongs to which compose stack

## Security notes

- Central Grafana (`3000`), Prometheus (`9092`), and Alertmanager (`9093`) are
  published on the LAN host; restrict via firewall / reverse proxy as needed.
- The API `/metrics` endpoint is unauthenticated and bound to `127.0.0.1:8003`
  on the host; Prometheus reaches it over the Docker network only.
- Change the default Grafana password via `GRAFANA_ADMIN_PASSWORD` in the
  `monitoring` repo `.env`.

## References

- [monitoring/README.md](../../monitoring/README.md) — central stack
- [monitoring/PORTS.md](../../monitoring/PORTS.md) — port reference
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Alert Rules Syntax](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/)

---

**Status:** Production (central monitoring stack on `192.0.2.20`)
