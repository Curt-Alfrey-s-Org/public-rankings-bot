# Rankings-Bot User Guide

## Table of Contents
1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [API Endpoints](#api-endpoints)
4. [Authentication](#authentication)
5. [Admin Operations](#admin-operations)
6. [Deployment](#deployment)
7. [Troubleshooting](#troubleshooting)

---

## Overview

**Rankings-Bot** is a FastAPI-based system for managing pool (billiards) player rankings across multiple organizations:

- **WPBA** (Women's Professional Billiards Association) - Women's rankings
- **WPA** (World Pool Association) - Men's and Women's rankings

The system includes:
- PostgreSQL database with full schema and historical snapshots
- Web scrapers for automated data collection
- REST API with JWT authentication
- Role-based access control (admin, director)
- Rate limiting and caching

---

## Quick Start

### Prerequisites

- Python 3.10+
- Docker & Docker Compose (recommended for production)
- FastAPI, uvicorn, requests, beautifulsoup4

### Installation

```bash
cd /home/ansible/rankings-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements-api.txt

# Initialize database
python database/db_manager.py
```

### Start API Server

**Development:**
```bash
cd api
uvicorn main:app --reload --host 0.0.0.0 --port 8003
```

**Production (with Gunicorn):**
```bash
gunicorn -w 4 -b 0.0.0.0:8003 api.main:app
```

**Docker:**
```bash
docker build -t rankings-bot-api .
docker run -d -p 8003:8003 \
  -e JWT_SECRET="your-secret" \
  -e ADMIN_USERNAME="admin" \
  -e ADMIN_PASSWORD="password" \
  rankings-bot-api
```

---

## API Endpoints

### Public Endpoints (No Auth Required)

#### GET `/api/rankings/types`
Returns available ranking types with metadata.

**Response:**
```json
{
  "ranking_types": [
    {
      "code": "WPBA_Women",
      "display_name": "WPBA Women",
      "org_code": "wpba",
      "is_active": true,
      "org_name": "Women's Professional Billiards Association",
      "url": "https://wpbapool.com",
      "primary_color": "#E84C3D",
      "theme": "professional"
    },
    // ... more ranking types
  ],
  "count": 3
}
```

#### GET `/api/rankings/{ranking_type}`
Get rankings for a specific organization and division.

**Parameters:**
- `ranking_type` (path): `wpba-women`, `wpa-women`, `wpa-men`
- `limit` (query, default: 100): Number of records
- `offset` (query, default: 0): Pagination offset

**Example:**
```bash
curl http://localhost:8003/api/rankings/wpba-women?limit=10&offset=0
```

**Response:**
```json
{
  "total": 256,
  "limit": 10,
  "offset": 0,
  "count": 10,
  "rankings": [
    {
      "rank": 1,
      "player_name": "Player Name",
      "points": 1000,
      "country": "USA",
      "rank_change": 0,
      "last_update": "2025-02-06T10:00:00Z"
    },
    // ... more players
  ],
  "association": "WPBA",
  "division": "Women",
  "ranking_type": "WPBA_Women"
}
```

#### GET `/api/rankings/player/{name}`
Get specific player details and history.

**Example:**
```bash
curl http://localhost:8003/api/rankings/player/Player%20Name
```

#### GET `/api/rankings/history`
Get historical ranking snapshots with date filtering.

**Parameters:**
- `start_date` (query): ISO format date (e.g., `2025-01-01`)
- `end_date` (query): ISO format date (e.g., `2025-02-06`)

#### GET `/api/rankings/last-update`
Get timestamp of last ranking refresh.

**Response:**
```json
{
  "wpba_women": "2025-02-06T10:00:00Z",
  "wpa_women": "2025-02-06T10:00:00Z",
  "wpa_men": "2025-02-06T10:00:00Z",
  "database_size_mb": 2.4
}
```

---

### Admin Endpoints (Requires Authentication)

#### POST `/api/rankings/refresh`
Trigger manual refresh of all rankings from web sources.

**Requirements:**
- Role: `admin`
- Rate limit: 1 request per 5 minutes (returns 429 if exceeded)

**Query Parameters:**
- `tournament_name` (optional): Apply specific tournament point rules

**Example:**
```bash
curl -X POST http://localhost:8003/api/rankings/refresh \
  -H "Authorization: Bearer {admin_token}"
```

**Response:**
```json
{
  "timestamp": "2025-02-06T10:15:00Z",
  "wpba_women": {
    "success": true,
    "count": 256,
    "error": null
  },
  "wpa_women": {
    "success": true,
    "count": 312,
    "error": null
  },
  "wpa_men": {
    "success": true,
    "count": 448,
    "error": null
  },
  "metadata": {
    "success": true,
    "error": null
  }
}
```

#### POST `/api/rankings/import-csv`
Bulk import rankings from CSV file (admin only).

**Fields:**
- `file`: CSV file with columns: rank, player_name, points, country, ranking_type

#### GET `/api/rankings/stats/summary`
Get summary statistics across all rankings (admin only).

---

## Authentication

### JWT Authentication

Rankings-Bot uses JWT (JSON Web Tokens) with two roles:

- **Admin**: Full access (refresh, settings, import)
- **Director**: Data input (import, update)

### Getting a Token

#### Admin Login
```bash
curl -X POST http://localhost:8003/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin_password"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 604800
}
```

#### Using Token
Include in Authorization header:
```bash
curl -H "Authorization: Bearer {your_token}" \
  http://localhost:8003/api/rankings/refresh
```

### Environment Configuration

Set credentials via environment variables:

```bash
export JWT_SECRET="your-secret-key"
export ADMIN_USERNAME="admin"
export ADMIN_PASSWORD="your-password"
export DIRECTOR_USERNAME="director"
export DIRECTOR_PASSWORD="director-password"
```

---

## Admin Operations

### Manual Refresh

Admin users can manually trigger ranking updates:

```bash
# Refresh all ranking types
curl -X POST http://localhost:8003/api/rankings/refresh \
  -H "Authorization: Bearer {token}"

# Refresh with tournament rules
curl -X POST "http://localhost:8003/api/rankings/refresh?tournament_name=Spring%202025" \
  -H "Authorization: Bearer {token}"
```

### Scheduled Refresh

Set up cron job for automated daily refresh:

```bash
# In crontab (refresh daily at 2 AM)
0 2 * * * curl -X POST http://localhost:8003/api/rankings/refresh \
  -H "Authorization: Bearer $(get_admin_token)"
```

### Import from File

Load rankings from tournament final_results.txt:

```bash
cp /path/to/final_results.txt ./tournament_tools/final_results.txt

curl -X POST "http://localhost:8003/api/rankings/refresh?tournament_name=MyTournament" \
  -H "Authorization: Bearer {token}"
```

### View Statistics

```bash
curl http://localhost:8003/api/rankings/stats/summary \
  -H "Authorization: Bearer {token}"
```

---

## Deployment

### Docker Compose (Recommended)

Edit `docker-compose.yml`:

```yaml
services:
  rankings-bot-api:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8003:8003"
    volumes:
      - rankings_db:/app/database
      - ./logs:/app/logs
    environment:
      - JWT_SECRET=${JWT_SECRET}
      - ADMIN_USERNAME=${ADMIN_USERNAME}
      - ADMIN_PASSWORD=${ADMIN_PASSWORD}
      - DIRECTOR_USERNAME=${DIRECTOR_USERNAME}
      - DIRECTOR_PASSWORD=${DIRECTOR_PASSWORD}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8003/api/rankings/types"]
      interval: 30s
      timeout: 10s
      retries: 3

  rankings-bot-frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "5176:80"
    depends_on:
      - rankings-bot-api
    restart: unless-stopped

volumes:
  rankings_db:
    driver: local
```

**Deploy:** (use Docker Compose V2; see docs/UPGRADE_AND_VERSIONS.md)

```bash
docker compose up -d --build
```

### Tunnel + Nginx

For production with Nginx (probilliards-nginx):

```yaml
# See nginx-config/ and docs/CLOUDFLARE_TUNNEL_NGINX.md
http:
  services:
    rankings-api:
      loadBalancer:
        servers:
          - url: http://rankings-bot-api:8000
    rankings-frontend:
      loadBalancer:
        servers:
          - url: http://rankings-bot-frontend:80

  routers:
    rankings-api:
      rule: "Host(`www.probilliardssoftware.com`) && PathPrefix(`/api`)"
      service: rankings-api
      entrypoints: [websecure]
      tls:
        certResolver: letsencrypt

    rankings-frontend:
      rule: "Host(`rankings.probilliardssoftware.com`)"
      service: rankings-frontend
      entrypoints: [websecure]
      tls:
        certResolver: letsencrypt
```

### Docker Deployment

**Deploy with Docker Compose:**
```bash
# Full production deployment
bash ./scripts/full_deploy.sh --force-docker

# Or manually with docker-compose
docker-compose down -v  # Clean slate if needed
docker-compose build --no-cache
docker-compose up -d
```

**Services deployed:**
- PostgreSQL (Docker-network-only; no host port — use `docker exec rankings-bot-postgres psql ...` for admin)
- Redis (port 127.0.0.1:6379)
- Rankings Bot API (port 127.0.0.1:8003:8003, container port 8003)
- Celery Worker (background tasks)
- Nginx reverse proxy (on `tunnel_network`, configured in separate nginx container)

**Environment** (`.env` file):
```bash
DATABASE_URL=postgresql://rankingsbot_user:change-me@postgres:5432/rankingsbot
POSTGRES_PASSWORD=rankingsbot_secure_password
JWT_SECRET=your_jwt_secret_here
REDIS_URL=redis://redis:6379/0
```

See [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) for deployment details.

### Monitoring and Logs

**View container logs:**
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f rankings-bot-api
docker-compose logs -f postgres
```

**Check health:**
```bash
# API health check
curl http://127.0.0.1:8003/api/health

# Database connection (Postgres is Docker-network-only)
docker exec rankings-bot-postgres psql -U rankingsbot_user -d rankingsbot -c "SELECT 1;"

# Redis connectivity
docker-compose exec redis redis-cli ping
```

**Restart services:**
```bash
# Restart API
docker-compose restart rankings-bot-api

# Restart all services
docker-compose restart

# Full restart with rebuild
docker-compose down
docker-compose up -d --build
```

---

## Troubleshooting

### Database Not Found Error

**Error:** `HTTP 500: Database not found`

**Solution:**
```bash
# Check database file exists
ls -la database/rankings.db

# Initialize schema
python database/db_manager.py

# Verify tables
psql $DATABASE_URL -c "\dt"
```

### Rate Limit Exceeded

**Error:** `HTTP 429: Refresh endpoint rate limited. Please wait XXX seconds`

**Solution:**
- Admin users limited to 1 refresh per 5 minutes
- Wait for cooldown or modify rate limit in `api/rate_limiter.py`

### Authentication Failed

**Error:** `HTTP 401: Unauthorized`

**Solution:**
```bash
# Check token format
curl -H "Authorization: Bearer VALID_TOKEN" \
  http://localhost:8003/api/rankings/types

# Generate new token
curl -X POST http://localhost:8003/api/auth/login \
  -d '{"username":"admin","password":"PASSWORD"}'
```

### Scraper Errors

**Error:** Rankings not updating from sources

**Solution:**
```bash
# Test scrapers manually
python scrapers/wpba_scraper.py
python scrapers/wpa_scraper.py

# Check network connectivity
curl -I https://wpbapool.com
curl -I https://wpapool.com

# View logs
tail -f logs/rankings-api.log
```

### Container Won't Start

**Error:** Docker build/startup fails

**Solution:**
```bash
# Check logs
docker logs rankings-bot-api

# Rebuild without cache
docker compose build --no-cache rankings-bot-api

# Verify environment variables
docker exec rankings-bot-api env | grep -E "JWT|ADMIN"
```

---

## Support

For issues or questions:

1. Check logs: `tail -f logs/rankings-api.log`
2. Run tests: `pytest tests/ -v`
3. Review documentation: See `docs/` folder
4. Contact: See repository maintainers

---

**Last Updated:** February 6, 2025  
**Version:** 1.0.0
