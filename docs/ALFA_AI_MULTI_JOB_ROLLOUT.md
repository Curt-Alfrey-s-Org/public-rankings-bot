# ALFa AI — multi-job rollout (operator runbook)

Phased **jobs** for bringing the ALFa AI stack and rankings-bot integration online without skipping security or trust-zone steps. Each job has a clear exit criterion before the next starts.

**Related:** [ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md](ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md) · [ENV_VARS.md](ENV_VARS.md) LiteLLM section · [ALFa AI — DISTRIBUTED_AI.md](../../alfa-ai/docs/DISTRIBUTED_AI.md) · [ALFa AI — DEPLOYMENT_BASELINE.md](../../alfa-ai/docs/DEPLOYMENT_BASELINE.md)

---

## Job 0 — Preconditions

| Step | Action | Done when |
|------|--------|-----------|
| 0.1 | Confirm [PORT_ASSIGNMENTS.md](../../alfa-ai/docs/PORT_ASSIGNMENTS.md) and rankings-bot reserved ports are respected. | From `alfa-ai` repo: `./scripts/preflight_ports.sh deploy/.env` exits 0 on a **clean** host. If the stack is **already** bound to those ports, use `./scripts/preflight_ports.sh deploy/.env --allow-in-use` (still enforces reserved-port rules; only skips “must be free”). |
| 0.2 | Create shared Docker network for tunnel ingress if used: `docker network create tunnel_network` (name must match compose). | `docker network inspect tunnel_network` succeeds. |
| 0.3 | Ollama reachable from the ALFa AI host at `OLLAMA_BASE_URL` (models pulled for `public-chat` / `app-chat` aliases, e.g. `llama3.1:8b`). | `curl` to Ollama tags/list or a minimal generate succeeds from the host. |

---

## Job 1 — Secrets and production keys

Completes trust-zone checklist items: **LiteLLM master key**, **orchestrator API token**, and optional **per-zone keys** for rankings-bot.

| Step | Action | Done when |
|------|--------|-----------|
| 1.1 | In `alfa-ai` `deploy/.env` (from [deploy/env.example](../../alfa-ai/deploy/env.example)): set **`LITELLM_MASTER_KEY`** to a long random secret (not the dev default). | Value stored only in deploy secrets / vault; not committed. |
| 1.2 | Set **`ALFA_AI_API_TOKEN`** to a long random secret; set **`ALFA_AI_REQUIRE_API_AUTH=true`** for any environment reachable beyond loopback. | API returns **401** on `/api/runs` (or protected routes) without `Authorization: Bearer`. |
| 1.3 | (Optional) Configure LiteLLM **virtual keys** for teams if you want distinct proxy credentials; map rankings-bot **`LITELLM_API_KEY_PUBLIC`** / **`LITELLM_API_KEY_APP`** / **`LITELLM_API_KEY`** per [ENV_VARS.md](ENV_VARS.md). | Each trust zone uses the intended bearer token at the proxy. |

---

## Job 2 — Core ALFa AI stack (no Petals required)

| Step | Action | Done when |
|------|--------|-----------|
| 2.1 | `cp deploy/env.example deploy/.env` and fill DB/redis URLs if non-default; keep host binds on `127.0.0.1` per baseline. | File present and reviewed. |
| 2.2 | Start stack **or** hybrid: **Full Compose:** `docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d`. **Hybrid (systemd already on 8412):** do **not** start `alfa-ai-api`; run `docker compose ... up -d alfa-ai-litellm` (and optional `alfa-ai-petals-gateway`). See [DEPLOYMENT_BASELINE.md](../../alfa-ai/docs/DEPLOYMENT_BASELINE.md) § hybrid. | API health on **8412**; LiteLLM `/health` on **8413** when using the proxy. |
| 2.3 | Health checks: ALFa API `GET /health`; LiteLLM `GET /health` on mapped proxy port. | HTTP 200. |
| 2.4 | Run preflight script: `alfa-ai/scripts/alfa_ai_rollout_preflight.sh deploy/.env` (add `--strict` before production cutover). | Exit 0. |

---

## Job 3 — Petals swarm and gateway (optional / Milestone 6)

Skip until you need distributed heavy models. For the current LAN rollout, treat this as a phased bring-up:

1. **`apps`** is the authoritative git checkout / sync source.
2. Bring up **hub** first as the **initial live Petals worker / bootstrap** (`hub` management/SSH, current worker peer `.157`).
3. Then bring up **`orchestrator`** as the **main brain** (Ollama + ALFa AI + LiteLLM + Petals gateway).
4. Then bring up **`apps`** as a **GPU Petals worker** (RTX 3060 8GB; standard `docker-compose.worker.yml` in `alfa-ai` `deploy/petals/`).
5. Only after those first nodes are stable, add the next Win11 LAN GPU workers (see [alfa-ai NODE_INVENTORY](../../alfa-ai/docs/NODE_INVENTORY.md)).

