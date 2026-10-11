# Environment Variables

Required and optional environment variables for Rankings-Bot. Copy `.env.example` (or the
per-environment placeholder templates `.env.production.example`, `.env.staging.example`,
`.env.development.example`, `.env.ports.example`, `staging.env.sh.example`) to the git-ignored
`.env` and fill in values. Never commit real env files. `.env.*`, `*.env`, `staging.env.sh` and
`env.production.snippet` are git-ignored; only `*.example` templates are tracked.

## Required (Core)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (e.g. `postgresql://user:pass@host:5432/db`) |
| `TEST_CENTER_DATABASE_URL` | **Production (set by Compose):** connection string to the dedicated `postgres-testcenter` container — a completely separate Postgres instance (own process, memory, WAL, connections) so Test Center can never impact live data or resources. Per PostgreSQL docs, databases on the same cluster share the postmaster, `shared_buffers`, and `max_connections`; a separate instance avoids all of that. If unset, Test Center falls back to `DATABASE_URL` with a warning (not recommended). |
| `JWT_SECRET` | Strong random secret for JWT signing; **never use default in production** |
| `BOT_API_KEY` | **Required in production** (the API refuses to start without it). Anonymous server-to-server callers (e.g. the USPBF nginx proxy) must send it as `X-API-Key` together with `X-User-Role: user`. Must equal USPBF's `BOT_API_KEY`. Optional with `DEBUG=true` (check skipped with a warning). See [API_ACCESS_POLICY.md](API_ACCESS_POLICY.md). |

## Auth Bootstrap

Used **only at API startup** to create users that do not exist yet; existing users (and their
passwords) are never modified. **There is no default password.** Passwords must have 8+ chars
with upper, lower, digit and special character. Each `<PREFIX>_PASSWORD` can be replaced by
`<PREFIX>_PASSWORD_HASH` (pre-computed Argon2/bcrypt hash). Created users must change their
password at first login (enforced server-side). See [AUTH_DESIGN.md](AUTH_DESIGN.md).

| Variable | Description |
|----------|-------------|
| `SUPER_ADMIN_USERNAME` | Super admin username (default: tornybotca1) |
| `SUPER_ADMIN_PASSWORD` | Super admin password. **Production: required while the super admin does not exist** (startup fails otherwise). Dev (`DEBUG=true`): super admin is skipped when unset. |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Bootstrap admin (created only when a password is set). Don't use `admin` as the username: it's the login honeypot. Production compose requires `ADMIN_PASSWORD`. |
| `DIRECTOR_USERNAME`, `DIRECTOR_PASSWORD` | Bootstrap director (created only when a password is set). Production compose requires `DIRECTOR_PASSWORD`. |
| `USER_USERNAME`, `USER_PASSWORD` | Bootstrap user (created only when a password is set). Production compose requires `USER_PASSWORD`. |
| `SCORE_KEEPER_USERNAME`, `SCORE_KEEPER_PASSWORD` | Optional bootstrap score keeper device account |
| `DEFAULT_RESET_PASSWORD` | Optional fixed temporary password for admin "reset password". Unset (recommended) = random one-off password per reset, shown to the admin once. |
| `STAGING_SUPER_ADMIN_USERNAME`, `STAGING_SUPER_ADMIN_PASSWORD`, `STAGING_ADMIN_PASSWORD`, `STAGING_DIRECTOR_PASSWORD`, `STAGING_USER_PASSWORD` | `docker-compose-staging.yml` only: required (no defaults) |
| `STAGING_POSTGRES_PASSWORD` | `docker-compose-staging.yml` only: **required** (no default). Password of the staging Postgres `rankings` user; also interpolated into the staging `DATABASE_URL`, so use URL-safe characters (letters, digits, `-`, `_`, `.`, `~`). On an existing staging volume, set it to the current password or change it with `ALTER USER rankings PASSWORD ...` first. |

## API & CORS

