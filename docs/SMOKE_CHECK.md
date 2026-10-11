# Post-deploy smoke check

Use this checklist after deploying Rankings Bot to production (e.g. www.probilliardssoftware.com).

## Script (quick run)

From project root (Rankings-Bot):

```bash
# Local (API on 127.0.0.1:8003)
./scripts/smoke_check.sh

# Production (after cutover)
BASE_URL=https://www.probilliardssoftware.com ./scripts/smoke_check.sh

# With login check (use env vars from .env)
ADMIN_USERNAME=your_admin ADMIN_PASSWORD=secret BASE_URL=https://www.probilliardssoftware.com ./scripts/smoke_check.sh
```

Credentials come from the project .env (e.g. ADMIN_USERNAME, ADMIN_PASSWORD); see .env.example if not set.

The script checks: `/api/health`, `/api/system/health`, `/`, `/api/rankings/wpa`, `/api/rankings/wpba`, and optionally Admin login + `/api/auth/me`. See also `scripts/verify_ports_and_health.sh` for host ports, Docker, and Admin/Director login.

## 1. Health

- [ ] **API health:** Open `https://your-domain/api/health` — expect `{"status":"healthy",...}`.
- [ ] **System health (optional):** Open `https://your-domain/api/system/health` — expect 200 and JSON.

## 2. Frontend

- [ ] **Home:** Open `https://your-domain/` — app loads (Rankings or login).
- [ ] **No console errors:** DevTools → Console — no red errors on load.

## 3. Guest

- [ ] **Rankings:** Rankings page loads; WPBA/WPA tabs work; table or “no data” shows.
- [ ] **Locked actions:** Refresh / Export show as disabled or open login when clicked (tooltips explain).

## 4. Admin

- [ ] **Login:** Sign in as Admin (credentials from `.env`).
- [ ] **Refresh:** Click Refresh — request succeeds; rankings/last-updated may change.
- [ ] **Export:** Export to CSV works.
- [ ] **Data input (Admin):** Data input page loads; Backup database button works (downloads file).

## 5. Director (optional)

- [ ] **Director login:** Sign in as Director.
- [ ] **Data input:** Data input page shows quality/audit; no Backup button (Admin only).

## 6. Other pages

- [ ] **Movement:** Movement page loads; WPBA/WPA tabs; Export to CSV if data exists.
- [ ] **Settings / Logs / System:** Load without errors.

If any step fails, see [DEPLOY_DEBUG_HTTP.md](DEPLOY_DEBUG_HTTP.md) (Debug section) and check Nginx, API logs, and CORS.
