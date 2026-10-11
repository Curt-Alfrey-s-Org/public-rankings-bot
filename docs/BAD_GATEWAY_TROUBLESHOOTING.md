# 502 Bad Gateway — Troubleshooting Reference

**AI / maintainers:** For **which file to edit** vs **which doc to read** first, see **docs/NETWORKING_DOC_HOOKS.md**. This document covers upstream/API binding, UFW, and the “127 net” misconception; **docs/PORT_MANAGEMENT.md** covers host **8088** vs **127.0.0.1:8088** for LAN access to nginx.

This doc describes the **recurring** case where the site shows **502 Bad Gateway** after a rebuild or restart, and how to fix and prevent it.

---

## Is the 127 net (loopback) prohibiting the website?

**Short answer: No.** The 127.0.0.0/8 (loopback) range is **not** what blocks the site.

- **Internet switch (iptables):** When the bot “internet forbid” switch is on, the firewall rules **explicitly allow** 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, and 192.0.2.0/24. So 127 (localhost) is **allowed** in both directions; it is not prohibited.
- **Traffic path:** When Nginx runs **in Docker**, it reaches the host API at **host.docker.internal:8003**, which on Linux is the host’s Docker bridge IP (e.g. 172.17.0.1). That traffic is **not** 127; it’s 172.x → host. So the 127 net is not in the path between the nginx container and the API.
- **UFW:** On this server, UFW has a rule like “127.0.0.1 8000 ALLOW IN 127.0.0.1” for “Rankings bot API local only.” That only allows **localhost → port 8000**; it does not block 127 or the website. Nginx in Docker uses port **8003** and is allowed from 172.17/172.18/172.21.

**What usually causes 502:** Port mismatch (API on a different port than Nginx expects), API not bound to 0.0.0.0, or UFW blocking Docker → host on the API port. See below.

**Related (different issue):** If you use **host port 8088** to reach **probilliards-nginx** from another machine on the LAN (headless server + browser on Win11), the Docker **ports** mapping must **not** be loopback-only (`127.0.0.1:8088`). Use **`8088:80`** and see **docs/PORT_MANAGEMENT.md** (section *Nginx `8088` publish*). That is about **who can connect to the published host port**, not about the loopback range “blocking” Cloudflare traffic.

---

## Symptom

- **https://www.probilliardssoftware.com/** returns **502 Bad Gateway** (or times out).
- The host API is running and returns 200 locally: `curl -s http://127.0.0.1:8003/api/health` → 200.
- Flow: **Visitor → Cloudflare → cf-probilliards (tunnel) → probilliards-nginx:80 → host:8003 (API)**. The failure is between **nginx container** and **host API**.

---

## Root cause (recurring)

The **nginx container** reaches the host API at **host.docker.internal:8003**. On Linux that resolves to the host’s Docker bridge IP (often **172.17.0.1**). The container itself is on **tunnel_network**, which can use a **different subnet** (e.g. **172.21.0.0/16**).

If **UFW** (or another firewall) is active, it may **block** traffic from those Docker subnets to the host on port **8003**. Result:

- From the **host**: `curl http://127.0.0.1:8003/api/health` → 200.
- From **inside the nginx container**: `curl http://host.docker.internal:8003/api/health` → **timeout** or connection refused.

So the proxy cannot reach the backend → 502 Bad Gateway.

---

## 1. Diagnose

Run the gateway diagnostic (use sudo if Docker needs it):

```bash
cd /home/ansible/rankings-bot/Rankings-Bot
sudo ./scripts/diagnose_rankings_bot_gateway.sh
```

If **Step 3** fails (“Nginx container cannot reach …”), the container cannot reach the API. The diagnostic tests **rankings-bot-api:8003** first, then **host.docker.internal:8003**. The **live nginx config** may use a different upstream (see `nginx-config/Dockerfile`). If the image uses **HOST-API** (host.docker.internal) but that path fails (e.g. UFW), you get 502 even when the diagnostic passes on rankings-bot-api. **Fix:** Use the config that matches your API: container upstream (`rankings-bot-cloudflare-docker.conf`) when the API runs in Docker; HOST-API only when the API runs on the host.

