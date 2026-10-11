# Ollama Integration & AI Monitor

Local LLM (Ollama) augments rankings-bot for name matching, bracket extraction, text coaching, and narratives. The **AI Monitor** admin page shows every Ollama request/response for debugging and prompt tuning.

---

## What uses Ollama

| Feature | Code area | Ollama `feature` label (AI Monitor) |
|---------|-----------|-------------------------------------|
| Ambiguous player name matching | `api/services/ollama_name_resolver.py`, scrapers, enrichment | `name_resolution` |
| Tournament bracket text when regex fails | `api/services/ollama_extractor.py`, `scrapers/tournament_bracket_parser.py` | `bracket_extraction` |
| Messy PDF ranking text | `ollama_extractor.py` | `pdf_extraction` |
| Text-only pool coaching | `POST /api/ai-coach/ask`, optional `text_question` on analyze | `text_coaching` |
| Player performance overview narrative | `api/routes/player_performance.py` | `player_narrative` (skipped when overview data unchanged — in-process cache; no new log row) |
| Alfa player comparison narrative | `api/routes/alfa_ratings.py` | `matchup_narrative` |
| Role-scoped Q&A (Settings → Rankings Assistant) | `POST /api/rankings-assistant/ask`, `api/services/rankings_assistant_context.py` | `rankings_assistant` |
| In-app ALFa Q&A (player pages / general) | `POST /api/ai-narrative/ask`, `api/routes/ai_narrative.py` | `page_question` |
| **Public** ALFa demo (USPBF homepage via same-origin `/api/`) | `POST /api/ai-narrative/demo-ask` (no JWT; per-IP cooldown) | `uspbf_demo` |

If `OLLAMA_ENABLED` is false or Ollama is unreachable, the app falls back to existing deterministic behavior (no silent substitution of wrong data for critical merges).

**LiteLLM / trust zones:** When `LITELLM_ENABLED=true`, `POST /api/ai-narrative/ask` and `demo-ask` can route chat via the ALFa AI LiteLLM proxy using separate model aliases (`public-chat` vs `app-chat`). See **[ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md](ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md)** and **[ENV_VARS.md](ENV_VARS.md)** (`LITELLM_*`).

---

## Environment variables

See **[ENV_VARS.md](ENV_VARS.md)** — full table. Summary:

| Variable | Purpose |
|----------|---------|
| `OLLAMA_ENABLED` | `true` / `1` / `yes` to enable |
| `OLLAMA_BASE_URL` | Ollama HTTP API, e.g. `http://192.0.2.10:11434` (Windows host on LAN) |
| `OLLAMA_TIMEOUT` | Request timeout seconds (default `60`) |
| `OLLAMA_MODEL_STRUCTURED` | Model for JSON/structured tasks (default `mistral:7b`) |
| `OLLAMA_MODEL_CHAT` | Model for coaching/narratives (default `llama3.1:8b`) |

Production Compose passes these from `.env` into `rankings-bot-api` and `celery-worker`.

---

## Health check

`GET /api/health/detailed` includes an `ollama` object (sync HTTP probe; no nested async loop issues).

**After deploy**, confirm from the host (via nginx, e.g. port **8088** in the default stack):

```bash
curl -sS "http://127.0.0.1:8088/api/health/detailed" | python3 -c "import sys,json; print(json.load(sys.stdin).get('ollama'))"
```

Expect `"status": "healthy"`, `base_url` matching `OLLAMA_BASE_URL`, and your configured model names. If `unreachable`, the API container cannot reach `OLLAMA_BASE_URL` on the LAN (firewall, wrong IP, or Ollama not listening on `0.0.0.0`).

Containers should show the same Ollama variables (from root `.env`):

```bash
docker exec rankings-bot-api printenv | grep ^OLLAMA
docker exec rankings-bot-celery-worker printenv | grep ^OLLAMA
```

Prometheus metrics (when enabled): `ollama_requests_total`, `ollama_request_duration_seconds`, `ollama_tokens_total` — see `api/routes/metrics.py`.

---

## AI Monitor (admin UI)

### Website vs internal (trust zones)

- **Website / app users:** Settings → **AI Monitor (website)** (`/settings/admin/ai-monitor`) — rows whose logged `metadata.trust_zone` is `public_web` or `app_authenticated` (demo, Ask AI, narratives, Rankings Assistant, coaching, etc.). When **`AI_MONITOR_WEBSITE_ONLY`** is true (default), internal/batch calls are excluded here.
- **Internal / batch:** Settings → **AI Monitor (internal)** (`/settings/admin/ai-monitor-internal`) — **super admin only**; complement of the website filter (missing trust zone or not public/app). May contain operational prompts; keep behind your normal HTTPS/tunnel auth.

### Website monitor details

- **Role:** Admin or super_admin
- **Shows:** Recent Ollama calls with feature, model, duration, status, expandable request/response text, error rows highlighted
- **API:** `GET /api/admin/ai-monitor?limit=100&feature=text_coaching&status=error`

### Internal monitor API

- **API:** `GET /api/admin/ai-monitor/internal?limit=100` (super_admin JWT only)

Data is stored in **`ollama_activity_log`** (Alembic revision **050**). Apply with:

```bash
docker exec rankings-bot-api python -m alembic upgrade head
```

---

## Database table

`ollama_activity_log` columns (high level): `created_at`, `feature`, `model`, `prompt_summary`, `request_text`, `response_text`, `duration_seconds`, `eval_tokens`, `prompt_tokens`, `status`, `error_message`, `metadata`. Request/response are truncated at insert time (see `api/services/ollama_activity_log.py`).

---

## Docker Compose (single file)

All app services, including Postgres and Redis, are defined in **`production/docker-compose.prod.yml`**. Root **`docker-compose.yml`** only `include:`s that file for backward compatibility. Deploy with `./scripts/full_deploy.sh` or `./scripts/start.sh` — see **[START_STOP_RESTART.md](START_STOP_RESTART.md)** and **[PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md)**.

Postgres data volume is pinned to **`rankings-bot_postgres_data`** (external) so existing data is preserved when moving to the unified compose.

---

## Operating Ollama in production (no extra scripts)

**Ollama is not a log watcher.** It does not read `rankings_bot.log`, container logs, or health payloads unless application code **explicitly** puts text into a prompt and calls the model. There is no background job that feeds errors to Ollama for diagnosis.

**How to debug in live state:** use **Settings → AI Monitor** (and optional **`docker logs -f rankings-bot-api`**) to see **when** the app called Ollama, **what** was sent, and **what** came back. That is the audit trail for Ollama behavior — not “Ollama noticed an error.”

CI no longer runs mocked Ollama/AI Coach unit tests; validation is **observation** of real traffic in AI Monitor + normal app/logging tooling.

---

## Grok for heavier admin tasks

Local **Ollama** handles structured extraction, name matching, text coaching (with Grok as secondary for coaching when Ollama fails). **Grok** (`XAI_API_KEY`) is used for vision (AI Coach video) and **AI Dev Tools** (Settings → super admin → AI Dev Tools: scraper diagnose, tournament QA, safe rankings NL assist, docs Q&A, email drafts, merge hints, CI log triage).

## Related code

- `api/services/ollama_client.py` — HTTP client, logging hook
- `api/services/ollama_activity_log.py` — DB writes
- `api/services/health_check.py` — `check_ollama()`
- `alembic/versions/050_ollama_activity_log.py` — migration
- `api/routes/admin_dev_tools.py` — Grok-backed super-admin tools
