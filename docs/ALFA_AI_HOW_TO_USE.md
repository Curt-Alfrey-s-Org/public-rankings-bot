# ALFa AI — how to use (when the stack is ready)

This is the **operator and product** guide after Jobs 0–2 of [ALFA_AI_MULTI_JOB_ROLLOUT.md](ALFA_AI_MULTI_JOB_ROLLOUT.md) are green (ALFa API + LiteLLM healthy; Ollama reachable from LiteLLM).

## What you can run

| Capability | Who | Where | Inference |
|------------|-----|-------|-------------|
| **Public demo Ask** | Website visitors (e.g. USPBF) | `POST /api/ai-narrative/demo-ask` | `public-chat` via LiteLLM when enabled, else Ollama direct |
| **In-app Ask AI** | Signed-in users | App → `POST /api/ai-narrative/ask` | `app-chat` via LiteLLM when enabled, else Ollama direct |
| **ALFa orchestrator** | Operators / automation | `POST /api/runs` on ALFa API (**8412**) | LiteLLM / tools inside ALFa stack; requires **Bearer** token when auth is on |
| **Heavy / Petals models** | Internal | LiteLLM model names e.g. `codellama-7b-instruct` | After Petals workers + gateway are up ([DISTRIBUTED_AI.md](../../alfa-ai/docs/DISTRIBUTED_AI.md)) |

## Prerequisites on the ALFa host

1. **Ollama** running with models LiteLLM expects (defaults include **`llama3.1:8b`** for `public-chat` / `app-chat`).
2. **ALFa API** on **`127.0.0.1:8412`** (systemd **or** Docker — [DEPLOYMENT_BASELINE.md](../../alfa-ai/docs/DEPLOYMENT_BASELINE.md) hybrid section).
3. **LiteLLM** on **`127.0.0.1:8413`**:  
   `docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d alfa-ai-litellm` (from **`alfa-ai/deploy/`**).
4. Quick check:  
   `bash /home/ansible/alfa-ai/scripts/alfa_ai_rollout_preflight.sh /home/ansible/alfa-ai/deploy/.env` → **Preflight passed.**

## Enable LiteLLM in rankings-bot

Production and staging load **`../.env`** from [production/docker-compose.prod.yml](../production/docker-compose.prod.yml). Set in your real **`.env`** (see [`.env.example`](../.env.example) LiteLLM block):

```env
LITELLM_ENABLED=true
LITELLM_API_KEY=sk-alfa-ai-litellm-dev
```

**`LITELLM_BASE_URL`** (pick one):

- **Production (recommended):** both **`rankings-bot-api`** and **`alfa-ai-litellm`** are on **`tunnel_network`** → use the container DNS name and **internal** proxy port:  
  `LITELLM_BASE_URL=http://alfa-ai-litellm:4000`
- **Host / dev** (curl on the server, or API not in Docker):  
  `LITELLM_BASE_URL=http://127.0.0.1:8413`

Use the **same bearer value** for **`LITELLM_API_KEY`** as **`LITELLM_MASTER_KEY`** in **`alfa-ai/deploy/.env`** (change both to a strong secret in production).

Recommended trust-zone aliases (must exist in **`alfa-ai/deploy/litellm_config.yaml`**):

```env
LITELLM_MODEL_PUBLIC=public-chat
LITELLM_MODEL_PAGE_QUESTION=app-chat
LITELLM_MODEL_CHAT=app-chat
LITELLM_TIMEOUT=600
```

After editing **`.env`**, apply with your normal deploy (**Update website** / `./scripts/full_deploy.sh` per [START_STOP_RESTART.md](START_STOP_RESTART.md)).

**Important:** `docker compose restart rankings-bot-api` does **not** reload variables from **`.env`**. Recreate the API container so new **`LITELLM_*`** values take effect, for example from the repo root:

```bash
# If you use .env.compose-host-user for UID/GID, pass BOTH files (base .env first):
docker compose -f production/docker-compose.prod.yml --env-file .env --env-file .env.compose-host-user up -d --no-deps --force-recreate rankings-bot-api
```

## Verify rankings-bot → LiteLLM

From a shell that can reach **`LITELLM_BASE_URL`** with the API key:

```bash
curl -sS http://127.0.0.1:8413/health/liveliness
curl -sS http://127.0.0.1:8413/v1/chat/completions \
  -H "Authorization: Bearer sk-alfa-ai-litellm-dev" \
  -H "Content-Type: application/json" \
  -d '{"model":"public-chat","messages":[{"role":"user","content":"Say OK in one word."}]}'
```

