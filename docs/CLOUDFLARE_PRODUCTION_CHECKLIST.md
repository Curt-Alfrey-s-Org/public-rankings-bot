# Production: Cloudflare & Tunnel Checklist

When the site is in **production** (`./scripts/switch-site.sh production`), the app at https://www.probilliardssoftware.com must reach your API. If you see **405 Method Not Allowed** on login or **404** on `/api/splash-config`, the request is often altered or mis-routed before it reaches nginx/API.

---

## 1. Tunnel: single public hostname for www

In **Cloudflare Zero Trust** → **Networks** → **Tunnels** → **cf-probilliards** → **Public Hostname**:

- **One** hostname: **www.probilliardssoftware.com** (and optionally **probilliardssoftware.com**) → **http://probilliards-nginx:80**.
- **Do not** add a **Path** rule that sends **/api/\*** to a *different* service. All traffic for www must go to the same nginx so it can proxy both the SPA and `/api/` to the API.

## 2. Redirect rules

In **Cloudflare Dashboard** → your zone → **Rules** → **Redirect Rules**:

- Ensure no rule redirects **https://www.probilliardssoftware.com** (or **/api/**) in a way that causes the **browser to resend the request as GET**. A redirect on the same URL can turn POST into GET and cause 405.
- Use **https://www.probilliardssoftware.com** for all app and API requests (not apex or HTTP).

## 3. Verify from the server

Run the verification script (see below). It checks that the API accepts requests directly; if that passes but the public URL fails, the issue is between the browser and your server (Cloudflare/tunnel).

---

## Verification script

From repo root:

```bash
./scripts/verify_production.sh
```

This checks:

- **Direct API** (http://127.0.0.1:8003): GET /api/splash-config, POST /api/auth/login (expect 401 or 200). If these fail, fix the API/stack first.
- **Public URL** (optional): GET and POST to https://www.probilliardssoftware.com/api/... If direct works but public returns 405/404, fix Cloudflare/tunnel using this checklist.
