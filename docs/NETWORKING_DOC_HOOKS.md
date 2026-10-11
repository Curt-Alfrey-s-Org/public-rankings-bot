# Networking & ports — doc hooks for AI and maintainers

**Process (how we use these hooks):** [AI_INLINE_DOC_REF_PROCESS.md](AI_INLINE_DOC_REF_PROCESS.md)

**Purpose:** Central index so tools and humans **read the right docs before changing** Docker publishes, loopback (`127.0.0.1`), or the tunnel → nginx → API path. **Do not assume** “everything is localhost” or “127 blocks the site” without reading the linked sections.

**Indexed in:** [docs/INDEX.md](INDEX.md) (Deployment & Operations).

---

## Rules (read the linked docs for full context)

1. **Public site path:** Visitor → **Cloudflare Tunnel** → **`probilliards-nginx:80`** → **`rankings-bot-api:8003`** using **Docker DNS** on `tunnel_network` / `rankings-bot-network`. This path does **not** use the host’s `127.0.0.0/8` range between tunnel and API when the API runs in Compose.

2. **Host port `8088` (optional):** Maps host → **probilliards-nginx** for local/LAN testing. Use **`8088:80`** (all interfaces) if **another PC** on the LAN must open `http://<server-LAN-ip>:8088`. **`127.0.0.1:8088:80`** only accepts connections **to the server itself** (loopback), not from other machines—unless you SSH port-forward.

3. **API process bind address (inside container):** The API must listen on **`0.0.0.0:8003`** inside the container so nginx and healthchecks can reach it. This is **not** the same topic as Docker **publish** bind (item 2). See **docs/BAD_GATEWAY_TROUBLESHOOTING.md** (“127 net” section + API binding).

4. **Older multi-bot docs** (e.g. `.github/PORT_ASSIGNMENTS.md`) may say “API on **127.0.0.1** on the host”; **Rankings Bot production** often has **no** host publish for the API. See **docs/PORT_MANAGEMENT.md**.

---

## Source file → documentation (hooks)

| Repository path | Read these docs |
|-----------------|-----------------|
| `nginx-config/docker-compose.nginx.yml` | **docs/PORT_MANAGEMENT.md** (section *Nginx `8088` publish*), **docs/BAD_GATEWAY_TROUBLESHOOTING.md** (loopback myths + related 8088 note), **docs/MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md** |
| `nginx-config/Dockerfile` | **docs/CLOUDFLARE_TUNNEL_NGINX.md**, **docs/MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md**, **nginx-config/README.md** |
| `nginx-config/rankings-bot-*.conf` | **docs/FIX_PRODUCTION_LOGIN_404_405.md**, **docs/BAD_GATEWAY_TROUBLESHOOTING.md** |
| `production/docker-compose.prod.yml` | **docs/PORT_MANAGEMENT.md**, **docs/REQUEST_FLOW_AND_ARCHITECTURE.md**, **docs/BAD_GATEWAY_TROUBLESHOOTING.md**, **docs/PRODUCTION_DEPLOYMENT.md** |
| `scripts/full_deploy.sh` | **docs/PRODUCTION_DEPLOYMENT.md**, **docs/PORT_MANAGEMENT.md**, **docs/NETWORKING_DOC_HOOKS.md** (this file) |
| `scripts/start.sh`, `scripts/start_web.sh` | **This file**, **docs/MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md** |
| `scripts/switch-site.sh` | **docs/MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md** |

Inline comments in those files repeat `docs/...` paths so searches and AI context stay aligned with this table.
