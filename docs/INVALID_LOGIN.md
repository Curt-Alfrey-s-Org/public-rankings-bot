# Invalid Login at www.probilliardssoftware.com

When the site shows "Invalid username or password" (401), work through this checklist.

## How login works

**Credentials:** Login is validated only from the database (`users` table). No env or file fallbacks at login. See **docs/AUTH_DESIGN.md**. Required in `.env`: `JWT_SECRET`, `DATABASE_URL`. User/password in `.env` are optional (bootstrap-only). If you can't log in, the DB password for that username doesn't match.

## 1. Run the login diagnostic

On the server (where the API runs):

```bash
cd /home/ansible/rankings-bot/Rankings-Bot
./scripts/diagnose_login.sh
```

Optionally test via public URL:

```bash
BASE_URL=https://www.probilliardssoftware.com ./scripts/diagnose_login.sh
```

This checks: API health, POST /api/auth/login (optionally with credentials from `.env` for testing), and public URL reachability.

## 2. API must have JWT_SECRET and DB

Login is validated from the **database** only. The API needs:

- **JWT_SECRET** (required) — for signing tokens
- **DATABASE_URL** (required) — so it can read the `users` table

User/password in `.env` are optional (bootstrap-only). See **docs/AUTH_DESIGN.md**.

**If the API runs under systemd:** It does **not** load `.env` by default. Add to the service file:

```ini
EnvironmentFile=/home/ansible/rankings-bot/Rankings-Bot/.env
```

Then: `sudo systemctl daemon-reload && sudo systemctl restart rankings-bot-api`

**If the API runs in Docker:** Ensure the container has these env vars (e.g. from `docker-compose` or `env_file: .env`). **Important:** `DATABASE_URL` must use the Docker container hostname (Postgres is Docker-network-only, no host port). Example: `DATABASE_URL=postgresql://rankingsbot_user:PASSWORD@rankings-bot-postgres:5432/rankingsbot`. See docs/DOCKER_POSTGRES_ONLY.md.

**If the API runs manually:** Start it from the project root after sourcing `.env`, or export the variables before starting uvicorn.

## 3. Use credentials that exist in the database

Login checks the **database** only.

**First login:** There is no default password. Set `SUPER_ADMIN_USERNAME` / `SUPER_ADMIN_PASSWORD` in `.env`; the API creates that super_admin at startup (production refuses to start without it) and forces a password change at first login; use it to create admin accounts from the app. See **docs/AUTH_DESIGN.md**. If that doesn't work, run `python3 scripts/ensure_super_admin.py` on the server (recovery). For Bama, create from the app or run `scripts/set_bama_admin.py`.

**Optional .env:** Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `.env` (e.g. `ADMIN_USERNAME=Bama`, `ADMIN_PASSWORD=YourSecurePassword`). Restart the API. Bootstrap creates that admin; then log in at the site with that username and password. No script. See **docs/AUTH_DESIGN.md**.

**Already deployed but can’t log in:** Run `python3 scripts/set_bama_admin.py` on the server to set or reset the Bama admin password (recovery). See **docs/AUTH_DESIGN.md**.

**Specific user can't log in (e.g. debbieltstup):** The user may not exist or has the wrong password. Fix options: (1) Log in as admin/super_admin, go to **Settings → Admin → User management**, click **Edit role** for the user, then use **Reset to default password** or **Set custom password**. The user must change the password on next login. (2) On the server, run `python3 scripts/create_or_reset_user.py USERNAME [role]` — you will be prompted for the new password. Example: `python3 scripts/create_or_reset_user.py Debbieltstup user`.

**Super admin (bootstrap):** Created only from `SUPER_ADMIN_USERNAME` and `SUPER_ADMIN_PASSWORD` in `.env` (no default password). **403 "Password change required"** after login means the account still has `must_change_password` set: change the password first (the web app shows the gate automatically).

### Super admin account shows role "user" (can't access admin / Settings)

If in Settings → Admin you see the super_admin account with role **user**, that account will log in but won’t have admin or super_admin access. Only a **super_admin** can set another user’s role to super_admin in the UI, so you must fix it on the server:

1. **On the server** (where the API and DB run):
   ```bash
   cd /home/ansible/rankings-bot/Rankings-Bot
   source .env 2>/dev/null || true
   python3 scripts/ensure_super_admin.py
   ```
   This sets user **tornybotca1** to role `super_admin` and the password you provide via `SUPER_ADMIN_PASSWORD`.

2. **Log in** at the site with **tornybotca1** and that password. You’ll have full super_admin access.

3. Optionally, in Settings → Admin, change any other user’s role (including to super_admin) if needed.

## 4. Frontend must call the same API

Production frontend should use **same-origin** so the login request goes to `https://www.probilliardssoftware.com/api/auth/login`. Rebuild with:

```bash
cd frontend
VITE_API_URL= VITE_WS_URL= npm run build
```

Then redeploy (restart API if it serves `frontend/dist`, or copy `frontend/dist` to the right place).

## 5. Database is the only source for login

The backend validates **only** against the database. If a `User` exists, login uses that user's **hashed password**. To fix "invalid login": use the password that is stored in the DB for that username, or update the password in the DB (via the app or direct DB update). Env vars do not override existing users.

## 6. HTTP and Docker

- **502 Bad Gateway:** Nginx cannot reach the API. Run `sudo ./scripts/diagnose_rankings_bot_gateway.sh` and fix any reported issue (API on 8003, UFW, tunnel).
- **503 or "Database unavailable" after rebuild:** The API container cannot reach Postgres. Set `DATABASE_URL` so the host is reachable from the container (e.g. `host.docker.internal` or host IP; see section 2). Restart the API container after changing env.
- **CORS:** If the browser blocks the request, add the site origin to `CORS_ORIGINS` and restart the API.
- **Timeout:** Increase frontend timeout or check that the API and Nginx are responding quickly.

## Quick test (curl)

From the server, use a username and password that exist in the database:

```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"username":"YOUR_DB_USERNAME","password":"YOUR_DB_PASSWORD"}' \
  http://127.0.0.1:8003/api/auth/login
```

If this returns `{"access_token":"...","role":"...",...}`, the API and credentials are correct; the issue is likely frontend (wrong URL, CORS, or cached build). If it returns 401, that username/password pair is not valid in the DB.
