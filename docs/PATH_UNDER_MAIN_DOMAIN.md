# Run Rankings Bot as a Path on the Main Domain

Use this when your main domain is already live (e.g. Cloudflare Tunnel + Nginx) and you want the rankings bot as **another page** — no subdomain, no new DNS.

**Result:** https://www.probilliardssoftware.com/rankings-bot

**Page live but rankings not loading?** See **docs/CONNECT_BOT.md** — ensure the Docker stack is running and Nginx routes to the API.

---

## 1. Build the frontend with a base path

On the server (or your build machine), from the Rankings-Bot app root:

```bash
cd ~/rankings-bot
export VITE_BASE_PATH=/rankings-bot
./scripts/build_frontend_with_docker.sh
```

`build_frontend_with_docker.sh` clears `VITE_API_URL` / `VITE_WS_URL` inside the build container (same-origin). This builds the app so assets and routes use `/rankings-bot/` as the base path.

---

## 2. Add Nginx path-based config

Add a **path-based** route for the rankings API in your Nginx config (e.g. `nginx-config/rankings-bot-cloudflare.conf` or equivalent):

- Route `/rankings-bot` to `http://rankings-bot-api:8003`
- Use `proxy_pass` with appropriate path handling

Reload the Nginx container after changing config:

```bash
docker restart probilliards-nginx
```

---

## 3. Start the stack (if not already running)

```bash
cd ~/rankings-bot
./scripts/full_deploy.sh --force-docker
```

---

## 4. Open the site

- **URL:** https://www.probilliardssoftware.com/rankings-bot
- No new DNS, no subdomain.

---

## Quick checklist

| Step | Action |
|------|--------|
| Build | `export VITE_BASE_PATH=/rankings-bot && ./scripts/build_frontend_with_docker.sh` |
| Nginx | Add path config for /rankings-bot → rankings-bot-api:8003, restart Nginx |
| Stack | `./scripts/full_deploy.sh --force-docker` |
| Test | Open https://www.probilliardssoftware.com/rankings-bot |
