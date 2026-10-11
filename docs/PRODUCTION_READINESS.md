# Production readiness

**Current status:** See [PRODUCTION_STATUS_AND_NEXT_STEPS.md](PRODUCTION_STATUS_AND_NEXT_STEPS.md) for present state and next steps (web + app).

Use the project **CHECKLIST.md** (Production readiness section) as the go-live checklist. This doc summarizes the must-haves.

**Principle:** All critical processes must work correctly before go-live. That means: deploy/start/stop, API and backend, networking (Nginx → API, tunnel), web app, and (if used) mobile. Use the verification steps and test list below to confirm each area.

## Must complete before production

1. **JWT_SECRET** — Set in `.env` file. Use a strong, random value. If unset, the API uses a default and logs a startup warning; that default must never be used in production.
   - Generate one: `openssl rand -base64 32` (add the output to `.env` as `JWT_SECRET=...`).
2. **DATABASE_URL** — Production Postgres URL; must be loadable by the API (via `.env` file).
3. **Single API starter** — Docker Compose only; all deployment scripts use Docker Compose.
4. **super_admin password** — Change tornybotca1’s password after first login (or run `scripts/ensure_super_admin.py` with a new password). See [AUTH_DESIGN.md](AUTH_DESIGN.md).
5. **CORS** — Defaults include probilliardssoftware.com; set `CORS_ORIGINS` if needed.
6. **Health** — Use `/api/health` for monitoring.
7. **Backups** — Postgres and critical data; e.g. `scripts/backup_postgres.sh` and cron.
8. **Cloudflare Tunnel** — For full deploy (site reachable via domain), add **TUNNEL_TOKEN** to `.env`. Get it from Cloudflare Zero Trust → Tunnels → your probilliards tunnel → Configure. Tunnel container name is **cf-probilliards**.

## Verify

After setting JWT_SECRET and DATABASE_URL and starting the API, run from project root:

```bash
./scripts/verify_production.sh
```

This checks: JWT_SECRET set and not default, DATABASE_URL set, `/api/health` 200, and optionally that Docker containers are running. It does not echo secrets. Fix any `[FAIL]` items before go-live. Then run the **process and module verification** list below (deploy, API, networking, web, and mobile as applicable) so that all critical processes work correctly.

## After verification passes

1. **Set super_admin password** — Set `SUPER_ADMIN_PASSWORD` in `.env` before first start (no default; production refuses to start without it on a fresh DB). The first login forces a password change. To reset from the server:  
   `SUPER_ADMIN_PASSWORD='your-new-password' python3 scripts/ensure_super_admin.py`  
   (Then restart is not required; next login uses the new password.)
2. **Smoke check with login** — From project root:  
   `ADMIN_USERNAME=tornybotca1 ADMIN_PASSWORD=yourpassword BASE_URL=https://www.probilliardssoftware.com ./scripts/smoke_check.sh`  
   (Use local BASE_URL if testing on the server.)
3. **CORS / backups** — Confirm CORS_ORIGINS if using other domains; ensure backup cron runs (e.g. `scripts/backup_postgres.sh`).

## Process and module verification (test list)

Before go-live, confirm each area works. Run from **Rankings-Bot** project root unless noted. Fix any failure before treating the system as production-ready.

### 1. Deploy and lifecycle

| What to test | How to verify | Script / command |
|--------------|----------------|-------------------|
| Full deploy | Full deploy runs to completion; API health 200 after; Nginx can reach API | `./scripts/full_deploy.sh` — uses Docker Compose for all services. Then: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8003/api/health` → 200. **Modules:** See script header in `scripts/full_deploy.sh` (networks → Postgres when prod → app stack → API health wait → nginx → tunnel). |
| Start all | Start script brings up stack and API responds | `./scripts/start.sh` (Docker) or `./scripts/start.sh --dev` (host). Then health check as above. |
| Stop all | Stop script brings down stack cleanly | `./scripts/stop.sh`. Then health check → non-200 or connection refused. |
| Update website (rebuild) | Rebuild script runs; site serves new frontend | Admin UI → Update website (with log), or `./scripts/rebuild_website_now.sh`. Hard refresh browser; check version or content. |

### 2. Config and environment

| What to test | How to verify | Script / command |
|--------------|----------------|-------------------|
| Production config | JWT_SECRET and DATABASE_URL set and valid; no default JWT | `./scripts/verify_production.sh` — all [PASS]. |
| Health endpoint | API reports healthy | `curl -s http://127.0.0.1:8003/api/health` (or BASE_URL) → 200 and `"status":"healthy"`. |