| Variable | Description |
|----------|-------------|
| `API_PORT` | API port (default: 8003) |
| `CORS_ORIGINS` | Comma-separated allowed origins (defaults include probilliardssoftware.com) |
| `DISABLE_GLOBAL_RATE_LIMIT` | Set to `true` to disable global API rate limiting (200 req/min per IP) |
| `PUBLIC_REGISTRATION_ENABLED` | Enables public self-service signup `POST /api/auth/register` and the `/register` form. **Default: off** (returns 403 "coming soon"). Pro accounts are admin-provisioned and unaffected. Set `true`/`1`/`yes`/`on` to open public signup. Read at request time (no restart needed). |
| `AUTH_REGISTER_IP_COOLDOWN_SEC` | Seconds between public `POST /api/auth/register` attempts from the same client IP (default: **120**). Also throttles `POST /api/auth/request-verification-email`. |
| `AI_NARRATIVE_DEMO_IP_COOLDOWN_SEC` | Seconds between public `POST /api/ai-narrative/demo-ask` attempts per client IP (USPBF homepage demo; default: **25**; set **0** to disable in-process cooldown — not recommended) |
| `AI_NARRATIVE_TRUST_FORWARDED_FOR` | **Obsolete (ignored since 2026-09-25).** Client IP now comes from Uvicorn's proxy-header handling; see `FORWARDED_ALLOW_IPS`. |
| `FORWARDED_ALLOW_IPS` | Trusted reverse proxies (comma-separated IPs/CIDRs) whose `X-Forwarded-For` Uvicorn honours (`scripts/docker-api-cmd.sh` passes `--proxy-headers --forwarded-allow-ips`). Default `127.0.0.1,::1,10.0.0.0/8,172.16.0.0/12,192.0.2.0/24` (the nginx containers on the Docker networks). The client IP used for login/rankings/demo rate limits, login lockout and honeypot IP blocks is the right-most **untrusted** hop, so client-supplied values are ignored. Narrow it to your proxy subnet(s) (e.g. the `tunnel_network` subnet from `docker network inspect tunnel_network`) if untrusted hosts can reach the API from a private address. Never set `*`. |
| `RATE_LIMIT_MAX_KEYS` | Cap on (IP, bucket) keys kept by the in-memory rate limiter per worker (default **50000**); stale keys are swept every minute and least recently used keys are evicted above the cap. Limits are per Uvicorn worker. |
| `API_BIND_ADDR` | Host address for the API's published port in `production/docker-compose.prod.yml` (default **127.0.0.1**, i.e. `127.0.0.1:8003`). nginx reaches the API over Docker DNS; set `0.0.0.0` only if a proxy on another host must connect to port 8003. |
| `AI_NARRATIVE_DEMO_REDIS_WINDOW_SEC` | When `REDIS_URL` is set: sliding window length in seconds for demo-ask per IP (default **300**) |
| `AI_NARRATIVE_DEMO_REDIS_MAX_PER_WINDOW` | When `REDIS_URL` is set: max demo-ask requests per IP per window (default **30**) |
| `AI_NARRATIVE_DEMO_SLIDING_MAX` | Without Redis: max demo-ask calls per IP per sliding window (default **15**) |
| `AI_NARRATIVE_DEMO_SLIDING_WINDOW_SEC` | Without Redis: sliding window seconds for demo-ask (default **60**) |

## AI Monitor

| Variable | Description |
|----------|-------------|
| `AI_MONITOR_WEBSITE_ONLY` | When `true` (default), **Settings → AI Monitor (website)** only lists `ollama_activity_log` rows with `metadata.trust_zone` in `public_web` / `app_authenticated`. Set `false` to show all rows on the website monitor (legacy behavior). Internal traffic still appears under **AI Monitor (internal)** (super admin). |

## Logging

| Variable | Description |
|----------|-------------|
| `LOG_LEVEL` | INFO, DEBUG, WARNING, ERROR |
| `LOG_FILE` | Path to log file (default: rankings_bot.log in project root) |
| `DEBUG` | Set to `true` for debug mode |
| `PERF_LOG_SLOW_MS` | Log requests slower than this (ms); 0 = disabled |

## Email & Notifications

