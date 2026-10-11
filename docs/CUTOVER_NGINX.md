# Cutover to Nginx-only (standard deployment)

Use this checklist **on the server** when switching Rankings Bot to **Nginx** + host API on :8003. Traffic: **Cloudflare Tunnel (cf-probilliards)** → Nginx → API. One proxy, one flow. See **docs/PRODUCTION_DEPLOYMENT.md** and **docs/CLOUDFLARE_TUNNEL_NGINX.md**.

---

## Before you start

- You have SSH to the server.
- **cf-probilliards** (Cloudflare Tunnel) runs in Docker and will route `www.probilliardssoftware.com` to Nginx (host:80 or container probilliards-nginx:80).
- Nginx: either installed on host, or you will run the **probilliards-nginx** container (see **docs/CLOUDFLARE_TUNNEL_NGINX.md**).
- Rankings Bot repo is on the server (e.g. `~/rankings-bot/Rankings-Bot`).

---

## 1. Install Nginx config and reload

**Using Cloudflare Tunnel (cf-probilliards):** Nginx receives traffic from the tunnel; **no certs** on the server.

- **Nginx on host:** Copy `rankings-bot-cloudflare.conf`, enable, reload. In Zero Trust set tunnel route: `www.probilliardssoftware.com` → `http://172.17.0.1:80`.
- **Nginx in Docker:** Run `docker-compose -f nginx-config/docker-compose.nginx.yml up -d` (from repo root). Set tunnel route → `http://probilliards-nginx:80`. See **docs/CLOUDFLARE_TUNNEL_NGINX.md**.

```bash
cd ~/rankings-bot/Rankings-Bot
# Option A: Nginx on host
sudo cp nginx-config/rankings-bot-cloudflare.conf /etc/nginx/sites-available/rankings-bot
sudo ln -sf /etc/nginx/sites-available/rankings-bot /etc/nginx/sites-enabled/rankings-bot
sudo nginx -t && sudo systemctl reload nginx

# Option B: Nginx in Docker (tunnel routes to probilliards-nginx:80)
docker-compose -f nginx-config/docker-compose.nginx.yml up -d
```

**Not using Cloudflare** (direct HTTPS on origin): Use `nginx-config/rankings-bot.conf`; that config needs SSL certs.

If Nginx isn't the main listener on 80/443, adjust your Nginx setup so this server block is used for `www.probilliardssoftware.com`.

---

## 2. API on host, port 8003

Nginx proxies to `127.0.0.1:8003`. Something must be listening there:

- **API Configuration:** Ensure API is configured for port 8003 in your environment.
- **systemd:** Use port 8003 in the service file (see `docs/rankings-bot-api.service.example`). Then:
  ```bash
  sudo systemctl daemon-reload
  sudo systemctl restart rankings-bot-api
  sudo systemctl status rankings-bot-api
  ```
- **Manual:** Stop any process on 8003, then:
  ```bash
  cd ~/rankings-bot/Rankings-Bot
  ./scripts/restart_api.sh
  ```
  (`restart_api.sh` uses port 8003 by default.)

Check:

```bash
curl -s http://127.0.0.1:8003/api/health
```

You should see `{"status":"healthy",...}`.

---

## 3. Frontend build (if not already)

```bash
cd ~/rankings-bot/Rankings-Bot/frontend
npm run build
cd ..
```

The API serves `frontend/dist` from disk. After a code change, deploy with:

```bash
./scripts/deploy_website.sh --reload-nginx
```

---

## 4. Smoke-check

- **Health:** Open `https://www.probilliardssoftware.com/api/health` → `{"status":"healthy",...}`.
- **Site:** Open `https://www.probilliardssoftware.com/` → Rankings Bot UI.
- **Login:** Log in as Admin/Director if you use auth.
- **Hard refresh / incognito:** Confirm you see the latest frontend (no stale cache).

---

## 5. If something breaks

- **502 Bad Gateway:** Nginx can't reach the API. Check API is listening on 8003: `curl -s http://127.0.0.1:8003/api/health`. Restart API: `./scripts/restart_api.sh` or `sudo systemctl restart rankings-bot-api`.
- **Old site / wrong app:** Nginx might be proxying to the wrong port. Ensure Nginx config proxies to `127.0.0.1:8003`.
- **SSL errors:** Nginx config references Let's Encrypt paths; ensure certs exist (e.g. `sudo certbot certonly` for the domain) and paths in `rankings-bot.conf` match.

---

**Done.** Traffic flow: **Browser → Nginx (:443) → API (host :8003) → frontend/dist + /api**. One proxy, one deploy command: `./scripts/deploy_website.sh --reload-nginx`.
