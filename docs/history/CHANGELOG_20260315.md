# Changelog — March 15, 2026

**Branch:** main  
**Scope:** Rankings Bot — production hardening, script consolidation, docs, Hot Streak, infrastructure

---

## Summary

- Consolidated start/stop scripts; removed deprecated scripts
- PROJECT_ROOT standardization across routes
- Production verification and smoke check improvements
- Hot Streak page, maintenance/demo workflow, Cloudflare docs
- Database migrations (license, local ranking system, materialized views)
- Nginx config split (maintenance vs production)
- Various docs and bug fixes

---

## Scripts

### Consolidated
- **start.sh** — Single entry point for full stack (frontend build, Docker, postgres, API, nginx)
- **start_web.sh**, **start_mobile.sh** — Web and mobile dev servers
- **stop.sh** — Unified stop (nginx, API, postgres, Redis, celery)
- **stop_web.sh**, **stop_mobile.sh** — Web/mobile dev stop
- **switch-site.sh** — Toggle maintenance vs production nginx config

### Removed (archived or superseded)
- `start-rankings-bot.sh`, `start_app.sh`, `start_deps.sh`, `start_gui.sh`, `start_rankings_bot_all.sh`, `start_website_server.sh`
- `stop_api.sh`, `stop_app.sh`, `stop_deps.sh`, `stop_dev.sh`
- `docker-compose.dev.yml`, `docker-compose.staging.yml`
- `production/docker-compose.host-api.yml`
- `nginx-config/rankings-bot-cloudflare-docker-HOST-API.conf`

### Updated
- `verify_production.sh` — Simplified checks; direct API + optional public URL
- `restart_api.sh`, `restore_from_backup.sh`, `full_deploy.sh` — PROJECT_ROOT / path fixes
- Scripts using `get_database_manager` or `PROJECT_ROOT` — standardized imports

---

## API & Backend

- **PROJECT_ROOT** — Replaced local definitions with `from project_root import PROJECT_ROOT` in:
  - `api/routes/splash_config.py`, `login_features.py`, `tournament_history.py`, `admin.py`
- **auth.py**, **main.py** — Auth and lifespan refinements
- **tournaments.py**, **player_performance.py**, **rankings.py** — Route and model updates
- **postgres_manager.py** — Schema and query updates for license, local ranking system

---

## Database

- **Migrations**
  - `040_add_license_to_v_current_rankings.py` — License in current rankings view
  - `041_add_local_ranking_system.py` — Local ranking system support
  - `042_add_mv_tournament_history_recent.py` — Materialized view for recent tournament history
- **SQL**
  - `add_license_to_v_current_rankings.sql` — Manual migration option
  - `schema_tournament_management.sql`, `schema_tournament_postgres.sql` — Schema updates

---

## Frontend

- **HotStreak.tsx** — New Hot Streak page (placement chart, association tabs, Fargo chart)
- **App.tsx**, **Sidebar.tsx** — Navigation and routing updates
- **Leaderboard.tsx**, **TournamentHistory.tsx**, **PlayerPerformance.tsx** — UI and data flow
- **PerformanceCharts.tsx**, **RankingsTrendChart.tsx**, **WinRateDistribution.tsx** — Chart components
- **useLiveUpdates.ts**, **useWebSocket.ts** — Live update hooks
- **API clients** — `client.ts`, `rankings.ts`, `tournaments.ts`, `users.ts`, etc.

---

## Nginx & Deployment

- **nginx-config/**
  - `rankings-bot-maintenance.conf` — Maintenance page
  - `rankings-bot-production.conf` — Production app
  - `maintenance/` — Maintenance page assets
  - `server-block-main-site-app.conf.sample` — Sample server block
- **docker-compose.yml**, **docker-compose.performance.yml**, **production/docker-compose.prod.yml** — Service and port updates

---

## Documentation

### New
- `docs/CLOUDFLARE_PRODUCTION_CHECKLIST.md` — Cloudflare tunnel and production checklist
- `docs/DOCKER_POSTGRES_ONLY.md` — Postgres-only Docker setup
- `docs/FIX_PRODUCTION_LOGIN_404_405.md` — 404/405 login fix
- `docs/HOT_STREAK_CHANGES.md` — Hot Streak feature notes
- `docs/MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md` — Maintenance vs demo workflow
- `docs/RECHARTS_CONSOLE_WARNING_FIX.md` — Recharts width/height warning fix
- `docs/SPLASH_CONFIG.md` — Splash configuration
- `docs/SSOT_DIRECTOR_TOURNAMENTS.md` — Director tournaments single source of truth
- `docs/UNSAVED_FILES_ANALYSIS.md` — Un saved files analysis

### Updated
- `docs/ROADMAP.md`, `docs/PRODUCTION_STATUS_AND_NEXT_STEPS.md`, `docs/INDEX.md`
- `docs/DEPLOYMENT_SCRIPTS.md`, `docs/START_STOP_RESTART.md`, `docs/WHAT_CONTROLS_THE_WEBSITE.md`
- `CHECKLIST.md`, `START_HERE.md`, `REVIEW_AND_DEPLOY.md`, `QUICK_START_REFERENCE.md`
- Various deployment, auth, and database docs

---

## Other

- **.gitignore** — Ignore patterns updated
- **.docker-build-hash** — Build hash refresh
- **alembic.ini**, **alembic/env.py** — Alembic config
- **config/splash_config.json** — Splash config
- **mobile/README.md** — Mobile app notes
- **scripts/archive/** — Archived legacy scripts
- **Tests** — `test_auth_login.py`, `test_tournament_api.py`, `test_tournaments_more.py` updates

---

## Next Steps (from ROADMAP)

- Phase 0: Data integrity (Poison Saigon, WPA Women points, per-tournament buttons)
- Phase 6: Tech debt (splash_v1/auth_v1 deprecation)
- Hot Streak: Placement sparkline chart
- Live Est. Rating + Live Odds pipeline
- Mobile: EAS init, Android build, expansion phases
