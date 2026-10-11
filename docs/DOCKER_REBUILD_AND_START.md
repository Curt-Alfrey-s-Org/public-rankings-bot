# Docker: faster rebuilds and conditional rebuild/start

## Summary

- **Full deploy** (`./scripts/full_deploy.sh`) rebuilds API/nginx images **only when the build context changed** (Dockerfile or requirements files). Use `--no-cache` to force a full rebuild.
- **Start** (`./scripts/start.sh`) brings up the full stack. For rebuild detection, use full_deploy.sh.
- The API image uses a **slim dependency set** (`requirements-deps.txt`) and **layered Dockerfile** so code-only changes rebuild quickly (reuse deps layer).

## Build context hash (intelligent layering)

- **Script:** `./scripts/docker_build_hash.sh`  
  Content hash of: `Dockerfile`, `requirements-api.txt`, `requirements-deps.txt`, compose, and app code (`api/`, `scrapers/`, `database/`, `scripts/`, `alembic/`, `alembic.ini`, root `*.py`). Tracks all inputs per Docker/Python standards.
- **Stored hash:** `.docker-build-hash` (gitignored). Written after a successful image build; used to skip rebuild when unchanged.
- **BuildKit:** `DOCKER_BUILDKIT=1` enables intelligent layering, cache mounts, parallel stages (Docker docs).

## Commands

| Command | Behavior |
|--------|----------|
| `./scripts/full_deploy.sh` | Deploy; rebuild images only if hash changed (uses cache). |
| `./scripts/full_deploy.sh --no-cache` | Force full image rebuild (no cache). |
| `./scripts/full_deploy.sh --rollback-on-failure` | On failure, run stop.sh to clean up orphan containers. |
| `./scripts/start.sh` | Start containers (no rebuild). Use `full_deploy.sh` for rebuild. |

## Requirements layout

- **requirements-api.txt** — FastAPI, uvicorn, DB, auth, Celery (API core).
- **requirements-deps.txt** — Scrapers, PDF, pandas, email, payments (slim; no pytest/dash/ML).
- **requirements.txt** — Full stack for local dev/tests; not used by the Docker image.
