# Production 404/405: Problem and Fix (Tunnel → Nginx → API)

**Symptoms:** On https://www.probilliardssoftware.com, `GET /api/splash-config` returns **404**, and `POST /api/auth/login` or `POST /api/logs/frontend` return **405**. Login fails. Direct calls to the API (e.g. `curl http://127.0.0.1:8003/api/splash-config`) succeed.

**Scope:** Traffic path is **Cloudflare Tunnel → probilliards-nginx → rankings-bot-api**. The problem is in this chain (tunnel to app), not in Cloudflare DNS or zone settings.

## Quick reference: what went wrong

| Symptom | Cause | Fix |
|---------|-------|-----|
| 404 on GET /api/splash-config | nginx `proxy_pass` with URI part rewrote the path | Use `proxy_pass http://$backend_rankings` (no URI) |
| 405 on POST /api/auth/login | Same URI rewriting affected method/path | Same fix |
| Direct API works, public URL fails | Request changed between tunnel → nginx → API | Fix nginx proxy_pass; rebuild API if middleware added |

---

## 1. Problem summary

| Observation | Meaning |
|-------------|--------|
| 404 body is `{"detail":"Not Found"}` | Response comes from **FastAPI** (the API), not nginx. So the request reaches the API. |
| Direct to API (127.0.0.1:8003) returns 200 for `/api/splash-config` | API routes are correct when path/method are as expected. |
| Through nginx (same host), same path returns 404 | The **path or method** the API sees when traffic goes through nginx differs, so a different handler runs. |
| 405 on POST login | Route is found but **method** is wrong (e.g. GET instead of POST), or a redirect turned POST into GET. |

So: **path normalization** (e.g. trailing slash) and **method preservation** across the proxy chain are the focus.

---

## 2. Root cause (why the API returns 404)

### 2.1 API container has no frontend build

