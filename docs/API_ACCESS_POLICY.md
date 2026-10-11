# API access policy (`/api/*`)

Decided in the 2026-09-25 security review fixes (finding 18). Implementation:
`api/middleware/access_control.py` (registered in `api/main.py`). Tests:
`tests/backend/test_api_access_control.py`. Keep this file, the module docstring and the
tests in sync when adding endpoints.

## Why this changed

`RequireApiKeyMiddleware` existed but was never registered, so `BOT_API_KEY` did nothing,
and `RequireUserOrAdminMiddleware` let requests through with no token and an empty
`X-User-Role` header. Every `/api/*` route without its own auth dependency was effectively
anonymous.

## The rules

| Tier | Who / what | Requirement |
|------|------------|-------------|
| **Open** (any method) | `/api/health`, `/api/app-version`, `/api/v1/config`, `/api/v1/health*`, `/api/auth/*`, `/api/v1/auth/*` | none |
| **Public read** (GET/HEAD only) | `/api/splash-config`, `/api/login-features`, `/api/media/slideshow`, `/api/assets/serve/*`, `/api/live/updates`, `/api/live/status`, `/api/tournaments/{id}/stream`, `/api/docs/notifications-email`, `/api/docs/director-import` | none |
| **Signed-in** | web app / mobile app after login | `Authorization: Bearer <JWT>` (validated server-side; legacy `auth_sessions` tokens still accepted) |
| **Server-to-server** | USPBF nginx proxy, scripts | `X-API-Key: $BOT_API_KEY` **and** `X-User-Role: user` (or `admin`) |

Anything else under `/api/` gets **401** (no/invalid key, no role header, invalid token),
**403** (unknown `X-User-Role` value, or a password-change-restricted token), or **503**
(`BOT_API_KEY` not configured; production refuses to start in that case).

Notes:

- **Public-read** endpoints are what the web app loads before sign-in, or from the browser
  where no custom header can be sent (`<img>`/`<video>` `src`, `EventSource`, plain `<a href>`).
  They are read-only and carry no private data. The production web build does **not** embed
  `VITE_API_KEY` (see `scripts/build_frontend_with_docker.sh`), so the SPA relies on this
  list before login and on its Bearer token after login.
- `X-User-Role` never grants privileges. Route dependencies (`require_admin`,
  `require_director_or_admin`, …) read the role from the JWT, so admin/director write routes
  still need a Bearer token even when a valid API key is sent.
- **No role-header exemptions** (follow-up 2026-09-25): without a Bearer token, every
  non-public path needs the API key **and** a non-empty `X-User-Role` of `user`/`admin`.
  The former exemptions for `POST /api/ai-narrative/demo-ask` and `/api/test-tournaments/*`
  were removed: the USPBF proxy always sends `X-User-Role: user`, and the test center is
  used signed-in (its write routes require a director/admin JWT anyway).
- **must_change_password / force_password_reset:** a login token for a user with
  `must_change_password` **or** `force_password_reset` (Pro/Fargo first login) set carries
  the `pwd_change_required` claim. Until the password is changed it gets
  `403 {"detail": "Password change required"}` everywhere except
  `POST /api/users/change-password`, `GET /api/auth/me`, `POST /api/auth/logout`,
  `POST /api/auth/setup-email` and `POST /api/auth/resend-verification` (email setup runs
  before the password gate in the web app). After the change, the same token works normally.
  The WebSocket `/ws` treats such a token as anonymous.
- `DEBUG=true` with no `BOT_API_KEY`: the key check is skipped with a warning (local dev
  only). The role-header and token checks still apply.

## USPBF (static site) compatibility

The USPBF nginx (`USPBF/nginx-config/uspbf-nginx-production.conf`, `location /api/`)
injects `X-API-Key: ${BOT_API_KEY}` and `X-User-Role: user` into every proxied request.
The site uses `GET /api/rankings/*`, `/api/tournament-history/*`, `/api/news`,
`/api/login-features` and `POST /api/ai-narrative/demo-ask`, so it keeps working
**as long as USPBF's `BOT_API_KEY` equals this API's `BOT_API_KEY`**.

USPBF follow-up (review finding 21) is done in USPBF PR #1: the proxy strips any
client-sent `X-User-Role` / `X-API-Key` and only forwards an allowlist (the GET endpoints
above plus `POST /api/ai-narrative/demo-ask`) with the server key and `X-User-Role: user`.

## Client IP (rate limits, lockout, IP blocks)

The API never reads the raw `X-Forwarded-For` value. Uvicorn runs with `--proxy-headers
--forwarded-allow-ips "$FORWARDED_ALLOW_IPS"` (`scripts/docker-api-cmd.sh`), so the header is
only honoured when the TCP peer is a trusted proxy and the client is the right-most
untrusted hop. Application code reads `request.client.host` via `api/client_ip.py`. See
`FORWARDED_ALLOW_IPS` in [ENV_VARS.md](ENV_VARS.md).

## Adding an endpoint

- Needs to be reachable before login or from `<img>`/`EventSource`? Add it to
  `_PUBLIC_READ_EXACT` / `_PUBLIC_READ_PREFIXES` / `_PUBLIC_READ_PATTERNS` (GET/HEAD only,
  read-only, no private data) and to the table above.
- Otherwise do nothing. Signed-in users send a Bearer token, and server callers send the key.