| Step | Action | Done when |
|------|--------|-----------|
| 3.1 | Bootstrap **hub** first per [DISTRIBUTED_AI.md](../../alfa-ai/docs/DISTRIBUTED_AI.md); capture the address list from the log line **`Running a server on [...]`** (or **`Full list of visible multiaddresses: ...`**). Use the advertised **worker peer** address (currently `.157`), not the `hub` management/UI IP. | hub stays up and logs DHT / visible addresses without restart loops. |
| 3.2 | Bring up **`orchestrator`** as the main brain; set `PETALS_INITIAL_PEERS` in `alfa-ai` `deploy/.env` to the hub bootstrap address list and verify the gateway can reach it. | `alfa-ai-petals-gateway` starts and sees the bootstrap peer. |
| 3.3 | Bring up **`apps`** as a **GPU** worker with the same `PETALS_MODEL` and hub bootstrap peer (`docker-compose.worker.yml`, not CPU-only compose). | `apps` joins the same swarm without endless restart. |
| 3.4 | Verify **`alfa-ai-petals-gateway`** health and LiteLLM route to a supported Petals-backed model (for current rollout, a supported Llama-family model such as CodeLlama, not `deepseek_v2`). | Chat completion to the Petals-backed alias returns text (may be slow). |

---

## Job 4 — Rankings-bot integration

| Step | Action | Done when |
|------|--------|-----------|
| 4.1 | On rankings-bot production/staging `.env`: `LITELLM_ENABLED=true`, `LITELLM_BASE_URL` points to reachable LiteLLM (tunnel or LAN URL as appropriate), keys match Job 1. | Container/host can `curl` LiteLLM with the configured key. |
| 4.2 | Set **`LITELLM_MODEL_PUBLIC=public-chat`**, **`LITELLM_MODEL_PAGE_QUESTION=app-chat`** (or deliberate overrides). | Demo and Ask AI hit Ollama-backed aliases only for those zones. |
| 4.3 | Deploy rankings-bot (e.g. **Update website** / `./scripts/full_deploy.sh` per project docs). | `POST /api/ai-narrative/demo-ask` and authenticated `ask` succeed under expected rate limits. |

---

## Job 5 — Edge: TLS and internal API exposure

Completes: **never expose `/api/runs` without TLS + token on the tunnel/network edge.**

| Step | Action | Done when |
|------|--------|-----------|
| 5.1 | Terminate TLS at Cloudflare, nginx, or tunnel product in front of **`alfa-ai-nginx`** / API; no plain-text orchestrator URLs on the public Internet. | Browser / `curl -v` shows TLS to the public hostname. |
| 5.2 | Firewall: only loopback or bastion can reach raw host ports if services are port-mapped to `127.0.0.1` (already in compose). | Scan confirms no unintended exposure. |
| 5.3 | Document who may call **`ALFA_AI_API_TOKEN`** and rotate token on schedule. | Runbook updated; token rotation tested once. |

---

## Job 6 — Verification and sign-off

| Step | Action | Done when |
|------|--------|-----------|
| 6.1 | Run rankings-bot tests that cover trust boundaries: `tests/backend/test_ai_trust_boundary.py` (or full API suite in CI). | All green. |
| 6.2 | Manual: public demo request uses only demo knowledge; internal bundle not reachable without JWT. | Matches expectations in [ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md](ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md). |
| 6.3 | Update checklist in [ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md](ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md) when Jobs 1, 5, and 6 are complete for your environment. | Boxes checked. |

---

## Quick command reference

```bash
# From alfa-ai repo root
./scripts/preflight_ports.sh deploy/.env
./scripts/preflight_ports.sh deploy/.env --allow-in-use   # if API/LiteLLM ports already in use by this stack
./scripts/alfa_ai_rollout_preflight.sh deploy/.env
./scripts/alfa_ai_rollout_preflight.sh deploy/.env --strict   # before production

# Stack (see DEPLOYMENT_BASELINE for exact cwd / compose invocation)
docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d
```

---

## Summary table

| Job | Purpose |
|-----|---------|
| 0 | Ports, network, Ollama |
| 1 | Secrets, LiteLLM master key, API token, optional virtual keys |
| 2 | Compose up, API + LiteLLM health |
| 3 | Petals workers + gateway (optional) |
| 4 | Rankings-bot LiteLLM env + deploy |
| 5 | TLS + edge hardening for orchestrator |
| 6 | Tests + checklist sign-off |
