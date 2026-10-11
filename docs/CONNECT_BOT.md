# Connect the rankings bot to the website

The rankings bot (API + frontend) is reachable via **Nginx** (reverse proxy). Nginx routes requests to the API container.

---

## Architecture

```
Browser → Cloudflare → cf-probilliards → probilliards-nginx (:80) → rankings-bot-api (:8003)
```

- **Nginx container:** `probilliards-nginx` on `tunnel_network`
- **API container:** `rankings-bot-api` on port 8003
- **Upstream:** Nginx proxies to `rankings-bot-api:8003` (container DNS)

---

## Prerequisites

1. **Docker stack running:** `./scripts/full_deploy.sh --force-docker`
2. **Networks:** `tunnel_network` and `rankings-bot-network` exist
3. **Nginx config:** `nginx-config/rankings-bot-cloudflare.conf` (or equivalent) is used by the Nginx container

---

## Verify connectivity

- **Health:** `curl https://www.probilliardssoftware.com/api/health`
- **API:** `curl https://www.probilliardssoftware.com/api/rankings`

---

## Troubleshooting

- **502 Bad Gateway:** See **docs/BAD_GATEWAY_TROUBLESHOOTING.md**
- **Bot not visible:** See **docs/TROUBLESHOOT_BOT_NOT_VISIBLE.md**
- **Updates not showing:** See **docs/WHY_UPDATES_DONT_SHOW.md**
