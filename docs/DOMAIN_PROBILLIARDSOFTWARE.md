# Domain: probilliardssoftware.com

The Rankings Bot is served at **www.probilliardssoftware.com** and the mobile app at **app.probilliardssoftware.com**, using the **cf-probilliards** Cloudflare Tunnel and **probilliards-nginx**.

**Current mode (March 2026):** The main site (www) can show **maintenance** (static page) or **production** (live app). Switch with `./scripts/switch-site.sh maintenance | production`. See **[MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md](MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md)**.

## What you need to do

1. **DNS:** Point probilliardssoftware.com, www.probilliardssoftware.com, app.probilliardssoftware.com to your tunnel (CNAME to tunnel endpoint).
2. **Cloudflare Tunnel:** In Zero Trust → Tunnels → **your probilliards tunnel** → Public Hostname, set:
   - **probilliardssoftware.com** → HTTP → **http://probilliards-nginx:80**
   - **www.probilliardssoftware.com** → HTTP → **http://probilliards-nginx:80**
   - **app.probilliardssoftware.com** → HTTP → **http://probilliards-nginx:80**
3. **Run the tunnel connector (cf-probilliards):** Use `./scripts/start_cf_probilliards.sh` (see below) or run the container manually so the tunnel shows **Active** in Cloudflare.
4. **Restart:** `sudo docker restart probilliards-nginx` and `sudo docker restart cf-probilliards` when you change config.

## Start cf-probilliards tunnel

The tunnel must run on **tunnel_network** so it can reach **probilliards-nginx:80**.

**Option A – script (token from env):**
```bash
export TUNNEL_TOKEN='YOUR_PROBILLIARDS_TUNNEL_TOKEN'   # from Cloudflare Zero Trust → Tunnels → your tunnel → Configure
cd Rankings-Bot && ./scripts/start_cf_probilliards.sh
```

**Option B – docker run:**
```bash
sudo docker run -d \
  --name cf-probilliards \
  --restart unless-stopped \
  --network tunnel_network \
  -e TUNNEL_TOKEN="$TUNNEL_TOKEN" \
  cloudflare/cloudflared:latest \
  tunnel --no-autoupdate run --token "$TUNNEL_TOKEN"
```

Check: `sudo docker ps --filter name=cf-probilliards` and `sudo docker logs cf-probilliards --tail 20`.

See **CLOUDFLARE_TUNNEL_NGINX.md** for Nginx and tunnel options.
