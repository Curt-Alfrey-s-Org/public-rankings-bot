# ALFa AI — trust zones and rollout definition of done

This document is the **single checklist** for public website AI vs in-app AI vs internal (ALFa AI orchestrator / ops) AI. It aligns [ALFa AI — MILESTONE_BACKLOG.md](../../alfa-ai/docs/MILESTONE_BACKLOG.md) and [ALFa AI — DISTRIBUTED_AI.md](../../alfa-ai/docs/DISTRIBUTED_AI.md) with rankings-bot behavior.

**Implementation / dev path:** Code, tests, LiteLLM aliases, rollout docs, and [ALFA_AI_HOW_TO_USE.md](ALFA_AI_HOW_TO_USE.md) are in place. The two **unchecked** items below are **production operator** tasks (secrets + TLS/edge), not missing software.

## Trust zones

| Zone | Audience | Entry points | Knowledge / data | Inference route names (LiteLLM) |
|------|----------|--------------|------------------|----------------------------------|
| **public_web** | Visitors (USPBF homepage demo) | `POST /api/ai-narrative/demo-ask` | `build_demo_alfa_knowledge_bundle` only — USPBF + marketing JSON, **no** per-user DB | `public-chat` (Ollama-backed alias in LiteLLM) |
| **app_authenticated** | Signed-in app users | `POST /api/ai-narrative/ask` | Tier/deals + optional `build_server_ask_ai_bundle` when player allowed | `app-chat` or heavy model via env |
| **internal** | Operators / coding agents | ALFa AI API (`/api/runs`, …), Cursor-style workflows | Workspace + tools; **not** mixed into public prompts | Petals / coder models via ALFa AI LiteLLM config |

**Rule:** Internal or private data must never appear in `public_web` prompts or logs labeled as internal-only.

## Definition of done (checklist)

### Public demo (`demo-ask`)

- [x] No JWT; middleware allows the route without Bearer.
- [x] Knowledge from `build_demo_alfa_knowledge_bundle` only (no `build_server_ask_ai_bundle`).
- [x] Rate limiting: Redis fixed window when `REDIS_URL` is set; otherwise in-memory sliding window + optional per-IP cooldown.
- [x] Client IP: configurable trust for `X-Forwarded-For` (`AI_NARRATIVE_TRUST_FORWARDED_FOR`) behind a **trusted** reverse proxy.
- [x] AI Monitor rows include `trust_zone: public_web` in metadata where logging supports it.

### In-app Ask AI (`/ask`)

- [x] JWT required; player context gated with `_can_access_player`.
- [x] LiteLLM optional: when `LITELLM_ENABLED=true`, uses **app** model key (`LITELLM_MODEL_PAGE_QUESTION` / `app-chat`); otherwise Ollama direct.
- [x] Metadata `trust_zone: app_authenticated` on logged LLM calls where supported.

### LiteLLM / ALFa AI cluster

- [x] LiteLLM config exposes distinct **logical** model names: `public-chat`, `app-chat`, plus existing heavy routes (`codellama-7b-instruct`, …).
- [x] Rankings-bot env: optional `LITELLM_API_KEY_PUBLIC` vs default app key for stricter key separation (same proxy, different credentials when desired).
- [ ] Production: set `LITELLM_MASTER_KEY` and per-caller keys per [ALFa AI deploy/env.example](../../alfa-ai/deploy/env.example).

### ALFa AI orchestrator API

- [x] Bearer auth when `ALFA_AI_API_TOKEN` is set; disable with `ALFA_AI_REQUIRE_API_AUTH=false` for local dev only.
- [ ] Production: never expose `/api/runs` without TLS + token on the tunnel/network edge.

### Tests

- [x] Boundary tests: demo path does not load private server bundles; auth required for ALFa AI API when token configured.

### Documentation

- [x] [ENV_VARS.md](ENV_VARS.md) — demo trust, Redis demo limits, LiteLLM zone models.
- [x] [ALFa AI — DISTRIBUTED_AI.md](../../alfa-ai/docs/DISTRIBUTED_AI.md) — trust zones and keys (updated in same rollout).
- [x] [ALFA_AI_MULTI_JOB_ROLLOUT.md](ALFA_AI_MULTI_JOB_ROLLOUT.md) — phased operator jobs (ports → secrets → stack → Petals → rankings-bot → TLS → sign-off).

## Related docs

- [ALFA_AI_HOW_TO_USE.md](ALFA_AI_HOW_TO_USE.md) — enable and verify end-to-end when the stack is up.
- [ALFA_AI_MULTI_JOB_ROLLOUT.md](ALFA_AI_MULTI_JOB_ROLLOUT.md) — multi-job rollout runbook (execute Jobs 1 and 5 for remaining production checkboxes above).
- [OLLAMA_AND_AI_MONITOR.md](OLLAMA_AND_AI_MONITOR.md) — features and AI Monitor.
- [ENV_VARS.md](ENV_VARS.md) — Ollama, LiteLLM, demo limits.
