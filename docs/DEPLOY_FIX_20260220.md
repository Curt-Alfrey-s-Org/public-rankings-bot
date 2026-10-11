# Deployment Fix — February 20, 2026

## Issue

Running `./scripts/full_deploy.sh --force-docker` failed with exit code 1:

```
[04:19:10] 2bb. Applying database migrations (container)...
FAILED: No 'script_location' key found in configuration.
[04:19:10] ERROR: Alembic migrations failed in container.
```

## Root Cause

The Dockerfile was **not copying the alembic migration files** into the Docker image:
- Missing: `alembic/` directory (migration scripts)
- Missing: `alembic.ini` (configuration file)

When the deploy script executed `docker exec rankings-bot-api python -m alembic upgrade head`, alembic couldn't find its configuration.

## Solution

Added migration files to Dockerfile Layer 3 (application code):

**File:** [Dockerfile](../Dockerfile)

```dockerfile
# -----------------------------------------------------------------------------
# Layer 3: application code (rebuild on code change; reuses layers above)
# -----------------------------------------------------------------------------
COPY api/ /app/api/
COPY scrapers/ /app/scrapers/
COPY database/ /app/database/
COPY scripts/ /app/scripts/
COPY alembic/ /app/alembic/          # ← ADDED
COPY alembic.ini /app/                # ← ADDED
COPY *.py /app/
COPY frontend/dist/ /app/frontend/dist/
```

## Verification

After the fix, deployment completed successfully:

```bash
[04:21:39] 2bb. Applying database migrations (container)...
INFO:alembic.runtime.migration:Context impl PostgresqlImpl.
INFO:alembic.runtime.migration:Will assume transactional DDL.
INFO:alembic.runtime.migration:Running upgrade 020 -> 021, Add tournaments.is_test_tournament column to filter test tournaments.
[04:21:40] 2c. Waiting for API health...
[04:21:45]    ✅ API health 200.
```

### System Status

```
✅ All containers running (Up About a minute)
✅ API health: healthy
✅ Uptime: 83s
✅ 4 tournaments accessible
✅ Migration 021 applied successfully
```

## Impact

- **Before:** Deployments failed at migration stage
- **After:** Full deploy completes successfully with all migrations applied

## Related Files

- [Dockerfile](../Dockerfile) — Docker image build configuration
- [alembic.ini](../alembic.ini) — Alembic configuration
- [alembic/versions/021_add_is_test_tournament.py](../alembic/versions/021_add_is_test_tournament.py) — Latest migration
- [scripts/full_deploy.sh](../scripts/full_deploy.sh) — Full deployment script

## Testing

To verify the fix works:

```bash
cd /home/ansible/rankings-bot
./scripts/full_deploy.sh --force-docker
```

Expected result: Exit code 0, all containers running, migrations applied.

---
**Status:** ✅ RESOLVED  
**Deployment Mode:** Docker Production (per PRODUCTION_DEPLOYMENT.md)  
**Date:** February 20, 2026
