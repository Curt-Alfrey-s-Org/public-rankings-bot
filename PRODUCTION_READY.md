# Rankings-Bot — Production Ready Deployment

## 🚀 Production Deployment

```bash
# Full rebuild + deploy (recommended for production)
./scripts/full_deploy.sh --no-cache
```

This handles everything automatically:
- ✅ Frontend build
- ✅ Docker image rebuild (no cache)
- ✅ Network setup (tunnel_network, rankings-bot-network)
- ✅ PostgreSQL, Redis, API, Celery worker startup
- ✅ Nginx reverse proxy
- ✅ Cloudflare tunnel
- ✅ Health validation

**Redis is auto-started.** No manual setup needed.

---

## 📋 Deployment Checklist

### Pre-Deployment

- [ ] `.env` configured with required secrets:
  ```bash
  cp .env.example .env
  # Edit .env with:
  # - JWT_SECRET (strong random string)
  # - XAI_API_KEY (Grok API key)
  # - BOT_API_KEY (service token)
  # - DATABASE_URL (if not using default Postgres)
  ```

- [ ] Docker and Docker Compose installed
- [ ] System has 6GB+ free memory
- [ ] Ports available: 8003 (API), 6379 (Redis), 443/80 (tunnel/nginx)

### Deployment

```bash
# Full production rebuild + deploy
./scripts/full_deploy.sh --no-cache

# View logs during deployment
tail -f logs/full_deploy.log
```

This rebuilds frontend, Docker images, starts all services (including Redis), nginx, and tunnel.

### Post-Deployment

- [ ] Check deployment succeeded: `docker compose ps`
- [ ] View full logs: `./deploy.sh logs`
- [ ] Test API: `./deploy.sh health`
- [ ] Test video upload: Upload to AI Coach and verify Celery processes it
- [ ] Check tunnel: Verify app is accessible via Cloudflare domain

---

## 🏗️ Architecture

`./scripts/full_deploy.sh --no-cache` orchestrates the complete stack:

### Services (Started by full_deploy.sh)

| Service | Port | Purpose | Auto-Started |
|---------|------|---------|:---:|
| **PostgreSQL** | 5432 | Main database | ✅ |
| **Redis** | 6379 | Cache + Celery broker | ✅ |
| **Rankings API** | 8003 | FastAPI backend | ✅ |
| **Celery Worker** | — | Video analysis (Grok) | ✅ |
| **Nginx** | 80/443 | Reverse proxy | ✅ |
| **Cloudflare Tunnel** | — | Remote access | ✅ |

### Networks

- **Internal**: `rankings-bot-network` (Postgres, Redis, API, Celery)
- **External**: `tunnel_network` (API exposed to Cloudflare)

### Data Persistence

| Item | Location | Survives Restart |
|------|----------|:---:|
| Database | `postgres_data/` volume | ✅ |
| Redis cache | `redis_data/` volume | ✅ |
| Video frames | `./pools_coaching_frames/` | ✅ |
| Logs | `./logs/` | ✅ |

---

## 🎮 Common Commands

### Full Production Deploy

```bash
# Complete rebuild (frontend + Docker images + all services)
./scripts/full_deploy.sh --no-cache

# Standard deploy (uses cached layers where possible)
./scripts/full_deploy.sh
```

### Service Management (After Deployment)

```bash
# View service status
./deploy.sh status

# View logs
./deploy.sh logs

# Restart all services
./deploy.sh restart

# Stop all services
./deploy.sh stop

# Health check
./deploy.sh health
```

### Specific Service Logs

```bash
# API logs
./deploy.sh logs api

# Celery worker (video analysis)
./deploy.sh logs celery
```

---

## 🔧 Video Upload (AI Coach) Flow

```
User uploads video
    ↓
API stores frames + creates analysis record
    ↓
Celery worker pulls from Redis queue
    ↓
Grok API analyzes pool game
    ↓
Results stored in database
    ↓
User polls /poll endpoint → gets results
```

