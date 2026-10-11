# Rankings Bot Roadmap

## Current priority (most important)

- [ ] **Get the rankings bot website working correctly** — https://www.probilliardssoftware.com must load, show the app, and stay up. Deploy with `./scripts/full_deploy.sh --force-docker`. See `docs/START_WEBSITE.md` and `docs/DEPLOY_WEBSITE.md`.

## Production Readiness Plan — June 2026 audit refresh

**State as of 2026-06-09:** stack deployed and healthy (`production/docker-compose.prod.yml`:
postgres ×2, redis, api, celery — all containers `healthy`; https://www.probilliardssoftware.com
returns 200; `/api/health` OK). FastAPI uses the lifespan pattern (`api/main.py`), SQLAlchemy 2 +
Alembic (43 migrations), Python 3.12 base image, central monitoring exporters running.
The items below are what still separates "running" from "production-grade". Networking constants
are **immutable** throughout this plan: `tunnel_network`, nginx `proxy_pass` targets, and the
Rankings Bot API port contract (`8003`, container-only behind probilliards-nginx per
`docs/PORT_MANAGEMENT.md`) must not change.

### P0 — Production blockers (do first)

- [x] **Remove default-credential fallbacks from production compose.** *(Done 2026-06-09:
  the four `*_PASSWORD` vars now use `${VAR:?Set … in .env}`; `.env.example` documents them.
  **Operator action required before the next `docker compose up`: the live `.env` does not yet
  define `SUPER_ADMIN_PASSWORD` / `ADMIN_PASSWORD` / `DIRECTOR_PASSWORD` / `USER_PASSWORD` —
  add strong values or compose will fail loudly by design.** Verified: `docker compose config`
  passes with values set, fails with the error message when missing.)*
  *Compose interpolation docs:*
  https://docs.docker.com/reference/compose-file/interpolation/ ; Twelve-Factor III (config in env):
  https://12factor.net/config
