# Production Readiness & React Native Conversion

**Current status:** See [Rankings-Bot/docs/PRODUCTION_STATUS_AND_NEXT_STEPS.md](../Rankings-Bot/docs/PRODUCTION_STATUS_AND_NEXT_STEPS.md) for present state and next steps.

This document tracks server-side production readiness, API readiness for a mobile app, and steps to convert the web frontend to React Native (iOS/Android). See [Roadmap.md](../Roadmap.md) for the short summary and link.

---

## 1. Server: Production ready

### Already in place
- **Deployment:** Nginx + host API on 8003, Cloudflare Tunnel, SPA served from API.
- **Database:** PostgreSQL only, `DATABASE_URL`, shared `get_database_manager()`.
- **API:** Health (`/api/health`), system health/self-test (`/api/system/health`), rankings (WPBA/WPA, pagination, cache), auth (login/logout), CORS for web.
- **Docs:** Standard deployment, mobile browser access (Rankings-Bot/docs/MOBILE_ACCESS.md), monitoring (Rankings-Bot/docs/MONITORING_HEALTH.md), Postgres backups (Rankings-Bot/docs/POSTGRES_BACKUPS_AND_CUTOVER.md).
- **Security:** Parameterized SQL, no credentials in code; login returns a token.

### Checklist: close production gaps
- [x] **Website reliability** — Bot verified up on host: `http://127.0.0.1:8003/api/health` returns 200 and rankings endpoint responds. If the public URL (https://www.probilliardssoftware.com) fails, see `Rankings-Bot/docs/PRODUCTION_DEPLOYMENT.md`, `Rankings-Bot/docs/BAD_GATEWAY_TROUBLESHOOTING.md`.
- [x] **Auth** — Validate login token (or JWT) server-side; require Bearer for protected routes. Add token expiry and refresh. Do not rely only on client-sent `X-User-Role`.
- [ ] **Backups** — Automate Postgres backups (cron + e.g. `Rankings-Bot/scripts/backup_postgres.sh`); run at least one test restore; document where dumps are stored.
- [x] **DB on startup** — Schema/tables are ensured on API startup via `ensure_rankings_tables_postgres()` in lifespan (api/main.py). New/env-only deploys get tables created automatically.
- [x] **Rate limiting** — Per-IP rate limiting: login 10/min, rankings 120/min (api/rate_limiter.py + RateLimitMiddleware in api/main.py). Returns 429 with Retry-After when exceeded.
- [ ] **Observability** — Structured logging or alerting on `/api/health` failure (see Rankings-Bot/docs/MONITORING_HEALTH.md).

---

## 2. Server: Ready for app conversion
- [x] **Harden auth for mobile** — Validate Bearer token (or JWT) on every protected request; support token expiry and refresh.
- [x] **API versioning** — Introduce e.g. `/api/v1/` and route existing endpoints under it for a stable contract.
- [x] **CORS / docs** — Document that native app uses Bearer only; no CORS change required for pure native. If using WebView, allow the app origin.
- [x] **Document mobile API** — Base URL, auth (Bearer + how to get token), list of endpoints (rankings list, player detail, last-update, refresh), request/response shapes (see `frontend/src/api/rankings.ts` for types). Ensure error format is consistent and 401 for invalid/missing token. See [docs/MOBILE_API.md](MOBILE_API.md).
- [x] **App config endpoint** — e.g. `GET /api/v1/config` with `minAppVersion`, `maintenanceMode`, or feature flags.
- [ ] **Pagination** — Keep sensible max (e.g. 1000) for rankings and document it for load more or infinite scroll.
- [ ] **HTTPS only** — Already in place via Nginx/Cloudflare; ensure the app only talks to the API over HTTPS.

---

## 3. React Native conversion (iOS/Android)

### Phase A: Project and structure
- [ ] **Create React Native project** — Expo: `npx create-expo-app rankings-bot-mobile --template tabs` (or blank). Or bare: `npx react-native init RankingsBotMobile`.
- [ ] **Reuse logic, replace UI** — Copy or share `frontend/src/api/` (rankings, auth), types (e.g. `Ranking`, `RankingsResponse`), and pure logic. Replace `localStorage` with AsyncStorage (or secure store for token); replace `window`-based config with e.g. `react-native-config` or a config module.
- [ ] **Environment** — Use a config module or `react-native-config` so `API_BASE_URL` is set per build (dev/staging/prod).

### Phase B: Navigation and auth
- [ ] **Navigation** — Replace React Router with React Navigation (stack + tabs or drawer): e.g. Splash/Login then Main (Rankings, Settings, etc.).
- [ ] **Auth flow** — Login screen calls `POST /api/auth/login` (or `/api/v1/auth/login`) with shared API client. On success, store token in secure storage (e.g. `expo-secure-store`). Auth context sets `Authorization: Bearer <token>` on the client. Logout: clear storage and auth state.

### Phase C: Screens and API
- [ ] **Rankings screen** — WPBA/WPA toggle or tabs; list from `rankingsApi.getWPBA` / `getWPA` in a FlatList (or FlashList); support pagination (next page = `offset += limit`).
- [ ] **Other screens** — Settings (theme, logout), Player detail (`rankingsApi.getPlayer`), System/Logs if desired. Use modals or stack screens as needed.
- [ ] **Offline / loading** — Loading states and "Cannot reach server" handling; optionally cache last rankings in AsyncStorage.

### Phase D: Build and release
- [ ] **Icons and splash** — Use existing `icon.png` / `icon.svg` (Expo: `app.json` / `app.config.js`).
- [ ] **Permissions** — Network only by default; add push or other permissions if needed.
- [ ] **Build** — Expo: EAS Build for iOS and Android. Bare RN: Xcode and Android Studio with signing and release config.
- [ ] **Distribution** — iOS: App Store (certificates, provisioning, TestFlight). Android: Play Store or sideload (signing key, store listing).

### Phase E: Testing and polish
- [ ] **Test on devices** — Login, rankings list, pagination, refresh, player detail, logout. Test bad network and invalid token (401).
- [ ] **Security** — No API keys or secrets in the app binary; use env/build-time config and Bearer token from login only.

---

## 4. Combined quick checklist
**Server production:** Website up; auth validation; backups automated + test restore; DB on startup; rate limit and observability.
**Server for app:** API versioning; document mobile API; config endpoint.
**React Native:** RN project in `mobile/` (Expo); shared client + auth; React Navigation; Rankings + Settings screens; see `mobile/README.md`. Next: build and distribute; test on device; no secrets in binary.

---

## References
- [Roadmap.md](../Roadmap.md)
- Rankings-Bot/docs/PRODUCTION_DEPLOYMENT.md
- Rankings-Bot/docs/MOBILE_ACCESS.md
- Rankings-Bot/docs/MONITORING_HEALTH.md
- Rankings-Bot/docs/POSTGRES_BACKUPS_AND_CUTOVER.md
- `frontend/src/api/rankings.ts`