**Manual check from inside nginx (test the upstream nginx actually uses):**

If the image uses **HOST-API** config:
```bash
sudo docker exec probilliards-nginx curl -v --connect-timeout 5 http://host.docker.internal:8003/api/health
```
If the image uses **container** config (default): `http://rankings-bot-api:8003/api/health` instead.

- **Connection timed out** → firewall (usually UFW) blocking Docker → host:8003 (for host.docker.internal).
- **Connection refused** → nothing listening on 0.0.0.0:8003 or wrong port.

**Confirm API binding:**

```bash
ss -tlnp | grep 8003
# Expect: 0.0.0.0:8003 (not only 127.0.0.1:8003)
```

**Port and bind alignment (very common cause of 502):**

Nginx is configured for **port 8003**. The API must use **8003**. If the API is on a different port, the proxy gets connection refused → 502.

```bash
# See what is listening on 8003
ss -tlnp | grep 8003
```

- If the API is on a different port, update your Docker Compose configuration to use port 8003.
- The API must listen on **0.0.0.0** (not 127.0.0.1 only) so that both localhost and Docker (host.docker.internal) can connect. Scripts use `--host 0.0.0.0`; if your systemd unit overrides this, fix it to 0.0.0.0.

**Port 8003 conflict (host API vs Docker API):**

Only one process may bind to 8003. If you see `bind: address already in use`:

- **Standard (production):** Use **one** owner of port 8003 — either **`rankings-bot-api` in Docker Compose** or a **host** `systemd`/`uvicorn` service, not both. If systemd holds 8003, stop the API container (or don’t start it). If Compose owns 8003, disable/stop the host unit: `sudo systemctl stop rankings-bot-api` (if defined). Deploy: **`./scripts/full_deploy.sh`** for the full stack, or **`./scripts/deploy_website.sh`** for frontend-only (Docker build + API restart).

---

## 2. Fix: Allow Docker/tunnel subnets in UFW

If UFW is active, allow port **8003** from the subnets Docker uses. **Include the subnet of tunnel_network** (it can be 172.18, 172.21, etc., depending on the host).

**Option A – Add common subnets (recommended):**

```bash
sudo ufw allow from 172.17.0.0/16 to any port 8003 comment 'Rankings bot API from Docker'
sudo ufw allow from 172.18.0.0/16 to any port 8003 comment 'Rankings bot API from Docker/tunnel'
sudo ufw allow from 172.21.0.0/16 to any port 8003 comment 'Rankings bot API from tunnel_network'
sudo ufw status | grep 8003
```

**Option B – Use tunnel_network’s subnet only:**

```bash
# Get tunnel_network subnet (e.g. 172.21.0.0/16)
docker network inspect tunnel_network --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}'

# Then allow that subnet (replace with the value above)
sudo ufw allow from 172.21.0.0/16 to any port 8003 comment 'Rankings bot API from tunnel_network'
```

**Reload UFW** if you change rules: `sudo ufw reload`.

Then re-run the diagnostic; Step 3 should pass and the site should load.

---

## 3. Prevention

- **Use port 8003 for the API.** Nginx (HOST-API config) and UFW are set up for **8003**. Configure your Docker Compose to expose the API on port 8003.

- **Use the full bring-up script** so firewall and connectivity are re-checked on every rebuild:
  ```bash
  cd /home/ansible/rankings-bot/Rankings-Bot
  ./scripts/full_deploy.sh
  ```
  When systemd (rankings-bot-api.service) exists, the script uses the host API path automatically. That ensures UFW allows **172.17.0.0/16** and the **tunnel_network** subnet to port 8003, and verifies that the nginx container can reach the host API.

- **After any UFW or Docker network change** (or if you add a new Docker network), ensure port 8003 is allowed from that network’s subnet if the nginx container uses it to reach the host.

