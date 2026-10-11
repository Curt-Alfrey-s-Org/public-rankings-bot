# Upgrade and version notes

## Docker Compose V2 (required for Docker path)

The **Docker path** of `full_deploy.sh` (no `--no-docker`) uses `docker compose` (Compose V2). The old standalone `docker-compose` (V1) can hit `KeyError: 'ContainerConfig'` with newer Docker daemons.

- **Install (Ubuntu/Debian):** `sudo apt-get install -y docker-compose-v2`
- **Verify:** `docker compose version` → e.g. 2.37.x
- The script prefers `docker compose` when available and falls back to `docker-compose`.

## Current stack (reference)

| Component        | Host / image reference              | Notes |
|-----------------|--------------------------------------|--------|
| Docker          | 27.x                                 | Engine; no change needed. |
| Docker Compose  | 2.37+ (V2 plugin)                    | Use V2 for full deploy Docker path. |
| Python (API)    | 3.12 (Dockerfile: python:3.12-slim)  | Matches requirements; 3.12 LTS. |
| Node (frontend) | 20.x host; Dockerfile node:22-alpine | LTS; 22 in image is fine. |
| PostgreSQL      | 16 (docker-compose image)            | 16 LTS. |
| Redis           | 7-alpine                             | Current stable. |
| Nginx           | alpine (nginx-config image)          | Lightweight; no upgrade needed. |

## When to upgrade

- **Python / Node / Postgres:** When a dependency or security advisory requires a newer major version; test in dev first.
- **Docker / Compose:** Follow Ubuntu/Docker docs; V2 plugin gets updates via `apt upgrade`.
- **Frontend (npm):** `npm audit` and `npm update` periodically; major bumps (e.g. React 19) need testing.
- **Backend (pip):** `pip list --outdated` and bump in `requirements-*.txt` with tests.

No urgent upgrades required beyond using **Docker Compose V2** for the Docker deploy path.

- **Frontend:** Run `npm audit` and `npm audit fix` periodically. A moderate advisory may remain for `esbuild`/Vite (dev server); fixing it would require upgrading to Vite 7 (breaking). For production builds the risk is low; upgrade when ready.
- **Backend:** Run `pip check` and `pip list --outdated`; bump versions in `requirements-api.txt` / `requirements-deps.txt` as needed and re-test.
