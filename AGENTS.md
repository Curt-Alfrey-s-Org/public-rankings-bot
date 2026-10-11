# Agent Instructions — Rankings Bot

Rankings Bot is the **reference implementation** for ALFa AI and central-monitoring
integration across the 4-bot workspace. Keep it drift-free: other bots copy these
patterns, so a bug here propagates everywhere.

**Finding info first:** read [docs/INDEX.md](docs/INDEX.md). It maps topics (AI,
auth, rankings data, deployment, monitoring) so you don't scan all docs.

## Engineering standards (non-negotiable)

This repo follows the workspace rule
[`engineering-standards-and-drift-control`](../.cursor/rules/engineering-standards-and-drift-control.mdc)
plus the in-repo rules in [`.cursor/rules/`](.cursor/rules/): manuals-first,
no workarounds, industry standards only, preserve infrastructure constants, and a
**mandatory drift double-check after every change**.

## ALFa AI integration

The ALFa **brain** (LiteLLM proxy, orchestrator) runs on **`hub`**. Rankings Bot is
a **server-side consumer**: it calls LiteLLM through
[`api/services/litellm_client.py`](api/services/litellm_client.py) — never embeds keys
in the frontend, and never calls Ollama/Petals/LiteLLM directly from client code.

- **Trust zones & DoD:** [docs/ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md](docs/ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md)
  - `public_web` → `POST /api/ai-narrative/demo-ask`, model alias `public-chat`
  - `app_authenticated` → `POST /api/ai-narrative/ask`, model alias `app-chat` / `LITELLM_MODEL_PAGE_QUESTION`
  - `internal` → ALFa AI orchestrator (`/api/runs`), operator/agent models
- **Enable/verify:** [docs/ALFA_AI_HOW_TO_USE.md](docs/ALFA_AI_HOW_TO_USE.md); env in [docs/ENV_VARS.md](docs/ENV_VARS.md)
- **Telemetry:** LLM calls log to the `ollama_activity_log` table via
  `api/services/ollama_activity_log.py` (the LiteLLM path reuses the same logger).
  When you add a new LLM call site, set `feature`, `trust_zone` metadata, and ensure
  `duration_seconds`/token counts are populated (see the AI Monitor).
- **Model aliases are a contract:** alias names (`public-chat`, `app-chat`, …) must
  exist in `alfa-ai/deploy/litellm_config.yaml`. Do not invent aliases here.

### Sanctioned exception — xAI Grok vision coaching

[`api/services/grok_client.py`](api/services/grok_client.py) calls the **xAI Grok**
API directly (`grok-4` vision) for pool/billiards shot analysis (AI Coach, covert ops,
CI failure suggestions). This is an **intentional product decision**, not a workaround:
the LiteLLM/Ollama/Petals swarm does not serve this vision-coaching capability.

- Do **not** "fix" this by routing it through LiteLLM unless an equivalent vision
  alias is added to the brain and product signs off.
- The xAI key is server-side env only; never ship it to the client.
- Cost/latency constants live in `grok_client.py`; treat them as the source of truth.

## Monitoring integration

Production monitoring is the **central stack** in the separate `monitoring` repo on
`apps` — Rankings Bot does **not** run its own Prometheus/Grafana in production.

- Guide: [docs/MONITORING_RANKINGS_BOT.md](docs/MONITORING_RANKINGS_BOT.md)
- The API exposes `/metrics` (port 8003); `http_requests_total{status}` uses a
  **status class** label (`2xx`…`5xx`) — match it exactly in queries/alerts.
- Scrape job `rankings-bot-api`, alerts `monitoring/prometheus/rules/rankings_alerts.yml`,
  dashboards `monitoring/grafana/dashboards/rankings_bot_*.json`.
- Grafana `http://192.0.2.20:3000`, Prometheus `http://192.0.2.20:9092`.

## Infrastructure constants (do not change)

- Rankings Bot API: `127.0.0.1:8003:8003`; network `tunnel_network`; APIs bind
  `0.0.0.0` **inside** the container, `127.0.0.1` on the host.
- See workspace `.cursorrules` and [docs/PORT_MANAGEMENT.md](docs/PORT_MANAGEMENT.md).

## Code review / debugging / multi-bot

- **Review:** run `git diff`, focus on modified files, report Critical | Warnings | Suggestions.
- **Debug:** capture error + trace, reproduce, isolate, minimal fix, verify.
- **Multi-bot:** rankings-bot imports auth via `@/contexts/AuthContext` (others use
  `@/context/AuthContext`). Match the slate-950 / slate-800 / sky-500 theme and `@/` aliases.

## Git

Author and commit/push from **`apps`** (`git-push-from-apps` rule); other hosts pull.
