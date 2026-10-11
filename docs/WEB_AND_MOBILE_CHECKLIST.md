# Web app vs mobile app — start, stop, restart, rebuild

Simple checklist. **Web** = https://www.probilliardssoftware.com (Vite SPA + API). **Mobile** = (1) **mobile web** at https://app.probilliardssoftware.com (Expo web export, same API) and (2) **native app** (iOS/Android via Expo/EAS; no server to start/stop).

**Where to run:** On the server, from project root: `cd /home/ansible/rankings-bot/Rankings-Bot` unless noted.

---

## Start

| Action | Web app | Mobile app |
|--------|--------|------------|
| **Start** | **Full stack:** `./scripts/start.sh` (Docker + nginx).<br>**Dev:** `./scripts/start.sh --dev` (host API + frontend).<br>**API only (production):** `sudo systemctl start rankings-bot-api`<br>**API only (dev):** `./scripts/start_api.sh` | **Mobile web:** No diff — same stack as web (Nginx + API). Use web “Start” above.<br>**Native (dev only):** In `mobile/`: `npm start` then press `i` / `a` / `w`. No server start. |

---

## Stop

| Action | Web app | Mobile app |
|--------|--------|------------|
| **Stop** | **Production:** `sudo systemctl stop rankings-bot-api` or `./scripts/stop.sh`<br>**No systemd:** `./scripts/stop.sh --api-only` (kills process on port 8003) | **Mobile web:** No diff — stopping the API/Nginx stops both web and mobile web.<br>**Native:** N/A (no server to stop). |

---

## Restart

| Action | Web app | Mobile app |
|--------|--------|------------|
| **Restart** | **Production:** `sudo systemctl restart rankings-bot-api`<br>**Or:** `./scripts/restart_api.sh` (delegates to systemd if service exists, else stop + start on port) | **Mobile web:** No diff — same API and Nginx. Use web “Restart” above.<br>**Native:** N/A. |

---

## Rebuild (when necessary)

| Action | Web app | Mobile app |
|--------|--------|------------|
| **Rebuild** | **Standard (host API):** `./scripts/deploy_website.sh` or `./scripts/deploy_website.sh --reload-nginx` — builds Vite frontend, restarts API, optionally reloads Nginx.<br>**From Admin UI:** “Rebuild & deploy website” runs `rebuild_website_now.sh` (build frontend + restart host API when systemd exists, else Docker). | **Mobile web:** Different. Build Expo web, then restart Nginx so it serves new files:<br>1. `cd mobile && EXPO_PUBLIC_API_URL=https://www.probilliardssoftware.com npx expo export --platform web`<br>2. Restart Nginx container: `cd ../nginx-config && docker stop probilliards-nginx && docker rm probilliards-nginx && docker compose -f docker-compose.nginx.yml up -d --build`<br>**Native (iOS/Android):** Different. No server rebuild. Build in cloud: `cd mobile && eas build --platform all --profile preview` (or `production`). Submit: `eas submit --platform all --latest`. |

---

## Summary: where they differ

- **Start / stop / restart:** No diff for **mobile web** — it uses the same API and Nginx as the web app. **Native** app has no server; dev is `npm start` in `mobile/`.
- **Rebuild:** Differs. Web = build Vite frontend + restart API (and maybe Nginx). Mobile web = build Expo web export + rebuild/restart Nginx container. Native = EAS build/submit, no server changes.

---

## Quick reference

| | Web | Mobile web | Native (iOS/Android) |
|--|-----|------------|----------------------|
| **Start** | `./scripts/start.sh` or `sudo systemctl start rankings-bot-api` | No diff | `cd mobile && npm start` (dev) |
| **Stop** | `sudo systemctl stop rankings-bot-api` or `./scripts/stop.sh --api-only` | No diff | N/A |
| **Restart** | `sudo systemctl restart rankings-bot-api` or `./scripts/restart_api.sh` | No diff | N/A |
| **Rebuild** | `./scripts/deploy_website.sh [--reload-nginx]` | Expo web export + Nginx container restart | `eas build` / `eas submit` |

See also: **docs/PRODUCTION_DEPLOYMENT.md**, **docs/START_STOP_RESTART.md**, **docs/MOBILE_APP_SUBDOMAIN.md**, **mobile/README.md**.
