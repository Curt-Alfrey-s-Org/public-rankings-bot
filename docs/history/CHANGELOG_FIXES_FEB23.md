# Rankings Bot Fixes — February 23, 2026

## Summary
Fixed critical deployment issues preventing production website from running, and fully implemented Stage 2 bracket generation feature.

---

## Critical Production Fixes

### 1. Docker Network Configuration (YAML and Deploy Script)
**Problem:** docker-compose was creating `rankings-bot-network` in addition to external `tunnel_network`, causing DNS resolution failures and "Bad Gateway" errors.

**Changes:**
- **docker-compose.yml**: Removed duplicate `external: true` key in networks section (line 127)
- **docker-compose.yml**: Added `rankings-bot-frontend` service on `tunnel_network` only (lines 100-122)
- **production/docker-compose.prod.yml**: Removed `rankings-bot-network` from service networks; all services now exclusive to `tunnel_network`
- **production/docker-compose.host-api.yml**: Removed `rankings-bot-network` definition and service associations; all services to `tunnel_network` only
- **scripts/full_deploy.sh**: Removed legacy `rankings-bot-network` creation (line 456)

**Impact:** Cloudflare tunnel can now reach probilliards-nginx via DNS on shared tunnel_network. Website restored to production.

### 2. Frontend Nginx Proxy Configuration
**Problem:** Nginx reverse proxy couldn't connect to API due to network issues, then couldn't find API container.

**Changes:**
- **frontend/nginx.conf**: Changed upstream from `host.docker.internal:8003` to `rankings-bot-api:8003` (service name resolution on tunnel_network)

**Impact:** Frontend can now reach API container via Docker DNS on tunnel_network.

### 3. Cloudflare Tunnel Recovery
**Problem:** probilliards-nginx container was not running; tunnel had no destination to reach.

**Actions Taken:**
- Started `/rankings-bot/nginx-config/docker-compose.nginx.yml` to bring nginx online
- Restarted cf-probilliards tunnel container to reconnect configuration
- Verified tunnel connected and nginx reachable

**Result:** https://probilliardssoftware.com now serving with HTTP 200 OK.

---

## Stage 2 Bracket Generation Feature

### 1. Database Schema
**Files Modified:**
- **database/schema_tournament_postgres.sql**: Added stage2 columns to tournaments table
  - `stage2_cutoff` (INTEGER) — number of players advancing to Stage 2
  - `stage2_elimination_type` (VARCHAR) — winners/losers/grand_final
  - `stage2_seed_strategy` (VARCHAR) — placement/seed/manual
  - `stage2_started_at` (TIMESTAMP) — when Stage 2 bracket generation occurred

- **database/schema_tournament_add_only.sql** (NEW): Postgres-only script to add stage2 columns to existing tournaments table (no drop/recreate)

- **database/schema_tournament_management.sql**: SQLite-based schema removed (Postgres-only enforcement)

### 2. Backend Implementation
**api/tournament_manager.py:**
- Added stage2 column handling in `create_tournament()` (lines 361-373)
- Added stage2 column updates in `update_tournament()` (lines 479-502)
- Enhanced `generate_bracket()` method signature to support BYE player overrides (lines 618-625):
  - `bye_player_ids`: List of specific players to skip to avoid byes
  - `bye_seed_positions`: List of seed positions to place bye in specific slots
- Implemented automatic top-N player selection for Stage 2 cutoff
- Round-robin seeding strategy support for Stage 2 placement

**api/models/tournament_models.py:**
- Added stage2_cutoff, stage2_elimination_type, stage2_seed_strategy, stage2_started_at to Tournament model
- Created Stage2StartRequest model with all configuration fields
- Backward compatible with existing tournaments (fields optional)

**api/routes/tournaments.py:**
- Added `POST /{tournament_id}/start-stage2` endpoint (line 387)
- Validates cutoff size, seeding strategy, advancing player overrides
- Returns created matches count, final bracket size, timestamp

