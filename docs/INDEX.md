# Documentation Index

Quick reference for Rankings-Bot docs. Use this to find topics without scanning all files.

## AI & maintainer conventions

| Topic | Doc |
|-------|-----|
| **Large HTTP(S) downloads** (aria2 when helpful) | [HTTP_DOWNLOADS.md](HTTP_DOWNLOADS.md) → canonical **alfa-ai** `scripts/lib/http_fetch.sh` |
| **Inline doc reference process** (when to add hooks; grep `Doc refs (AI`) | [AI_INLINE_DOC_REF_PROCESS.md](AI_INLINE_DOC_REF_PROCESS.md) |
| **Auth / JWT / roles — file→doc hub** | [AUTH_DOC_HOOKS.md](AUTH_DOC_HOOKS.md) → [AUTH_DESIGN.md](AUTH_DESIGN.md), [ROLES_AND_PERMISSIONS.md](ROLES_AND_PERMISSIONS.md) |
| **Rankings data pipeline — file→doc hub** | [RANKINGS_DATA_DOC_HOOKS.md](RANKINGS_DATA_DOC_HOOKS.md) → [WPA_RANKINGS_DATA_FLOW.md](WPA_RANKINGS_DATA_FLOW.md), [WPBA_DATA_FLOW.md](WPBA_DATA_FLOW.md), [RANKINGS_TABLE_DESIGN.md](RANKINGS_TABLE_DESIGN.md) |

## Quality checks

| Topic | Notes |
|-------|--------|
| API / DB | `GET /api/health`, `GET /api/system/health` (built-in checks; no pytest suite in repo) |

## Dependencies

| Topic | Doc |
|-------|-----|
| **All dependencies (Python + frontend)** | [DEPENDENCIES.md](DEPENDENCIES.md) — requirements-api.txt, requirements-deps.txt, package.json, live-update defaults |

## Deployment & Operations

