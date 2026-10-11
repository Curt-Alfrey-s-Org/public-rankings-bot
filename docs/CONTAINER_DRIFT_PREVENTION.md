# Container Drift Prevention (No Workarounds)

This project is Docker-first for runtime and deployment. To maintain structure and prevent drift, all operational fixes must remain container-native.

## Why this exists

Drift occurs when app code, image version, and database schema move out of sync. A common anti-pattern is applying host-side workarounds (for example, bind-mounting newer host code into an older running image just to run migrations). That creates non-reproducible states.

## Mandatory policy

- Do not use host-side bind mounts to patch service code at runtime.
- Do not run API/web/worker processes directly on host for production-style operations.
- Do not apply ad-hoc SQL as a substitute for Alembic migrations.
- Always run migrations from the same container image version that will serve traffic.
- Use nginx as the single ingress path for app traffic; do not publish API/frontend ports directly to host.

## Required deployment order

1. Build or pull updated Docker images.
2. Run Alembic migrations from the API image.
3. Start/restart services via Docker Compose.
4. Verify system health and revision parity.

## Revision parity checks

Run checks from containerized context:

```bash
docker compose run --rm rankings-bot-api alembic current
docker compose run --rm rankings-bot-api alembic heads
```

If current does not match heads, deployment is incomplete.

## Build-hash verification

Every image build bakes a content hash into the image (OCI label + `/app/.build-hash`). The API exposes it at `GET /api/health` in the `build_hash` field. The deploy script (`full_deploy.sh`) passes the hash via `--build-arg BUILD_HASH=<hash>` at build time and, after `compose up`, compares the running container's reported hash against the expected one. If they differ, the deploy **exits non-zero** with a remediation command.

Verify manually:

```bash
# Expected hash (computed from source)
cat .docker-build-hash

# Running hash (from the container)
curl -s http://127.0.0.1:8003/api/health | python3 -c "import sys,json; print(json.load(sys.stdin).get('build_hash'))"
```

If they don't match, the running container is serving stale code. Force-recreate:

```bash
docker compose -f production/docker-compose.prod.yml up -d --force-recreate rankings-bot-api
```

## No-fallback policy

The codebase enforces a single source of truth for all data. Patterns that are prohibited:

- Hardcoded static data that duplicates what an API endpoint returns (e.g., menu items, feature lists).
- Secondary query paths that serve different data when the primary path fails.
- "Degraded mode" that silently returns stale or incomplete data instead of surfacing the error.

If a data source is unavailable, the UI shows a loading/empty state -- not stale data from a static duplicate. See `.cursor/rules/no-workarounds.mdc`.

## Operational rule of thumb

If a fix requires host-only steps, stop and convert it into a containerized, reproducible deployment step.

## References

- [Twelve-Factor App: Processes](https://12factor.net/processes)
- [Docker Compose docs](https://docs.docker.com/compose/)
- [FastAPI deployment guidance](https://fastapi.tiangolo.com/deployment/)
