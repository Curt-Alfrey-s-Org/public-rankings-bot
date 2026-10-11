# Production Status & Next Steps

**Last updated:** Feb 2026  
**Goal:** Production-ready web app and native mobile app (iOS/Android)

This document is the single source of truth for current status and what remains to reach full production readiness for both web and app.

---

## 1. Current Status Summary

### Web App — Production Ready ✅

| Area | Status | Notes |
|------|--------|------|
| **Deployment** | ✅ Live | https://www.probilliardssoftware.com — Nginx + host API (port 8100), Cloudflare Tunnel |
| **Backend** | ✅ Complete | FastAPI, PostgreSQL, systemd, health checks, rate limiting |
| **Auth** | ✅ Complete | JWT, Bearer validation, roles (guest, director, admin, super_admin) |
| **Frontend** | ✅ Complete | Vite SPA: Rankings (WPBA/WPA/Heyball), Movement, Tournaments, Director tools, AI Coach, Settings, Leaderboard |
| **Data Population** | ✅ Complete | WPBA (166 players), WPA Women (598), WPA Men (279), Heyball Men (206), Heyball Women (118) |
| **Live Updates** | ✅ Working | WebSocket connections, real-time data refresh across all pages |
| **Backups** | ✅ Automated | `backup_postgres.sh` via cron (2:00 AM) |
| **Observability** | ✅ In place | `/api/health`, structured logging, MONITORING_HEALTH.md |

**Operator verification (before go-live):** Run `./scripts/verify_production.sh` and `./scripts/smoke_check.sh`. Ensure JWT_SECRET is set (not default), super_admin password changed after first login.

---

### Mobile App — In Progress 🟡

| Area | Status | Notes |
|------|--------|------|
| **Project** | ✅ Exists | `Rankings-Bot/mobile/` — Expo/React Native |
| **Core screens** | ✅ Done | Rankings (WPBA/WPA tabs, Load more), Settings (Log out, Open full website) |
| **Auth & API** | ✅ Done | Bearer token, expo-secure-store, production API URL in eas.json |
| **Feature scope** | ✅ Defined | Player features only; no director capabilities (tournament creation/management) |
| **EAS config** | ✅ Done | `eas.json` with preview/production profiles |
| **Android build** | ⏳ Pending | Run `cd mobile && eas build --platform android --profile preview` |
| **iOS build** | ⏳ Blocked | Requires Apple Developer account ($99/year) + team approval |
| **Distribution** | ⏳ Pending | TestFlight (iOS), Play Store or sideload (Android) |
| **Mobile expansion** | ⏳ Pending | Phase 1–5: drawer menu, Movement, Tournaments, etc. — see MOBILE_APP_EXPANSION.md |

**Note:** `app.json` has `"projectId":"placeholder"` — run `eas init` in `mobile/` before first EAS build to get a real project ID.

---

## 2. Steps to Production Ready

### Web — Final Verification (≈15 min)

1. **JWT_SECRET** — Set in `.env` or systemd `EnvironmentFile`. Generate: `openssl rand -base64 32`
2. **Verify production** — `cd Rankings-Bot && ./scripts/verify_production.sh` — all [PASS]
3. **Smoke check** — `BASE_URL=https://www.probilliardssoftware.com ./scripts/smoke_check.sh`
4. **Change super_admin password** — After first login as tornybotca1/rtRT, change in Settings or:  
   `SUPER_ADMIN_PASSWORD='newpass' python3 scripts/ensure_super_admin.py`

### Mobile — Path to App Store / Play Store

| Step | Action | Doc / Command |
|------|--------|---------------|
| 1 | EAS project ID | `cd mobile && eas init` (replace placeholder in app.json) |
| 2 | Android build | `cd mobile && eas build --platform android --profile preview` |
| 3 | Test on device | `cd mobile && npm start` → scan QR with Expo Go, or press `w` for web |
| 4 | iOS build (when Apple ready) | `eas build --platform ios --profile preview` |
| 5 | Submit to stores | `eas submit --platform all --latest` (after builds succeed) |
| 6 | TestFlight (iOS) | Add internal testers; install via TestFlight |

**Pre-build checks:** API live (`curl https://www.probilliardssoftware.com/api/health`), `eas login`, Apple credentials when doing iOS.

### Mobile Expansion (Optional, Post-Launch)

| Phase | Scope | Doc |
|-------|--------|-----|
| 1 | Drawer menu + Home screen | MOBILE_APP_EXPANSION.md |
| 2 | Movement + Tournaments list (with “use tablet” message) | |
| 3 | Player Performance, Head-to-Head | |
| 4 | AI Coach, Covert Ops, full Settings | |
| 5 | Tablet layout (optional) | |

---

## 3. Quick Reference

| Task | Command / Doc |
|------|---------------|
| Start web stack | `./scripts/start.sh` or `sudo systemctl start rankings-bot-api` |
| Deploy website | `./scripts/deploy_website.sh --reload-nginx` |
| Verify production | `./scripts/verify_production.sh` |
| Smoke check | `./scripts/smoke_check.sh` or with BASE_URL |
| Run mobile dev | `cd mobile && npm start` (press w/i/a) |
| Android build | `cd mobile && eas build --platform android --profile preview` |
| iOS build | `cd mobile && eas build --platform ios --profile preview` |

---

## 4. Related Docs

| Topic | Doc |
|------|-----|
| Production readiness (must-haves) | [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) |
| Production & iOS checklist | [PRODUCTION_AND_IOS_READINESS.md](PRODUCTION_AND_IOS_READINESS.md) |
| Working checklist (go-live) | [../../CHECKLIST.md](../../CHECKLIST.md) |
| Web vs mobile (start/stop/rebuild) | [WEB_AND_MOBILE_CHECKLIST.md](WEB_AND_MOBILE_CHECKLIST.md) |
| Production deployment | [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) |
| Mobile expansion plan | [MOBILE_APP_EXPANSION.md](MOBILE_APP_EXPANSION.md) |
| Smoke check | [SMOKE_CHECK.md](SMOKE_CHECK.md) |