In the app: open **Ask AI** on an allowed page, or hit the public demo endpoint from the USPBF integration (rate limits apply).

## Chat widget look (contracts-bot parity)

Signed-in Ask ALFa uses **`@alfa-ai/chat-widget`** (same package as contracts-bot): dock geometry (`28rem` × `min(85dvh, 36rem)`), popup route **`/alfa-chat`**, and navy panel theme. Canonical spec: **`alfa-ai/docs/ALFA_AI_CHAT_WIDGETS.md`**.

| Change type | Operator step on `probilliards` |
|-------------|-------------------------|
| Rankings integration files (`AlfaWidgetShell`, copy, routes) | `git pull` → **Settings → Admin → Refresh app UI** (or **Update website**) |
| Package bump in `alfa-ai/packages/chat-widget` | Publish to Verdaccio on `hub`, then `git pull` + **Refresh app UI** on `probilliards` |
| API-only backend | `./scripts/rebuild_api.sh` (restarts nginx automatically) |
| Full stack (frontend + API + nginx + tunnel) | **Settings → Admin → Full deploy** (super admin) or `./scripts/full_deploy.sh` |

After any frontend rebuild, hard-refresh the browser (Ctrl+Shift+R). If the ALFa avatar still looks stale, use **Settings → Admin → Refresh app UI** (new build embeds `?v=<build_hash>` on the avatar URL to bypass CDN cache).

### Avatar cache (Cloudflare / PWA)

The chat widget loads `/branding/alfa-ai-avatar.png` (with `?v=<API build hash>` after each frontend rebuild). nginx no longer marks `/branding/` as immutable; the service worker does not precache it. If an old image persists, purge Cloudflare cache for `www.probilliardssoftware.com/branding/*` once, then hard-refresh.

## In-app Ask AI — player DB context (2026-07)

`POST /api/ai-narrative/ask` loads an authoritative Postgres snapshot (`build_server_ask_ai_bundle`) when a player is in scope.

| How player is chosen | Behavior |
|----------------------|----------|
| `player_name` from the widget (Player Performance / Head-to-Head / Tournament History registration) | Preferred; access checked via `_can_access_player` |
| Empty `player_name`, but the question names a player (e.g. “show stats for Debbie Teichert”) | Server extracts a candidate name (`re` named groups), resolves against `rankings` / aliases, then loads the same bundle if the user may view that player |
| No name and no resolvable mention | App/tier/deals knowledge only (`server_authoritative.note`) |

**Access:** admin/super_admin → any player; director/user → only self (`user_player_links` / username match). Forbidden names return **403**.

**PRO / paid ratings in the ask bundle:** when `_can_view_paid_ratings` is true (PRO tier, or admin/director/super_admin), the snapshot includes `alfa_rating` from `rankings` (when present) and `est_rating*` from `players` (when present). Lower tiers get rank/Fargo/placements only; the system prompt teasers PRO for live Est. / ALFa.

Code: `api/services/ask_ai_context.py`, `api/routes/ai_narrative.py`. Product copy: `config/alfa_knowledge.json`.

## AI Monitor

Super admins: **Settings → AI Monitor** (see [OLLAMA_AND_AI_MONITOR.md](OLLAMA_AND_AI_MONITOR.md)). Calls should show **`trust_zone`** (`public_web` vs `app_authenticated`) when routed through the narrative stack.

## Production hardening (before public Internet)

Complete [ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md](ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md): strong **`LITELLM_MASTER_KEY`**, **`ALFA_AI_API_TOKEN`**, **`ALFA_AI_REQUIRE_API_AUTH=true`**, TLS on the edge, and optional **`LITELLM_API_KEY_PUBLIC`** / **`LITELLM_API_KEY_APP`**. Use **`./scripts/alfa_ai_rollout_preflight.sh deploy/.env --strict`** on the ALFa host.

## Related docs

- [ALFA_AI_MULTI_JOB_ROLLOUT.md](ALFA_AI_MULTI_JOB_ROLLOUT.md) — phased rollout.
- [ENV_VARS.md](ENV_VARS.md) — all LiteLLM and demo variables.
- [ALFa AI — DISTRIBUTED_AI.md](../../alfa-ai/docs/DISTRIBUTED_AI.md) — Petals, vpn, model list.