### 3. Backend and API

| What to test | How to verify | Script / command |
|--------------|----------------|-------------------|
| API health + system | Health and system health return 200 | Smoke check (below) or: `curl -s -o /dev/null -w "%{http_code}" $BASE_URL/api/health` and `$BASE_URL/api/system/health`. |
| Auth (login + token) | Admin login and /api/auth/me with Bearer token | `ADMIN_USERNAME=... ADMIN_PASSWORD=... BASE_URL=... ./scripts/smoke_check.sh` (includes login when env set). Or `scripts/diagnose_login.sh`. |
| Rankings API | Rankings endpoints return data or valid empty | Smoke check, or: `curl -s "$BASE_URL/api/rankings/wpba?limit=5"` and `.../api/rankings/wpa?limit=5` → 200. |
| Database | Postgres reachable; schema present; rankings table usable | `pytest tests/backend/test_database.py -v` (with DATABASE_URL). Or API health 200 implies DB used by API is up. |
| Backend imports and startup | App and key modules load without error | `python3 tests/startup_test.py`. Optional: `python3 tests/runner.py` (backend/imports). |

### 4. Networking and proxy

| What to test | How to verify | Script / command |
|--------------|----------------|-------------------|
| Nginx → API | From Nginx container or host, API health 200 | `./scripts/diagnose_rankings_bot_gateway.sh`. Or: from host, `curl -s http://127.0.0.1:8003/api/health` → 200. |
| Public URL (if used) | HTTPS site loads and API responds | `curl -sI https://www.probilliardssoftware.com/` and `curl -s https://www.probilliardssoftware.com/api/health`. |
| CORS | Browser can call API from frontend origin | Load web app from production URL; open DevTools Network; trigger API call; no CORS error. |

### 5. Web app (frontend)

| What to test | How to verify | Script / command |
|--------------|----------------|-------------------|
| App load | Root and main routes load without 5xx | `./scripts/smoke_check.sh` (includes `/` and rankings). See [SMOKE_CHECK.md](SMOKE_CHECK.md). |
| Guest: rankings | Rankings page and WPBA/WPA tabs work | Manual: open Rankings; switch tabs; table or “no data” visible. |
| Admin: login, refresh, export | Admin can log in, refresh rankings, export CSV | Manual: Settings → Admin; login; Refresh rankings; Export CSV. |
| Director (if used) | Director can access allowed pages | Manual: log in as Director; Data input / Director flows. |

### 6. Mobile (React Native CLI — not Expo)

| What to test | How to verify | Script / command |
|--------------|----------------|-------------------|
| API base URL | App points at production API | Configure in `src/` (e.g. API base constant / env). Root `package.json` — pure RN; **no** `mobile/` Expo folder. |
| Login and rankings | App can log in and load rankings | Manual: open app; log in; open Rankings; data or “no data”. |
| Build | iOS / Android native projects | Committed `ios/` and `android/` (RN 0.81 template). From repo root: `npm install`, `cd ios && bundle exec pod install` (see [IOS_PURE_REACT_NATIVE_SETUP.md](IOS_PURE_REACT_NATIVE_SETUP.md)), `npx react-native run-ios` / `run-android`. |

### 7. Automated smoke check (summary)

Run the script that covers health, system health, frontend, rankings, and optional admin login:

```bash
# Local
./scripts/smoke_check.sh

# Production URL (and optional login)
ADMIN_USERNAME=your_admin ADMIN_PASSWORD=secret BASE_URL=https://www.probilliardssoftware.com ./scripts/smoke_check.sh
```

See [SMOKE_CHECK.md](SMOKE_CHECK.md) for the full checklist. For ports, Docker, and Admin/Director login: `./scripts/verify_ports_and_health.sh`.

## References

- **CHECKLIST.md** (repo root) — Production readiness checklist; check off as you go.
- **UPGRADE_AND_VERSIONS.md** — Docker Compose V2 and stack versions (required for Docker deploy path).
- **AUTH_DESIGN.md** — Auth and required config (JWT_SECRET, DATABASE_URL).
- **PRODUCTION_DEPLOYMENT.md** — Docker deployment standards.
- **rankings-bot-api.service.example** — systemd unit; must include `EnvironmentFile` to your `.env`.