- The **rankings-bot API** Docker image does **not** include the built React app: the Dockerfile has `RUN mkdir -p /app/frontend/dist` but does not `COPY` frontend build artifacts (see [Dockerfile](https://docs.docker.com/reference/dockerfile/) best practice: only copy what the process needs; here the API serves only the API, and nginx serves the SPA from elsewhere or from the same host).
- So at runtime, `frontend/dist` exists but is **empty** (no `assets/`). The API uses the **else** branch in `api/main.py`: it registers a **catch-all** route `GET /{path:path}` that:
  - returns **404** for any path starting with `api` (so “unknown” API paths are not served as static files);
  - returns 503 with a “Frontend not deployed” message for other paths.

References:

- [FastAPI: Path Operations](https://fastapi.tiangolo.com/tutorial/path-operations/) — route order and path matching.
- [Starlette routing](https://www.starlette.io/routing/) — first matching route wins; `/{path:path}` is a catch-all.

### 2.2 Trailing slash: catch-all wins over API route

- FastAPI/Starlette match routes **literally**. A route defined as `/api/splash-config` (no trailing slash) does **not** match a request with path `/api/splash-config/`.
- When a proxy or tunnel sends **`/api/splash-config/`** (with trailing slash), the exact route does not match, so the **catch-all** `GET /{path:path}` matches with `path = "api/splash-config/"`. The handler then does `if path.startswith("api"): raise HTTPException(404)`, so the client gets **404**.
- So a **trailing slash** in the request path (after nginx proxy) is enough to make the API return 404 for an otherwise valid API path.

Industry practice: proxies and backends often **normalize** paths (e.g. strip trailing slashes for API routes) so that routing is consistent. See [RFC 3986](https://www.rfc-editor.org/rfc/rfc3986) (path structure) and common proxy behavior (e.g. [nginx `proxy_pass`](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass) passes the request URI by default; normalization is often done at the application layer when proxies do not alter the path).

### 2.3 405 Method Not Allowed

- 405 means the **path** was matched but the **HTTP method** was not allowed for that route.
- If the tunnel or nginx (or a redirect) turns a **POST** into a **GET**, or forwards to a wrong path, the API would respond with 405 (or 404). So the fix is to ensure **method and path are preserved** through the chain (tunnel → nginx → API).

---

## 3. Fix (aligned with nginx, Docker, Python/FastAPI, React)

### 3.1 Application-side: normalize `/api` path (trailing slash)

**Done in code:** In `api/main.py`, **StripApiTrailingSlashMiddleware** runs first (outermost middleware). It rewrites the path so that `/api/.../` becomes `/api/...` before routing:

- For any request whose path starts with `/api`, ends with `/`, and has length > 4, set `scope["path"]` to the path with trailing slash removed.
- Routing then sees the path **without** trailing slash, so `/api/splash-config` and other API routes match correctly.

This follows:

- **FastAPI/Starlette:** Middleware can mutate `request.scope["path"]` before routing; routing then uses the normalized path. See [Starlette middleware](https://www.starlette.io/middleware/).
- **Python/ASGI:** The `scope` dict is the standard way to pass request data; modifying `scope["path"]` is valid and used for path rewriting.

No change to nginx or tunnel is required for the trailing-slash case; the API tolerates both forms.

### 3.2 Nginx: preserve method and path

- **`proxy_pass`:** Use `proxy_pass http://backend` (no URI part) so the full request URI is passed unchanged. With a URI part (e.g. `proxy_pass http://backend/api/`), nginx rewrites the URI and can cause 404/405. See [nginx proxy_pass](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass).
- **Method:** Do not use directives that change the method (e.g. avoid converting POST to GET). Our config uses `proxy_method $request_method` only when needed; the default is to forward the original method.
- **Host:** `proxy_set_header Host $host` preserves the original host so the API sees the same Host as the client.

Our production config: `rankings-bot/nginx-config/rankings-bot-production.conf` — `location /api/` uses `proxy_pass http://$backend_rankings` (no URI part) so the full request URI is passed unchanged; Host and headers set.

### 3.3 Tunnel (Cloudflare)

- One public hostname for **www.probilliardssoftware.com** (and apex if used) pointing at **http://probilliards-nginx:80**, with path “all” (no path filter). So **all** traffic for that host goes to nginx; nginx then routes `/api/` to the API and `/` to the app. No separate route that sends `/api` elsewhere (which would cause 404/405).
- No redirect or rule that converts POST to GET or changes the request path for `/api/*`.

### 3.4 Docker

- **Single process per container:** The API container runs one process (uvicorn). Nginx runs in its own container. No duplicate ownership of the same port. See [Twelve-Factor: Processes](https://12factor.net/processes) and project `.github/CODING_STANDARDS.md`.
- **Network:** Containers use the same Docker network (`tunnel_network`) so nginx can reach `rankings-bot-api:8003`. Port mappings follow `.github/PORT_ASSIGNMENTS.md`.

### 3.5 React / SPA

- Frontend calls same-origin `/api/...`. The browser sends requests to the same host (e.g. www.probilliardssoftware.com); the tunnel and nginx forward them to the API. No CORS or path changes are required for same-origin API calls; the fix is path/method preservation and normalization on the server side.

---

## 4. What we changed (so you don’t have to re-solve it)

| Item | Location | Change |
|------|----------|--------|
| **Trailing slash normalization** | `rankings-bot/api/main.py` | **StripApiTrailingSlashMiddleware**: rewrite `scope["path"]` for `/api/.../` → `/api/...` before routing. |
| **Nginx** | `rankings-bot/nginx-config/rankings-bot-production.conf` | Main server block is `default_server`; `location /api/` uses `proxy_pass http://$backend_rankings` (no URI part) so the full request URI is passed unchanged to the API; Host and method preserved. |
| **Tunnel** | Cloudflare Zero Trust | Single hostname for www (and apex) → `http://probilliards-nginx:80`, path “all”. No separate `/api` route. |

---

## 5. Verification

1. **Direct API** (from host):  
   `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8003/api/splash-config`  
   Expect **200**.

2. **Through nginx** (from host or from inside nginx container):  
   `curl -s -o /dev/null -w "%{http_code}" -H "Host: www.probilliardssoftware.com" http://127.0.0.1:80/api/splash-config`  
   Expect **200** (and **200** for `/api/splash-config/` after the middleware fix).

3. **Public URL:**  
   Run `./scripts/verify_production.sh`. Public URL steps should get **200** for splash-config and **401** or **200** for login (not 404/405).

4. **Login:**  
   Use https://www.probilliardssoftware.com and log in; no 404 on splash-config, no 405 on login.

---

## 6. If 404/405 come back

- **Fix not deployed:** The running API container may use an old image. Rebuild and restart: `sudo docker compose -f production/docker-compose.prod.yml build rankings-bot-api && sudo docker compose -f production/docker-compose.prod.yml up -d --force-recreate rankings-bot-api` (or `sudo ./scripts/full_deploy.sh --production`).
- **404:** Check that the request path the API sees is the one you expect (no unwanted trailing slash, no extra prefix). The middleware handles trailing slash; if the path is still wrong, check nginx and tunnel for path rewrites or multiple routes.
- **405:** Check that the **method** (GET/POST) is preserved. Inspect nginx/tunnel for redirects or rules that change the method. Optionally add short-lived logging in the API for `request.method` and `request.url.path` on `/api/auth/login` to confirm.
- **Direct OK, public not:** Fix is in tunnel or nginx (hostname, path, method preservation), not in Cloudflare zone/DNS.

---

## 7. References (industry standards)

| Topic | Reference |
|-------|-----------|
| Nginx proxy | [ngx_http_proxy_module](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass) — `proxy_pass`, request URI |
| FastAPI / Starlette | [Path operations](https://fastapi.tiangolo.com/tutorial/path-operations/), [Starlette routing](https://www.starlette.io/routing/), [middleware](https://www.starlette.io/middleware/) |
| ASGI scope | [ASGI spec](https://asgi.readthedocs.io/en/latest/specs/www.html) — `scope["path"]` |
| Docker / processes | [Twelve-Factor: Processes](https://12factor.net/processes), project `.github/CODING_STANDARDS.md` |
| Ports / network | `.github/PORT_ASSIGNMENTS.md`, `DOCKER_NETWORK_CONSTANTS.md` |

---

## 8. Avoiding this problem

1. **Nginx `proxy_pass` for /api/:** Use `proxy_pass http://$backend_rankings` (no URI part). Do **not** use `proxy_pass http://$backend_rankings/api/` — the URI part triggers rewriting and can cause 404/405.

2. **After API code changes:** Rebuild and restart the API container so middleware and route changes take effect.

3. **Tunnel config:** One hostname for www → `http://probilliards-nginx:80`, path "all". No separate /api route.

4. **Verification:** Run `./scripts/verify_production.sh` after deploy. If direct API is OK but public URL fails, the issue is in nginx or tunnel.
