# Rankings Bot — Working Checklist

Use this file in the file browser while you work. Check off items as you complete them.

**Current status & next steps:** See [Rankings-Bot/docs/PRODUCTION_STATUS_AND_NEXT_STEPS.md](Rankings-Bot/docs/PRODUCTION_STATUS_AND_NEXT_STEPS.md) for present state and path to production (web + app).

---

## Where to start (after refactor)

If you’re not sure where to pick up:

1. **Get the stack running**  
   From project root: `cd Rankings-Bot && ./scripts/start.sh`  
   (Or start API + frontend your usual way.) Then: `curl -s http://localhost:8003/api/health` → expect 200.

2. **Confirm you can log in**  
   Use the super admin from `SUPER_ADMIN_USERNAME` / `SUPER_ADMIN_PASSWORD` (server `.env`; there is no default password). If that fails, run:  
   `cd Rankings-Bot && source venv/bin/activate && python3 scripts/ensure_super_admin.py`  
   (Optional: create Bama admin: `python3 scripts/set_bama_admin.py` and follow the prompt.)

3. **Production go-live**  
   Work through the **Production readiness (go-live)** section below in order (JWT_SECRET → DATABASE_URL → single API starter → change super_admin password → CORS/health/backups).

4. **Mobile / app**  
   After production is checked off: **Server: Ready for app** is done; use **Mobile** section for build/test/distribution.

**Docs:** Auth → `Rankings-Bot/docs/AUTH_DESIGN.md`. Deployment → `Rankings-Bot/docs/PRODUCTION_DEPLOYMENT.md`. One-page production summary → `Rankings-Bot/docs/PRODUCTION_READINESS.md`.

---

## Production readiness (go-live)

Complete these before treating the app as production-ready:

- [ ] **JWT_SECRET** — Set to a strong, unique value in `.env` / systemd; never use default `rankings-bot-change-in-production` in production.
- [ ] **DATABASE_URL** — Set and reachable from the API; systemd service loads it (e.g. `EnvironmentFile`).
- [ ] **Single API starter** — systemd service installed; only systemd starts the API; scripts delegate via `systemctl restart rankings-bot-api`.
- [ ] **super_admin password** — Set `SUPER_ADMIN_PASSWORD` in `.env` before first start (required in production; no default). The first login forces a password change (server-enforced). CLI reset: `SUPER_ADMIN_PASSWORD='newpass' python3 scripts/ensure_super_admin.py`.
- [ ] **CORS** — Defaults include probilliardssoftware.com; set `CORS_ORIGINS` if using other domains.
- [ ] **Health checks** — `/api/health` used for monitoring; ensure your stack checks it.
- [ ] **Backups** — Postgres and critical data; cron or schedule in place (see `scripts/backup_postgres.sh`).

**Recommended:** Shorter JWT lifetime (e.g. 15–60 min) and refresh tokens; HTTPS only (Nginx/Tunnel); no secrets in repo.

**Verify:** After setting env and starting the API, run:  
`cd Rankings-Bot && ./scripts/verify_production.sh`  
(Checks JWT_SECRET, DATABASE_URL, /api/health, optional systemd; does not echo secrets.)

---

## Server: Production

- [x] **Website reliability** — Bot up; health 200; rankings respond
- [x] **Auth** — Token validated server-side; Bearer required; expiry/refresh
- [x] **Backups** — One backup run; daily cron at 2:00 AM (backup_postgres.sh → backup_postgres.log).
- [x] **DB on startup** — Schema ensured in API lifespan
- [x] **Rate limiting** — Login 10/min, rankings 120/min per IP; 429 + Retry-After
- [x] **Observability** — Health 5xx logged at ERROR; see Rankings-Bot/docs/MONITORING_HEALTH.md

---

## Server: Ready for app

- [x] Auth for mobile (Bearer); API versioning /api/v1/; mobile API doc; config endpoint
- [x] **Pagination** — Max 1000 in docs/MOBILE_API.md; app has Load more
- [x] **HTTPS only** — Nginx/Cloudflare; production API URL is HTTPS; docs/MOBILE_API.md

---

## Mobile (React Native / Expo)

- [x] Project in mobile/; API client + auth; React Navigation; Rankings + Settings
- [x] Rankings screen with WPBA/WPA tabs and Load more pagination
- [x] EAS config mobile/eas.json; build steps in mobile/README.md
- [ ] **Build** — Android: run `npx eas-cli build --platform android --profile preview`. iOS: waiting on Apple Developer account approval (paid program + team); then `--platform all`.
- [ ] **Test on device or laptop** — Laptop: `cd mobile && npm start` then press **w** for web (browser). Or Android emulator. Checklist: mobile/README.md (login, rankings, load more, logout, bad network, 401)
- [ ] **Distribution** — TestFlight / Play Store or sideload

**Note:** Waiting on Apple — iOS build blocked until Apple Developer account is approved and team is set up. Use Android build in the meantime.

---

## Mobile app expansion (full menu + screens)

Plan: **Rankings-Bot/docs/MOBILE_APP_EXPANSION.md**. Layout: drawer (hamburger) for full menu + bottom bar for main items; hide/expand drawer. Tournament Wizard and director tools: not on phone — message in web Tournaments section; in app use “use tablet or browser” when we add Tournaments.

- [x] **Director tab (web)** — Done. Top-level menu **Tournament Director**; sub-nav: Data input, Director mode, Score keeper, New Tournament, Tournament Player Management. Tournaments tab: History, Upcoming, Current, Bracket, Leaderboard. Redirects from old /tournaments/… URLs. Tablet/mobile: when expansion phases run, add same under Director.
- [ ] **Phase 1** — Drawer menu (mirror web sidebar) + Home screen. Bottom bar: Home, Rankings, Settings (or More).
- [ ] **Phase 2** — Movement screen; Tournaments list screen with “use tablet or browser” message for Wizard/Director.
- [ ] **Phase 3** — Player Performance, Head-to-Head (simplified or read-only).
- [ ] **Phase 4** — AI Coach, Covert Ops (admin), full Settings sub-pages or “Open full website”.
- [ ] **Phase 5 (optional)** — Tablet layout: drawer always visible; Tournament Wizard/Director on tablet.

**Start with:** Phase 1 (drawer + Home). See MOBILE_APP_EXPANSION.md for references (React Navigation drawer, breakpoints, Sidebar.tsx).

---

## Quick reference

| Task            | Where / command |
|-----------------|-----------------|
| Start bot       | ./Rankings-Bot/scripts/start.sh |
| Run backup      | cd Rankings-Bot && ./scripts/backup_postgres.sh |
| Run mobile      | cd mobile && npm start (press w for web) |
| Mobile on subdomain | https://app.probilliardssoftware.com (after build + nginx + tunnel; see Rankings-Bot/docs/MOBILE_APP_SUBDOMAIN.md) |
| EAS build       | cd mobile && npx eas-cli build --platform android --profile preview |
| Full details    | docs/PRODUCTION_AND_APP_CONVERSION.md |

---

**Next:** Test on laptop (Expo web: `cd mobile && npm start` then press **w**) or device/emulator. Then distribution. iOS when Apple account approved.

Update the [ ] / [x] in this file as you complete items.
