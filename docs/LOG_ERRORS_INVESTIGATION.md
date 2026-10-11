# Log Errors Investigation & Fixes

Investigation of `rankings_bot.log` errors and recommended actions.

## Summary

| Issue | Severity | Status |
|-------|----------|--------|
| `users.nickname` column missing | **Critical** | Fixed (migration 020) |
| Live updates "No event loop" | Medium | Fixed |
| Fargo sync WPA_Men failed=1 | Low | Expected (see below) |
| 401 on module-lights, health | Low | By design |
| 404 head-to-head | Low | Route/player lookup |
| 422 rankings endpoints | Low | Validation/params |

---

## 1. Critical: `column users.nickname does not exist`

**Symptom:** Login fails, super_admin bootstrap fails, auth errors.

**Cause:** User model has `nickname` but DB schema never had a migration for it.

**Fix applied:** Migration `020_add_users_nickname.py` adds the column.

```bash
cd Rankings-Bot && python3 -m alembic upgrade head
```

---

## 2. Live Updates: "No event loop available, event not broadcast"

**Symptom:** `[LIVE-UPDATES] No event loop available, event not broadcast` when scheduler jobs complete.

**Cause:** Scheduler runs in a thread pool; `asyncio.get_event_loop()` / `get_running_loop()` return nothing in that context.

**Fix applied:**
- `api/services/live_updates.py`: Store main event loop via `set_main_event_loop(loop)`; use it in `publish_scraper_event()` for `run_coroutine_threadsafe`.
- `api/main.py`: Call `set_main_event_loop(asyncio.get_running_loop())` at lifespan startup.

---

## 3. Fargo Sync WPA_Men failed=1

**Symptom:** `[STARTUP] Fargo sync WPA_Men failed count: 1` (recurring).

**Cause:** One player in WPA Men rankings is not in Fargo API Top-pool_opt_in and doesn't fuzzy-match. This is expected; unmatched players are logged to `admin_messages` for manual review.

**Action:** No code change. If you want to identify the player, check `admin_messages` for Fargo problem names.

---

## 4. 401 Unauthorized on `/api/system/module-lights`, `/api/system/health`

**Symptom:** `Auth: no credentials (Authorization header missing or not Bearer)`.

**Cause:** These endpoints require `require_admin` or `require_super_admin`. Frontend or monitoring may call without a token.

**Options:**
- **Module-lights:** Only shown to super_admin; ensure frontend sends Bearer token when user is logged in as super_admin.
- **System health:** Use public `/api/health` for monitoring; `/api/system/health` is for admin dashboard.
- **Smoke checks:** Use `/api/health` for unauthenticated checks; use `/api/system/health` only when `ADMIN_USERNAME`/`ADMIN_PASSWORD` are set.

---

## 5. 404 on Head-to-Head (`/api/players/{name}/head-to-head/{opponent}`)

**Symptom:** 404 for paths like `/api/players/debbie/head-to-head/alison`.

**Cause:** Player name lookup or route not finding a match. Names may be case-sensitive or require exact DB match.

**Action:** Verify player names exist in DB and match the route format. Check `api/routes/head_to_head.py` for lookup logic.

---

## 6. 422 on Rankings Endpoints (`/api/rankings/wpa-women`, `/api/rankings/wpba-women`)

**Symptom:** 422 Unprocessable Entity.

**Cause:** Usually validation (query params, body). Check request format (e.g. `limit`, `offset`, `system`).

**Action:** Inspect request logs for validation error detail; ensure frontend sends valid params.

---

## Quick Reference

| Endpoint | Auth | Use |
|----------|------|-----|
| `/api/health` | None | Load balancer, uptime monitors |
| `/api/system/health` | Admin | Admin dashboard, self-tests |
| `/api/system/module-lights` | Super admin | Status lights (backend, api, DB, etc.) |
