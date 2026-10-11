# Deployment Rules & Standards

## Single Source of Truth

### 1. API Deployment: Docker Only (Not Systemd)

**Rule: Use Docker containers for all API deployments. Systemd services are NOT used.**

Why:
- Docker provides native `restart: unless-stopped` auto-recovery
- Container-based deployments eliminate port conflicts (systemd vs Docker fighting over 8003)
- Docker networking is standard for production multi-container applications
- Systemd + Docker together cause ContainerConfig race conditions and 502 Bad Gateway errors

Implementation:
```bash
# Deploy with Docker (only method)
cd /home/ansible/rankings-bot
./scripts/full_deploy.sh               # Docker (default)
./scripts/full_deploy.sh --no-cache    # Docker with full rebuild
sudo docker-compose up -d              # Manual start
```

**NOT allowed:**
```bash
sudo systemctl restart rankings-bot-api   # ❌ Never use systemd
./scripts/full_deploy.sh --no-docker      # ❌ Host API path removed
```

### 2. Database: PostgreSQL Only (Not SQLite)

**Rule: All persistent data lives in PostgreSQL. No SQLite databases.**

Why:
- PostgreSQL supports concurrent connections and proper locking
- Suitable for multi-container architecture
- Handles complex queries needed for rankings aggregation
- SQLite has single-writer limitations in containerized environments

Implementation:
```dockerfile
# docker-compose.yml includes:
rankings-bot-postgres:
  image: postgres:15-alpine
  environment:
    POSTGRES_DB: rankingsbot
    POSTGRES_USER: rankingsbot_user
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
```

Database: `rankingsbot` (49 tables, alembic managed)

**NOT allowed:**
```python
sqlite:////path/to/rankings.db   # ❌ No SQLite
```

### 3. User Credentials: Database Only (Not .env)

**Rule: User accounts and authentication live in PostgreSQL `users` table. .env stores only system secrets.**

Why:
- Credentials in code/config files are security risks
- Database allows runtime user management (add, edit, revoke without redeploy)
- Separation of concerns: secrets vs. data
- Required for multi-environment setups (dev/staging/prod)

Database structure:
```sql
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  username VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,   -- bcrypt, never plaintext
  role VARCHAR(50) DEFAULT 'user',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  is_active BOOLEAN DEFAULT true
);
```

.env stores only:
```bash
POSTGRES_PASSWORD=<db-password>      # For Postgres container
JWT_SECRET=<signing-key>             # For token generation
TUNNEL_TOKEN=<cloudflare-token>      # For tunnel
DATABASE_URL=postgresql://...        # Connection string
```

**NOT allowed:**
```bash
# .env
ADMIN_USERNAME=admin          # ❌ App credentials in .env
ADMIN_PASSWORD=password123    # ❌ Never
API_KEY=secret-key            # ❌ Use database.users instead
```

Authentication flow:
```
POST /api/auth/login
  ↓
Lookup username in users table
  ↓
Compare password_hash using bcrypt
  ↓
Generate JWT (signed with JWT_SECRET from .env)
  ↓
Return token (valid for 7 days)
```

### 4. Verification Checklist

Before deployment, confirm:

- [ ] No `.env` file in .gitignore contains user credentials (only system secrets)
- [ ] All user accounts in PostgreSQL users table
- [ ] Docker images rebuild successfully
- [ ] All containers have `restart: unless-stopped` policy
- [ ] No systemd services managing the API (grep `-r "systemctl restart rankings-bot-api"`)
- [ ] Nginx points to Docker service DNS (`rankings-bot-api:8003`), not `localhost:8003`
- [ ] Database migrations run before API starts (`alembic upgrade head`)

### 5. Deployment Decision Tree

```
Start deploy
  ↓
Is it a Docker container deployment?
  ├─ YES → Use /scripts/full_deploy.sh (default)
  │          ✅ All containers auto-restart
  │          ✅ DNS resolution via Docker network
  │          ✅ Nginx reaches API via rankings-bot-api:8003
  │
  └─ NO → Not supported
           ❌ Systemd causes port conflicts
           ❌ Host API path removed from scripts
           ❌ Results in 502 Bad Gateway errors
```

### 6. Troubleshooting

**502 Bad Gateway?**
- Check: `sudo docker ps` — All containers running?
- Check: `curl http://127.0.0.1:8003/api/health` — API responding?
- Check: `sudo docker logs rankings-bot-nginx` — Nginx logs for upstream errors
- Fix: `cd /home/ansible/rankings-bot && sudo docker-compose up -d`

**Container won't start?**
- Issue: "ContainerConfig KeyError" during docker-compose up
- Fix: `sudo docker rm -f <container-id> && sudo docker-compose up -d`

**User login fails?**
- Check: `sudo docker exec rankings-bot-postgres psql -U rankingsbot_user -d rankingsbot -c "SELECT username, role FROM users;"`
- Verify: Password hash is bcrypt (starts with `$2a$` or `$2b$`)
- Test: `curl -X POST http://127.0.0.1:8003/api/auth/login-centralized -H "Content-Type: application/json" -d '{"username":"testuser","password":"testpass"}'`

---

**Last Updated:** Feb 24, 2026  
**Enforced By:** `scripts/full_deploy.sh` (Docker-only mode, systemd disabled)  
**Related:** [ARCHITECTURE.md](ARCHITECTURE.md), [DOCKER_NETWORKING_GUIDE.md](DOCKER_NETWORKING_GUIDE.md)
