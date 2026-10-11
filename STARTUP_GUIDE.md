# Rankings-Bot Production Startup Guide

## ⚡ Production Deployment

Everything (Postgres, Redis, API, Celery, Nginx, Tunnel) starts automatically:

```bash
./scripts/full_deploy.sh --no-cache
```

This is the standard command. It:
- ✅ Rebuilds frontend
- ✅ Rebuilds Docker images (no cache)
- ✅ Starts PostgreSQL, Redis, API, Celery worker
- ✅ Configures Nginx reverse proxy
- ✅ Sets up Cloudflare tunnel
- ✅ Validates everything is healthy

**No manual steps. Redis is auto-started.** One command handles the entire production deployment.

## Service Dependencies

Services start in the correct order (managed by docker compose):

```
PostgreSQL → Redis → API, Celery Worker → Nginx → Tunnel
```

All health checks pass before deployment completes.

## Verify Everything is Running

```bash
# After full_deploy.sh completes, check status
./deploy.sh status

# View full logs
./deploy.sh logs

# Check health (API, tunnel, etc.)
./deploy.sh health
```

## Video Upload (AI Coach)

Once deployed:
- 🎬 Upload video
- 🚀 Celery + Redis queue the analysis
- ✅ Results returned via polling

**No manual setup needed.** Redis and Celery are configured automatically in docker-compose.yml.

## Stopping Everything

```bash
./deploy.sh stop
```

## Restart or Redeploy

```bash
# Restart all services (keep images)
./deploy.sh restart

# Full redeploy (rebuild + restart everything)
./scripts/full_deploy.sh --no-cache

# Redeploy with cached layers (faster)
./scripts/full_deploy.sh
```

## Environment Configuration

Copy `.env.example` to `.env` and set required values:

```bash
cp .env.example .env
```

Required:
- `JWT_SECRET` - Authentication secret
- `XAI_API_KEY` - Grok API key (for video analysis)
- `BOT_API_KEY` - API access token

Optional (defaults provided):
- `CELERY_BROKER_URL` - Defaults to `redis://redis:6379/0`
- `REDIS_URL` - Defaults to `redis://redis:6379/0`
- `DATABASE_URL` - Defaults to `postgresql://rankings:change-me@postgres:5432/rankings`

Celery/Redis are auto-configured in docker-compose.yml; you don't need to set them manually.

## Data Persistence

- **PostgreSQL** → `postgres_data/` volume (survives restarts)
- **Redis** → `redis_data/` volume (survives restarts)
- **Logs** → `./logs/` directory
- **Video frames** → `./pools_coaching_frames/` directory

## Production Notes

⚠️ **Critical — DO NOT MODIFY:**
- Network: `tunnel_network` (hardcoded in Cloudflare tunnel config)
- Port 8003: Coordinated with nginx + tunnel routing
- See [PORT_ASSIGNMENTS.md](.github/PORT_ASSIGNMENTS.md) for details

## Useful Commands

```bash
# View service status
./deploy.sh status

# View all logs
./deploy.sh logs

# View specific service logs
./deploy.sh logs api
./deploy.sh logs celery

# Check health (API, tunnel, etc.)
./deploy.sh health

# Stop all services
./deploy.sh stop

# Restart services (keep images)
./deploy.sh restart

# Full redeploy (rebuild everything)
./scripts/full_deploy.sh --no-cache
```

---

**Standard production workflow:**
```bash
./scripts/full_deploy.sh --no-cache
```

After deployment, use `./deploy.sh` for management (status, logs, health, restart, stop).