| Topic | Doc |
|-------|-----|
| **Current system status** | [CURRENT_SYSTEM_STATUS.md](CURRENT_SYSTEM_STATUS.md) — live data population, working features |
| **Production status & next steps** | [PRODUCTION_STATUS_AND_NEXT_STEPS.md](PRODUCTION_STATUS_AND_NEXT_STEPS.md) — current state, web + app path to production |
| Production deployment | [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) |
| **Single production Compose file** | [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) — all services in `production/docker-compose.prod.yml`; root `docker-compose.yml` only re-exports via `include` |
| **Production deployment (Docker-only)** | [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) — deploy: `./scripts/full_deploy.sh` (optional `--production` / `--maintenance`); frontend build: **`./scripts/build_frontend_with_docker.sh`** only (no host npm) |
| Process ownership (Docker containers) | [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md), [CONTAINER_DRIFT_PREVENTION.md](CONTAINER_DRIFT_PREVENTION.md) |
| **Admin Update website / Full deploy (no docker.sock in API)** | [ADMIN_DEPLOY_HOST_DISPATCH.md](ADMIN_DEPLOY_HOST_DISPATCH.md) — request-file queue + host systemd path/oneshot dispatcher (`production/systemd/`, `scripts/deploy_request_dispatcher.sh`) |
| **Maintenance vs production (switch site)** | [MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md](MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md) — `./scripts/switch-site.sh maintenance \| production` |
| **Production: fix 404/405 login** | [FIX_PRODUCTION_LOGIN_404_405.md](FIX_PRODUCTION_LOGIN_404_405.md) — step-by-step tunnel fix; [CLOUDFLARE_PRODUCTION_CHECKLIST.md](CLOUDFLARE_PRODUCTION_CHECKLIST.md); `./scripts/verify_production.sh` |
| Environment variables | [ENV_VARS.md](ENV_VARS.md) |
| **Monitoring UI links (Grafana/Prometheus)** | [MONITORING_RANKINGS_BOT.md](MONITORING_RANKINGS_BOT.md) — `Settings > Admin > Health & logs`; set `VITE_GRAFANA_BASE_URL` and `VITE_PROMETHEUS_BASE_URL` |
| Data auto-refresh (scheduler) | [HOW_DATA_IS_UPDATED.md](HOW_DATA_IS_UPDATED.md) |
| **Rankings refresh (cron / host vs container)** | [RANKINGS_REFRESH_RUNBOOK.md](RANKINGS_REFRESH_RUNBOOK.md), [SCHEDULED_REFRESH.md](SCHEDULED_REFRESH.md) |
| **Scraper → DB → UI data map (which refresh updates which pages)** | [SCRAPER_TO_UI_DATA_MAP.md](SCRAPER_TO_UI_DATA_MAP.md) — entrypoint matrix, known Admin Refresh gap for Heyball/Artistic, verification SQL |
| Performance tuning (max perf) | [PERFORMANCE_TUNING.md](PERFORMANCE_TUNING.md) |
| Production & iOS readiness | [PRODUCTION_AND_IOS_READINESS.md](PRODUCTION_AND_IOS_READINESS.md) |
| Database upgrade (Postgres) | [DATABASE_UPGRADE.md](DATABASE_UPGRADE.md) |
| **Backup and recovery (full strategy + hub)** | [BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md) — local + NAS; all data dirs; cron; disaster recovery |
| Postgres backups (legacy reference) | [POSTGRES_BACKUPS_AND_CUTOVER.md](POSTGRES_BACKUPS_AND_CUTOVER.md) |
| **Postgres Docker-only (no host port)** | [DOCKER_POSTGRES_ONLY.md](DOCKER_POSTGRES_ONLY.md) — use `docker exec rankings-bot-postgres psql ...` |
| **Ports / 127 vs LAN (nginx 8088, API bind) — AI hook index** | [NETWORKING_DOC_HOOKS.md](NETWORKING_DOC_HOOKS.md) — file→doc map; then [PORT_MANAGEMENT.md](PORT_MANAGEMENT.md), [BAD_GATEWAY_TROUBLESHOOTING.md](BAD_GATEWAY_TROUBLESHOOTING.md) |
| **Splash config (single source, no fallbacks)** | [SPLASH_CONFIG.md](SPLASH_CONFIG.md) — config/splash_config.json; fix errors, don't fall back |
| **Start / stop / deploy** | [START_STOP_RESTART.md](START_STOP_RESTART.md) — `./scripts/start.sh`, `./scripts/full_deploy.sh`, `./scripts/stop.sh`; manual: `docker compose -f production/docker-compose.prod.yml` from repo root |
| **Ollama + AI Monitor** | [OLLAMA_AND_AI_MONITOR.md](OLLAMA_AND_AI_MONITOR.md) — env vars, features, `ollama_activity_log`, Settings → **AI Monitor (website)** vs **AI Monitor (internal)** (super admin) |
| **ALFa AI trust zones (public vs app vs internal)** | [ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md](ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md) — demo-ask vs Ask AI vs ALFa AI orchestrator; LiteLLM model aliases |
| **ALFa AI multi-job rollout (operator)** | [ALFA_AI_MULTI_JOB_ROLLOUT.md](ALFA_AI_MULTI_JOB_ROLLOUT.md) — phased Jobs 0–6: ports, secrets, stack, Petals, rankings-bot, TLS, verification |
| **ALFa AI Petals node inventory (GPU workers, hub `hub` management / `.157` worker peer)** | [alfa-ai/docs/NODE_INVENTORY.md](../../alfa-ai/docs/NODE_INVENTORY.md) — LAN port **31330**, `setup_hub_worker.sh`, link to [DISTRIBUTED_AI.md](../../alfa-ai/docs/DISTRIBUTED_AI.md) |
| **ALFa AI — how to use (ready checklist)** | [ALFA_AI_HOW_TO_USE.md](ALFA_AI_HOW_TO_USE.md) — enable LiteLLM in rankings-bot, URLs, verify, production notes |
| **ALFa AI — start/stop/health/logs (Compose)** | [alfa-ai/docs/START_STOP_AND_OPERATIONS.md](../../alfa-ai/docs/START_STOP_AND_OPERATIONS.md) — `./scripts/start.sh`, `./scripts/full_deploy.sh`, `./scripts/healthcheck.sh` (aligned with [START_STOP_RESTART.md](START_STOP_RESTART.md)) |
| **Grok: AI Dev Tools (super admin)** | Settings → **AI Dev Tools** — scraper triage, tournament QA, rankings NL assist, docs Q&A, email drafts, merge hints, CI log triage (`XAI_API_KEY`); API prefix `/api/admin/dev-tools` |
| **Disk / Docker cleanup** | [DOCKER_DISK_CLEANUP.md](DOCKER_DISK_CLEANUP.md) — `./scripts/cleanup_docker_disk.sh`; optional `RUN_DOCKER_CLEANUP_BEFORE_BUILD` in `./scripts/full_deploy.sh` |
| **Repo/server cleanup checklist** | [CLEANUP_DELETE_LIST.md](CLEANUP_DELETE_LIST.md) — logs, caches, optional doc archives, `data/` cautions, Docker prune |
| **Container drift prevention (no workarounds)** | [CONTAINER_DRIFT_PREVENTION.md](CONTAINER_DRIFT_PREVENTION.md) — container-only fixes; image/schema parity; build-hash verification; no-fallback policy |
| **Code quality audit (no workarounds/fallbacks)** | [CODE_QUALITY_AUDIT.md](CODE_QUALITY_AUDIT.md) — full-repo audit, what was fixed, what's acceptable per standards, known debt |

## Auth & Roles

