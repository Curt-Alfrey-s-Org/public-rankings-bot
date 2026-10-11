# Port Assignments (Source of Truth)

This file defines the canonical port assignments for all services in the rankings-bot environment.

## Core Rules

- **Host ports are fixed**. Do not change without coordinated updates across all repositories.
- **APIs bind to 127.0.0.1 on the host** (localhost only for security).
- **Container internal ports stay 8000** for FastAPI services.
- **Nginx connects via Docker DNS**, not host ports.

## API Host Bindings (Production)

| Service | Host Binding | Container Port | Repository |
|---------|--------------|----------------|------------|
| Rankings Bot API | **127.0.0.1:8003** | 8003 | rankings-bot |
| Market Bot API | **127.0.0.1:8004** | 8000 | market-pie5-bot |
| Contracts Bot API | **127.0.0.1:8002** | 8000 | contracts-bot |
| Credit Check Bot API | **127.0.0.1:8005** | 8000 | credit-check-bot |
| RV Auto Finder API | **127.0.0.1:8011** | 8011 | rv-auto-finder |
| ATEMS API | **127.0.0.1:5000** | 5000 | atems |

## ALFa AI (separate repo; host bindings)

Canonical detail: [alfa-ai/docs/PORT_ASSIGNMENTS.md](../../alfa-ai/docs/PORT_ASSIGNMENTS.md). Defaults must **not** collide with the API bindings above.

| Service | Host binding | Container / notes | Repository |
|---------|--------------|-------------------|------------|
| ALFa AI API | **127.0.0.1:8412** | 8000 in container **or** host `uvicorn` (see alfa-ai deploy docs — **one owner** per port) | alfa-ai |
| ALFa AI LiteLLM | **127.0.0.1:8413** | 4000 in container | alfa-ai |
| ALFa AI Postgres | **127.0.0.1:5540** | 5432 in container | alfa-ai |
| ALFa AI Redis | **127.0.0.1:6390** | 6379 in container | alfa-ai |
| ALFa AI nginx | **127.0.0.1:8090** | 80 in container | alfa-ai |
| ALFa AI operator console (LAN) | **0.0.0.0:8420** (default; Docker maps host **8420** → API **8000**) | Same API as **8412**; path **`/operator/`** | alfa-ai |

**8420** is intentionally reachable on the LAN for the operator UI; restrict with **UFW** to your private CIDR. See [alfa-ai/docs/OPERATOR_CONSOLE.md](../../alfa-ai/docs/OPERATOR_CONSOLE.md).

**Petals worker port (31330):** Not bound on the rankings-bot / main web host by default. Each **GPU worker** (e.g. current hub worker peer at **`192.0.2.157`**; management/UI still on **`192.0.2.30`**) listens on **31330/tcp** for the Petals DHT; allow that port from the ALFa AI host to workers. See [alfa-ai/docs/NODE_INVENTORY.md](../../alfa-ai/docs/NODE_INVENTORY.md) and [alfa-ai/docs/PORT_ASSIGNMENTS.md](../../alfa-ai/docs/PORT_ASSIGNMENTS.md).

## Frontend Development Ports (Debug Only)

| Service | Host Binding | Repository | Notes |
|---------|--------------|------------|-------|
| Rankings Bot Frontend | **5174:80** | rankings-bot | Vite dev server |
| Market Bot Frontend | **5176:80** | market-pie5-bot | Vite dev server |
| Contracts Bot Frontend | **5175:80** | contracts-bot | Vite dev server |
| Credit Check Bot Frontend | **8009:80** | credit-check-bot | Vite dev server |
| RV Auto Finder Frontend | **5181:5181** | rv-auto-finder | React/Vite frontend |

## Port Change Procedure

1. Update this file with new port assignment
2. Update corresponding repository configurations:
   - `vite.config.ts` (frontend port)
   - `scripts/start_gui.sh` (FRONTEND_PORT variable)
   - Documentation references
3. Test all affected services
4. Update `docs/PORT_MANAGEMENT.md` to reflect changes

## Verification

```bash
# Check if port is available
sudo lsof -i :5174

# Check service health
curl http://localhost:5174
curl http://localhost:8003/api/health
```