# 404 Diagnostic for www.probilliardssoftware.com

## Root causes and fixes applied

### 1. Nginx: wrong server_name
**Problem:** `nginx-config/rankings-bot.conf` used `rankings.probilliardssoftware.com` but the domain is `www.probilliardssoftware.com`.

**Fix:** Updated server_name and SSL cert paths to `www.probilliardssoftware.com`.

**Apply:** If using Nginx, update config and reload nginx.

### 2. Nginx: separate frontend/API upstreams
**Problem:** Nginx proxied `/` to 5176 and `/api` to 8003.

**Fix:** Single upstream `rankings_bot` on 8003. All traffic goes to the API.

### 3. frontend/dist must exist
**Problem:** API returns 503/404 when `frontend/dist` is missing.

**Fix:** Build the frontend:
```bash
cd Rankings-Bot/frontend
npm install && npm run build
```

## Checklist for deployment

- [ ] API running on 0.0.0.0:8003 (not 127.0.0.1)
- [ ] `frontend/dist` exists (run `npm run build` in frontend/)
- [ ] Nginx (or probilliards-nginx) routes `www.probilliardssoftware.com` to API:8003
- [ ] SSL cert exists for `www.probilliardssoftware.com`

## Verify

```bash
# Health
curl https://www.probilliardssoftware.com/api/health

# Root (should return HTML)
curl -I https://www.probilliardssoftware.com/
```
