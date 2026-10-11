# AI governance (consumer stub)

**Canonical source:** [alfa-ai `docs/AI_GOVERNANCE.md`](https://github.com/example-owner-s-Org/alfa-ai/blob/main/docs/AI_GOVERNANCE.md)

This consumer repo follows the ALFa cluster AI oversight model:

- **L1 default:** programmatic routing; AI enriches and suggests only.
- **L2 mutate:** human Approve before any SSH, settings, or remediation apply.
- **L3 auto-fix:** off by default; allowlisted playbooks only after drills.

Consumer bots do not implement host actions or incident remediation. They call the
shared LiteLLM gateway over HTTP with env-configured model aliases.

**Production requirements (audit D-003 / D-006 / D-013):**

- `LITELLM_BASE_URL` points at the brain (`http://192.0.2.30:8413` unless on shared Docker network).
- `LITELLM_API_KEY` is a **unique** key (prefer LiteLLM virtual keys) — no shared `sk-*-dev` placeholders.
- When `LITELLM_ENABLED=true`, do **not** silently fall back to direct Ollama unless `LITELLM_ALLOW_OLLAMA_FALLBACK=true` (break-glass only).

Standards extracts: alfa-ai `docs/standards/README.md`.
Autonomy matrix: alfa-ai `docs/AI_AUTONOMY_AND_OVERSIGHT.md`.
Host map: alfa-ai `docs/REPO_HOST_MAPPING.md`.

Do not duplicate the full governance doc here — link and comply with env boundaries.
