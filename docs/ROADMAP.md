# Rankings Bot Roadmap

**Last updated:** 2026-10-02 (scraper source fixes)

## Unresolved scraper sources (2026-10-02)

These lists cannot be filled from a live page or API. The code no longer invents them.

1. **Fargo ratings.** No official ratings CSV is on this host, and FargoRate has no public bulk API. `scripts/refresh_fargo.py` does not download ratings. The rows in `players.fargo_score` stay until `scripts/import_fargo_csv.py` is given an official export. See `docs/FARGO_LOOKUP.md`.
2. **Digital Pool 8-ball and 10-ball pro rankings.** The public GraphQL API has no per-game ranking view. Helpers return an empty list so they cannot copy the overall composite. The newest distinct snapshots are 2026-03-08 (8-ball 70 players, 10-ball 204). Those copies match 2025-12-16, so they were already frozen.
3. **Artistic rankings newer than 2/16/25.** The WPA Rankings page still links that PDF. Saved 2026-10-02: 21 players (Tim Chin, Florian Kohler, Gaston Tomadoni). Points for the 2023 and 2024 world championships are on each `WPA_Artistic` row (`2023_wc_pts`, `2024_wc_pts`). Separate buttons need `WPA_Artistic_2023_WC` and `WPA_Artistic_2024_WC` added to `rankings_ranking_system_check`.
4. **2026 UK Open.** Digital Pool has no 2026 UK Open event. The only name match is `uk-open-2022`. The local row has no Digital Pool URL.
5. **2026 Yalin WPA Men's 8-Ball.** Digital Pool has no matching event. The local row has no Digital Pool URL.


---

## Doc / code discrepancy register (compliance remediation)

Use this table to triage mismatches between documentation and the running system.  
**Columns:** ID, topic, doc claim, code/config source of truth, verdict, owner decision, exit criteria.

| ID | Topic | Doc claim (example path) | Code / config SoT | Verdict | Exit criteria |
|----|-------|---------------------------|-------------------|---------|---------------|
| DOC-001 | Data refresh | `docs/HOW_DATA_IS_UPDATED.md` — APScheduler starts with no scraper jobs | `api/services/background_scheduler.py` | **resolved** 2026-10-02 | Doc matches the empty scheduler |
| DOC-002 | Migrations | `docs/PRODUCTION_DEPLOYMENT.md` — migrations on container startup | `Dockerfile` CMD uvicorn only; `scripts/full_deploy.sh` runs `alembic upgrade` in container | **resolved** | Doc updated: migrations run via full_deploy.sh step 2bb |
| DOC-003 | Dev ports | `docs/CURRENT_SYSTEM_STATUS.md` — frontend 5000 / API 8100 | `frontend/vite.config.ts` (5174), API 8003 | doc-wrong | Status doc matches Vite + PORT_ASSIGNMENTS |
| DOC-004 | Production API | `docs/PRODUCTION_STATUS_AND_NEXT_STEPS.md` — host API :8100 | `production/docker-compose.prod.yml` — API container :8003 | doc-wrong / env-specific | Single production story: Compose + Nginx |
| DOC-005 | Mobile | `docs/PRODUCTION_READINESS.md` — Expo / `mobile/` paths | Root `package.json` React Native CLI; `src/`; committed `ios/` + `android/` | doc-wrong | Remove stale Expo/EAS/`cd mobile` from active setup docs |
| DOC-006 | Index | `docs/INDEX.md` links `PRODUCTION_API_OWNERSHIP.md` | File missing; link retargeted to `PRODUCTION_DEPLOYMENT.md` + `CONTAINER_DRIFT_PREVENTION.md` | **resolved** | Broken link removed |
| DOC-007 | Database | Root `PRODUCTION_DEPLOYMENT.md` — SQLite summary lines | `docker-compose.yml` `DATABASE_URL` Postgres; `database/__init__.py` runtime guard | **resolved** | Runtime rejects non-Postgres URLs |
| DOC-008 | Frontend build | `scripts/full_deploy.sh` — host npm was default | **Docker only:** `scripts/build_frontend_with_docker.sh` (no host npm). API container uses Docker CLI + `HOST_REPO_ROOT` + socket for Admin rebuild | **resolved** | See `docs/ENV_VARS.md`, `production/docker-compose.prod.yml` |
| DOC-011 | Admin Update website | Button fails with "permission denied" or "no lockfile" | Root cause: `HOST_REPO_ROOT` must be in `.env` (set to host repo path). Without it, `docker run -v` mounts a non-existent host path → empty `/workspace`. Docker socket access requires the host user to be in the `docker` group. | **resolved** | `.env` has `HOST_REPO_ROOT=/home/ansible/rankings-bot`; `ansible` is in `docker` group on host |
| DOC-009 | Web serving | Mixed docs (Nginx vs API static vs `serve` container) | Production: Nginx -> FastAPI -> dist. Dev compose: `frontend/Dockerfile` now uses `nginx:1.27-alpine` runtime | **resolved** | No Node `serve` in any Dockerfile |
| DOC-010 | Rankings storage | Legacy single `rankings` row per org | Alembic `049_*` association tables + mirror; legacy endpoints now check association tables first | **resolved** | Paginated + legacy endpoints use `_resolve_physical_rankings_read` |

**Workflow:** For each row, pick `doc-wrong` | `code-wrong` | `both-partial` | `env-specific`, update doc or code, add “verified \<date\> / \<commit\>” in the doc footer, then mark the row resolved in git history or a short CHANGELOG entry.

---

## AI / maintainer inline doc references ✅

- **Done (Rankings Bot):** Hub docs + `Doc refs (AI / maintainers)` in high-impact modules. **Process:** [AI_INLINE_DOC_REF_PROCESS.md](AI_INLINE_DOC_REF_PROCESS.md). **Hubs:** [NETWORKING_DOC_HOOKS.md](NETWORKING_DOC_HOOKS.md), [AUTH_DOC_HOOKS.md](AUTH_DOC_HOOKS.md), [RANKINGS_DATA_DOC_HOOKS.md](RANKINGS_DATA_DOC_HOOKS.md). **Discover:** [INDEX.md](INDEX.md) § *AI & maintainer conventions*; ripgrep: `Doc refs (AI`.
- **Sibling repos:** Apply the same process over time; each repo’s roadmaps link to the process doc above (on disk next to this repo: sibling `rankings-bot` checkout).

