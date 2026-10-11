# Full Deploy Script and Errors to Avoid

This doc describes **scripts/full_deploy.sh**, the admin **Rebuild & start all images** button, and common errors so you can avoid or fix them quickly.

---

## When to use full_deploy.sh

- **Intended for nightly maintenance** (run once per day). The script is long-running (Docker build, nginx, tunnel).
- Use it when you want to: rebuild the API (and optional frontend) image, restart app containers, rebuild/restart nginx, ensure firewall and tunnel are up.
- For quick website-only updates on the Docker host: run `./scripts/build_frontend_with_docker.sh` (or `./scripts/deploy_website.sh` if your stack uses it), then refresh/restart per your compose layout. **Do not use host npm** for production frontend builds.
- **Deployment:** The script uses Docker Compose for all services. See [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md).

---

## How the script runs

- **Starts under `/bin/sh`** then **re-execs with `/bin/bash --norc --noprofile`** so it does not inherit your shell’s `BASH_ENV` or completion. That avoids errors like `_parse_usage: syntax error` when your terminal has broken bash completion.
- **Leaves Docker swarm** if the engine is in swarm mode, so compose works (see “Docker swarm / Compose V2” below).
- **Verbose build output:** sets `BUILDKIT_PROGRESS=plain` so Docker build streams full logs instead of a single updating line (so it’s clear the script is not hung).
- **Timeouts:** build step and “up” step have timeouts so a stuck compose or build does not hang the script forever.
- **Network restore (Docker path):** After bringing up the app stack, runs `restore-docker-networks.sh` (if present under `~/scripts/`) so the standard network pattern is applied (rankings-bot-network + tunnel_network). Step 6 verifies nginx can reach the API via `rankings-bot-api:8003` or `host.docker.internal:8003`.

---

## Admin “Rebuild & start all images” button

The button in **Settings → Admin** runs the same full deploy (script path resolved on the server).

- **API on the host:** The API must be started with **`REBUILD_ALL_IMAGES_SCRIPT`** set to the full path of `scripts/full_deploy.sh`, or the button will show “Rebuild not available on this server.”
  - **restart_api.sh** and **start_api.sh** set it automatically.
  - **systemd:** Add to your service file:
    - `Environment="REBUILD_ALL_IMAGES_SCRIPT=/path/to/Rankings-Bot/scripts/full_deploy.sh"`
  - After changing env or installing the service, **restart the API** once so it picks up the variable.
- **API in Docker:** The production compose file sets `REBUILD_ALL_IMAGES_SCRIPT=/app/scripts/full_deploy.sh` in the API container so the button works without extra config.

---

## Errors to avoid

### 1. Docker swarm / Compose V2

- **Symptom:** “The Docker Engine you're using is running in swarm mode” and/or **`KeyError: 'ContainerConfig'`** when running `docker-compose up -d` or `full_deploy.sh`.
- **Cause:** Docker in swarm mode, or using **Docker Compose V1** (standalone `docker-compose`) with a newer Docker daemon, which can hit a `ContainerConfig` bug.
- **Fix:**
  1. **Use Docker Compose V2:** Install and use `docker compose` (V2 plugin). See **docs/UPGRADE_AND_VERSIONS.md**. Scripts prefer V2 when available.
  2. **Leave swarm** if active: full deploy does `docker swarm leave --force` at the start. For manual runs: `sudo docker swarm leave --force`.
- **If you need swarm for other projects:** Run `full_deploy.sh` only when swarm can be left; or run rankings-bot on a host that is not in swarm.

### 2. “Rebuild not available” / script not found (host API)

- **Symptom:** Admin page shows “Rebuild not available on this server” or “Full-deploy script not found” under the button.
- **Cause:** API runs on the **host** and was started without `REBUILD_ALL_IMAGES_SCRIPT` (or the path is wrong).
- **Fix:**
  - Start the API with **restart_api.sh** or **start_api.sh** (they set the variable), or
  - Set and export before starting uvicorn:  
    `export REBUILD_ALL_IMAGES_SCRIPT="/full/path/to/Rankings-Bot/scripts/full_deploy.sh"`
  - For systemd: add `Environment="REBUILD_ALL_IMAGES_SCRIPT=..."` to the service file, then `sudo systemctl daemon-reload && sudo systemctl restart rankings-bot-api`.

