# Changelog 2026-09-25: security review fixes (findings 3, 17, 18)

## Security
- **Auth bootstrap (finding 3):** removed the hardcoded `TEMP_PASSWORD` / default super-admin
  password. `ensure_bootstrap_users()` (api/auth.py) creates missing users only from
  `<PREFIX>_PASSWORD` / `<PREFIX>_PASSWORD_HASH` env vars at startup (no longer on mobile login).
  Production raises `BootstrapConfigError` and aborts startup when `SUPER_ADMIN_PASSWORD` is
  missing on a fresh DB or a bootstrap password fails the policy. The startup self-test now
  reports the real Auth Bootstrap result.
- **Server-side forced password change (finding 3):** login issues a token with the
  `pwd_change_required` claim for `must_change_password` users. `get_current_user`, the
  access middleware and `/ws` reject it (403) until the password is changed. Allowed:
  `POST /api/users/change-password`, `GET /api/auth/me`, `POST /api/auth/setup-email`,
  `POST /api/auth/resend-verification`, `POST /api/auth/logout`.
- **Admin password reset:** no hardcoded fallback. Without `DEFAULT_RESET_PASSWORD` a random
  one-off password is generated per reset.
- **Env files (finding 17):** `.env.development`, `.env.production`, `.env.staging`, `.env.ports`,
  `staging.env.sh`, `env.production.snippet` untracked; `.gitignore` covers `.env.*`/`*.env`
  (placeholder `*.example` templates stay tracked). Added `.env.production.example`,
  `.env.staging.example`, `.env.development.example`, `.env.ports.example`, `staging.env.sh.example`.
- **API access control (finding 18):** `RequireApiKeyMiddleware` is registered (constant-time
  key compare). `RequireUserOrAdminMiddleware` rejects anonymous requests with a missing/empty
  role header. Production requires `BOT_API_KEY`. Policy: docs/API_ACCESS_POLICY.md.
- `docker-compose-staging.yml`: removed `staging123` defaults; staging bootstrap and
  `BOT_API_KEY` vars are required.
- `scripts/verify_ports_and_health.sh`: no default passwords (login checks skipped unless set).
- Docs: removed plaintext credentials from PRODUCTION_DEPLOYMENT.md / REVIEW_AND_DEPLOY.md.

## Tests
- `tests/backend/test_auth_bootstrap.py`, `tests/backend/test_api_access_control.py` (new).