- [x] **Reduce or isolate the Docker socket mount in `rankings-bot-api`.** *(Done 2026-06-09:
  socket mount + `group_add` removed from `production/docker-compose.prod.yml`. Admin
  "Update website" / "Full deploy" now write a request file to `DEPLOY_REQUEST_DIR`
  (`logs/deploy-requests/`, inside the existing `./logs` bind mount); a host-side
  systemd path/oneshot pair (`production/systemd/rankings-bot-deploy.{path,service}` →
  `scripts/deploy_request_dispatcher.sh`, action-allowlisted) runs the same repo scripts on the
  host and appends to the same log files the API streams. Single owner stays with Compose.
  **Operator action required: install + enable `rankings-bot-deploy.path` before the next
  `docker compose up` — see `docs/ADMIN_DEPLOY_HOST_DISPATCH.md`.**)*
  Docker socket access is root-equivalent on the host
  (https://docs.docker.com/engine/security/#docker-daemon-attack-surface).
- [x] **Migrate password hashing off passlib.** *(Done 2026-06-09: `api/auth.py` now uses
  `pwdlib` `PasswordHash((Argon2Hasher(), BcryptHasher()))` — Argon2id for new hashes, bcrypt
  kept so existing hashes verify and transparently upgrade via `verify_and_update()` on next
  successful login (legacy 72-byte truncation preserved for bcrypt verification only).
  passlib + `bcrypt<4.1` pins removed from `requirements-api.txt` / `requirements.txt`; replaced
  with `pwdlib[argon2,bcrypt]>=0.3.0`. New tests: `tests/backend/test_password_hashing.py`
  (16 cases: argon2 hash, legacy bcrypt verify, re-hash path, >72-byte edge, failure paths).
  Full suite 52 passed; API image rebuilt with new deps and smoke-tested. Still TODO:
  propagate the same shape to market-pie5-bot.)*
  FastAPI security tutorial: https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/#password-hashing ;
  pwdlib guide: https://frankie567.github.io/pwdlib/guide/
- [ ] **Raise automated test coverage on the API core.** `tests/backend/` has 7 test files for a
  large API surface (auth, director import, tournaments, scrapers, AI routes). Minimum production
  gate: auth flows (login/roles/expiry), rankings read endpoints, director import happy + failure
  path, health endpoints. Wire into a pre-deploy gate in `scripts/full_deploy.sh` (deploy aborts on
  red). pytest + httpx `ASGITransport` pattern per FastAPI testing docs:
  https://fastapi.tiangolo.com/advanced/async-tests/

### P1 — Hardening & ops gaps

- [ ] **Backup restore drill.** Backups exist (`scripts/automated_backup_with_retention.sh`, cron
  per NEXT_STEPS.md §1). What's untested is restore: document and run a quarterly
  `pg_restore`-into-scratch-container drill; record last-drill date in `docs/POSTGRES` docs.
- [ ] **Pin production dependency versions.** `requirements-api.txt` uses open-ended `>=` ranges,
  so rebuilds can silently change versions (drift). Generate a lock/constraints file
  (`pip-compile` or `pip freeze` constraints) used by `Dockerfile.base`; upgrade deliberately, not
  as a rebuild side effect. *pip constraints:* https://pip.pypa.io/en/stable/user_guide/#constraints-files
- [ ] **Single source for Python deps.** Root `requirements.txt` is a merged "universal bot" file
  (includes yfinance/backtrader/etc. that this repo doesn't serve) while the image builds from
  `requirements-api.txt`. Decide one authoritative file per artifact and mark the other clearly or
  delete it — duplicated dep lists are drift.
- [ ] **uvicorn workers review.** `UVICORN_WORKERS=4` with per-worker pools (`DB_POOL_SIZE=5`,
  `MAX_OVERFLOW=10`) ⇒ up to 60 connections vs Postgres default `max_connections=100` (shared with
  Celery + exporters). Verify headroom; document in `docs/PORT_MANAGEMENT.md` companion. FastAPI
  deployment docs on workers/process managers: https://fastapi.tiangolo.com/deployment/server-workers/
- [ ] **Keep no-automatic-scraping posture.** Any new refresh feature stays manual/admin-triggered
  (workspace rule `no-automatic-scraping.mdc`); verify `SKIP_BACKGROUND_SCHEDULER` honored on every
  deploy path.

### P2 — Supported-version upgrades (frontend toolchain is EOL)

- [ ] **Vite 5.4 → 7/8.** Per https://vite.dev/releases (June 2026): regular patches only for
  `vite@8.0`, important fixes for `7.3`, security-only for `6.4` — **Vite 5 is unsupported**.
  Recommended path per the Vite 8 announcement (https://vite.dev/blog/announcing-vite8): migrate
  5→6→7 via the migration guides, optionally stage `rolldown-vite` on 7 before 8.
- [ ] **Node engines floor.** `frontend/package.json` declares `"node": ">=18"`; Node 18 reached
  EOL 2025-04-30 (https://nodejs.org/en/about/previous-releases). Raise to `>=20.19` (or 22 LTS) —
  also required by Vite 7+. Update the `node:20-alpine` builder reference when bumping.
- [ ] **React Router v6 / TanStack Query / Zustand major-version review** during the Vite bump —
  React Router 7 is the supported line (https://reactrouter.com/upgrading/v6); do as one toolchain
  PR with the frontend build verified through `scripts/build_frontend_with_docker.sh`.
- [ ] **psycopg2-binary → psycopg 3 (or source-built psycopg2) for production.** psycopg2 docs
  advise the `-binary` wheel is not recommended for production use
  (https://www.psycopg.org/docs/install.html#psycopg-vs-psycopg-binary); SQLAlchemy 2 fully
  supports psycopg 3 (https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg).

### P3 — Repo hygiene & doc drift

- [ ] **Clean the repo root.** ~220 root entries including shell-accident files (`e:`, `e:.save`,
  `by tournament participation:")`, `, {with_stops} with stops > 0")`), tarball backups, ad-hoc
  logs, and dozens of session-summary MDs. Move historical session docs under `docs/archive/`,
  delete junk files, and gitignore generated logs/backups. (Docs-vs-code drift control per
  workspace `engineering-standards-and-drift-control.mdc` §5.)
- [ ] **Roadmap truth pass.** Phases above are marked ✅ COMPLETE; reconcile against reality after
  each P0/P1 item lands so this file stays the single planning source.
- [ ] **LiteLLM client parity.** `api/services/litellm_client.py` is the **workspace reference
  implementation** — when it changes, propagate the shape (async httpx, graceful degrade,
  telemetry) to the other bots, not the reverse. Brain endpoints stay on `hub`
  (`http://192.0.2.30:8413`); never loopback from `apps`.

---

## AI / maintainer doc hooks (done here; copy pattern to other repos)

- See `docs/AI_INLINE_DOC_REF_PROCESS.md` and `docs/INDEX.md` § *AI & maintainer conventions*. Sibling bots: add a roadmap backlog item pointing at `../rankings-bot/docs/AI_INLINE_DOC_REF_PROCESS.md`.

---

## Phase 1.5: Web GUI Rankings Display ✅ COMPLETE

### Frontend Components:
- [x] Create `frontend/src/pages/Rankings.tsx` - Main rankings page component
- [x] Create `frontend/src/components/RankingsTable.tsx` - Reusable table component with sort/filter
- [x] Create `frontend/src/api/rankings.ts` - API client functions for rankings endpoints
- [x] Create `frontend/src/components/PlayerDetailModal.tsx` - Modal for player details/history

### Frontend Features:
- [x] Add Rankings route to `frontend/src/App.tsx`
- [x] Update `frontend/src/components/Sidebar.tsx` with Rankings navigation item
- [x] Implement WPBA/WPA tab switching in Rankings page
- [x] Add search/filter functionality for player names and countries
- [x] Implement pagination for large ranking lists
- [x] Add sortable columns (rank, name, country, points)
- [x] Add "Export to CSV" functionality
- [x] Display last updated timestamp
- [x] Add refresh button to manually trigger data update

### Polish & Testing:
- [x] Add loading states and error handling
- [x] Ensure responsive design (mobile/tablet/desktop)
- [x] Add TypeScript types for rankings data
- [ ] Test with real WPBA/WPA data from API (manual / server)
- [x] Simplify UI to rankings-first (sidebar shows Rankings, Settings, Logs, System only)

### Documentation:
- [x] Update `frontend/README.md` with rankings component information
- [ ] Add screenshots/demo to main README.md (optional)

---

## Phase 2: Data Collection & Validation ✅ COMPLETE

- [x] Validate WPBA scraper against live source; handle rate limits and errors — `scrapers/fetch_utils.py` + WPBA uses retries and Retry-After
- [x] Validate WPA scraper against live source; handle rate limits and errors — WPA uses same retry/rate-limit handling
- [x] Add scheduled/periodic refresh (cron or systemd timer) for rankings data — see `scripts/refresh_rankings.py` and `docs/SCHEDULED_REFRESH.md`
- [x] Store and expose ranking history (snapshot_date) for trend views
- [x] Data quality checks: duplicate players, missing fields, point consistency
- [x] Optional: API endpoint for “last N snapshots” or “rank over time” for a player

---

## Phase 2.2: Guest Showcase — “Show the bells and whistles, look but don’t use”

**Goal:** Let guests see everything the bot can do (full UI visible) but without using advanced features. All tooltips work so guests can learn what the bot is capable of. Add a strong intro and a splash page featuring WPBA/WPA players.

### Guest experience
- [x] **Show full UI to guests** — All pages, sidebar items, and controls are visible (Rankings, Settings, Logs, System, Refresh button, Export, etc.) so guests can explore the interface.
- [x] **Lock advanced actions for guests** — Buttons/actions that change data or config (Refresh, Export, Settings changes, Run Test, etc.) are disabled or show “Sign in as Admin/Director to use” (or open login modal); guests can only look and navigate.
- [x] **Tooltips everywhere for guests** — Every feature that’s locked or advanced has a working tooltip (and optional short “What this does” copy) so guests understand what the bot is capable of (e.g. “Refresh rankings from WPBA/WPA sources”, “Export rankings to CSV”, “Run system self-tests”).
- [x] **Intro / “What this bot does”** — A compelling intro (e.g. on Login page, first-time guest landing, or a small “About” / “Capabilities” panel) that explains: tracks WPBA & WPA rankings, refresh from official sources, export, history, system health, etc., so guests get a clear picture of capabilities.

### Splash page
- [x] **Splash page with player imagery** — A dedicated splash (or enhanced existing splash) that shows photos of women WPBA and WPA players to set the tone and celebrate the sport.
- [x] **Highlight Debbie Teichert** — Include a prominent spot for Debbie Teichert (photo + short caption) on the splash or in a “Featured players” section.
- [x] **Legal / licensing** — Use only images we have rights to (e.g. official WPBA/WPA media, licensed, or placeholder until licensed); add credits/captions where needed.

### Theme & layout (from WPBA/WPA sites)
- [x] **Scrape WPBA and WPA sites for themes and layouts** — Fetch or document the official WPBA and WPA websites (colors, fonts, header/footer patterns, card/table styles, spacing) so the Rankings Bot UI can match their look and feel.
- [x] **Document design tokens** — Capture primary/secondary colors, typography (font families, sizes), logo usage, and layout patterns (e.g. nav style, content width, rankings table styling) into a short design doc or tokens file.
- [x] **Apply matching theme in app** — Use `docs/DESIGN_TOKENS_WPBA_WPA.md` (or a respectful derivative) for splash page, guest intro, and main UI so the app feels aligned with WPBA/WPA branding while remaining clearly our product.

### Creator & business attribution (attract more business)
- [x] **Advertise creator and business in the app** — Prominently show who built the app and where to find more: creator name (Example Example), business site **alfaqd.com**, GitHub account, and **x.com/example**, so guests and visitors can connect and attract more business.
- [x] **Self-hosted cloud messaging** — Mention that the site is self-hosted (e.g. “Self-hosted by alfaqd.com” or “Built and hosted by Example Example — custom cloud & web”) in footer, About, or splash so visitors know you run your own cloud/websites and can hire you for similar work.
- [x] **Placement** — Add creator/business links in at least one of: app footer, Login page, splash page, or dedicated “About / Built by” section; keep it visible to guests without cluttering the main workflow.

### Implementation notes
- Reuse existing role checks: guest sees full UI, `isAdmin`/`isDirector` gates only disable or hide the *action* (click), not the visibility of the control or its tooltip.
- Ensure all interactive elements that are disabled for guests have `title`/`aria-label` and optional tooltip component so screen readers and hover both work.

---

## Phase 2.5: Directors Account (data input) ✅ COMPLETE

**Goal:** Add a **Directors** role — users who can **input data** (e.g. rankings, tournament results) in addition to viewing.

**Current roles:** Guest (view only), Admin (full access: refresh, settings), Director (data input + view).

- [x] Backend: Add `director` role to auth (JWT, login flow, credentials from env or separate store)
- [x] Backend: Protect “data input” endpoints (e.g. submit rankings, bulk import) with `require_director` or `require_director_or_admin`
- [x] Frontend: Directors login option on Login page (or separate Director sign-in)
- [x] Frontend: Data input UI for Directors (forms / upload for rankings or tournament data); hide or restrict for Guest, allow for Director and Admin
- [x] Optional: Director-only settings or audit log for who submitted what
- [x] Manual entry and file import: Directors can enter rows (rank, name, points, country) or upload PDF, DOCX, XLSX, XML, CSV, TXT; see docs/DIRECTOR_IMPORT.md.

---

## Phase 3: Ranking Engine ✅ COMPLETE

**Goal:** Use stored rankings and history to compute or surface derived metrics, trends, and reporting (e.g. rank-over-time, movement, optional projections). Build on Phase 2 history and quality checks.

- [x] Define scope: rank-over-time views, movement detection, optional “player comparison” or “snapshot diff”
- [x] Backend: optional movement/change detection (reuse or extend `ranking_changes` table)
- [x] API: endpoints for trend/movement data (e.g. “rank over time” already exposed; add movement or snapshot-diff if needed)
- [x] Frontend: optional “Rank over time” or “Movement” view using existing player history and snapshots API
- [x] Documentation: document Phase 3 capabilities and API for reporting

---

## Phase 4: Automation & Integration ✅ COMPLETE

**Goal:** Automate refresh, optional notifications, and integrations so the bot runs reliably without manual steps.

- [x] Optional: in-app or email notification when rankings change (e.g. after scheduled refresh)
- [x] Optional: backup/export of DB or snapshots (e.g. script or Admin-only export)
- [x] Document or harden health/status (e.g. /api/health, self-test) for monitoring
- [x] Optional: webhook or external integration (e.g. post refresh summary to a URL)

---

## Phase 5: UI & Reporting ✅ COMPLETE

**Goal:** Improve reporting and UI (exports, links to docs, optional Admin backup button).

- [x] Optional: Admin “Backup DB” button on Data input or Settings (downloads /api/rankings/backup)
- [x] Optional: link to email notifications doc (docs/NOTIFICATIONS_EMAIL.md) from Settings or Rankings
- [x] Optional: additional report views or exports (e.g. movement CSV)

---

## Final: Update master setup script ✅ COMPLETE

**Goal:** Keep `setup.sh` (and any related setup docs) in sync with the project so a fresh run installs and configures everything that has been added or fixed.

- [x] Ensure `setup.sh` installs/checks all required dependencies (Python, pip, venv; Node/npm for frontend if needed)
- [x] Ensure database init runs current schema (e.g. `database/schema.sql`), including any new tables (e.g. audit_log)
- [x] Document or run API/frontend start steps (e.g. start bot server, `cd frontend && npm install && npm run build` or dev)
- [x] Mention or copy `.env.example` so users know required env vars (e.g. JWT_SECRET, ADMIN_*, DIRECTOR_*)
- [x] Optional: reference desktop icon / start script and scheduled refresh (e.g. `scripts/refresh_rankings.py`, cron/systemd) in final instructions

---

## Deploy, Debug, Test & Fixes ✅ COMPLETE

**Goal:** Deploy the app to the website, run tests, find and fix errors (including HTTP and API issues).

- [x] **Deploy to website** — Deploy Rankings Bot to production (e.g. www.probilliardssoftware.com); Docker, Nginx, build frontend, run API. *(See docs/DEPLOY_WEBSITE.md and docs/DEPLOY_DEBUG_HTTP.md.)*
- [x] **Test** — Run full test suite (startup tests, backend integration, frontend); test with real WPBA/WPA data from API where possible. *(Scraper tests fixed: patch `get_with_retry` instead of `requests`.)*
- [ ] **Debug** — Debug runtime issues (logs, browser console, API responses).
- [x] **Find errors** — Identify and document errors (scrapers, auth, CORS, 404s, timeouts, etc.). *(Found: tests/backend/test_scrapers.py patched wrong module.)*
- [x] **Fix HTTP and API** — Fix HTTP issues (proxying, headers, status codes) and API issues (endpoints, errors, CORS, base URL / `VITE_API_URL`). *(Fixed: scraper unit tests; see docs/DEPLOY_DEBUG_HTTP.md for production HTTP/API checklist.)*

---

## Future / What's next (optional)

**Goal:** Optional improvements after launch.

- [x] Test with real WPBA/WPA data from API on a live or staging server (Phase 1.5 optional). *(Steps: docs/DEPLOY_DEBUG_HTTP.md — “Test with real WPBA/WPA data”.)*
- [ ] Add screenshots or short demo to main README (Phase 1.5 optional).
- [x] Post-deploy: smoke-check production (health, login, rankings load, refresh as Admin). *(Checklist: docs/SMOKE_CHECK.md.)*
- [x] Optional: monitoring/alerting (e.g. health endpoint + cron or Uptime Robot). *(See docs/MONITORING_HEALTH.md — external monitoring.)*
- [x] Optional: more report views or exports; link to notifications doc from Settings. *(Settings → Alerts: “Learn more about email notifications” links to doc.)*

---

## Next step (planned): research + audit subagent pass

Run the two-stage subagent workflow developed in `alfa-ai/docs/audit/` during the May 2026 ALFa AI architectural audit. The pattern surfaced 64 findings (17 Critical) on alfa-ai; we want the same coverage on every active repo before resuming feature work.

1. **Research Agent** — gathers OFFICIAL upstream docs for every technology this repo uses (versions, security posture, best practices, deprecations). Writes per-component facts + an audit checklist to `docs/audit/research/<component>.md` and a master `docs/audit/research/INDEX.md`.
2. **Audit Agent** — reads the research files, audits this repo against the embedded checklists + cross-cutting checks (internal-doc consistency, stale references, security-currency vs published CVEs, cluster-rules compliance). Writes findings + a severity-ranked remediation backlog to `docs/audit/audit-findings.md`.

Both passes are read-only on the host stack — they only write into the new `docs/audit/` directory. Remediation is gated on explicit per-finding approval.

**Reference workflow:**
- Pattern: `/home/ansible/alfa-ai/docs/audit/`
- Research output format: `/home/ansible/alfa-ai/docs/audit/research/INDEX.md`
- Audit output format: `/home/ansible/alfa-ai/docs/audit/audit-findings.md`

Added 2026-05-13 after the alfa-ai audit proved the pattern at scale.

---
