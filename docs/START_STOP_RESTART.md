# Start, Stop, and Restart — Rankings Bot

**Primary entry points**

| Role | Script |
|------|--------|
| **Start / restart stack** (Docker Node frontend build, Docker images, nginx, optional p/m site mode) | `./scripts/start.sh` |
| **Full deployment** (same frontend build, image rebuild strategy, **Alembic in API container**, nginx image, verification -- heavier path) | `./scripts/full_deploy.sh` |
| **Full stop** | `./scripts/stop.sh` |

`./scripts/start.sh` and `./scripts/full_deploy.sh` are **not** identical: use **`full_deploy.sh`** when you need the full release pipeline (migrations, post-deploy checks). Use **`start.sh`** for routine bring-up.

**Frontend build:** `scripts/start.sh` and `scripts/full_deploy.sh` build the frontend **only** via `scripts/build_frontend_with_docker.sh` (ephemeral `node:20-alpine` container). **Host npm is not used.** Output goes to `frontend/dist/`, bind-mounted into the API container. **Admin → Update website** runs on the **host** via the deploy dispatcher (`production/systemd/rankings-bot-deploy.path` + `scripts/deploy_request_dispatcher.sh`); the API container holds no docker.sock (see `docs/ADMIN_DEPLOY_HOST_DISPATCH.md`).

---

## Quick Reference

| Action | Command |
|--------|---------|
| **Start full stack** | `./scripts/start.sh` |
| **Start with forced image rebuild** | `./scripts/start.sh --no-cache` |
| **Full deploy (migrations + verify)** | `./scripts/full_deploy.sh` |
| **Full deploy, clean rebuild** | `./scripts/full_deploy.sh --no-cache` |
| **Maintenance mode (no prompt)** | `./scripts/start.sh --maintenance` or `./scripts/full_deploy.sh --maintenance` |
| **Production site mode (no prompt)** | `./scripts/start.sh --production` or `./scripts/full_deploy.sh --production` |
| **Stop full stack** | `./scripts/stop.sh` |
| **Stop and Cloudflare tunnel** | `./scripts/stop.sh --tunnel` |
| **Start web only** | `./scripts/start_web.sh` |
| **Stop web only** | `./scripts/stop_web.sh` |
| **Start mobile only** | `./scripts/start_mobile.sh` |
| **Stop mobile only** | `./scripts/stop_mobile.sh` |
| **Start dev: Docker flow** | `./scripts/start.sh --dev` |
| **Stop dev** | `./scripts/stop.sh --dev` |
| **Start deps only** | `./scripts/start.sh --deps-only` |
| **Stop deps only** | `./scripts/stop.sh --deps-only` |
| **Start app only** | `./scripts/start.sh --app-only` |
| **Stop app only** | `./scripts/stop.sh --app-only` |

**Volumes:** `stop.sh` does **not** remove Postgres/Redis data volumes.

**Canonical Compose file:** Production uses **`production/docker-compose.prod.yml`** for Postgres, Redis, API, Celery, and monitoring. Root **`docker-compose.yml`** only `include:`s that file so older commands still work. Prefer the scripts above or explicit `-f production/docker-compose.prod.yml`.

---

## Production (Docker)

| Action | Command |
|--------|---------|
| **Routine start** | `./scripts/start.sh` |
| **Release deploy** | `./scripts/full_deploy.sh` |
| **Status** | `docker ps` |
| **API logs** | `docker logs rankings-bot-api -f` |

---

## Development

### Web app only (API + frontend)
```bash
./scripts/start_web.sh
./scripts/stop_web.sh
```

### Mobile app only (Metro)
```bash
./scripts/start_mobile.sh
./scripts/stop_mobile.sh
```

### Docker incremental (deps then app)
```bash
./scripts/start.sh --deps-only
./scripts/start.sh --app-only
./scripts/stop.sh --app-only
```

See `docs/DOCKER_POSTGRES_ONLY.md`.

---

## Script options

### start.sh
- `--dev` | `--deps-only` | `--app-only` | `--tunnel` | `--no-cache` | `--production` | `--maintenance`

### full_deploy.sh
- `--no-cache` | `--production` | `--maintenance` | `--rollback-on-failure` | `--verbose`

### stop.sh
- `--app-only` | `--deps-only` | `--dev` | `--tunnel`

---

## Archived reference

See **`scripts/archive/README.md`**.

---

## Troubleshooting

### `ERROR: Compose up failed.` with `container ... has no healthcheck configured`

`scripts/start.sh` runs `docker compose … up -d --wait`. Per
[Docker's compose up reference](https://docs.docker.com/reference/cli/docker/compose/up/),
`--wait` waits for every service to be `running` **or** `healthy`. A service
declared with `healthcheck: disable: true` hits a gap in Compose's semantics —
it prints `has no healthcheck configured` and returns non-zero, so `start.sh`
aborts with `ERROR: Compose up failed.` even though all containers are up.

Fix: give the service a real `healthcheck:` block, or remove the `healthcheck:`
block entirely so Compose uses the `running` gate. For the Celery worker in
this repo we use a `celery inspect ping` probe — see
[`docs/MONITORING_HEALTH.md` → Container healthchecks](MONITORING_HEALTH.md#container-healthchecks-docker-compose-up---wait)
for the full rationale and tuning.