| Topic | Doc |
|-------|-----|
| **Auth code ↔ docs (AI hook index)** | [AUTH_DOC_HOOKS.md](AUTH_DOC_HOOKS.md) |
| Auth design | [AUTH_DESIGN.md](AUTH_DESIGN.md) |
| Roles and permissions | [ROLES_AND_PERMISSIONS.md](ROLES_AND_PERMISSIONS.md) |
| Role capabilities | [ROLE_CAPABILITIES.md](ROLE_CAPABILITIES.md) |

## Tournaments & Leagues

| Topic | Doc |
|-------|-----|
| **Billiards tournament lifecycle (product scope: creation → brackets → scoring → rankings → awards)** | [BILLIARDS_TOURNAMENT_LIFECYCLE.md](BILLIARDS_TOURNAMENT_LIFECYCLE.md) |
| **New Tournament wizard (4-step UI, API order on create, Test Center / AI rules)** | [TOURNAMENT_WIZARD_VISUAL_OVERVIEW.md](TOURNAMENT_WIZARD_VISUAL_OVERVIEW.md) |
| **Branch changelog: tournament overhaul + Test Center (`tournament-overhaul`)** | [CHANGELOG_20260410_TOURNAMENT_OVERHAUL.md](CHANGELOG_20260410_TOURNAMENT_OVERHAUL.md) |
| **WPBA-style Test Center E2E (64 DE, R-points)** | [WPBA_TEST_CENTER_E2E.md](WPBA_TEST_CENTER_E2E.md) |
| Tournament director / scorekeeper API | [TOURNAMENT_DIRECTOR_SCOREKEEPER_API.md](TOURNAMENT_DIRECTOR_SCOREKEEPER_API.md) |
| Tournament scraper | [TOURNAMENT_SCRAPER_GUIDE.md](TOURNAMENT_SCRAPER_GUIDE.md) |
| Lower-priority roadmap (leagues, tours, i18n) | [ROADMAP_LOWER_PRIORITY.md](ROADMAP_LOWER_PRIORITY.md) |
| League Manager (ExternalPool reference) | [LEAGUE_MANAGER.md](LEAGUE_MANAGER.md) |
| ExternalPool analysis & video walkthrough | [EXTERNALPOOL_ANALYSIS.md](../EXTERNALPOOL_ANALYSIS.md) |

## Rankings & Import

| Topic | Doc |
|-------|-----|
| **Rankings pipeline code ↔ docs (AI hook index)** | [RANKINGS_DATA_DOC_HOOKS.md](RANKINGS_DATA_DOC_HOOKS.md) |
| **Rankings pipeline roadmap / open work (TODO)** | [RANKINGS_PIPELINE_ROADMAP.md](RANKINGS_PIPELINE_ROADMAP.md) — done vs open: WPA drop decision, CP GraphQL, name variance, Heyball, container-name normalization |
| **Changelog: rankings pipeline fixes (2026-06-07)** | [CHANGELOG_20260607_RANKINGS_PIPELINE_FIXES.md](CHANGELOG_20260607_RANKINGS_PIPELINE_FIXES.md) — WPBA word-parser, WPA resilience, CP import + domain revert |
| **WPBA tournament SSOT (canonical `wpba_evt_*`, per-event parser, leaderboard wiring)** | [WPBA_TOURNAMENT_SSOT.md](WPBA_TOURNAMENT_SSOT.md) |
| **WPA/Heyball tournament SSOT (digitalpool archives, leaderboard wiring, drop guard, CP)** | [WPA_TOURNAMENT_SSOT.md](WPA_TOURNAMENT_SSOT.md) |
| **WPBA PDF → rankings vs tournament history (which table each page reads)** | [WPBA_DATA_FLOW.md](WPBA_DATA_FLOW.md) — ingestion, table extraction, overall uses WPA-style strict columns, per-tournament buttons from API |
| **WPA Men/Women HTML → split + API menus (parallel to WPBA)** | [WPA_RANKINGS_DATA_FLOW.md](WPA_RANKINGS_DATA_FLOW.md) — `wpa_column_labels`, discovered columns, `wpa-*-tournament-systems`, zero-data split skip |
| **Rankings table design (first-class columns + source_data JSONB)** | [RANKINGS_TABLE_DESIGN.md](RANKINGS_TABLE_DESIGN.md) — schema, Heyball/WPA/WPBA column storage, UI dynamic columns, code paths |
| **Data consolidation model (players vs rankings, rebuild flow)** | [RANKINGS_DATA_CONSOLIDATION.md](RANKINGS_DATA_CONSOLIDATION.md) — source-of-truth split, snapshot rebuild script, alias seeding, verification |
| **Current missing player data tracker** | [MISSING_PLAYER_DATA_TRACKER.md](MISSING_PLAYER_DATA_TRACKER.md) — latest list of players missing country/license/Fargo plus report paths |
| **Historical scraper, WPA Artistic, PDF import (step-by-step)** | [RANKINGS_IMPORT_PDF.md](RANKINGS_IMPORT_PDF.md) — previous-ranking page, Artistic tab, file import, all columns on Rankings page |
| **Upload format (CSV, XLSX, PDF, etc.)** | [UPLOAD_FORMAT.md](UPLOAD_FORMAT.md) — required columns, file types, WPA Men auto-split, same columns for rankings and tournaments |

