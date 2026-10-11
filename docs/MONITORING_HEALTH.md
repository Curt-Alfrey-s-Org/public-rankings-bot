# Monitoring and Health Checks

Use these endpoints and scripts for uptime checks, alerting, and monitoring (e.g. cron, systemd, or external monitors).

## Endpoints

### 1. Simple liveness: `GET /api/health`

**Use for:** Uptime checks, load balancer health, “is the API up?”

- **URL:** `http://<host>:8003/api/health` (or your `API_PORT` / `API_URL`)
- **Response:** `200 OK` with JSON: `{ "status": "healthy", "service": "Rankings Bot API", "version": "1.0.0" }`
- **No auth.** Fast; no DB or self-test.

**Example (curl):**

```bash
curl -sf http://127.0.0.1:8003/api/health && echo "OK" || echo "FAIL"
```

- `-s` silent, `-f` fail on HTTP 4xx/5xx. Exit 0 = OK, non‑zero = fail (use in cron/scripts).

---

### 2. Full health and self-test: `GET /api/system/health`

**Use for:** Deeper checks (self-test, startup status). Cached ~60 seconds to avoid running tests on every request.

- **URL:** `http://<host>:8003/api/system/health`
- **Response:** `200 OK` with JSON including:
  - `status`: `"healthy"` | `"degraded"` | `"error"`
  - `self_test`: passed/failed counts, results, timings
  - Optional: `startup_timings`, `system` (platform, Python version)
- **No auth.** Heavier than `/api/health`; use for periodic checks (e.g. every 1–5 minutes), not every second.

**Example (curl, check status field):**

```bash
STATUS=$(curl -sf http://127.0.0.1:8003/api/system/health | jq -r '.status')
[ "$STATUS" = "healthy" ] || exit 1
```

---

## Scripts for monitoring

### Scheduled refresh: `scripts/refresh_rankings.py`

- **Exit code:** `0` = both WPBA and WPA refresh OK; `1` = one or both failed.
- Use in cron or systemd to refresh data; alert if exit code is non‑zero.
- See **docs/SCHEDULED_REFRESH.md** for cron/systemd setup.

### Database and API startup

- **Setup:** `./setup.sh` or `./master_setup.sh` (see README).
- **Start API:** `./start_api.sh` (or desktop icon). API listens on `API_PORT` (default 8003).
- If the API is behind a reverse proxy (e.g. Nginx), point your monitor at the same URL the frontend uses (e.g. `https://your-domain/api/health`).

### External monitoring (Uptime Robot, cron, etc.)

- **HTTP(S) check:** Point any uptime checker at `https://your-domain/api/health`. Expect 200 and JSON `"status":"healthy"`. Alert on timeout or non-200.
- **Uptime Robot / Pingdom:** Add a monitor for `https://your-domain/api/health` (HTTP(s) keyword or status 200). Optional: add a second monitor for `https://your-domain/` (frontend).
- **Cron:** `curl -sf https://your-domain/api/health >/dev/null || echo "Rankings Bot API down"` (pipe to mail or your alerting).

---

## Suggested use

| Goal                 | Endpoint or script              | Frequency / note        |
|----------------------|---------------------------------|--------------------------|
| “Is the API up?”     | `GET /api/health`               | Every 30–60 s            |
| “Is the app healthy?”| `GET /api/system/health`       | Every 1–5 min            |
| Refresh rankings     | `scripts/refresh_rankings.py`   | Per cron/systemd (e.g. daily) |
| Alert on failure     | Non‑zero exit from curl or script | Per your alerting tool  |

---

## Optional: readiness (DB)

The app does not expose a separate “readiness” endpoint. If the DB is missing or broken, requests that use it (e.g. `/api/rankings/wpba`) will return 500. For “is the API and DB ready?” you can:

- Call `GET /api/health` for “process is up,” and
- Call `GET /api/rankings/last-update` (or another read-only rankings endpoint); 200 = DB reachable, 500 = investigate.

No auth is required for these GETs.

---

## Where logs live

| Component | Location | Env / notes |
|-----------|----------|-------------|
| **API** | `rankings_bot.log` (project root) | Override with `LOG_FILE` env var. Level: `LOG_LEVEL` (default INFO); `DEBUG=true` enables DEBUG. |
| **API (Docker)** | `docker logs rankings-bot-api` | Or `docker logs <container-name>` for your API container. |
| **Frontend** | Browser DevTools Console | API calls, errors, timeouts. Optional: Sentry when configured. |
| **Postgres** | `docker logs rankings-bot-postgres` | When using Docker Postgres. |

---

## Observability: health failure

- **Structured logging:** When `/api/health` or `/api/v1/health` returns 5xx, the API logs at **ERROR** with `Health check failed: path=... status=...`. Use this for log-based alerting (e.g. grep, or ship logs to your monitoring).
- **Alerting:** Use an HTTP monitor (cron, Uptime Robot, etc.) that calls `/api/health` and alerts on non-200 or timeout (see "External monitoring" above). Optionally run `GET /api/system/health` periodically and alert when `status` is not `"healthy"`.

---

## Container healthchecks (`docker compose up --wait`)

These healthchecks are distinct from the `/api/health` endpoints above. They run
**inside** each container and are used by Docker Compose to decide when a service
is "ready". `scripts/start.sh` invokes:

```bash
docker compose -f production/docker-compose.prod.yml up -d --wait
```