---

## Next step: post-merge host steps from the 2026-09-26 review (PR #24 fixes, PR #25 deps)

Open for review, not merged: [#24](https://github.com/example-owner-s-Org/Rankings-Bot/pull/24) (fixes, `fix/review-2026-09-26`) and [#25](https://github.com/example-owner-s-Org/Rankings-Bot/pull/25) (deps, `deps/update-2026-09-26`). The host steps for both PRs are here; this section is committed on the #24 branch. No new env vars, no DB migration, no files to back up.

Host: `probilliards`, `/home/operator/rankings-bot`. That's the canonical host per [REPO_HOST_MAPPING.md](https://github.com/example-owner-s-Org/contracts-bot/blob/main/docs/REPO_HOST_MAPPING.md); `/home/ansible/rankings-bot` on `apps` is a backup clone. Compose file: `production/docker-compose.prod.yml` (services `rankings-bot-api`, `celery-worker`).

**Merge order: merge #24 before #25, or both together.** Don't rebuild with only #25 merged. #24 caps `sqlalchemy<2.1`. Without that cap, a `rankings-bot-base` rebuild installs SQLAlchemy 2.1 and the API crashes with `No module named 'psycopg'`. The two branches merge with each other cleanly. If both are merged before you deploy, do the pull and rebuild once.

### Before pulling
- [ ] On the host, run `cd /home/operator/rankings-bot && git status --short`. If tracked frontend files (`frontend/package.json`, `frontend/package-lock.json`, `frontend/src/api/*.ts`, `frontend/src/hooks/useLiveUpdates.ts`) show local edits, the pull will refuse to overwrite them. Commit them first (see the first decision below) or `git stash`.

### After merging PR #24
- [ ] `cd /home/operator/rankings-bot && git pull`
- [ ] `requirements-api.txt` changed, so rebuild the base image: `docker build -f Dockerfile.base -t rankings-bot-base:local .` (or `docker buildx bake --file ../alfa-ai/deploy/cluster/docker-bake.hcl rankings-bot-base rankings-bot-app`).
- [ ] Rebuild and recreate the API and worker: `docker compose -f production/docker-compose.prod.yml build rankings-bot-api celery-worker && docker compose -f production/docker-compose.prod.yml up -d --force-recreate rankings-bot-api celery-worker`
- [ ] Check the driver: `docker exec rankings-bot-api python -c "import sqlalchemy;print(sqlalchemy.__version__)"` should print `2.0.x`, and `docker logs --tail 50 rankings-bot-api` should show no `psycopg` error.
- [ ] Frontend (`PlayerDetailModal.tsx` changed): `./scripts/build_frontend_with_docker.sh` rebuilds `frontend/dist`, which probilliards-nginx serves. Only if you still run the legacy `rankings-bot-frontend` container: also rebuild its image from `frontend/Dockerfile`, which now copies `vendor/` before `npm ci`.
- [ ] Smoke test:
  - As admin, open a player modal, change the history period and reload. `GET /api/users/preferences/ranking_history_days` should return the saved value (not null, 500 or 401).
  - The head-to-head page should show ALFa ratings for admins.
- [ ] Tests on a checkout: export a dummy `DATABASE_URL`, then run `pytest tests/backend --ignore=tests/backend/test_system_self_test_paths.py`. Expect 122 passed.

### After merging PR #25
- [ ] `git pull`, then rebuild the base image again (`requirements-deps.txt` / `requirements.txt` drop PyPDF2) and the API and worker. Use the same three commands as for #24.
- [ ] Frontend (`package-lock.json` was regenerated): `./scripts/build_frontend_with_docker.sh`. Legacy `rankings-bot-frontend` image only: rebuild it (its runtime is now `nginx:1.30-alpine`).
- [ ] Check that the WPBA rankings refresh still parses PDFs (`pdfplumber` only now) and that the site loads.

### Decisions for you
- [ ] **Commit the missing frontend files** from the host's working tree. Check the live `probilliards` clone `/home/operator/rankings-bot` (and the `apps` backup `/home/ansible/rankings-bot`) for them. Until this is done the frontend does not build from a clean checkout (`vite build` fails on `main`, and the vite 6 upgrade is blocked).
  - Files: `frontend/src/lib/{logger,upcomingEventPrefill,testCenterLogger,testCenterErrorHandler,testCenterUpcomingPrefill,tournamentPersistence,performanceMetricsTracker,exportImportService,sharingUtils,tournamentTemplates}.ts` and `frontend/src/api/stats.ts`.
  - Also the newer working-tree `api/auth.ts`, `api/rankings.ts` and `hooks/useLiveUpdates.ts`, plus `i18next` / `react-i18next` in `frontend/package.json`.
  - Commands: `git status frontend/`, then `git add -f <files>`, commit, push and open a PR.
- [ ] **Fargo backfill** is missing (`api/routes/admin.py:122`): `PostgresManager.backfill_latest_fargo` no longer exists, so the pre-rebuild backfill silently does nothing. Port it to psycopg2?
- [ ] **`POST /api/alfa/video-analysis-update` is broken** (`api/routes/alfa_ratings.py:902-980`): it imports a non-existent `AlfaEngine`, trusts `user_id` from the request body, and the Celery caller posts to `localhost:8003` with no auth. Redesign or remove it?
- [ ] `api/routes/rankings.py:63-66` puts `/home/ansible` first on `sys.path`. Remove it?
- [ ] `tests/backend/test_system_self_test_paths.py` needs a live Postgres at import time.
- [ ] `.github/workflows/lint.yml` uses Node 20 (EOL). Bump it to 22 yourself; the agent has no `workflow` scope.
- [ ] Majors not applied (#25):
  - vite 5 → 6.4.3+ (dev-server-only advisories)
  - react-router-dom 6 → 7 (backslash open redirect)
  - recharts 3
  - `node:20-alpine` builder → 22
  - eslint 10

---

## Next step: post-merge host steps from the 2026-09-25 security review

From [#21](https://github.com/example-owner-s-Org/Rankings-Bot/pull/21) and [#22](https://github.com/example-owner-s-Org/Rankings-Bot/pull/22) (both merged 2026-09-25). Details: [CHANGELOG_20260925_SECURITY_REVIEW_FIXES.md](CHANGELOG_20260925_SECURITY_REVIEW_FIXES.md), [CHANGELOG_20260925_SECURITY_REVIEW_FOLLOWUP.md](CHANGELOG_20260925_SECURITY_REVIEW_FOLLOWUP.md), [ENV_VARS.md](ENV_VARS.md). Deploy together with USPBF [#1](https://github.com/example-owner-s-Org/USPBF/pull/1) (shared `BOT_API_KEY`).

- [ ] **Before `git pull` on any server, back up** `.env.development`, `.env.production`, `.env.staging`, `.env.ports`, `staging.env.sh`, `env.production.snippet`. They are now untracked, so the pull deletes the working-tree copies. Restore them after pulling (they stay git-ignored).
- [ ] **Rotate** (all remain in git history): everything those six files contained (DB passwords, `JWT_SECRET`, `BOT_API_KEY`, API keys, user passwords); the admin/director/user passwords that were in `PRODUCTION_DEPLOYMENT.md` / `REVIEW_AND_DEPLOY.md`; any account still on the old bootstrap temp password or old super-admin default; the `rankings_user` Postgres password hardcoded in the two super-admin scripts; the old staging Postgres and Grafana defaults; the super-admin password whose hash was in `config/super_admin.json` (if still in use).
- [ ] **Production `.env`:** `BOT_API_KEY` (required at startup; must equal USPBF's `BOT_API_KEY`; only `A-Za-z0-9._~+/=-`, e.g. `openssl rand -hex 32`), `SUPER_ADMIN_PASSWORD`, `ADMIN_PASSWORD`, `DIRECTOR_PASSWORD`, `USER_PASSWORD` (8+ chars with upper, lower, digit and special, or startup fails). Don't use `admin` as `ADMIN_USERNAME` (login honeypot). Optional: `SCORE_KEEPER_PASSWORD` (scorekeeper account is no longer auto-created); narrow `FORWARDED_ALLOW_IPS` to the Docker network subnets.
- [ ] **Staging `.env`** (see `.env.staging.example`): `BOT_API_KEY`, `STAGING_SUPER_ADMIN_PASSWORD`, `STAGING_ADMIN_PASSWORD`, `STAGING_DIRECTOR_PASSWORD`, `STAGING_USER_PASSWORD`, `STAGING_POSTGRES_PASSWORD` (URL-safe chars), `GRAFANA_ADMIN_PASSWORD`. If the staging volume already exists, run `ALTER USER` so the Postgres password matches, and change Grafana's password in its UI.
- [ ] **Rebuild + recreate:** rebuild `rankings-bot-base` (new pip deps), then `docker compose -f production/docker-compose.prod.yml up -d --force-recreate`. Confirm `docker port rankings-bot-api` shows `127.0.0.1:8003`.
- [ ] **Smoke test:** logged-out splash/login incl. slideshow and splash media; live bracket and live-update streams; USPBF rankings, tournaments, news and demo chat; a `must_change_password` user gets 403 everywhere until the password is changed; login audit rows and 429s show real client IPs, not the nginx container IP. If a browser `<img>`/`EventSource`/`<a href>` hits another `/api/` path, add it to the public list in `api/middleware/access_control.py` and [API_ACCESS_POLICY.md](API_ACCESS_POLICY.md).
- [ ] **Tooling:** `scripts/fix_super_admin.py` / `scripts/reset_super_admin_password.py` now need `DATABASE_URL` and `SUPER_ADMIN_PASSWORD` exported. Android: create a local `android/app/debug.keystore`; release builds need the `RANKINGSBOT_UPLOAD_*` Gradle properties.
- [ ] Run `pytest tests/` on a checkout (CI only lints; both PRs were edited without a checkout).

**Deferred (from #22):**
- Rate limits are still per Uvicorn worker; a shared Redis limiter for login/rankings is a larger change.
- Redis still has no `requirepass`; adding one needs coordinated `REDIS_URL` changes.

---

## Current Priority

- [ ] **Security & Code Quality Fixes** — Critical security vulnerabilities and code issues must be resolved immediately
- [ ] **Website stability** — https://www.probilliardssoftware.com must load, show the app, and stay up. API on port **8003**; Nginx routes the domain. See [BAD_GATEWAY_TROUBLESHOOTING.md](BAD_GATEWAY_TROUBLESHOOTING.md) if 502. ✅ (COMPLETED)

### Security & Code Quality Issues (RESOLVED ✅)

| Issue | Severity | File | Status |
|-------|----------|------|--------|
| Hardcoded credentials in source code | CRITICAL | `api/routes/auth.py`, `database/__init__.py`, scripts | ✅ Completed |
| Insecure default JWT secret | CRITICAL | `api/auth.py` | ✅ Completed |
| Overly permissive CORS configuration | HIGH | `api/main.py` | ✅ Completed |
| Duplicate function definitions | MEDIUM | `api/auth.py` | ✅ Completed |
| Massive lifespan() function (500+ lines) | MEDIUM | `api/main.py` | ✅ Completed |
| Duplicate imports | LOW | `api/main.py` | ✅ Completed |
| Inconsistent error handling | MEDIUM | Various services | ✅ Completed |
| Missing timeout/circuit breaker patterns | MEDIUM | External API calls | ✅ Completed |

**Status:** All critical security and code quality issues have been resolved. The codebase now follows industry standards and security best practices.

---

## Completed Phases

### Phase 1.5: Web GUI Rankings Display ✅

- Rankings page, WPBA/WPA tabs, search/filter, pagination, export CSV, refresh
- Player detail modal, responsive design, TypeScript types

### Phase 2: Data Collection & Validation ✅

- WPBA/WPA scrapers with rate limits, scheduled refresh, ranking history
- Data quality checks, duplicate detection, missing fields

### Phase 2.2: Guest Showcase ✅

- Full UI visible to guests, locked actions with tooltips
- Splash page, WPBA/WPA theme, creator attribution

### Phase 2.5: Directors Account ✅

- Director role, data input UI, manual entry/import (PDF, DOCX, XLSX, CSV)

### Phase 3: Ranking Engine ✅

- Rank-over-time, movement detection, optional projections

### Phase 4: Automation & Integration ✅

- Scheduled refresh, notifications, backups, health/self-test

### Phase 5: UI & Reporting ✅

- Admin backup DB, exports, movement CSV

### Phase 6: Market Gap (External Pool/Fargo) ✅

- **Fargo:** API sync, handicap calculator, submit to Fargo Rate
- **SMS/Email:** Match notifications, reminders
- **Live brackets:** WebSocket/SSE, real-time updates
- **Payments:** Stripe, registration, waitlist
- **Double elimination:** Losers bracket, finals reset
- **Extras:** Projected match times, QR check-in, director table view, win probability

### Lower Priority (Done) ✅

- League management, Tour/series support

---

## Planned / Future

### Note: CI test workflow removed

The repository no longer ships a pytest suite or GitHub **Tests** / Grok-on-failure workflows. Use **Settings → AI Dev Tools → CI log triage** (super admin) with a pasted log if you want Grok help on failures.

**Maintenance-page testing:** Showing the public maintenance page is an **nginx** switch only (`./scripts/switch-site.sh maintenance`) — see [MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md](MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md).

### High Priority

| Item | Status | Notes |
|------|--------|-------|
| Round robin / group stage | ✅ Completed | Tournament format extension |
| Alfa rating Phase 3 tuning | ✅ Completed | Context adjustments, anomaly thresholds, video integration |
| Player Performance — super admin dedupe + UX | In progress | Remove duplicate player lists for super_admin (keep only "Browse any player" chips); deduplicate API names by case-insensitive trim. Branch: `tournament-overhaul`, file: `PlayerPerformance.tsx`. Deploy: `./scripts/build_frontend_with_docker.sh` then hard refresh. |

### Test Center — Full double elimination + WPBA verification ✅

- **Goal:** Test Center remains the only isolated tournament sandbox (`test_*` tables); verify **64-player double elimination** (winners + losers + single grand final, no bracket-reset match), WPBA-style **R-points** bands, and metadata (location, dates, prize pool, `race_to_final`).
- **Implementation:** `api/services/bracket_engine.py` (DE for 64, `WPBA_CLASSIC_POINTS` / `wpba_points_for_placement`), `api/routes/test_tournaments.py` (winner + loser routing, leaderboard ranks, `seed-classics-demo-players`), Test Center UI (setup fields, bracket **sections**, leaderboard **wpba_r_points**).
- **Isolated views (delivered):** On tournament completion, results persist to test DB view tables; **Test Rankings / Test Leaderboard / Test Hot Streak / Test Tournament History** sub-tabs reuse production page components with `/api/test-center/*` mirrors (`api/routes/test_center_views.py`, `frontend/src/contexts/ApiPathContext.tsx`). Test center schema bootstrap: `database/schema_testcenter_bootstrap.sql`.
- **Merge gate (`tournament-overhaul` → `main`):** Run the checklist in [WPBA_TEST_CENTER_E2E.md](WPBA_TEST_CENTER_E2E.md) against the containerized stack.
- **Full lifecycle (product scope):** See [BILLIARDS_TOURNAMENT_LIFECYCLE.md](BILLIARDS_TOURNAMENT_LIFECYCLE.md) for how real tournament software runs events end-to-end vs what Test Center validates.
- **Production wizard parity (goal):** Test Center endpoints should align with the 4-step production API sequence in [TOURNAMENT_WIZARD_VISUAL_OVERVIEW.md](TOURNAMENT_WIZARD_VISUAL_OVERVIEW.md).

#### Production wizard parity — critical bug found + partial fix (2026-07-06)

**Root cause found:** `api/tournament_manager.py` (the module backing the *production* tournament wizard — create → register → generate bracket → record results) was written against SQLite (`?` placeholders, `dict(row)` on tuple cursors, `PRAGMA table_info`) but the app has run on Postgres-only since the SQLite migration (`docker-compose.yml` `DATABASE_URL`, `database/__init__.py` runtime guard — see DOC-007 above). Every query in this module raised `psycopg2.errors.SyntaxError` or `TypeError` at runtime. Production `tournaments` and `matches` tables were confirmed **empty**, meaning this code path had never actually succeeded in production. Test Center (`api/routes/test_tournaments.py`) was unaffected — it already used `%s` placeholders and a manual row-to-dict helper.

Two further logic bugs were found and fixed while porting (never previously exercised, so never caught):

- `_advance_loser` had a `bracket_type == 'losers'` branch that tried to route the *loser* of a losers-bracket match forward — but an LB match loser has lost twice and must be eliminated, not routed. The correct alternating-round LB internal-progression logic (odd round → same match index, slot `player2_id`; even round → merge pairs) needed to live in `_advance_winner` (advancing the *survivor* of each LB match) instead.
- Both functions used bracket column names `'operator'` / `'player2'` in the losers-bracket drop-in `UPDATE ... SET {slot} = ...` calls; the real columns are `operator_id` / `player2_id`. Silently updated a non-existent column (`UndefinedColumn`) on every double-elimination bracket.
- Round-1 BYE matches (status `'bye'`, `winner_id` pre-set at generation time) were never advanced into round 2 — `_advance_winner` is only invoked from `update_match_score`/`set_match_outcome`, which never fire for a bye. `_generate_single_elimination` now advances bye winners immediately after all rounds are created.

**Fixed and live-smoke-tested on `probilliards`** (disposable test tournaments/players, cleaned up after): `create_player`, `get_player`, `create_tournament`, `get_tournament`, `update_tournament`, `delete_tournament`, `register_player`, `unregister_player`, `get_tournament_players`, `record_check_in`, `generate_bracket`, `_generate_single_elimination` (incl. BYE auto-advance), `_generate_double_elimination`, `_create_grand_final_reset`, `update_match`, `update_match_score`, `set_match_outcome`, `_advance_winner`, `_advance_loser`, `_winners_bracket_num_rounds`, `get_tournament_matches`, `get_match`. Verified: single elimination with and without BYEs, double elimination at 4/8/16 players (proving the losers-bracket routing generalizes beyond the old hardcoded 8-player/3-round shape), table assignment, and forfeit/DQ outcome recording.

**Deferred Postgres port completed (2026-07-07):** The following paths were ported from SQLite `?` placeholders / tuple-row access to Postgres (`%s`, `_row_to_dict` / `_rows_to_dicts`, `RETURNING id`, `STRING_AGG`, `CURRENT_DATE`):

- `start_stage2`, `_generate_round_robin`, `_generate_group_stage`
- `forfeit_match`, `get_matches_by_table`, `get_matches_for_score_keeper`
- `update_player`, `dedupe_players`, `recalculate_rankings`
- `table_calls` (`create_table_call`, `get_table_calls`, `process_table_call_warnings`)
- `process_match_reminders`, games/racks (`create_game`, `get_game`, `update_game`, `get_match_games`, `synchronize_match_score_from_games`)
- `api/services/tournament_payment.py`, `media_store.py`, `competitors_import.py`
- `api/routes/tours.py`, `leagues.py`
- `scrapers/tournament_scraper_improved.py` and maintenance scripts (`import_competitors_tournament.py`, `load_per_tournament_rankings_into_tournaments.py`, `scrape_fargo_players.py`, `archive/hometown_scraper.py`)

**Previously deferred (now fixed — see list above):**

#### SQLite removal — repo cleanup (2026-07-07)

**Audit:** No `*.db` files on `probilliards` (`/home/operator/rankings-bot`) or `apps` backup clone. Production data lives only in Docker volume `rankings-bot_postgres_data`.

**Removed from repo:**
- `database/schema_tournament_management.sql` (SQLite DDL)
- `scripts/init_db.sh` (created `database/rankings.db` via deleted `db_manager`)
- `DATABASE_STATUS.md` (stale mixed SQLite/Postgres report)

**Updated:** setup scripts (`setup.sh`, `master_setup.sh`), `database.py` re-exports, `docs/DATABASE_CONFIG.md`, scraper import (`tournament_scraper_improved.py` → `PostgresManager`), `manual_fargo_scrape.py --apply` (Postgres connection, not file path), backup download filename in UI (`.dump` not `.db`), last `PRAGMA table_info` fallbacks in `tournament_manager.py`.

**Still contains historical SQLite mentions** (archive/migration notes only): root `DEPLOYMENT_*.md`, `REVIEW_AND_DEPLOY.md`, `OBSOLETE_FILES.md`. Active tournament code paths listed above are Postgres-safe as of 2026-07-07.

#### Production wizard — UI fixes + deploy smoke (2026-07-07) ✅

**Fixed on `main` and verified on `probilliards`:**

- Post-create redirect: `/tournament-wizard/bracket` (was `/brackets` → wildcard redirect).
- `generate-bracket` 422: removed duplicate `tournament_id` from request body model.
- Step 2 crash: AI coach used `template.name` instead of API field `template_name`.
- Step 3 empty pool: admin/super_admin fall back to full active roster when association-scoped pool is empty (directors remain scoped).
- **Deploy gate:** `scripts/smoke_test_tournament_wizard.sh` runs core + deferred Python smokes and `e2e_production_wizard_http.py` after API restart (`deploy_website.sh`, `rebuild_api.sh`, `full_deploy.sh`; skip with `SKIP_TOURNAMENT_SMOKE=1`).
- **Line endings:** repo `.gitattributes` enforces `*.sh` LF so Linux deploy hosts do not hit CRLF shebang errors.

**Automation vs browser:** HTTP E2E covers create → register → bracket → score → delete. Full 4-step UI walkthrough remains optional operator validation (login blocked until `.env` `ADMIN_PASSWORD` matches DB — use super_admin account or JWT for smoke).

### High Priority (Next Up): Live Est. Rating + Live Odds

Goal: deliver rack-by-rack live `Est. Rating` updates from scorekeeper data, update live match odds as game state changes, and use published Fargo values for ongoing calibration until parity is good enough to reduce scrape dependency.

#### Scope and Rules

- `Fargo` remains published/scraped reference and does not update live during tournament play.
- `Est. Rating` updates after each rack result (not only after match completion).
- `Est. Rating` is visible admin+ only and appears next to `Fargo` in overall rankings views.
- Match win/loss odds refresh after each rack and each match score change.
- Directors can use suggested points templates, override as needed, and save finalized tournament settings as reusable templates.

#### Phase 1 — Rack Event Pipeline

| Item | Status |
|------|--------|
| Scorekeeper `POST .../games` path (`match_id`, `game_number`, `winner_id`, break/run-out metadata) | ✅ `api/routes/tournaments.py` + `tournament_manager.create_game` |
| Match score synced from rack aggregate (`race_to`) | ✅ `synchronize_match_score_from_games` (smoke Test 4) |
| `rack_completed` broadcast (SSE/WebSocket) | ✅ `broadcast_rack_completed` on game create |
| Idempotency / duplicate guards for rack submissions | ⏳ unique `(match_id, game_number)` when present; explicit test still optional |
| Rack submit publishes live UI refresh | ✅ `POST /api/tournaments/games` calls `notify_data_changed` + tournament SSE |
| Scorekeeper posts racks (not only bulk score) | ✅ `MatchEntryModal` simpleMode `+` → `tournamentsApi.submitGame` (2026-07-12) |

#### Phase 2 — Live Est. Rating Engine

| Item | Status |
|------|--------|
| Recompute both players' `est_rating` on rack completion | ✅ `LiveRatingEngine.process_game_completion` on game create |
| Audit trail (`est_rating_transitions`, formula version, confidence, robustness) | ✅ engine + Alembic schema |
| Push to rankings/match views without refresh | ✅ rack submit emits `notify_data_changed(scores|rankings|leaderboard)` + tournament SSE `rack_completed`; `useLiveUpdates` + `Bracket.tsx` invalidate React Query keys (2026-07-07) |
| Calibrated K / confidence from DB | ✅ loads `rating_calibration_params` (Alembic `060`); formula_version `live_elo_v1_calibrated` |

#### Phase 3 — Live Odds Recalculation ✅ (2026-07-12)

| Item | Status |
|------|--------|
| Recompute in-match win odds on rack completion | ✅ `recompute_and_broadcast_live_odds` after `POST /games` |
| Recompute on manual match score update | ✅ `PUT /matches/{id}/score` |
| Recompute on match state transition (forfeit/DQ) | ✅ `PATCH /matches/{id}/outcome` |
| Score-state inputs (race-to, rating delta, optional break in context) | ✅ `live_odds_v1` Elo rack + race-to DP; break metadata in snapshot `context` |
| Store odds snapshots for validation/tuning | ✅ table `live_odds_snapshots` (Alembic `059`) + denorm on `matches` |
| API + UI | ✅ `GET .../odds`, `.../odds/history`; BracketViewer “Live” odds line |

Formula: per-rack Elo (scale 400 on `est_rating` → Fargo fallback) + remaining-games DP to race targets (`api/services/live_odds_engine.py`).

#### Phase 4 — Fargo Comparison + Formula Calibration ✅ (2026-07-12)

| Item | Status |
|------|--------|
| Compare EST vs published Fargo (use `players.fargo_score`) | ✅ `api/services/est_fargo_comparison.py` + `POST /api/rating-accuracy/compare-est-fargo` + Settings **Compare EST vs Fargo** |
| MAE/RMSE + segment error (robustness / rating bands) | ✅ returned in job payload; RMSE written when column present |
| Calibration tables on Alembic-only DBs | ✅ Alembic `060` `rating_calibration_params` + `system_accuracy_improvement` |
| Live EST uses calibrated params | ✅ `LiveRatingEngine._load_calibration_params` |
| CLI | ✅ `scripts/run_est_fargo_comparison.py` |

Nightly schedule optional (admin-triggered first; respects no-auto-scrape for Fargo refresh).

#### Phase 5 — Reduce Fargo Scrape Dependency (Gate-Based)

- Define objective acceptance gates before reducing dependency:
  - sustained low error over multiple refresh windows
  - no major regressions in key segments
- After gates are met:
  - keep `est_rating` as primary live value
  - keep Fargo scrape as periodic verification/fallback

#### Points Tiers and Director Workflow

- Keep suggested points structures in Tournament Wizard.
- Allow director override per event before bracket play.
- Save tournament-final points structure with that event snapshot.
- Support "Save as template" from finalized event settings.
- Ensure guaranteed placement tiers can update standings points as players advance (not only after full tournament closeout).

#### Immediate Data Integrity and UX Corrections

| Item | Status | Notes |
|------|--------|-------|
| Find all future tournaments and populate them | Done | Scraper + recovery scripts; `scripts/run_tournament_scraper_hourly.py`, `scripts/recover_future_tournaments.sh` |
| Remove News from Tournament History and Leaderboard | Done | Leaderboard filters `wpba events`, `wpa news`, etc. in `isRealTournament`; Tournament History uses tournament_history API (no News in source) |
| Fix missing players in Poison Saigon 9-Ball tournament | Script ready | Run `scripts/fix_poison_saigon_rankings.py` when needed |
| Fix incorrect WPA Women points | Pending | Requires data audit; see MISSING_PLAYER_DATA_TRACKER.md |
| Rankings tournament buttons use scraped per-tournament points | Pending | Ensure per-tournament points from scraper flow to UI; audit Rankings page |
| Hot Streak page enhancements | Done | Placement chart, association tabs, Fargo chart, tooltips; see [HOT_STREAK_CHANGES.md](HOT_STREAK_CHANGES.md) |

### Medium Priority

| Item | Status | Notes |
|------|--------|-------|
| Native mobile apps | In progress | iOS TestFlight setup with Apple Developer account |
| Multi-language (i18n) | Planned | 14+ languages (External Pool parity) |

### High Priority (In Progress): ExternalPool Tournament Intelligence

Goal: continuously enrich `tournament_history` with ExternalPool event structure, bracket graph, and player-level tournament stats so rankings, hot streak, and analytics can use real match context (not just placement snapshots).

#### Data Ingestion Scope

- **Tournament structure**: event/tournament metadata, draw type, tournament type, stage/round hierarchy.
- **Bracket graph**: per-match rows with stage, round, match number, table, players, winner, and scores.
- **Player tournament stats**: per-event placement, points, seeds, participation counts.
- **Joinable links**: persist canonical event URL + bracket viewer URL for traceability and refresh.

#### Tab Coverage Plan (Per Tournament)

| ExternalPool Tab | Current scraper status | Storage now | Next upgrade |
|---|---|---|---|
| Overview | In progress | `tournament_history` + raw tab payload JSON | Normalize more overview fields into DB columns/reporting |
| Bracket | In progress | `tournament_history_matches` + raw payload | Add stage progression and elimination path derivations |
| Live Scores | Partial | Pulled from `matches` query into raw payload | Stream to live endpoints/WebSocket pipeline |
| Matches | In progress | Raw payload + bracket-linked notes | Add dedicated persisted match facts table/view |
| Schedule | Partial | `scheduled_time` captured in notes/raw payload | First-class schedule API + UI timeline |
| Players | In progress | `tournament_results` + raw player payload | Persist richer player metrics (robustness/skill/status) |
| Stats | Planned | Available via GraphQL; not normalized yet | Materialize tournament/player stat rollups |
| Performance | Planned | Available via GraphQL match/player fields | Derived performance metrics + leaderboards |

#### Current Status

- `ExternalPoolTournamentHarvester` implemented and running against production containers.
- Bootstrap import run completed (2026-03-20): `scanned=120`, `matched_events=13`, `updated_history_rows=13`, `upserted_results=312`, `replaced_matches=1457`, `errors=0`.
- Tab-coverage validation run completed (2026-03-20, forced): `scanned=60`, `matched_events=17`, `updated_history_rows=17`, `upserted_results=384`, `replaced_matches=1711`, `errors=0`.
- Initial imports started successfully and are writing:
  - `tournament_history` metadata enrichments
  - `tournament_results` upserts (player placements/points)
  - `tournament_history_matches` full bracket/match refresh rows
  - raw per-tournament tab payload archives in `EXTERNALPOOL_TAB_ARCHIVE_DIR` (default: `/tmp/externalpool_tabs`)
- No runtime import errors observed in current ingestion runs.
- Tournament tab-coverage APIs are live:
  - per-tournament: `GET /api/tournaments/history/{tournament_id}/tab-coverage`
  - bulk list with filters: `GET /api/tournaments/history/tab-coverage`
- UI surfacing is live in:
  - `TournamentHistory` details (tab chips + performance summary)
  - `System` admin page (incomplete coverage monitor with association/year filters)
  - `TournamentHistory` card list (coverage badge per tournament)

#### Next Delivery Steps

1. **Fargo hot streak completion**: finalize data quality and edge-case handling for "last 3 Fargo ratings" view and validate with targeted tests/UI verification.
2. **Coverage expansion**: run scheduled/backfill harvests over larger history windows (newest-first, then full backlog).
3. **Quality gates**: add matching-confidence checks to avoid cross-event mis-assignment (name/date false positives).
4. **Derived player stats**:
   - wins/losses by event
   - score differential
   - finish percentile (placement normalized by field size)
   - stage/round reached and elimination path context
5. **API surfacing**: add endpoints/fields for tournament structure and bracket timeline views in frontend.
6. **Product integration**:
   - roadmap-backed use in Hot Streak, Tournament History detail pages, and analytics dashboards
   - admin refresh controls for targeted re-harvest by event/date range.

### High/Medium Priority: UI Surfacing for Inside Spin + Digital Pool harvested data (2026-07)

A July 2026 audit of the active scrapers (`insidesp_scraper.py` + `insidesp_tier2_scraper.py`, `externalpool_scraper.py`, `externalpool_tournament_harvester.py`) plus the persistence layer (`save_rankings` → `source_data`, `tournament_results`, `tournament_history_matches`) and current read paths (`get_rankings_paginated`, `/api/tournament-history/leaderboard-results`, etc.) found that a large amount of useful structured data is already being collected, archived, and written to Postgres — but has no (or only incidental raw-column) presentation in the UI or on the USPBF static site.

Related: `docs/MULTI_SOURCE_DATA_INTEGRATION_PLAN.md`, `docs/SCRAPER_TO_UI_DATA_MAP.md`, and the detailed "scraped vs. displayed" analysis in recent session transcripts.

**Data already in the DB (examples)**
- Inside Spin: `insidesp_rating` (Display Rating), `matches_rated`, `insidesp_nationality`, discipline, full recent events (dates/locations/winners + Tier-2 participantRows with placement/points/slugs).
- Digital Pool Pro rankings + history: `digitalpool_player_id` + 8–10 parallel ranks (`fargo_*`, `matchroom_*`, `wpa_*` variants + weighted) + `rank_date` time series in `source_data`.
- DP tournaments: seeds, `race_to`, `current_round`, `status`, `is_eliminated`, per-side bracket fields (name/seed/country/score/race_to), table/scheduled/duration, fargo-at-match, derived tab slices (schedule/live/stats/performance), many extra columns on `tournament_history_matches` (elo, equipment, location, confidence, etc.).
- Player profile enrichment (city, gender, DP fargo id/rating, join/last_active) fetched by `scrape_player_profile`.

**What the UI currently shows**
- InsideSpin_* and Competitors_Pool_* / DigitalPool_* systems appear in the Rankings drill-down and render via the generic table (extra keys from `source_data` may appear as columns).
- Leaderboard / Recent Podiums and Tournament History show only basic name/date + 1st/2nd/3rd from `tournament_results`.
- No dedicated rating volume display, no cross-rank comparison, no seeds, no bracket viewer, no DP-enriched player context.

**Quick wins (presentation work only — data already present)**
- ✅ Promote `insidesp_rating` + `matches_rated` (+ nationality) to first-class columns for InsideSpin systems (`RankingsTable.tsx`, 2026-07-12).
- ✅ Display seed, race_to, current_round, status when present on history results (Alembic `061` + harvester upsert + Tournament History detail).
- Surface cross-system ranks (e.g. "also ranked X in Fargo World / Matchroom") as chips or extra columns on Competitors_Pool views. *(still open)*
- ✅ Simple matches table from `tournament_history_matches` on Tournament History detail (`GET .../matches`, 2026-07-12).
- Time filter / snapshot browser for DigitalPool_* historical (`rank_date` series). *(still open)*

**Larger surfacing items**
- Dedicated Inside Spin ratings browser + browsable recent events catalog (with location, winner, full or top-N participants).
- Player profile enrichment from DP (city/gender/DP fargo/join dates) exposed in player detail modals, rankings hover, and Tournament History player views.
- Stats / Performance / Schedule tab-style views that mirror the source SPA tabs (materialized from harvested bracket + player data).
- Inside Spin player slugs + DP `digitalpool_player_id` surfaced (and eventually used) for identity crosswalks and richer player cards.
- Gap-fill vs. authoritative indicators (IS-only events vs. DP-matched) visible in tournament lists.

All ingestion remains manual/admin-triggered per the no-automatic-scraping rule. The work here is purely about exposing what the scrapers and harvester already capture.

### 2026 Stability and Self-Healing Program (In Progress)

This track aligns with `.github/CODING_STANDARDS.md`, FastAPI/React manuals, SQLAlchemy pooling guidance, and OWASP-aligned error-handling practices.

#### Immediate (Completed)

- Fixed runtime crashers in rankings/system/auth routes (`NameError`, undefined vars, SQL placeholder mismatches).
- Fixed import-time logger initialization bug in enrichment engine.
- Rebuilt `scripts/refresh_rankings.py` to remove duplicate/broken `main()` paths.
- Corrected dependency typo in `requirements.txt`.
- Removed obsolete SQLite mounts from production Docker compose where Postgres is authoritative.

#### Short-Term (Completed)

- Enabled SQLAlchemy connection pooling (`QueuePool`) with env-driven settings.
- Enabled `pool_pre_ping` and `pool_recycle` for resilient connection reuse.
- Added database connection retry/backoff in `PostgresManager.get_connection()`.
- Standardized API error envelope with `request_id` and `X-Request-ID` response header.
- Added request ID middleware and propagated IDs into error logging context.
- Eliminated silent email dry-run success masking unless explicitly enabled (`EMAIL_DRY_RUN=1`).

#### Error Handling and Self-Healing (Completed)

- Added reusable circuit breaker service and integrated it for:
  - Stripe API calls
  - Fargo dashboard calls
  - shared scraper HTTP fetches
- Added scraper resilience controls:
  - global inter-request pacing (`SCRAPER_MIN_REQUEST_INTERVAL_SEC`)
  - stale last-known-good fallback for transient upstream failures
  - scraper reliability metrics exported via health checks
- Added background task supervisor with crash tracking, backoff restart, and degraded health signaling.

#### Frontend Resilience (Completed)

- Added route-level error boundaries across previously uncovered routes.
- Added user-facing retry UI for failed Home/Tournament History/Future Tournaments loads.
- Replaced blocking `alert()` notifications with `sonner` toast notifications.
- Added global connection status banner with retry and reconnect state.
- Standardized React Query global retry/backoff defaults.

#### Feature Completion (Completed)

- Alfa engine now consumes recent `tournament_results` + `tournament_history` for pattern analysis.
- Payment receipt workflow now supports optional email receipts (`PAYMENT_RECEIPT_EMAIL_ENABLED=1`).
- Error boundary and frontend logger now support Sentry integration when available.

#### Validation and Tests (Completed for this track)

- Added targeted backend tests for circuit breaker behavior, request ID middleware, and scraper stale fallback behavior.

### Fargo Rating Ideas (from research)

- Percentile-based divisions (post-registration cutoffs)
- Starter rating for unrated players
- Rating robustness (games count), decay by 200 games
- Fair-match calculator (match length from Fargo diff)
- Match chart (R3/R4/R5) for tournament handicapping

### Alfa Rating v2

- [ALFA_RATING_V2_SPEC.md](ALFA_RATING_V2_SPEC.md) — Full spec
- Phase 1–2 complete; Phase 3 (validation/tuning) in progress

### Feature Backlog (owner/date TBD)

| Area | Item | Notes |
|------|------|-------|
| UX | AI Coach tooltips for every page | Contextual guidance per page, similar to Tournament Wizard coach |
| i18n | Multi-language support (14+ languages) | External Pool parity; owner TBD |
| UX | Two-panel layout, sticky filters, movement indicators | |
| Admin | Bulk import with audit trail, first-run setup wizard | |
| Fargo | Case study: rating stability vs opponent strength | |
| Mobile | PWA-first option before native | |
| Observability | Structured logging, request tracing | In progress (request ID, Sentry) |
| Data/UI | Surface Inside Spin Display Rating + matches_rated as first-class columns/cards (InsideSpin_* systems) | Currently only incidental source_data extras; rating + volume is the core value of the source |
| Data/UI | Inside Spin ratings + events browser (catalog with dates/locations, full or top participants) | Tier-1 + Tier-2 data already scraped into rankings + tournament_history/results |
| Data/UI | Digital Pool cross-system rank comparison (Fargo/Matchroom/WPA variants) on Competitors_Pool lists | Parallel ranks live in source_data; no dedicated view or "also ranked" chips |
| Data/UI | Show seed / race_to / current_round / status for DP-enriched tournament fields | Only basic placement+points written to tournament_results today |
| UI | Bracket / full results / match detail viewer for harvested Digital Pool events | Rich data in tournament_history_matches (table, scheduled, scores, round, winner, extra cols); no viewer |
| Data/UI | Player profile enrichment from DP (city, gender, DP fargo, join/last_active) in modals and detail pages | Fetched by scraper; not surfaced |
| Historical/UI | Historical snapshot browser or timeline for DigitalPool_* (pro_world_rankings by rank_date) | Time series captured; only latest snapshot shown per system |

See [ROADMAP_LOWER_PRIORITY.md](ROADMAP_LOWER_PRIORITY.md) for deferred items (round robin, mobile, i18n).

### Tech Debt

- Consolidate duplicate PROJECT_ROOT definitions across routes (see CODING_STANDARDS.md)
- Timeout/retry standards documented in `.github/CODING_STANDARDS.md`
- Consider deprecating `splash_v1`, `auth_v1` if fully migrated (see CODING_STANDARDS.md)

---

## References

- [ROADMAP_LOWER_PRIORITY.md](ROADMAP_LOWER_PRIORITY.md) — Deferred items (round robin, mobile, i18n)
- [PRODUCTION_AND_IOS_READINESS.md](PRODUCTION_AND_IOS_READINESS.md) — Production checklist, iOS steps
- [EXTERNALPOOL_ANALYSIS.md](../EXTERNALPOOL_ANALYSIS.md) — Market analysis source
- [MULTI_SOURCE_DATA_INTEGRATION_PLAN.md](MULTI_SOURCE_DATA_INTEGRATION_PLAN.md) — Digital Pool + Inside Spin ingestion plan (data already being captured)
- [SCRAPER_TO_UI_DATA_MAP.md](SCRAPER_TO_UI_DATA_MAP.md) — Detailed scraper → table → page mapping (use to trace why a scraped field is not visible)