## Fargo & Ratings

| Topic | Doc |
|-------|-----|
| Fargo quick reference (CLI, admin) | [FARGO_QUICK_REFERENCE.md](FARGO_QUICK_REFERENCE.md) |
| Fargo lookup | [FARGO_LOOKUP.md](FARGO_LOOKUP.md) |
| Fargo rating history | [FARGO_RATING_HISTORY.md](FARGO_RATING_HISTORY.md) |
| Fargo rating scale | [FARGO_RATING_SCALE.md](FARGO_RATING_SCALE.md) |
| Fargo rating gaps & fair match | [FARGO_RATING_GAPS.md](FARGO_RATING_GAPS.md) |
| Alfa rating v2 spec | [ALFA_RATING_V2_SPEC.md](ALFA_RATING_V2_SPEC.md) |

## Website & Frontend

| Topic | Doc / Command |
|-------|---------------|
| **Recharts console warning fix** | [RECHARTS_CONSOLE_WARNING_FIX.md](RECHARTS_CONSOLE_WARNING_FIX.md) — width/height -1 warning; downgrade to 2.15.x |
| **Hot Streak page changes** | [HOT_STREAK_CHANGES.md](HOT_STREAK_CHANGES.md) — placement chart, association tabs, Fargo chart, tooltips |
| ALFA-style setup screens, ExternalPool-inspired UI | [ALFA_SETUP_SCREENS_REFERENCE.md](ALFA_SETUP_SCREENS_REFERENCE.md) |
| Start website | [START_WEBSITE.md](START_WEBSITE.md) |
| Deploy website | [DEPLOY_WEBSITE.md](DEPLOY_WEBSITE.md) |
| Smoke test | `./scripts/smoke_test.sh [URL]` |
| Verify production | `./scripts/verify_production.sh` |
| Mobile app | [MOBILE_ACCESS.md](MOBILE_ACCESS.md), [MOBILE_APP_MIGRATION.md](MOBILE_APP_MIGRATION.md) |

## Troubleshooting (index)

| Symptom / topic | Doc | One-line |
|-----------------|-----|----------|
| **Console: API timeouts, WebSocket 1006, Workbox, QUIC, health timeout** | [DEBUG_CONSOLE_ERRORS.md](DEBUG_CONSOLE_ERRORS.md) | Root cause: API not on 8003; Workbox precache conflicts; QUIC/HTTP3; runbook for all console errors |
| **Recharts: width(-1) height(-1) warning** | [RECHARTS_CONSOLE_WARNING_FIX.md](RECHARTS_CONSOLE_WARNING_FIX.md) | Recharts 3.x bug; fix: downgrade to 2.15.x |
| 502 Bad Gateway | [BAD_GATEWAY_TROUBLESHOOTING.md](BAD_GATEWAY_TROUBLESHOOTING.md) | Nginx/proxy can't reach API; check port 8003, tunnel, upstream |
| Production login 404/405 | [FIX_PRODUCTION_LOGIN_404_405.md](FIX_PRODUCTION_LOGIN_404_405.md) | Tunnel/proxy path normalization; proxy_pass without URI |
| Bot not visible | [TROUBLESHOOT_BOT_NOT_VISIBLE.md](TROUBLESHOOT_BOT_NOT_VISIBLE.md) | Bot instance not started or not reachable |
| Updates not showing | [WHY_UPDATES_DONT_SHOW.md](WHY_UPDATES_DONT_SHOW.md) | Live updates / WebSocket / polling not working |
| Smoke check | [SMOKE_CHECK.md](SMOKE_CHECK.md) | `./scripts/smoke_check.sh` — verify login, health, rankings |
| General troubleshooting | [TROUBLESHOOTING_GUIDE.md](TROUBLESHOOTING_GUIDE.md) | Broader troubleshooting steps |
| Deploy debug (HTTP) | [DEPLOY_DEBUG_HTTP.md](DEPLOY_DEBUG_HTTP.md) | HTTP-level deploy debugging |

## Archive

- [docs/archive/](archive/) — Completion reports and implementation summaries (historical reference)
- [docs/archive/legacy/](archive/legacy/) — superseded operational docs kept for reference

## Skip When Scanning

- `archive/` — archived completion reports
- `screenshots/`, `diagrams/` — assets
