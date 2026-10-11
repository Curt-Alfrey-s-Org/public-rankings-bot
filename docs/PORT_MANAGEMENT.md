# Port Management Guide (Canonical)

**AI / maintainers:** Before editing ports or `127.0.0.1` publishes, read **[NETWORKING_DOC_HOOKS.md](NETWORKING_DOC_HOOKS.md)** (file→doc map and rules). This doc expands on nginx **8088**, API **0.0.0.0**, and production vs multi-bot host bindings.

**Source of truth (multi-bot workspace):** [PORT_ASSIGNMENTS.md](../.github/PORT_ASSIGNMENTS.md) — may differ from Rankings-only Docker production; see *Core Rules* below.

This environment uses **nginx + Cloudflare tunnel** with strict port assignments.
**Nginx ↔ API** uses **Docker DNS** (`rankings-bot-api:8003`, etc.), not host loopback, for the live site path.

Some older notes refer to **APIs on 127.0.0.1 on the host** (multi-bot / host-uvicorn layouts). **Rankings Bot production** in `production/docker-compose.prod.yml` often has the **API only on the Docker network** (no host port publish); tunnel → `probilliards-nginx:80` → API still never requires LAN clients to hit 127.

## Core Rules

- **Host ports are fixed**. Do not change without coordinated updates.
- **When an API is published on the host**, prefer documenting the real bind (Docker production usually has **no** `8003` on the host; use `docker exec` / container DNS for checks).
- **Container internal ports stay 8000** for FastAPI services (Rankings API container uses **8003** internally).
- **Nginx connects via Docker DNS** to the API for production traffic.

## Nginx `8088` publish (Rankings Bot — LAN / headless server)

`nginx-config/docker-compose.nginx.yml` maps host **8088** → nginx **80** for optional local testing.

- **Do not** use **`127.0.0.1:8088:80`** (loopback-only) if you need **Chrome on another PC** on the private network to open **`http://<server-LAN-IP>:8088`**. Loopback bind only accepts connections **to the server itself**, not from other machines (unless you SSH port-forward).
- Use **`8088:80`** (all interfaces) and restrict with **UFW** to your LAN CIDR if needed. Same topic as **API listen address**: see **docs/BAD_GATEWAY_TROUBLESHOOTING.md** (API must listen on **0.0.0.0** inside the container so peers can connect; the “127 net” section there is about **misconceptions for the public site**, not about forbidding loopback everywhere).
- **Public users** still use Cloudflare → tunnel → **`probilliards-nginx:80`** on Docker; they do not use host 8088.

## Current Port Assignments (Host Bindings)

| Service | Host Binding | Container Port |
|---------|--------------|----------------|
| Rankings Bot API | **127.0.0.1:8003** | 8003 |
| Market Bot API | **127.0.0.1:8004** | 8000 |
| Contracts Bot API | **127.0.0.1:8002** | 8000 |
| Credit Check Bot API | **127.0.0.1:8005** | 8000 |
| ATEMS API | **127.0.0.1:5000** | 5000 |

### ALFa AI (alfa-ai repo)

Host defaults are **8412** (API), **8413** (LiteLLM), **5540** (Postgres), **6390** (Redis), **8090** (nginx). They are reserved in the multi-bot map and listed in **[.github/PORT_ASSIGNMENTS.md](../.github/PORT_ASSIGNMENTS.md)** and [alfa-ai/docs/PORT_ASSIGNMENTS.md](../../alfa-ai/docs/PORT_ASSIGNMENTS.md). Host ports **8000-8030** are intentionally avoided for ALFa AI to reduce collisions with local tools and IDEs.

**Operator console (LAN):** Docker Compose may also publish **`8420`** → the same API container (**`http://<host>:8420/operator/`**). Treat it like **8088** for nginx: bind on all interfaces only when you need LAN browsers, then **restrict with UFW** to your private CIDR. Details: [alfa-ai/docs/OPERATOR_CONSOLE.md](../../alfa-ai/docs/OPERATOR_CONSOLE.md).

**Single owner per port:** do not run **both** systemd/host `uvicorn` on **8412** and the **alfa-ai-api** Compose service publishing **8412**. Pick one: full stack in Docker, or hybrid (e.g. systemd API + `docker compose up -d alfa-ai-litellm` only). See [alfa-ai docs/DEPLOYMENT_BASELINE.md](../../alfa-ai/docs/DEPLOYMENT_BASELINE.md).

## Frontend Ports (Optional, Debug Only)

| Service | Host Binding | Notes |
|---------|--------------|-------|
| Rankings Bot Frontend | **5174:80** | Optional local access |
| Market Bot Frontend | **5176:80** | Optional local access |
| Contracts Bot Frontend | **5175:80** | Optional local access |
| Credit Check Bot Frontend | **8009:80** | Optional local access |

## Local Dev Script (Deprecated for Production)

`scripts/configure_ports.sh` is **deprecated for server deployments**.
Use only for local development environments.

## Check Port Conflicts

```bash
# Check if port is in use
sudo lsof -ti :8003

# Kill process on port (if needed)
sudo lsof -ti :8003 | xargs -r sudo kill -9
```

## Troubleshooting

**"Address already in use" error:**
- A service is already bound to that host port
- Stop the conflicting process or container

**API connection failing:**
- Ensure nginx routes to the container DNS name (not host port)
- Verify the API container is healthy and on `tunnel_network`