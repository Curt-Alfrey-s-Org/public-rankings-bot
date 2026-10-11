# Troubleshoot: Don't See the Bot at the Website

If **https://www.probilliardssoftware.com** (or your domain) doesn't show the rankings bot, use this checklist.

---

## "Invalid response" or connection errors

This usually means the browser is talking to the server **by IP** instead of the public domain, or the reverse proxy (Nginx) can't reach the API.

**Fix:** Use the **domain**, not the IP:

- **Use:** **https://www.probilliardssoftware.com**
- **Avoid:** `http://192.0.2.20:8003` or raw IP addresses

---

## 1. API container is running

On the **server**:

```bash
docker ps | grep rankings-bot-api
# Should show rankings-bot-api running

curl -s http://127.0.0.1:8003/api/health
# Should return: {"status":"healthy","service":"Rankings Bot API",...}
```

If the API is down, deploy:

```bash
cd ~/rankings-bot
./scripts/full_deploy.sh --force-docker
```

---

## 2. Nginx routes to the API

The Nginx container (`probilliards-nginx`) must proxy to `rankings-bot-api:8003`. Check:

1. **Nginx config** — `nginx-config/rankings-bot-cloudflare.conf` (or equivalent) is used by the Nginx container.
2. **Same network** — Nginx and API are on `tunnel_network`.
3. **Upstream** — Nginx upstream is `rankings-bot-api:8003` (container DNS), not `host.docker.internal`.

---

## 3. Cloudflare Tunnel

If you use **Cloudflare Tunnel**, the tunnel must send traffic to the Nginx container. The tunnel routes (e.g. `www.probilliardssoftware.com`) should point to `http://probilliards-nginx:80`.

---

## 4. URL and cache

- Open **https://www.probilliardssoftware.com**
- Try a **private/incognito** window or **clear cache** for the site.

---

## 5. Check Nginx and API logs

```bash
docker logs probilliards-nginx 2>&1 | tail -50
docker logs rankings-bot-api 2>&1 | tail -50
```

Look for **502 Bad Gateway** (Nginx can't reach the API) or connection errors.

---

## Quick checklist

| Check | Action |
|-------|--------|
| API up | `docker ps \| grep rankings-bot-api` and `curl -s http://127.0.0.1:8003/api/health` |
| Nginx config | Nginx container uses correct upstream (rankings-bot-api:8003) |
| Same network | Nginx and API on tunnel_network |
| Tunnel | Cloudflare Tunnel points to probilliards-nginx:80 |
| URL | https://www.probilliardssoftware.com |
