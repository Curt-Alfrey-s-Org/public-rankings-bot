# Cloudflare Tunnel → Nginx → Rankings Bot (probilliardssoftware.com)

Traffic flow: **Visitor → Cloudflare → cf-probilliards (Docker) → probilliards-nginx → API :8003**.

For **probilliardssoftware.com** we use the **cf-probilliards** tunnel container. It runs in Docker and forwards traffic to **probilliards-nginx:80**; Nginx proxies to the API on the host (port 8003). Start the connector with `./scripts/start_cf_probilliards.sh` (see **docs/DOMAIN_PROBILLIARDSOFTWARE.md**).

**Important:** The tunnel must use the **tunnel_network** Docker network so it can reach **probilliards-nginx**.

---

## Recommended: Nginx in Docker (Option B)

**Best for most setups:** Run Nginx as a container (**probilliards-nginx**) on the same network as **cf-probilliards** (e.g. `tunnel_network`). Tunnel routes: `www.probilliardssoftware.com` → `http://probilliards-nginx:80`; **app.probilliardssoftware.com** → `http://probilliards-nginx:80` (mobile app).

- Matches how your other bots work (tunnel → container by name: credit-check-bot-frontend, etc.).
- No Nginx on the host; no relying on `172.17.0.1` from the tunnel.
- One network, one pattern: tunnel talks only to containers by name.

Use **Option A** (Nginx on host) only if you prefer a single system Nginx for multiple sites and are happy pointing the tunnel at the host IP.

---

## Two ways to run Nginx

### Option A: Nginx on the host

- Nginx runs on the **host** (system install), listens on port **80**, uses `nginx-config/rankings-bot-cloudflare.conf`, proxies to `127.0.0.1:8003`.
- **Tunnel route** (Cloudflare Zero Trust → cf-probilliards → Public Hostname):  
  `www.probilliardssoftware.com` → **`http://172.17.0.1:80`** (Linux; Docker bridge to host) or **`http://host.docker.internal:80`** (Mac/Windows).
- cf-probilliards must be able to reach the host; on Linux the host is usually `172.17.0.1` from containers.

### Option B: Nginx in a Docker container

- Nginx runs in a **container** (e.g. **probilliards-nginx**) on the same network as **cf-probilliards** (e.g. `tunnel_network`). Nginx proxies to the **host** API at `172.17.0.1:8003` (see `nginx-config/rankings-bot-cloudflare-docker.conf`).
- **Tunnel route:**  
  `www.probilliardssoftware.com` → **`http://probilliards-nginx:80`**.
- No Nginx install on the host; everything behind the tunnel is Docker + host API.

---

## Setting the tunnel route (Zero Trust)

1. Open **Cloudflare Zero Trust** → **Networks** → **Tunnels** → your **probilliards tunnel** (connector runs as **cf-probilliards**).
2. **Public Hostname** (or **Ingress**): add one entry per hostname (all → same origin):
   - **probilliardssoftware.com** (apex): **Service** `HTTP`, **Origin** `http://probilliards-nginx:80`.
   - **www.probilliardssoftware.com** (main site): **Service** `HTTP`, **Origin** same.
   - **app.probilliardssoftware.com** (mobile app): **Service** `HTTP`, **Origin** same. Nginx serves mobile from `/var/www/mobile-app` for this hostname.
3. Save. Restart the connector if needed: `sudo docker restart cf-probilliards`.

---

## Checklist

- [ ] **cf-probilliards** container is on the same Docker network as the tunnel origin (same network as **probilliards-nginx**; e.g. `tunnel_network`).
- [ ] **API** on host is listening on **0.0.0.0:8003** (`./scripts/restart_api.sh` or systemd) so the Nginx container can reach it via `host.docker.internal:8003`.
- [ ] **Nginx** (host or container) is using `rankings-bot-cloudflare.conf` (host) or `rankings-bot-cloudflare-docker.conf` (container); no certs needed.
- [ ] **DNS:** `probilliardssoftware.com` and `www.probilliardssoftware.com` (and `app.probilliardssoftware.com` if used) point to your tunnel (e.g. CNAME to `*.cfargotunnel.com` or Cloudflare proxy).

**If Option B returns 502 or timeout:** From the Nginx container, the host API is reached at `host.docker.internal:8003` (compose adds `extra_hosts: host.docker.internal:host-gateway`). On some Linux hosts you may need to allow traffic from the Docker bridge to the host (e.g. port 8003). Ensure the API is bound to **0.0.0.0:8003**, not 127.0.0.1. If **UFW** is active, add rules to allow 8003 from `172.17.0.0/16` and `172.18.0.0/16` (see step 4 in the Bad gateway checklist below).

---

## Bad gateway (502) — fix checklist

When https://www.probilliardssoftware.com/ shows **Bad Gateway**:

1. **Tunnel origin:** In Zero Trust → Tunnels → your probilliards tunnel → Public Hostname, ensure `www.probilliardssoftware.com` → **`http://probilliards-nginx:80`**. Connector container: **cf-probilliards**.

2. **probilliards-nginx running and on network:**
   ```bash
   sudo docker ps -a --filter name=probilliards-nginx
   sudo docker inspect probilliards-nginx --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'
   ```
   If not on `tunnel_network`, connect: `sudo docker network connect tunnel_network probilliards-nginx`. If created without `--add-host=host.docker.internal:host-gateway`, recreate the container with that flag (see nginx-config/README.md).

3. **Host API on 8003:** Something must be listening on **0.0.0.0:8003** (not only 127.0.0.1):
   ```bash
   curl -s http://127.0.0.1:8003/api/health
   ss -tlnp | grep 8003
   ```
   If nothing listens, start the API: `cd ~/rankings-bot/Rankings-Bot && ./scripts/restart_api.sh` or `sudo systemctl start rankings-bot-api`.

4. **Nginx → host from inside Docker:** From the Nginx container, the host is `host.docker.internal:8003`. Test:
   ```bash
   sudo docker exec probilliards-nginx curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 http://rankings-bot-api:8003/api/health
   ```
   If this fails (timeout or non-200), the API is not reachable from the container. Ensure API binds **0.0.0.0:8003** and (on Linux) the container was started with `--add-host=host.docker.internal:host-gateway`. **If UFW is active**, allow port 8003 from Docker/tunnel subnets (tunnel_network is often 172.21.x; see [BAD_GATEWAY_TROUBLESHOOTING.md](BAD_GATEWAY_TROUBLESHOOTING.md)):
   ```bash
   sudo ufw allow from 172.17.0.0/16 to any port 8003 comment 'Rankings bot API from Docker'
   sudo ufw allow from 172.18.0.0/16 to any port 8003 comment 'Rankings bot API from Docker/tunnel'
   sudo ufw allow from 172.21.0.0/16 to any port 8003 comment 'Rankings bot API from tunnel_network'
   ```

5. **Restart tunnel:** `sudo docker restart cf-probilliards`.

Run the full diagnostic script on the server: `sudo ./scripts/diagnose_rankings_bot_gateway.sh` (see below). **Recurring 502?** → Full steps and prevention: [docs/BAD_GATEWAY_TROUBLESHOOTING.md](BAD_GATEWAY_TROUBLESHOOTING.md).

---

## Deploy after a website change

```bash
cd ~/rankings-bot/Rankings-Bot
./scripts/deploy_website.sh --reload-nginx
```

If Nginx runs in Docker (Option B), rebuild/restart the **probilliards-nginx** container instead of `reload nginx` on the host; or use a script that does both (build frontend, restart API, restart nginx container).
