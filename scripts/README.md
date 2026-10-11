# Scripts Index

Run from **Rankings-Bot** project root: `./scripts/<script>.sh`.

## Start and stop (intelligent)

| Script | Purpose |
|--------|--------|
| `start.sh` | **Start** — full stack, or use flags: `--dev`, `--deps-only`, `--app-only`, `--tunnel` |
| `stop.sh` | **Stop** — full stack, or use flags: `--dev`, `--deps-only`, `--app-only`, `--api-only`, `--tunnel` |
| `start_web.sh` | Web app only (API + frontend) |
| `stop_web.sh` | Stop web app |
| `start_mobile.sh` | Mobile app only (Metro) |
| `stop_mobile.sh` | Stop mobile app |

See `docs/START_STOP_RESTART.md` for full documentation.

## Deploy and start

| Script | Purpose |
|--------|--------|
| `full_deploy.sh` | Full rebuild (API, frontend, nginx), networks, tunnel; use for full stack deploy. |
| `start_gui.sh` | Start API + frontend dev server, open browser (dev). |
| `restart_api.sh` | Restart host API (development only). |
| `stop.sh` | Stop Docker stack (or partial with flags). |
| `deploy_website.sh` | Build frontend, restart API, optional nginx reload (quick website updates). |
| `rebuild_website_now.sh` | Build frontend + restart API or Docker (used by Admin UI "Update website"). |
| `build_on_server.sh` | Build on server after code sync (e.g. after `scripts/deploy.sh user@host`). |
| `deploy.sh` | Rsync code to server; run `build_on_server.sh --restart` on server after. |

## API control

| Script | Purpose |
|--------|--------|
| `start_api.sh` | Start API (for development/debugging only). |
| `restart_api.sh` | Restart API (development only, use Docker for production). |
| `rebuild_api.sh` | Rebuild API image (with or without `--no-cache`). |

## Diagnostics and verification

| Script | Purpose |
|--------|--------|
| `diagnose_rankings_bot_gateway.sh` | 502 Bad Gateway: nginx, API port, tunnel, UFW. |
| `diagnose_login.sh` | Login/health check with env credentials. |
| `smoke_check.sh` | Health, login, rankings load (set ADMIN_* and BASE_URL). |
| `smoke_test_tournament_wizard.sh` | Runs core + deferred Python smokes and `e2e_production_wizard_http.py` after deploy. Set `SKIP_TOURNAMENT_SMOKE=1` to skip. Wired into `deploy_website.sh`, `rebuild_api.sh`, `full_deploy.sh`. |
| `smoke_test_tournament_manager.py` | Core wizard path smoke (SE/DE brackets, BYEs, forfeit). Run in API container: `docker exec -i rankings-bot-api python3 /app/scripts/smoke_test_tournament_manager.py` |
| `smoke_test_tournament_deferred.py` | Deferred paths smoke (round robin, group stage, games, stage2). Same container invocation under `/app/scripts/`. |
| `e2e_production_wizard_http.py` | HTTP E2E mirroring wizard create/bracket/score (JWT mint, no password). Default user `tornybotca1` / `super_admin`. |
| `verify_production.sh` | Production config (JWT, DB, ports). |
| `verify_ports_and_health.sh` | Ports, Docker, health. |
| `healthcheck.sh` | Used by monitor and containers. |

## Maintenance

| Script | Purpose |
|--------|--------|
| `backup_postgres.sh` | Postgres backup (cron). |
| `cleanup_old_rankings_snapshots.py` | Remove old rankings snapshots (keep latest or last N days). Run with `--dry-run` first. |
| `cron_refresh_rankings.sh` | Scheduled rankings refresh (cron). |
| `docker_cleanup_daily.sh` | Prune stopped containers and unused images (cron). |
| `tail_api_logs.sh` | Follow API logs with timestamps. |
| `monitor_rankings_bot.sh` | Optional monitoring loop (calls healthcheck). |

## One-time / setup

| Script | Purpose |
|--------|--------|
| `seed_leaderboard_players.py` | Seed a few active players so the Leaderboard UI shows example rows when the DB is empty. Run: `DATABASE_URL=... python scripts/seed_leaderboard_players.py` (use `--dry-run` to preview). |
| `init_db.sh` | **Removed** (July 2026). Use `alembic upgrade head` with `DATABASE_URL` (Postgres). |
| `configure_ports.sh` | Interactive port config (called from master_setup). |
| `install_desktop_launcher.sh` | Desktop shortcut. |
| `install_desktop_all_users.sh` | System-wide launcher. |
| `start_cf_probilliards.sh` | Start Cloudflare tunnel container (cf-probilliards). |
| `setup_website_no_restart.sh` | One-time nginx/host-API setup. |

## Dev / data refresh

| Script | Purpose |
|--------|--------|
| `update_frontend.sh` | Frontend build (no API restart). |
| `scrape_and_test.sh` | Scrape WPBA/WPA rankings (optional Fargo); no automated test suite. |
| `smoke_test.sh` | Production smoke: curl health / app-version / privacy. |
| `frontend_build_hash.sh` | Hash for cache / rebuild detection. |
| `docker_build_hash.sh` | Docker build hash. |

## Archived

| Location | Purpose |
|----------|---------|
| `archive/` | Old start/stop scripts consolidated into `start.sh` and `stop.sh`. See `archive/README.md`. |

Log output: `*.log` and `logs/` are gitignored. Cron scripts often append to a log (e.g. `docker_cleanup.log`, `backup_postgres.log`); run `docker_cleanup_daily.sh` or similar to prune Docker; remove old log files from disk as needed.
