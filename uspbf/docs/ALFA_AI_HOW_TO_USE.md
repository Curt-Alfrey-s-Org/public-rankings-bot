# ALFa AI on USPBF — Operator Usage Guide

**Site:** [example.com](https://example.com) (United States Pro Billiards Federation)  
**Host:** `192.0.2.20` (apps box)  
**AI backend:** `rankings-bot-api` → LiteLLM on `192.0.2.30:8413`  
**Authority:** [.cursor/plans/ALFA_AI_INTEGRATION_PLAN.md](../.cursor/plans/ALFA_AI_INTEGRATION_PLAN.md)

---

## What USPBF AI is

USPBF is a **static marketing site**. It does **not** run LLM code. The homepage **ALFa AI** floating button sends visitor questions to:

```
Browser → example.com/api/ai-narrative/demo-ask
       → uspbf-nginx (injects BOT_API_KEY)
       → rankings-bot-api:8003
       → LiteLLM http://192.0.2.30:8413 (alias: public-chat)
```

Signed-in player AI (AI Coach, Ask AI dock) lives in **Pro Billiards Software** at [app.example.com](https://app.example.com) / [probilliardssoftware.com](https://www.probilliardssoftware.com) — that is the **`app_authenticated`** trust zone in rankings-bot, not this repo.

---

## Prerequisites

| Component | Check |
|-----------|-------|
| USPBF stack | `cd /home/ansible/USPBF && ./start.sh --production` |
| cf-uspbf tunnel | `sudo docker logs cf-uspbf --tail 20` |
| rankings-bot-api | `curl -fsS http://127.0.0.1:8003/api/health` |
| Brain LiteLLM | `curl -fsS http://192.0.2.30:8413/health/liveliness` |
| Shared Docker network | `uspbf-nginx` and `rankings-bot-api` both on `tunnel_network` |
| API key parity | `BOT_API_KEY` in `USPBF/.env` = rankings-bot `BOT_API_KEY` |

---

## One-time / ongoing configuration

### 1. USPBF `.env`

```bash
cd /home/ansible/USPBF
cp env.example .env   # if needed
# Required for /api/ proxy:
# BOT_API_KEY=<same as rankings-bot-api>
# USPBF_TOKEN=<Cloudflare tunnel token>
```

See `env.example` L9–10.

### 2. rankings-bot LiteLLM (cross-repo)

In `/home/ansible/rankings-bot/.env`:

```env
LITELLM_ENABLED=true
LITELLM_BASE_URL=http://192.0.2.30:8413
LITELLM_MODEL_PUBLIC=public-chat
```

Recreate the API container after editing (restart alone does not reload env). Full details: `rankings-bot/docs/ALFA_AI_HOW_TO_USE.md`.

**Important:** Use the **LAN brain URL** above. Do **not** set `LITELLM_BASE_URL=http://alfa-ai-litellm:4000` on `apps` — the brain stack runs on `hub`, not the apps host.

### 3. Public demo knowledge

Marketing facts for the demo come from **`rankings-bot/api/config/uspbf_knowledge.json`**, loaded by `build_demo_alfa_knowledge_bundle()`. After editing that file, restart rankings-bot-api. After editing USPBF static copy/JS, rebuild nginx:

```bash
cd /home/ansible/USPBF
./start.sh --no-cache --production
```

See [ALFA_AI_KNOWLEDGE_SYNC.md](ALFA_AI_KNOWLEDGE_SYNC.md) (created with this plan).

---

## Verify the demo works

### LAN preview (port 8089)

```bash
curl -fsS -X POST http://127.0.0.1:8089/api/ai-narrative/demo-ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"What tiers does Pro Billiards Software offer?"}'
```

Expect JSON with `"answer": "..."`.

Or open `http://<server-ip>:8089/` and click the **ALFa AI** FAB.

### Production (through tunnel)

After `./start.sh --production` and cf-uspbf running, open `https://example.com/` and use the demo dock.

### Automated check

```bash
cd /home/ansible/USPBF
./scripts/verify-ai-demo.sh
```

(Script created in Stage 2 of the integration plan.)

---

## AI Monitor and telemetry

Demo calls log to **`ollama_activity_log`** in **rankings-bot Postgres** with:

- `feature`: `uspbf_demo`
- `metadata.trust_zone`: `public_web`

**View usage:** Sign in to Pro Billiards Software as super_admin → **Settings → AI Monitor** (rankings-bot UI). There is no AI Monitor inside USPBF.

---

## Maintenance vs production

- **Maintenance mode** (`./start.sh --maintenance`): apex/www show "Under Maintenance"; **app.example.com** still proxies to rankings-bot; **:8089** preview still serves full static site + `/api/` for testing.
- **Production mode** (`./start.sh --production`): apex/www serve marketing site including ALFa demo.

Switch without rebuild: `./scripts/switch-site.sh production|maintenance`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Demo "AI assistant is not enabled" (503) | LiteLLM off in rankings-bot | Set `LITELLM_ENABLED=true`; verify `hub:8413` |
| Demo 502 / empty answer | rankings-bot-api down | `./status-all-bots.sh`; restart rankings-bot |
| `/api/*` 401 | `BOT_API_KEY` mismatch | Align USPBF `.env` and rankings-bot `.env` |
| app.example.com 502 | rankings-bot not on `tunnel_network` | `/home/ansible/scripts/restore-docker-networks.sh` |
| Stale homepage after git pull | nginx image cache | `./start.sh --no-cache --production` |
| Tunnel up but site down | `USPBF_TOKEN` wrong | Cloudflare Zero Trust → cf-uspbf → re-copy token |

---

## Trust zone summary

| Zone | USPBF? | Model |
|------|--------|-------|
| `public_web` | **Yes** — homepage demo | `public-chat` |
| `app_authenticated` | Via app.example.com only | `app-chat` |
| `internal` | Operators on `hub:8420/operator/` | `agent` |

USPBF operators **never** embed LiteLLM keys in static JS. The browser never sees `BOT_API_KEY` — nginx adds it server-side (`bot-api-key-headers.conf.template`).

---

## Related docs

- [ALFA_AI_INTEGRATION_PLAN.md](../.cursor/plans/ALFA_AI_INTEGRATION_PLAN.md) — full staged plan
- [rankings-bot/docs/ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md](../../rankings-bot/docs/ALFA_AI_TRUST_ZONES_AND_ROLLOUT.md)
- [rankings-bot/docs/ALFA_AI_HOW_TO_USE.md](../../rankings-bot/docs/ALFA_AI_HOW_TO_USE.md)
- [/home/ansible/docs/ALFA_AI_HOST_apps_USAGE.md](/home/ansible/docs/ALFA_AI_HOST_apps_USAGE.md) — host-level AI
- [README.md](../README.md) — stack overview

---
