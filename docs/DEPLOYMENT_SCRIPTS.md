# Deployment Scripts (Docker-Only) Guide

This guide explains the deployment scripts and their typical usage patterns.

## Script Overview

| Script | Purpose | Deps Status | App Status |
|--------|---------|-------------|-----------|
| `full_deploy.sh` | Complete redeploy (build + start all) | Start | Start |
| `start.sh` | Intelligent start (full, --deps-only, --app-only, --dev) | — | — |
| `stop.sh` | Intelligent stop (full, --deps-only, --app-only, --dev) | — | — |
| `start.sh --deps-only` | Start only Postgres + Redis | Start | Leave as is |
| `stop.sh --deps-only` | Stop only Postgres + Redis | Stop | Leave as is |
| `start.sh --app-only` | Start only API + Celery + Frontend | Must be healthy | Start |
| `stop.sh --app-only` | Stop only API + Celery + Frontend | Leave as is | Stop |

## Common Scenarios

### 1. First-Time Deployment (Change everything)
```bash
./scripts/full_deploy.sh
```
- Rebuilds all Docker images (frontend, API, celery)
- Starts all containers (postgres, redis, api, celery, frontend, nginx)
- Runs migrations
- Verifies health checks
- **Typical time: 5-10 minutes**

### 2. Code Change (Frontend/API only, no schema changes)
```bash
./scripts/stop.sh --app-only   # Stop just the app (databases keep running!)
./scripts/start.sh --app-only  # Rebuild + start app (quick)
```
- Postgres and Redis stay healthy and connected (other services can use them)
- Only rebuilds changed images
- Faster than full deploy: ~1-2 minutes
- **Great for rapid iteration**

### 3. Quick App Restart (No rebuilds needed)
```bash
./scripts/stop.sh --app-only
# ... do something ...
./scripts/start.sh --app-only
```
- Reuses existing images
- Fastest option if code hasn't changed

### 4. Database Maintenance (Backup/Restore)
```bash
./scripts/stop.sh --app-only   # Stop app, keep db running for manual work
# ... do backup/restore ...
./scripts/start.sh --app-only  # Restart app
```
- App is stopped but can reconnect to db
- No need to restart databases

### 5. Scheduled Maintenance (Nightly rebuild)
```bash
./scripts/full_deploy.sh
```
- Complete rebuild ensures clean state
- Run once per night during low-traffic window
- **Typical time: 5-10 minutes**

### 6. Emergency Rollback (Everything stops)
```bash
./scripts/stop.sh
# ... investigate/fix issues ...
./scripts/full_deploy.sh   # Full redeploy after fix
```
- Nuclear option: everything stops
- Use when database/cache corruption suspected
- Use when full reset needed

### 7. Dependency Restart (Rare)
```bash
./scripts/stop.sh --deps-only  # Postgres + Redis down
# ... perform maintenance (upgrades, repairs) ...
./scripts/start.sh --deps-only # Bring them back up
```
- App containers must be stopped first (to avoid errors)
- Stop app before stopping deps

## Implementation Details

### Dependencies Container Strategy
**Why separate?**
- Database and cache changes rarely (stable)
- App code changes frequently (during development)
- Keeping deps running saves restart time (~3 min saved per deploy)
- Health checks ensure deps are always responsive

### Docker Compose Behavior
Each script uses `docker compose` (V2) for:
- **Service selection**: Only restart what changed
- **Health checks**: Auto-waits for services to be healthy
- **Port management**: Ensures no port conflicts
- **Logging**: Centralized container logs

### Health Check Validation
All `start_*` scripts verify:
- Postgres: `pg_isready` returns 0
- Redis: `redis-cli ping` returns PONG
- API: HTTP GET `/health` returns 200

### Error Handling
If a service fails to start:
1. Check logs: `docker compose logs SERVICE_NAME`
2. Verify networks: `docker network ls | grep tunnel_network`
3. Verify images: `docker image ls | grep rankings-bot`
4. Full reset: `./scripts/stop.sh && ./scripts/full_deploy.sh`

## Network & Port Assumptions

All scripts assume:
- **Network**: `tunnel_network` exists (external, created by nginx)
- **Ports**: Host ports match assignments in [PORT_ASSIGNMENTS.md](../docs/PORT_ASSIGNMENTS.md)
- **Docker Compose**: V2 installed (or fallback to v1)
- **Sudo**: Docker requires `sudo` (non-root user)

## Environment Variables

All scripts respect `.env`:
- `DATABASE_URL` - Postgres connection (default: host-based)
- `JWT_SECRET` - Auth token signing key
- `TUNNEL_TOKEN` - Cloudflare tunnel auth
- `REBUILD_WEBSITE_LOG` - (internal) Log streaming for admin UI

## Typical 24-Hour Cycle

```
23:00 → ./scripts/full_deploy.sh     # Nightly rebuild (dev code)
        ✅ All fresh images
        ✅ Migration ran
        ✅ Ready for next day

During day:
  - Code change → ./scripts/stop.sh --app-only + start.sh --app-only (fast)
  - Bug fix → Same as above
  - Database issue → ./scripts/stop.sh + full_deploy.sh (full reset)

22:00 → Repeat nightly
```

## Debugging

### Logs streaming
```bash
docker compose logs -f rankings-bot-api      # API logs
docker compose logs -f celery-worker         # Celery logs
docker compose logs -f postgres              # Database logs
```

### Container status
```bash
docker compose ps                             # All containers
docker compose exec postgres pg_isready      # DB health
docker compose exec redis redis-cli ping     # Cache health
```

### Manual cleanup
```bash
docker compose down -v                       # Full reset (volume erase!)
docker system prune                          # Clean unused images
```

---

**Next**: See [DEPLOYMENT_QUICK_START.sh](../DEPLOYMENT_QUICK_START.sh) for one-line deployment.
