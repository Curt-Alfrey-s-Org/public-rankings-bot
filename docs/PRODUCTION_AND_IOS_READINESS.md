# Production & iOS Readiness Checklist

**Goal:** Production-ready per industry standards, ready for iOS testing on TestFlight (Apple Developer account active).

**Current status:** See [PRODUCTION_STATUS_AND_NEXT_STEPS.md](PRODUCTION_STATUS_AND_NEXT_STEPS.md) for present state and next steps.

---

## 1. Production Readiness (IAW Industry Standards)

### 1.1 Security & HTTPS

- [x] **HTTPS everywhere** — All traffic over TLS (Cloudflare Tunnel / Nginx provides this)
- [x] **Secrets in env** — No hardcoded keys; `.env` in `.gitignore`; `docs/ENV_VARS.md` documents required vars
- [ ] **JWT_SECRET** — Strong, random; not default. Run `./scripts/verify_production.sh` to check. Startup warns if unset. **Operator must set.**
- [x] **CORS** — Defaults include `www.probilliardssoftware.com`, `app.probilliardssoftware.com`; override with `CORS_ORIGINS`
- [x] **Rate limiting** — Global API rate limit (200 req/min per IP); endpoint-specific limits for refresh, auth, ALFa. Set `DISABLE_GLOBAL_RATE_LIMIT=true` to disable.

### 1.2 Database & Backups

- [x] **PostgreSQL** — Single source of truth; migrations applied (`alembic upgrade head`)
- [x] **Backups** — Scheduled `pg_dump` via `./scripts/backup_postgres.sh` (see `docs/POSTGRES_BACKUPS_AND_CUTOVER.md`); cron at 2:00 AM
- [x] **Connection pooling** — SQLAlchemy pool configured (`SQLALCHEMY_POOL_SIZE`, `SQLALCHEMY_MAX_OVERFLOW`, `SQLALCHEMY_POOL_RECYCLE`)

### 1.3 Process & Deployment

- [x] **Single process manager** — Docker Compose for production (see `docs/PRODUCTION_DEPLOYMENT.md`, `docs/START_WEBSITE.md`)
- [x] **Health checks** — `/api/health` and `/api/health/detailed` used by monitoring
- [x] **Graceful shutdown** — systemd `TimeoutStopSec=30`; uvicorn handles SIGTERM

### 1.4 Logging & Observability

- [x] **Structured logs** — `LOG_FILE` and `LOG_LEVEL` configurable (see `docs/ENV_VARS.md`)
- [ ] **Error tracking** — Errors logged with context; optional: Sentry integration
- [x] **App version** — `MIN_APP_VERSION` env; `GET /api/app-version` for force-update flow

### 1.5 Testing

- [x] **Core tests pass** — `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python run_comprehensive_tests.py`
- [ ] **Smoke test** — `./scripts/smoke_check.sh` or `curl https://www.probilliardssoftware.com/api/health` (requires API running). **Operator must run.**

### 1.6 Documentation

- [x] **Deployment docs** — `docs/PRODUCTION_DEPLOYMENT.md`
- [x] **Environment vars** — `docs/ENV_VARS.md` documents required and optional vars; `.env.example` in repo

---

## 2. iOS Readiness (TestFlight → App Store)

*Note: Mobile app (`mobile/`) may be in a separate repo or not yet created. When present, follow steps below.*

### 2.1 Mobile App Build

- [x] **EAS configured** — `mobile/eas.json` with `preview` and `production` profiles
- [x] **Bundle ID** — `com.probilliardssoftware.rankings` in `app.json`
- [x] **API URL** — `EXPO_PUBLIC_API_URL` set to production URL in build profiles
- [ ] **EAS project ID** — Run `eas init` in `mobile/` to replace `placeholder` in app.json
- [ ] **Android build** — `cd mobile && eas build --platform android --profile preview`
- [ ] **iOS build** — `cd mobile && eas build --platform ios --profile preview` (requires Apple Developer account)
- [ ] **Signing** — EAS credentials linked to Apple Developer account (for iOS)

### 2.2 TestFlight (Internal Testing)

- [ ] **Apple Developer account** — Active ($99/year)
- [ ] **App Store Connect** — App created; bundle ID matches
- [ ] **Upload** — `eas submit --platform ios --latest` (or via EAS dashboard)
- [ ] **Internal testers** — Add team; install via TestFlight

### 2.3 App Store Submission (When Ready)

- [ ] **App icons** — 1024×1024 and required sizes
- [ ] **Screenshots** — iPhone/iPad per required sizes
- [x] **Privacy policy** — `https://www.probilliardssoftware.com/privacy` (route added)
- [ ] **App description** — Short and full
- [ ] **ITSAppUsesNonExemptEncryption** — Already `false` in `app.json` (no export compliance needed)

### 2.4 Mobile-Specific Checks

- [ ] **API reachable** — Mobile app can reach `https://www.probilliardssoftware.com` (or configured API)
- [ ] **Auth flow** — Login works on device
- [ ] **Secure storage** — `expo-secure-store` for tokens (already in plugins)

---

## 3. Pre‑iOS Checklist (Do Before First Build)

1. **Verify API is live** — `curl https://www.probilliardssoftware.com/api/health`
2. **Verify mobile app runs in dev** — `cd mobile && npm start` → press `i` (iOS Simulator) or scan QR with Expo Go
3. **EAS login** — `eas login` (Expo account)
4. **Apple credentials** — `eas credentials` or let EAS prompt during first iOS build

---

## 4. Testing (Local)

```bash
# Create venv and install deps (PEP 668 / externally-managed env)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Run comprehensive test suite
.venv/bin/python run_comprehensive_tests.py
```

## 5. Quick Commands

| Task | Command |
|------|---------|
| Start website | See `docs/START_WEBSITE.md`, `docs/DEPLOY_WEBSITE.md` |
| Smoke test | `./scripts/smoke_check.sh` or `BASE_URL=https://www.probilliardssoftware.com ./scripts/smoke_check.sh` |
| Verify production | `./scripts/verify_production.sh` (JWT_SECRET, DB, health) |
| iOS build (preview) | `cd mobile && eas build --platform ios --profile preview` |
| iOS build (production) | `cd mobile && eas build --platform ios --profile production` |
| Submit to TestFlight | `cd mobile && eas submit --platform ios --latest` |
| Run dev on phone | `cd mobile && npm start` → scan QR with Expo Go |

---

## 6. Low Priority (Roadmap — Kept for Later)

- League management
- Tour/series support
- Round robin / group stage
- Native mobile apps expansion (beyond current rankings)
- Multi-language support (i18n)

---

---

## 7. Code vs Operator Checklist

| Implemented in code | Operator must verify |
|---------------------|----------------------|
| Rate limiting, CORS defaults, connection pooling, graceful shutdown, health endpoints, app version, smoke script, verify_production.sh | HTTPS (Nginx/Cloudflare), JWT_SECRET in .env, backups in cron, systemd service installed, smoke test returns 200 |

**See also:** `docs/APP_NOOB_CHECKLIST.md`, `docs/WEB_AND_MOBILE_CHECKLIST.md`, `mobile/README.md`