### 3. Frontend Implementation
**frontend/src/pages/Bracket.tsx:**
- Added Stage 2 configuration section with 6 input controls:
  - Stage 2 Cutoff (integer, default 16)
  - Seed Strategy (dropdown: placement/seed/manual)
  - Race To (integer)
  - Advancing Players Override (comma/space-separated list)
  - BYE Player IDs (comma/space-separated list)
  - BYE Seed Positions (comma/space-separated list)
- Implemented `startStage2Mutation` to call API and refresh bracket display
- Shows success toast and updates query cache

**frontend/src/api/tournaments.ts:**
- Added Stage2StartRequest interface matching backend
- Implemented `startStage2(tournamentId, data)` API client method
- Proper error handling and TypeScript types

**frontend/src/components/BracketGrid.tsx:**
- Added stage2 bracket type rendering with 🎯 icon indicator
- Displays stage2 matches between losers and grand_final rounds
- Full match results and player advancement tracking

### 4. Documentation
**New Files:**
- **DATABASE_RULES.md**: Postgres-only enforcement rules; bans SQLite imports, .db files, sqlite:// URIs
- **STAGE2_POSTGRES_COMPLETE.md**: Complete architecture and API reference for Stage 2
- **DEPLOYMENT_READY_STAGE2.md**: Integration testing checklist
- **DEPLOYMENT_COMPLETE.md**: Full deployment status verification

---

## Testing & Validation

### Local Testing (Development)
✅ Frontend loads at http://localhost:3000  
✅ API responds at http://localhost:8003/api/health  
✅ Stage 2 UI controls functional on Bracket page  
✅ All containers running on tunnel_network only  

### Production Testing
✅ https://probilliardssoftware.com returns HTTP 200  
✅ Frontend assets served via nginx reverse proxy  
✅ Cloudflare tunnel connected and stable  
✅ No "Bad Gateway" 502 errors  

---

## Files Changed Summary

| Category | Files |
|----------|-------|
| Docker/Compose | docker-compose.yml, production/docker-compose.prod.yml, production/docker-compose.host-api.yml, scripts/full_deploy.sh |
| Database | database/schema_tournament_postgres.sql, database/schema_tournament_add_only.sql, database/schema_tournament_management.sql |
| Backend | api/tournament_manager.py, api/routes/tournaments.py, api/models/tournament_models.py |
| Frontend | frontend/src/pages/Bracket.tsx, frontend/src/api/tournaments.ts, frontend/src/components/BracketGrid.tsx, frontend/nginx.conf |
| Documentation | DATABASE_RULES.md, STAGE2_POSTGRES_COMPLETE.md, DEPLOYMENT_READY_STAGE2.md, DEPLOYMENT_COMPLETE.md |

---

## Deployment Steps Executed

1. Applied Postgres schema migrations (4 tables, 40+ columns)
2. Rebuilt API and Celery worker Docker images (--no-cache)
3. Started full docker-compose stack with corrected network configuration
4. Verified all containers on tunnel_network only
5. Started probilliards-nginx and cloudflared tunnel
6. Validated production website at https://probilliardssoftware.com

---

## Backward Compatibility

✅ All stage2 fields optional in existing tournament records  
✅ Existing bracket generation unaffected (single/double elimination still works)  
✅ Postgres migration adds columns without removing existing data  
✅ SQLite completely removed; Postgres-only enforced  

---

## Known Issues Fixed

- ❌ Bad Gateway 502 errors → ✅ FIXED (network isolation)
- ❌ probilliards-nginx not running → ✅ FIXED (containers started)
- ❌ Cloudflared tunnel unreachable → ✅ FIXED (tunnel restarted and verified)
- ❌ Stage 2 feature incomplete → ✅ FIXED (full implementation + UI)

---

**Commit Date:** February 23, 2026 at 07:45 UTC  
**Status:** ✅ PRODUCTION READY
