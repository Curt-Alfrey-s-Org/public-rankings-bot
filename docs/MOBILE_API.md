# Mobile API (v1)

Stable contract for the React Native (or any mobile) app. Base path: **`/api/v1`**.

## Base URL

- **Production:** `https://www.probilliardssoftware.com`
- **Local:** `http://localhost:8003` (or your `API_PORT`)

All endpoints below are relative to the base URL (e.g. `GET /api/v1/health`).

## Auth

- **Login:** `POST /api/v1/auth/login` with body `{"username": "...", "password": "..."}`. No API key or Bearer required. The response includes `must_change_password`; when `true`, the token only works for `POST /api/users/change-password` (body `{"new_password": "..."}`) and `GET /api/auth/me` until the password is changed. Everything else returns `403 {"detail": "Password change required"}`.
- **Response:** `{"success": true, "token": "...", "user": "...", "role": "user"|"admin"}` or `{"success": false, "message": "..."}`.
- **Protected requests:** Send `Authorization: Bearer <token>` on every request to `/api/v1/*` (except health, auth, config). No `X-API-Key` needed when using Bearer.
- **Token expiry:** Default 24h; configurable via server `AUTH_TOKEN_EXPIRY_HOURS`. On 401, prompt re-login.
- **Logout:** `POST /api/v1/auth/logout` with optional body `{"token": "..."}` to invalidate the token server-side.

## Endpoints (no auth unless noted)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/v1/health | No | Liveness; returns `status`, `service`, `version`, `api_version`. |
| GET | /api/v1/config | No | App config: `minAppVersion`, `maintenanceMode`. |
| POST | /api/v1/auth/login | No | Login; returns `token`, `user`, `role`. |
| POST | /api/v1/auth/logout | No | Optional body `{"token":"..."}` to invalidate. |
| GET | /api/v1/rankings/wpba | Bearer | WPBA rankings (paginated). |
| GET | /api/v1/rankings/wpa | Bearer | WPA rankings (paginated). |
| GET | /api/v1/rankings/player/{name} | Bearer | Player data (WPBA + WPA). |
| GET | /api/v1/rankings/last-update | Bearer | Last update timestamps (wpba, wpa). |
| POST | /api/v1/rankings/refresh | Bearer | Trigger rankings refresh. |

## Request/response shapes

### GET /api/v1/rankings/wpba?limit=100&offset=0

**Response:** `RankingsResponse`

```json
{
  "total": 150,
  "limit": 100,
  "offset": 0,
  "count": 100,
  "rankings": [
    { "name": "...", "rank": 1, "points": 1000, "country": "...", "date": "2026-02-12" }
  ],
  "association": "WPBA"
}
```

### GET /api/v1/rankings/wpa?limit=100&offset=0

Same shape as WPBA; `association`: `"WPA"`.

### GET /api/v1/rankings/player/{player_name}

**Response:** `PlayerData`

```json
{
  "player_name": "...",
  "wpba": { "current": { "name": "...", "rank": 1, "points": 100, "country": "...", "date": "..." }, "history": [] },
  "wpa": { "current": null, "history": [] }
}
```

### GET /api/v1/rankings/last-update

**Response:** `{ "wpba": "2026-02-12T...", "wpa": "2026-02-12T..." }` (ISO strings or null).

### POST /api/v1/rankings/refresh

**Response:** `{ "timestamp": "...", "wpba": { "success": true, "count": 150, "error": null }, "wpa": { "success": true, "count": 200, "error": null } }`.

## Errors

- **401:** Missing or invalid/expired token. Body: `{"detail": "Invalid or expired token"}`. Client should clear stored token and show login.
- **403:** Not allowed (e.g. role). Body: `{"detail": "..."}`.
- **5xx:** Server error. Body: `{"detail": "..."}`.

## Pagination

- `limit`: 1–1000 (default 100). Documented max 1000 for "load more" / infinite scroll.
- `offset`: 0-based. Next page: `offset += limit` until `offset >= total`.

## HTTPS

Use HTTPS in production. The app should only call the API over HTTPS (no plain HTTP for production base URL).

## Reference

- TypeScript types: `frontend/src/api/rankings.ts`, `frontend/src/api/auth.ts`
- Checklist: [docs/PRODUCTION_AND_APP_CONVERSION.md](PRODUCTION_AND_APP_CONVERSION.md)
