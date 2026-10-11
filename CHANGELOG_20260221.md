# Changelog - February 21, 2026

## Session Summary
Complete system overhaul: Docker-only deployment, tournament management, API fixes, UI improvements.

## Infrastructure Changes

### Docker-Only Migration
- **Removed systemd service** (`rankings-bot-api.service`)
- **Updated stop.sh** to check active services, not just file existence
- **Fixed network labels** in docker-compose to prevent `rankings-bot-network` conflicts
- **Updated full_deploy.sh** to use `--force-docker` flag
- All deployment now goes through Docker containers on `tunnel_network`

### Database
- **Added migration 021**: `is_test_tournament` column
- **Added migration 006**: `tables_available` column for tournaments
- **Populated players table** from rankings data (756 players)
- **Populated player_statistics** from tournament results (516 with stats)

## API Changes

### New Endpoints
- **DELETE /api/tournaments/{tournament_id}** - Delete tournaments (director/admin only)
- **GET /api/tournaments/current** - Get currently active tournament

### Fixed Endpoints
- **GET /api/tournaments/players** - Fixed nationality validation (truncate to 3 chars)
- **GET /api/tournaments/{id}/matches** - Added `GRAND_FINAL` to BracketType enum
- **POST /api/admin/system/rebuild-frontend** - Disabled in Docker-only mode
- **GET /api/live/updates** - Fixed SSE implementation (StreamingResponse)

### Route Registration
- Registered `live_updates` router in main.py
- Fixed 404 errors on `/api/live/updates`

### System Health
- **Fixed module lights** to check local files instead of self-HTTP
- All status checks now return proper responses

## Frontend Changes

### New Features
- **Current Tournament page** (`/current-tournament`)
  - Shows active tournament with bracket, players, live scores
  - Empty state when no active tournament
  - Added sidebar tab for all users
- **Tournament wizard** navigation auto-redirects to Brackets tab after creation
- **Brackets tab** now has Edit/Delete buttons (hover to show)
- **Tables field** added to tournament creation Step 1

### Removed Features
- **Rebuild Frontend button** removed from Settings/Admin (Docker-only mode)
- **Rebuild Frontend button** removed from System page

### Bug Fixes
- Fixed image cache-busting for `alfa-head.png` (added `?v=` parameter)
- Fixed SSE connection error display

## Files Modified

### Backend
- `api/main.py` - Registered live_updates router
- `api/routes/admin.py` - Disabled rebuild-frontend in Docker mode
- `api/routes/tournaments.py` - Added DELETE endpoint, fixed nationality validation
- `api/routes/live_updates.py` - Fixed SSE with StreamingResponse
- `api/routes/system.py` - Fixed module lights checks
- `api/models/tournament_models.py` - Added GRAND_FINAL to BracketType enum
- `api/routes/tournament_wizard.py` - Added tables_available persistence

### Frontend
- `frontend/src/pages/CurrentTournament.tsx` - New page (created)
- `frontend/src/pages/TournamentWizard.tsx` - Added tables field, fixed navigation
- `frontend/src/pages/Bracket.tsx` - Added edit/delete buttons
- `frontend/src/pages/SettingsAdmin.tsx` - Removed rebuild button
- `frontend/src/pages/System.tsx` - Removed rebuild button
- `frontend/src/pages/Home.tsx` - Cache-busted alfa-head.png
- `frontend/src/pages/SplashLogin.tsx` - Cache-busted alfa-head.png
- `frontend/src/pages/CustomizationDashboard.tsx` - Cache-busted alfa-head.png
- `frontend/src/components/Sidebar.tsx` - Added Current Tournament tab
- `frontend/src/App.tsx` - Added /current-tournament route
- `frontend/src/api/tournaments.ts` - Added getCurrentTournament call

### Scripts
- `scripts/stop.sh` - Fixed to detect active services, remove all containers
- `scripts/full_deploy.sh` - Uses --force-docker, fixed network creation
- `scripts/backup_database.sh` - Created comprehensive backup script
- `scripts/populate_players_from_rankings.py` - Created DB-only population script

### Database
- `database/migrations/021_add_is_test_tournament.py` - New migration
- `database/migrations/006_add_tables_available.sql` - New migration
- `database/schema_tournament_postgres.sql` - Updated with tables_available

### Docker
- `Dockerfile` - Added alembic/ and alembic.ini to fix migrations
- `docker-compose.yml` - Network labels fixed
- `docker/nginx/nginx.conf` - Reverted to rankings-bot-api:8003

### Documentation
- `docs/DOCKER_ONLY_MIGRATION_20260220.md` - Docker-only setup guide
- `docs/PRODUCTION_CONFIG_20260220.txt` - Production configuration
- `docs/DEPLOY_FIX_20260220.md` - Deployment fixes
- `docs/FULL_DEPLOY_BUTTON_UPDATE.md` - Button behavior changes

## Testing
- Updated `tests/backend/test_tournaments_create.py` - Added tables_available
- Updated `tests/backend/test_tournaments_routes_more.py` - Added tables_available

## Performance Improvements
- Container startup time reduced (proper health checks)
- Network latency improved (container-to-container DNS)
- Database queries optimized (proper indexing)

## Security Improvements
- API bound to 127.0.0.1 only (no external access)
- Tournament deletion requires proper permissions
- Test tournament protection for non-super-admins

## Breaking Changes
- Systemd API deployment no longer supported
- Rebuild Frontend button removed (use Full Deploy)
- Must use Docker-only mode going forward

## Next Steps
- Consider automated daily backups via cron
- Monitor SSE connections for memory leaks
- Add tournament search/filter in Brackets tab
- Implement real-time match updates via SSE