| Variable | Description |
|----------|-------------|
| `SMTP_EMAIL`, `SMTP_PASSWORD` | SMTP credentials for transactional email |
| `SENDGRID_API_KEY` | SendGrid API key (alternative to SMTP) |
| `PUBLIC_URL` | Base URL for links (e.g. https://www.probilliardssoftware.com) |
| `MATCH_REMINDER_SMS_ENABLED` | Enable SMS match reminders (Twilio/SNS) |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER` | Twilio SMS config |
| `AWS_SNS_TOPIC_ARN`, `AWS_REGION` | AWS SNS for SMS (alternative to Twilio) |
| `MATCH_REMINDER_EMAIL_ENABLED` | Enable email match reminders (default: true) |
| `MATCH_REMINDER_MINUTES` | Minutes before match to send reminder (default: 15) |

## Payments (Stripe)

| Variable | Description |
|----------|-------------|
| `STRIPE_SECRET_KEY` | Stripe secret key for tournament payments |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret for payment confirmations |

## Fargo Rate

| Variable | Description |
|----------|-------------|
| `FARGO_API_URL` | Fargo API base URL |
| `FARGO_SUBMIT_ENABLED` | Enable tournament result submission to Fargo |
| `FARGO_SUBMIT_URL` | Fargo submit endpoint URL |

## API process (production / Docker)

| Variable | Description |
|----------|-------------|
| `UVICORN_WORKERS` | Number of Uvicorn worker processes (default **4** in `production/docker-compose.prod.yml`; script default **4**). Each worker is a separate process with its own DB pool. Lower on small VMs (e.g. `2`); raise only after checking Postgres `max_connections` and CPU. |

**WebSockets:** Multiple workers do not share in-memory WS state; if live updates misbehave behind a load balancer, consider sticky sessions or a dedicated WS path strategy.

## Database (Connection Pooling)

| Variable | Description |
|----------|-------------|
| `DB_POOL_SIZE` | Connection pool size per **process** (default: **10** in code; production Compose sets **5** so `workers × (pool + overflow)` stays within Postgres limits) |
| `DB_MAX_OVERFLOW` | Max overflow connections per process (default: **20** in code; production Compose sets **10**) |
| `DB_POOL_TIMEOUT` | Pool checkout timeout in seconds (default: 30) |
| `DB_POOL_RECYCLE` | Recycle connections after seconds (default: 3600) |

## Background Scheduler (Auto-Refresh)

| Variable | Description |
|----------|-------------|
| `SKIP_BACKGROUND_SCHEDULER` | Set to 1/true/yes to disable built-in scheduler (default: enabled but starts with zero jobs; refresh is triggered manually via admin UI or `scripts/refresh_rankings.py`) |

## Monitoring (Grafana + Prometheus)

| Variable | Description |
|----------|-------------|
| `GRAFANA_ADMIN_USER` | Grafana admin username (default: admin) |
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin password. **Required by `docker-compose-staging.yml`** (no default; compose fails when unset). Grafana only applies it on first start of a fresh data volume; change an existing admin password in Grafana itself. |
| `VITE_GRAFANA_BASE_URL` | Grafana base URL for frontend links — central stack (e.g. http://192.0.2.20:3000) |
| `VITE_PROMETHEUS_BASE_URL` | Prometheus base URL for frontend links — central stack (e.g. http://192.0.2.20:9092) |

## Ollama (local LLM)

Optional. When disabled, rankings-bot uses existing non-LLM paths only.

| Variable | Description |
|----------|-------------|
| `OLLAMA_ENABLED` | `true` / `1` / `yes` to enable Ollama-backed features |
| `OLLAMA_BASE_URL` | Ollama server base URL (default `http://localhost:11434`). For Docker on a Linux host calling Ollama on another LAN machine (e.g. Win11), use that host’s IP, e.g. `http://192.0.2.10:11434` (see `.env.example`). |
| `OLLAMA_TIMEOUT` | HTTP timeout in seconds (default `60`) |
| `OLLAMA_MODEL_STRUCTURED` | Model for structured JSON tasks — name match, extraction (default `mistral:7b`) |
| `OLLAMA_MODEL_CHAT` | Model for coaching and narratives (default `llama3.1:8b`) |

**Docker:** The API container must be able to reach `OLLAMA_BASE_URL` on the network (same LAN or routed path). Do not use `localhost` inside the container unless Ollama runs in the same container/network namespace.

**Win11 + Cursor:** If you test Ollama on the Windows host with `curl http://127.0.0.1:11434`, Cursor may bind that port while running; use the machine’s LAN URL (e.g. `http://192.0.2.10:11434`) instead.

See **[OLLAMA_AND_AI_MONITOR.md](OLLAMA_AND_AI_MONITOR.md)** for features, AI Monitor, and migration `050`.

## LiteLLM (distributed AI via ALFa AI cluster)

Optional. When enabled, rankings-bot can route heavy LLM tasks through the ALFa AI LiteLLM proxy, which dispatches to Ollama (fast local) or Petals (distributed swarm across multiple GPUs). See [ALFa AI — DISTRIBUTED_AI.md](../../alfa-ai/docs/DISTRIBUTED_AI.md).

| Variable | Description |
|----------|-------------|
| `LITELLM_ENABLED` | `true` / `1` / `yes` to enable LiteLLM client (default `false`) |
| `LITELLM_BASE_URL` | LiteLLM proxy URL (default `http://localhost:8413`) |
| `LITELLM_API_KEY` | API key for the LiteLLM proxy |
| `LITELLM_MODEL_CHAT` | Default model when `LITELLM_MODEL_PAGE_QUESTION` is unset (default `app-chat` in code; may be a heavy model like `codellama-7b-instruct` if you set it). Must exist in the LiteLLM proxy `model_list`. |
| `LITELLM_MODEL_PUBLIC` | Model alias for **public** USPBF demo only (default `public-chat`). See [ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md](ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md). |
| `LITELLM_MODEL_PAGE_QUESTION` | Model alias for signed-in **Ask AI** (`/api/ai-narrative/ask`). When unset, `LITELLM_MODEL_CHAT` is used. |
| `LITELLM_API_KEY_PUBLIC` | Optional separate LiteLLM bearer key for the public trust zone (defaults to `LITELLM_API_KEY`). |
| `LITELLM_API_KEY_APP` | Optional separate LiteLLM bearer key for the app trust zone (defaults to `LITELLM_API_KEY`). |
| `LITELLM_TIMEOUT` | Request timeout in seconds (default `600`). Distributed inference is slow; keep this high. |

Usage in code: `from api.services.litellm_client import get_litellm_client, get_litellm_client_for_trust_zone, is_litellm_enabled` — narrative routes use `api/services/ai_narrative_llm.py` for trust-zone routing.

**Trust zones:** [ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md](ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md)

## Docker Compose (host user for bind mounts)

API and Celery services use `user: "${HOST_UID:-1000}:${HOST_GID:-1000}"` so writes to mounted `frontend/`, `logs/`, and `config/` match the deploy user — **on production that is the `ansible` account**, not root. Do not run compose in a way that leaves those directories root-owned (e.g. omitting `.env.compose-host-user` while using root’s UID).

| Variable | Description |
|----------|-------------|
| `HOST_UID` | Host user ID for container processes (default `1000`). `scripts/start.sh`, `full_deploy.sh`, and `rebuild_*.sh` generate `.env.compose-host-user` and pass it as `--env-file` so values work with `sudo docker compose`. |
| `HOST_GID` | Host group ID (same pattern as `HOST_UID`). |
| `HOST_REPO_ROOT` | **Legacy (no longer set on the API service):** absolute host path to this repo, used when deploy scripts ran *inside* `rankings-bot-api` against a mounted docker.sock. The socket mount was removed (root-equivalent on the host); Admin deploys now run on the host via the deploy dispatcher — see `DEPLOY_REQUEST_DIR` and `docs/ADMIN_DEPLOY_HOST_DISPATCH.md`. Still honored by `build_frontend_with_docker.sh` if you ever run it inside a container by hand. |
| `DEPLOY_REQUEST_DIR` | **Production (API container):** directory where Admin **Update website** / **Full deploy** write request files (`/app/logs/deploy-requests`, inside the `./logs` bind mount). A host systemd path unit (`production/systemd/rankings-bot-deploy.path`) consumes the queue and runs the deploy scripts, so the API never holds `/var/run/docker.sock`. Unset in dev → endpoints run the scripts directly. See `docs/ADMIN_DEPLOY_HOST_DISPATCH.md`. |

**Frontend builds (production):** Use **`scripts/build_frontend_with_docker.sh`** only — do not run `npm` on the host for deploys. `npm ci` / `vite` run inside a short-lived Node container.

If you run `docker compose` by hand, either export `HOST_UID`/`HOST_GID`, add them to `.env`, or from the repo root run `. ./scripts/export_compose_uid_gid.sh && write_compose_host_user_env "$PWD"` and pass `--env-file .env.compose-host-user`.

## Other

| Variable | Description |
|----------|-------------|
| `WPBA_PDF_URL` | Override WPBA rankings PDF URL (default: latest WPBA official PDF) |
| `EXTERNALPOOL_MATCH_MIN_SCORE` | External Pool tournament harvester: minimum fuzzy score (0-1, default **0.35**) before the token and year gates in `docs/SCRAPING.md`. Lowering this does not bypass those gates. |
| `EXTERNALPOOL_SEARCH_LIMIT` | Max events per GraphQL `events` query when searching (default **36**). |
| `EXTERNALPOOL_TAB_ARCHIVE_DIR` | Where to write raw JSON tab payloads (default `/tmp/externalpool_tabs`; ensure the API user can write it, or mount a volume). |
| `MIN_APP_VERSION` | Minimum client version; API returns 426 if client is older (force-update flow) |
| `VITE_APP_VERSION` | Frontend build version (set in CI) |
| `REBUILD_WEBSITE_SCRIPT` | Path to rebuild script (auto-detected if unset) |
| `SKIP_STARTUP_REFRESH` | Skip rankings refresh on startup (1/true/yes) |
| `RECAPTCHA_SECRET_KEY` | reCAPTCHA for registration |
| `XAI_API_KEY` | Grok/xAI for AI Coach and **AI Dev Tools** (super admin) |
| `REDIS_URL` | Redis for Celery/background jobs |

**Maintenance scripts** (`scripts/fix_super_admin.py`, `scripts/reset_super_admin_password.py`): require `DATABASE_URL` and `SUPER_ADMIN_PASSWORD` in the environment (no built-in database credentials; they exit with an error when unset) and never print the password. Optional `SUPER_ADMIN_USERNAME`.
