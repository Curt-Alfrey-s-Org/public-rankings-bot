# Development Workflow & Environment Management

## Environment Overview

Everything runs in Docker. Use the main compose file for development and production:

| Environment | Database | Purpose |
|-------------|----------|---------|
| Development / Production | `rankingsbot` | Single Docker stack (Postgres, Redis, API, Celery) |

## Quick Start Development

### 1. Start Development Environment
```bash
# Start full stack (Postgres, Redis, API, Celery, frontend)
docker compose up -d

# Or production compose
docker compose -f production/docker-compose.prod.yml up -d
```

### 2. Work on Feature Branches
```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes, test, commit
git add .
git commit -m "feat: Add your feature"

# Push and create PR
git push origin feature/your-feature-name
```

### 3. Deploy
```bash
# Full deploy (production)
./scripts/full_deploy.sh --force-docker

# Or manually
docker compose -f production/docker-compose.prod.yml up -d
```

## Branching Strategy

### Main Branches
- **`main`** - Production-ready code, protected branch
- **`develop`** - Integration branch for features (optional)

### Feature Branches
- **`feature/**` - New features (e.g., `feature/future-tournaments-recovery`)
- **`bugfix/**` - Bug fixes
- **`hotfix/**` - Critical production fixes

### Workflow
1. Create feature branch from `main`
2. Develop and test on feature branch
3. Create Pull Request for code review
4. Merge to `main` after approval
5. Deploy from `main`

## Database Management

### Backups (Automatic)
- **Production**: Every 2 hours via cron
- **Development**: Manual backups before risky operations
- **Location**: `backups/rankings_*.dump`

### Database Access (Docker-network-only)
```bash
docker exec -it rankings-bot-postgres psql -U rankingsbot_user -d rankingsbot
```

## Safety Guidelines

### ✅ Always
- Work on feature branches, never directly on `main`
- Backup database before destructive operations
- Test changes in development environment first
- Use environment-specific configurations

### ❌ Never
- Modify production database directly
- Push untested code to `main`
- Skip backups before migrations
- Share environment files with sensitive data

## Current Branch: feature/future-tournaments-recovery

This branch is for extracting future tournament data from backup files to restore missing tournament information.