### 3. API won’t start: `ImportError: cannot import name 'require_super_admin'`

- **Symptom:** API exits on startup with:
  - `ImportError: cannot import name 'require_super_admin' from 'api.auth'`
- **Cause:** `api/auth.py` must define **`require_super_admin`**; routes (e.g. `api/routes/auth.py`, `admin.py`) depend on it. If the function is removed or renamed, the import fails.
- **Fix:** Ensure **api/auth.py** defines:
  - `def require_super_admin(user: dict = Depends(get_current_user)) -> dict:`
  - with a check for `role == "super_admin"` and 403 otherwise. Do not remove this function.

### 4. .env breaks startup (“loqe” or command not found when sourcing .env)

- **Symptom:** When you run `restart_api.sh` or source `.env`, you see something like **`command 'loqe' not found`** (or another unknown command).
- **Cause:** A line in **`.env`** is being executed as a shell command (e.g. a typo like `loqe` instead of a variable, or an unquoted value that runs as a command).
- **Fix:** Edit **`.env`** and fix or remove the bad line. Keep only valid `KEY=value` lines; do not run arbitrary commands from `.env`. After fixing, restart the API.

### 5. full_deploy.sh “hangs” or script doesn’t end

- **Symptom:** Script seems to hang after “naming to docker.io/library … 0.0s” or during “Restarting app containers.”
- **Cause:** Compose “up” can hang under swarm (see #1) or in edge cases. The script uses timeouts so it will eventually continue or exit.
- **Fix:** Use Docker Compose V2 and ensure swarm is left (script does this automatically). If you still see a hang, the step will time out (e.g. 2 minutes for “up”); check Docker/compose logs for the underlying error.

### 6. Port 8003 conflict (host API vs Docker API)

- **Symptom:** `bind: address already in use` or `failed to bind port 127.0.0.1:8003/tcp` when running `full_deploy.sh`.
- **Cause:** Two processes try to use 8003: systemd (host API) and the Docker API container. Only one may bind.
- **Fix:** Only one process may bind 8003. **Pick one:** Docker **`rankings-bot-api`** (recommended; see `production/docker-compose.prod.yml`) **or** a host API service — not both. If a stale host unit exists: `sudo systemctl stop rankings-bot-api` (if applicable), then **`./scripts/full_deploy.sh`**. See [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md).

### 7. Bash completion errors when running scripts in terminal

- **Symptom:** When you run `./scripts/restart_api.sh` or other scripts, you see:
  - `bash: _parse_usage: line 16: syntax error near unexpected token '('`
  - `bash: error importing function definition for '_parse_usage'`
- **Cause:** Your shell loads bash completion (e.g. via `BASH_ENV` or profile) that has a syntax error.
- **Fix:** **full_deploy.sh** re-execs with a clean bash so it runs without those errors. For **restart_api.sh**, either fix your `BASH_ENV`/completion files or run the API in a clean environment, e.g.:
  - `env BASH_ENV= /bin/bash --norc --noprofile -c 'cd /path/to/Rankings-Bot && ./scripts/restart_api.sh'`

---

## See also

- **docs/UPGRADE_AND_VERSIONS.md** — Docker Compose V2 install and stack versions.
- **docs/DEPLOY_UPDATES.md** — When to rebuild and how updates reach the live site.
- **docs/BAD_GATEWAY_TROUBLESHOOTING.md** — 502 and nginx → API connectivity.
- **docs/rankings-bot-api.service.example** — systemd example with `REBUILD_WEBSITE_SCRIPT` and `REBUILD_ALL_IMAGES_SCRIPT`.