---

## 4. After full_deploy, site still Bad Gateway

If `./scripts/full_deploy.sh` reports success (including “Nginx can reach API”) but the website still returns **502 Bad Gateway**:

- **Host API (standard):** Check that the host API is running: `curl -s http://127.0.0.1:8003/api/health`. If not, `sudo systemctl restart rankings-bot-api`. Ensure nginx was built with `USE_HOST_API=1` (see nginx-config/Dockerfile).
- **Docker path:** The API container may have exited after deploy or the wrong container may be running.

1. **Diagnose**
   ```bash
   cd /home/ansible/rankings-bot/Rankings-Bot
   sudo ./scripts/diagnose_rankings_bot_gateway.sh
   ```
   Check that **rankings-bot-api** is running and on **tunnel_network**:
   ```bash
   sudo docker ps -a --filter name=rankings-bot-api
   sudo docker ps -a --filter name=probilliards-nginx
   sudo docker inspect rankings-bot-api --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}'
   ```
   If the API container is exited, inspect logs: `sudo docker logs rankings-bot-api --tail 100` (look for “Shutting down” or errors).

2. **Restore the API** (if rankings-bot-api is stopped or missing)  
   Ensure Postgres is up (same stack as API — **`production/docker-compose.prod.yml`**; root `docker-compose.yml` includes it). Then:
   ```bash
   cd /home/ansible/rankings-bot/Rankings-Bot
   sudo docker compose -f production/docker-compose.prod.yml up -d rankings-bot-api
   ```

3. **Confirm nginx can reach the API**
   ```bash
   sudo docker exec probilliards-nginx curl -s -o /dev/null -w "%{http_code}" http://rankings-bot-api:8003/api/health
   ```
   Expect **200**. If you get non-200, run the diagnostic again and fix networks/UFW as in sections 1–2 above.

**Note:** The deploy script’s step 2d (restore Docker networks) must **only connect networks** and must **not** stop or restart the API container. If you use a custom `restore-docker-networks.sh`, ensure it does not stop/restart `rankings-bot-api`.

---

## 5. Checklist summary

| Check | Command / action |
|-------|-------------------|
| 127 net blocking? | No — internet switch allows 127/8; Nginx in Docker uses 172.x, not 127. See “Is the 127 net prohibiting…” above. |
| API port = 8003 | `ss -tlnp \| grep 8003` — API must be on 8003. |
| API up on host | `curl -s http://127.0.0.1:8003/api/health` → 200 |
| API bound to 0.0.0.0 | `ss -tlnp \| grep 8003` → `0.0.0.0:8003` (not only 127.0.0.1) |
| Nginx → host from container | `sudo docker exec probilliards-nginx curl -s -o /dev/null -w "%{http_code}" http://host.docker.internal:8003/api/health` → 200 |
| UFW allows Docker/tunnel → 8003 | `sudo ufw status \| grep 8003`; add 172.17.0.0/16, 172.18.0.0/16, 172.21.0.0/16 (or tunnel_network subnet) |
| Full diagnostic | `sudo ./scripts/diagnose_rankings_bot_gateway.sh` (see also **master-control.md**) |

---

## 6. See also

- **Bad gateway (502) — fix checklist:** [CLOUDFLARE_TUNNEL_NGINX.md](CLOUDFLARE_TUNNEL_NGINX.md#bad-gateway-502--fix-checklist)
- **Request flow:** [REQUEST_FLOW_AND_ARCHITECTURE.md](REQUEST_FLOW_AND_ARCHITECTURE.md)
- **Diagnostic script:** `scripts/diagnose_rankings_bot_gateway.sh`
- **Full rebuild and start (includes UFW step):** `scripts/full_deploy.sh`
- **Full deploy script and errors to avoid:** [FULL_DEPLOY_AND_ERRORS.md](FULL_DEPLOY_AND_ERRORS.md) — swarm, rebuild button, API ImportError, .env typos, bash completion