Per [Docker's `compose up` reference](https://docs.docker.com/reference/cli/docker/compose/up/),
`--wait` blocks until every service is **`running`** (no healthcheck defined) or
**`healthy`** (healthcheck defined and passing). If a service explicitly sets
`healthcheck: disable: true`, Compose prints
`container <name> has no healthcheck configured` and returns non-zero on
`--wait`. That caused `start.sh` to abort with `ERROR: Compose up failed.`
even though every container was actually running.

Rule of thumb for this repo:

- **Never** use `healthcheck: disable: true` on a service that is reached by
  `--wait`. Either provide a real healthcheck, or omit the `healthcheck:` block
  entirely so Compose falls back to the `running` gate.
- Prefer a **real** healthcheck so `depends_on: service_healthy` and `--wait`
  both mean what they say.

### Celery worker: `celery inspect ping`

`production/docker-compose.prod.yml` → `celery-worker`:

```183:191:/home/ansible/rankings-bot/production/docker-compose.prod.yml
    healthcheck:
      test: ["CMD-SHELL", "celery -A api.services.celery_worker inspect ping -d celery@$$HOSTNAME -t 5 >/dev/null 2>&1 || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 45s
```

Design choices, and which Docker/Celery manual each maps to:

| Choice | Reference | Why |
|---|---|---|
| `test: ["CMD-SHELL", "... \|\| exit 1"]` | [Compose spec — `healthcheck.test`](https://docs.docker.com/reference/compose-file/services/#healthcheck) | Canonical form. First list element must be `NONE`, `CMD`, or `CMD-SHELL`; `CMD-SHELL` lets us use `\|\|`, `>/dev/null`, and `$HOSTNAME`. |
| `celery -A api.services.celery_worker inspect ping` | [Celery — Inspecting workers](https://docs.celeryq.dev/en/stable/userguide/workers.html#inspecting-workers) | Round-trip probe: client → broker → worker → broker → client. Proves the worker process is alive **and** still connected to Redis — a bare `pgrep celery` would pass even if the broker connection had dropped. |
| `-d celery@$$HOSTNAME` | [Celery — replies/destinations](https://docs.celeryq.dev/en/stable/userguide/workers.html#commands) | Targets **this** worker by its node name. Compose escapes `$$` to a literal `$`, so the in-container shell expands `$HOSTNAME` at probe time. Without `-d`, the probe would accept any worker's reply — a false positive in a multi-worker cluster. Verified: `exit=0` when the targeted worker replies, `exit=69` when it doesn't. |
| `-t 5` | [Celery — control commands & timeouts](https://docs.celeryq.dev/en/stable/userguide/workers.html#commands) | Celery's default reply deadline is 1 s. We raise it to 5 s to tolerate transient broker latency during warm-up, but cap it so the probe can never hang longer than `timeout`. |
| `>/dev/null 2>&1 \|\| exit 1` | [Compose spec — exit codes](https://docs.docker.com/reference/compose-file/services/#healthcheck) | Healthchecks are judged on exit status only (0 = healthy, non-0 = unhealthy). Redirecting output keeps `docker inspect`'s `Health.Log` clean. |
| `interval: 30s`, `timeout: 10s`, `retries: 3` | [Compose spec](https://docs.docker.com/reference/compose-file/services/#healthcheck) defaults are 30 s / 30 s / 3 | Explicit `timeout: 10s` (< `interval`) so a stuck probe is killed before the next one starts, preventing probe pile-up. |
| `start_period: 45s` | [Compose spec](https://docs.docker.com/reference/compose-file/services/#healthcheck) | During start-up, probe failures don't count against `retries`. 45 s covers Celery boot (import + `mingle: searching for neighbors` + first broker handshake — observed ≈ 2 s, but ample headroom for cold disk / slow host). |

### Verification

```bash
# 1. Full Compose up returns 0 and all services report Healthy
docker compose -f production/docker-compose.prod.yml up -d --wait; echo "exit=$?"

# 2. Inspect the probe result for celery-worker
docker inspect --format '{{.State.Health.Status}}' rankings-bot-celery-worker
# → healthy

# 3. Show the last few probe runs
docker inspect --format \
  '{{range .State.Health.Log}}{{.End}} exit={{.ExitCode}}{{"\n"}}{{end}}' \
  rankings-bot-celery-worker | tail -5
```

### Other services

The other production services already define healthchecks that follow the same
pattern (see `production/docker-compose.prod.yml`):

| Service | Probe |
|---|---|
| `rankings-bot-api` | `curl -fsS http://localhost:8003/api/health` |
| `rankings-bot-postgres` | `pg_isready` |
| `rankings-bot-redis` | `redis-cli ping` |
| Central Prometheus / Grafana (`monitoring` stack on `apps`) | `/-/ready` and Grafana `/api/health` |

If you add a new service to the production compose file and it will be reached
by `--wait`, follow the same pattern: one real `CMD-SHELL` probe that exercises
the service's primary dependency (not just "the process exists").

---

## Prometheus + Grafana (central homelab stack)

Deep metrics and dashboards are **not** embedded in this repo. They live in the shared stack:

- **Repo / Compose:** `/home/ansible/monitoring` (see `README.md` there; Dockge: `/opt/stacks/monitoring`)
- **Grafana:** `http://192.0.2.20:3000` (LAN)
- **Prometheus:** `http://192.0.2.20:9092` (LAN — host `9092` because `9090` is used on the server)
- **API metrics (production container):** `http://<api-host>:8003/metrics` — scraped by central Prometheus when the API is on `rankings-bot-network`

**Admin UI (links from the web app):** Point `VITE_GRAFANA_BASE_URL` and `VITE_PROMETHEUS_BASE_URL` at the central URLs above (see [ENV_VARS.md](ENV_VARS.md)).

Quick verification:

```bash
curl -sf http://localhost:8003/metrics >/dev/null && echo "API metrics OK"
curl -sf http://192.0.2.20:9092/-/ready && echo "Prometheus OK"
curl -sf http://192.0.2.20:3000/api/health && echo "Grafana OK"
```