**Note:** If Redis is unavailable, analysis runs synchronously (blocking request).

---

## 📊 Monitoring & Health

## 📊 Monitoring & Health

### During Deployment

```bash
# Watch full deployment
./scripts/full_deploy.sh --no-cache | tee deployment.log

# Check specific build step
docker compose logs -f rankings-bot-api
```

### After Deployment

```bash
# Complete health check (API, nginx, tunnel)
./deploy.sh health

# View all service logs
./deploy.sh logs

# Check specific service status
docker compose ps

# Expected output (all running):
# rankings-bot-postgres      Up (healthy)
# rankings-bot-redis         Up (healthy)
# rankings-bot-api           Up (healthy)
# rankings-bot-celery-worker Up
# probilliards-nginx         Up
```

### Key Logs to Monitor

```bash
./deploy.sh logs api      # API startup/errors
./deploy.sh logs celery   # Video analysis processing
./deploy.sh logs          # All services
```

---

## 🔐 Security Notes

⚠️ **CRITICAL - DO NOT MODIFY:**
- Network name: `tunnel_network` (hardcoded in Cloudflare tunnel config)
- Port 8003: Coordinated with nginx + tunnel routing
- Port bindings: `127.0.0.1:PORT` (localhost only, nginx is gateway)

See `.github/PORT_ASSIGNMENTS.md` for complete reference.

---

## 📈 Performance Tuning

### Database (PostgreSQL)

Configured with production parameters:
- `shared_buffers: 2GB`
- `effective_cache_size: 8GB`
- `work_mem: 64MB`
- `max_connections: 100`

### Redis

Configured with:
- `maxmemory: 512MB` (auto-eviction of old cache)
- `maxmemory-policy: allkeys-lru` (least-recently-used)
- AOF (append-only file) enabled for persistence

### API

- 4 worker processes (uvicorn)
- Resource limits: 4GB max memory, 2 CPU cores
- Connection pools optimized

---

## 🐛 Troubleshooting

### Deployment Fails

```bash
# Check logs for error
./scripts/full_deploy.sh --no-cache 2>&1 | tail -50

# Check Docker is running
docker ps

# Check disk space
df -h

# Check ports are available
lsof -i :8003
lsof -i :6379
lsof -i :80
```

### Services Not Health

```bash
# Check all containers
./deploy.sh status

# View detailed logs
./deploy.sh logs

# Restart services
./deploy.sh restart
```

### Video Upload Fails

```bash
# Verify Redis + Celery are running
./deploy.sh status | grep -E "redis|celery"

# Check Celery logs for errors
./deploy.sh logs celery

# Check overall health
./deploy.sh health
```

### Memory/Performance Issues

```bash
# Check Docker resource usage
docker stats

# View API memory usage
docker compose top rankings-bot-api

# Check system memory
free -h
```

### Complete Reset (Last Resort)

```bash
# Stop everything
./deploy.sh stop

# Remove all containers and volumes
docker compose down -v

# Full redeploy
./scripts/full_deploy.sh --no-cache
```

---

## 📖 Additional Resources

- [full_deploy.sh](./scripts/full_deploy.sh) — Complete production deployment (see top of file for detailed docs)
- [deploy.sh](./deploy.sh) — Service management (start/stop/logs/health)
- [STARTUP_GUIDE.md](./STARTUP_GUIDE.md) — Quick reference
- [.env.example](./.env.example) — Environment variables
- [docker-compose.yml](./docker-compose.yml) — Development compose
- [production/docker-compose.prod.yml](./production/docker-compose.prod.yml) — Production compose
- [ARCHITECTURE.md](../ARCHITECTURE.md) — System design

---

**Standard Production Flow:**
```bash
./scripts/full_deploy.sh --no-cache
```

Everything starts automatically: PostgreSQL, Redis, API, Celery, Nginx, Tunnel.

**Need to check status later?**
```bash
./deploy.sh status
./deploy.sh health
./deploy.sh logs
```
