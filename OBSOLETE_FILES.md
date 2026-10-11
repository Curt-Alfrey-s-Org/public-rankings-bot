# Obsolete Files (Pre-Feb 20 SQLite/Systemd)

**Date:** Feb 23, 2026  
**Context:** Codebase fully migrated to PostgreSQL-only and Docker-only deployment. SQLite migration completed and all obsolete files removed.

## Files to DELETE (SQLite/Old Architecture)

### Scrapers (SQLite-based, not PostgreSQL-compatible)
- `scrapers/future_tournament_scraper.py` - Uses `sqlite3.connect()`, `rankings.db`
- `scrapers/tournament_history_scraper.py` - Uses `sqlite3.connect()`, `rankings.db`
- `rankings_gui.py` - Desktop GUI using SQLite `DatabaseManager('rankings.db')`
- `src/main.py` - Old CLI entry point with SQLite `--db rankings.db`

### Test Files (SQLite fixtures)
- `conftest.py` - Creates SQLite test DB `test_rankings.db`
- `tests/backend/test_integration.py` - Uses `sqlite3.connect('rankings.db')`
- `tests/backend/test_scrapers_manual.py` - Uses `DatabaseManager("test_rankings.db")`
- `test_scrapers_manual.py` (root) - Duplicate of above
- `test_scrapers.py` - Old scraper tests
- `test_icon.py` - Desktop GUI test
- `gui_reference.py` - Desktop GUI helper
- `verify_selftest_system.py` - Old verification script

### Scripts (Systemd/Old Deployment)
- `scripts/restart_api.sh` - Uses `systemctl restart rankings-bot-api` (❌ systemd not used)
- `scripts/install_desktop_all_users.sh` - Desktop launcher (not web deployment)
- `scripts/install_desktop_launcher.sh` - Desktop launcher (not web deployment)
- `scripts/copy_web_gui_only.py` - Old deployment pattern
- `frontend/setup_frontend.sh` - Old frontend setup (replaced by full_deploy.sh)

### Old Documentation (Pre-Feb 20)
- `REVIEW_AND_DEPLOY.md` - References systemd nginx reload
- `REVIEW_BEFORE_MASTER.md` - Old review checklist

## Files CONVERTED to PostgreSQL (Feb 20+)

### Core Database
- `database/__init__.py` ✅ PostgreSQL via SQLAlchemy
- `database/db_manager.py` ✅ PostgreSQL-only
- `database/schema_tournament_postgres.sql` ✅ PostgreSQL schema

### API (All PostgreSQL)
- `api/**/*.py` ✅ All routes/models use SQLAlchemy ORM
- Alembic migrations ✅ PostgreSQL

### Current Deployment
- `scripts/full_deploy.sh` ✅ Docker-only (no systemd)
- `docker-compose.yml` ✅ PostgreSQL container
- `production/docker-compose.prod.yml` ✅ Production stack

## Action Plan

1. **DELETE** all files in "Files to DELETE" section above
2. **Keep** files in "Files CONVERTED" section  
3. **Port assignments:** Keep 8003 for Rankings Bot API (working)
4. **Network:** All containers on `tunnel_network` (required)

## Commands to Clean Up

```bash
# Remove obsolete scrapers
rm scrapers/future_tournament_scraper.py
rm scrapers/tournament_history_scraper.py
rm rankings_gui.py
rm src/main.py

# Remove obsolete tests
rm conftest.py
rm test_scrapers_manual.py
rm test_scrapers.py
rm test_icon.py
rm gui_reference.py
rm verify_selftest_system.py
rm tests/backend/test_integration.py
rm tests/backend/test_scrapers_manual.py

# Remove obsolete scripts
rm scripts/restart_api.sh
rm scripts/install_desktop_all_users.sh
rm scripts/install_desktop_launcher.sh
rm scripts/copy_web_gui_only.sh
rm frontend/setup_frontend.sh

# Remove old docs
rm REVIEW_AND_DEPLOY.md
rm REVIEW_BEFORE_MASTER.md

# Remove empty src/ directory if it only had main.py
rmdir src 2>/dev/null || true
```

## Current Production Stack (Feb 20+)

- **Database:** PostgreSQL 15 (container: `rankings-bot-postgres`)
- **API:** FastAPI in Docker (container: `rankings-bot-api`, port: **8003**)
- **Frontend:** React + Vite (served by API container)
- **Deployment:** `./scripts/full_deploy.sh --force-docker`
- **No systemd, no SQLite, no desktop GUI**
