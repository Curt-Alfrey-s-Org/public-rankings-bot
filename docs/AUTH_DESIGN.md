# Auth design — Rankings Bot

**Single source of truth for credentials:** the **database** (`users` table). All login checks use only the DB; no env or file fallbacks at login time.

## First login: there is no default password (changed 2026-09-25)

Until 2026-09-25 every startup created `admin`/`director`/`user`/`scorekeeper` (and the super
admin) with one hardcoded temporary password, in every environment. That is gone:

- Bootstrap users are created **only from env credentials** (`<PREFIX>_PASSWORD` or
  `<PREFIX>_PASSWORD_HASH`, see the table below), only when the user does not exist yet,
  and **only at API startup** (the mobile `/api/v1/auth/login` no longer runs bootstrap).
- **Production** (`DEBUG` unset/false): if the super admin does not exist and
  `SUPER_ADMIN_PASSWORD` is not set, or any configured bootstrap password fails the policy,
  the API **refuses to start** with an error naming the variable. The startup self-test
  reports "Auth Bootstrap" as failed instead of always passing.
- **Development** (`DEBUG=true`): accounts without a configured password are skipped with a
  warning. Set `SUPER_ADMIN_PASSWORD` (see `.env.development.example`) to get a login.
- Users created by bootstrap get `must_change_password=true`.

## Forced password change is enforced server-side

When a user with `must_change_password` logs in (`/api/auth/login` or `/api/v1/auth/login`),
the response still contains `must_change_password: true`, but the token now carries a
`pwd_change_required` claim. Until the password is changed, that token gets
`403 Password change required` from every protected endpoint except
`POST /api/users/change-password`, `GET /api/auth/me` (reports `must_change_password`),
`POST /api/auth/setup-email` and `POST /api/auth/resend-verification`. After a successful
change the flag is cleared in the DB and the same token regains normal access. Implemented in
`api/auth.py` (`get_current_user`, `get_optional_user`) and `api/middleware/access_control.py`.
See `docs/API_ACCESS_POLICY.md`.

## Production first login (optional .env)

1. Copy `.env.example` to `.env`.
2. Set **JWT_SECRET** and **DATABASE_URL** (required).
3. Set **ADMIN_USERNAME** and **ADMIN_PASSWORD** (e.g. `ADMIN_USERNAME=Bama`, `ADMIN_PASSWORD=YourSecurePassword`). Use a strong password (8+ chars, upper, lower, number, special).
4. Start or restart the API (systemd: `sudo systemctl restart rankings-bot-api`; Docker: restart the API container).
5. Open **https://www.probilliardssoftware.com/** and log in with that username and password.

Bootstrap creates the admin user on first run if it doesn’t exist. No manual script required. After that you can remove admin vars from `.env` if you prefer; login still uses the DB.

## Principles (standards-aligned)

- **OWASP / project standards:** One credential store per principal. Here that store is the DB. Passwords are hashed with **Argon2id** via `pwdlib` (FastAPI security tutorial pattern); legacy bcrypt hashes still verify and transparently upgrade to Argon2 on next successful login (`verify_and_update`). See [Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html); no plaintext storage.
- **Login path:** `authenticate_user(db, username, password)` → look up user by username → verify password against `user.password_hash`. Env vars are **not** read during authentication.
- **Bootstrap:** Optional env vars are used only to **create missing users** at startup/first use. If a user already exists in the DB, bootstrap does not update that user’s password. So changing `.env` after users exist has no effect on login.

## Required configuration

| Variable       | Purpose                          | Where |
|----------------|----------------------------------|--------|
| `JWT_SECRET`   | Signing key for access tokens    | `.env` or environment (required) |
| `DATABASE_URL` | PostgreSQL connection for `users` | `.env` or environment (required) |

**Production:** You must set `JWT_SECRET` to a strong, unique value. Never use the default `rankings-bot-change-in-production` in production. The API logs a startup warning if it detects the default. See project **CHECKLIST.md** (Production readiness).

## Optional configuration (bootstrap only)

These are used **only** to create users that do not yet exist. Omit them if you manage users entirely via the app or DB.

| Variable | Default | Purpose |
|----------|---------|--------|
| `SUPER_ADMIN_USERNAME` | `tornybotca1` | Username for bootstrap super_admin |
| `SUPER_ADMIN_PASSWORD` | — (**required in production** while the super admin does not exist) | Password for that user when created |
| `ADMIN_USERNAME` | `admin` | Username for bootstrap admin (if created). Avoid `admin`: web login treats it as a honeypot and blocks the IP. |
| `ADMIN_PASSWORD` | — | Password when creating that admin |
| `DIRECTOR_USERNAME` / `DIRECTOR_PASSWORD` | — | Same for director |
| `USER_USERNAME` / `USER_PASSWORD` | — | Same for user role |
| `SCORE_KEEPER_USERNAME` / `SCORE_KEEPER_PASSWORD` | `scorekeeper` / — | Same for score_keeper |
| `<PREFIX>_PASSWORD_HASH` | — | Alternative to `<PREFIX>_PASSWORD`: a pre-computed Argon2/bcrypt hash |

Passwords must meet the policy (8+ chars, upper, lower, number, special); a weak value is a
startup error in production.

If you do **not** set admin/director/user env vars, those roles are simply not auto-created; you can create them via the app (e.g. as super_admin) or directly in the DB.

### Admin password reset

When an admin resets a user's password (Settings → Admin → Edit user → Reset to default password), the password is set to a temporary value. The user **must change it on next login** (OWASP/NIST standard).

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEFAULT_RESET_PASSWORD` | — (random per reset) | Optional fixed temporary password for admin resets. When unset (recommended) a random one-off password is generated for each reset and shown to the admin once. Must meet strength rules. |

## Token lifetime

Access tokens use a fixed expiry (see `ACCESS_TOKEN_EXPIRE_DAYS` in `api/auth.py`). For stricter security, consider shorter-lived tokens (e.g. 15–60 minutes) and refresh tokens, per [Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html).

## Recovery: reset super_admin

If something went wrong and you can't log in as the super admin, set `SUPER_ADMIN_PASSWORD` in the server `.env` and run on the **server**:

```bash
cd /path/to/Rankings-Bot
source .env 2>/dev/null || true
python3 scripts/ensure_super_admin.py
```

That script forces the user to exist with the password you set via SUPER_ADMIN_PASSWORD. Normally bootstrap does this at API startup; the script is for recovery only.

## Recovery: reset admin password or create Bama

If you need to set or reset the Bama admin password, run on the **server**:

```bash
cd /path/to/Rankings-Bot
source .env 2>/dev/null || true
python3 scripts/set_bama_admin.py
```

You’ll be prompted to set a password for user `Bama` (admin role). Then log in at the site with **Bama** and that password.

## Summary

- **Who is in charge of creds?** The database. Login always validates against `users.password_hash`.
- **What is `.env` for?** Required: `JWT_SECRET`, `DATABASE_URL`. Optional: bootstrap-only user creation. You can leave user/password vars out of `.env` and manage accounts only in the DB or via the app.
