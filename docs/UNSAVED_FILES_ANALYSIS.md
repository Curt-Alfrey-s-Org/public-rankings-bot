# Unsaved/Modified Files Analysis

**Generated:** 2026-03-15

This document analyzes modified and untracked files in the rankings-bot workspace to determine whether they should be kept (saved/committed) or reverted.

---

## Summary

| Category | Count | Recommendation |
|----------|-------|----------------|
| **Keep (intentional improvements)** | ~90+ | Save/commit |
| **Fix required** | 2 | Apply fix then save |
| **Deleted (intentional cleanup)** | ~10 | Keep deleted |
| **Untracked (new files)** | ~20 | Review and add if desired |

---

## 1. Fix Required Before Save

### `scripts/fix_poison_saigon_rankings.py` — FIXED
- **Issue:** Script did not load `.env` before importing `database`. When run standalone, `DATABASE_URL` was not set.
- **Fix applied:** Added `load_dotenv(PROJECT_ROOT / ".env")` and hostname rewrite (`postgres` → `127.0.0.1`) for running on host outside Docker.
- **Status:** Script now loads env and connects. If you see "Connection refused", Postgres is not running on localhost (e.g. it is in Docker); run the script from inside the Docker network or ensure Postgres is reachable.

### `api/routes/splash_config.py`, `api/routes/login_features.py`, `api/routes/tournament_history.py`, `api/routes/admin.py` — FIXED
- **Issue:** Used local `PROJECT_ROOT` instead of canonical import.
- **Fix applied:** Replaced with `from project_root import PROJECT_ROOT` in all four files.

---

## 2. Keep — Plan Implementation (Debug, Error Handling, Docs)

These were implemented per the debug_error_handling_features_docs plan:

| File | Change |
|------|--------|
| `docs/MONITORING_HEALTH.md` | Where logs live table |
| `docs/INDEX.md` | Troubleshooting index |
| `docs/DEBUG_CONSOLE_ERRORS.md` | Workbox, QUIC, timeouts |
| `docs/QUICK_REFERENCE.md` | Health one-liner |
| `frontend/src/lib/logger.ts` | requestId in apiCall |
| `frontend/src/lib/toast.ts` | ERROR_MESSAGES, toast.apiError |
| `frontend/src/api/client.ts` | Toast on 401/403/423/503/timeout |
| `frontend/src/hooks/useLiveUpdates.ts` | JSDoc error handling |
| `frontend/src/hooks/useWebSocket.ts` | JSDoc error handling |
| `.github/CODING_STANDARDS.md` | Timeout/retry, PROJECT_ROOT, deprecation |
| `docs/ROADMAP.md` | Immediate Data Integrity checklist, Feature Backlog |

**Recommendation:** Keep all.

---

## 3. Keep — Other Intentional Changes

- **API routes** (`auth.py`, `rankings.py`, `tournaments.py`, etc.): Production fixes, error handling, feature work.
- **Frontend** (`App.tsx`, `Leaderboard.tsx`, `client.ts`, etc.): UI improvements, error boundaries, toast integration.
- **Scripts** (`verify_production.sh`, `backup_postgres.sh`, etc.): Deployment and ops improvements.
- **Docs** (40+ files): Documentation updates, deployment guides, troubleshooting.

**Recommendation:** Keep. These represent accumulated project work.

---

## 4. Deleted Files (Intentional Cleanup)

| File | Notes |
|------|-------|
| `docker-compose.dev.yml` | Replaced or consolidated |
| `docker-compose.staging.yml` | Replaced or consolidated |
| `scripts/start-rankings-bot.sh` | Replaced by `start.sh` |
| `scripts/start_app.sh`, `start_deps.sh`, `start_gui.sh`, etc. | Consolidated into `start.sh` / `start_web.sh` |
| `nginx-config/rankings-bot-cloudflare-docker-HOST-API.conf` | Superseded |
| `production/docker-compose.host-api.yml` | Superseded |
| `docs/diagrams/setup-a-host-api.mmd` | Removed |

**Recommendation:** Keep deleted unless you need them for reference.

---

## 5. Untracked New Files

| File | Recommendation |
|------|----------------|
| `alembic/versions/040_*`, `041_*`, `042_*` | Add if migrations are applied |
| `frontend/src/pages/HotStreak.tsx` | Add if Hot Streak feature is in use |
| `scripts/start.sh`, `start_web.sh`, `start_mobile.sh` | Add (consolidated starters) |
| `scripts/switch-site.sh` | Add if used for maintenance/demo workflow |
| `docs/FIX_PRODUCTION_LOGIN_404_405.md` | Add (troubleshooting doc) |
| `docs/MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md` | Add |
| `nginx-config/maintenance/`, `rankings-bot-maintenance.conf` | Add if used |

**Recommendation:** Review each; add those that are part of active workflows.

---

## 6. Actions Taken

1. **fix_poison_saigon_rankings.py:** Added `load_dotenv()` and hostname rewrite so DATABASE_URL is loaded from `.env` when run standalone; works on host (127.0.0.1) or in Docker (postgres).
2. **PROJECT_ROOT consolidation:** Applied to `splash_config.py`, `login_features.py`, `tournament_history.py`, `admin.py`.

---

## 7. Next Steps

1. Run `cd rankings-bot && source venv/bin/activate && python3 scripts/fix_poison_saigon_rankings.py` — requires Postgres reachable (Docker or local).
2. Commit the changes you want to keep; revert any you do not.
