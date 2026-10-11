# Deployment refactor review

**Scope:** PRODUCTION_DEPLOYMENT.md, scripts that start/restart the API, CODING_STANDARDS.md deployment section, Cursor rules.  
**Criteria:** Industry standards (Twelve-Factor, single process owner, no duplicate starters), clarity, consistency.

---

## Summary: Compliant with minor fixes

The refactor aligns with Twelve-Factor (process manager), FastAPI/uvicorn deployment guidance, and single-owner principle. One doc duplicate was removed; one recommendation remains (Cursor rule).

---

## 1. PRODUCTION_DEPLOYMENT.md

### Compliant

- **Standards alignment** section cites Twelve-Factor (Factor VI – Processes), FastAPI deployment, and project CODING_STANDARDS and PRODUCTION_API_OWNERSHIP. Core principle stated: production = single process manager (systemd); dev may use scripts.
- **No “systemd or script” as equal production options.** Production is explicitly systemd; scripts “delegate” when the service exists.
- **Process Management** section: production = systemd only; scripts delegate; dev = scripts start uvicorn when no systemd.
- **What to avoid** includes “Two starters for the same service (CRITICAL)” with clear rule: production MUST use systemd only; scripts MUST delegate.
- **How to move to the standard** distinguishes production (install systemd) vs development (use restart_api.sh, which delegates).

### Fixed in this review

- **Duplicate content:** Removed duplicate “4. Standard flow” and the repeated “After that, ‘what’s talking to what’…” paragraph at the end of “How to move to the standard.”

### Suggestion

- **Link path:** The link `../../.github/CODING_STANDARDS.md` may resolve differently depending on where the doc is viewed (e.g. from `Rankings-Bot/docs/` vs repo root). If links are broken from the docs folder, use `../.github/CODING_STANDARDS.md` from `docs/PRODUCTION_DEPLOYMENT.md`.

---

## 2. Scripts that start/restart the API

### restart_api.sh — Compliant

- Detects systemd service with `systemctl cat rankings-bot-api.service`; if present, runs `sudo systemctl restart rankings-bot-api` and exits. No direct uvicorn start when systemd owns the service.
- Fallback (no systemd): kill process on port, then `nohup uvicorn ...`. Comment references Twelve-Factor, FastAPI deployment, CODING_STANDARDS. Single-owner behavior is correct.

### start_api.sh — Compliant

- Same pattern: if systemd service exists, `sudo systemctl start rankings-bot-api` and exit. Otherwise dev mode with `uvicorn --reload`. Doc references STANDARD_DEPLOYMENT and PRODUCTION_API_OWNERSHIP.

### start_rankings_bot_all.sh — Compliant

- Step 2 calls `./scripts/restart_api.sh` only. It does not start uvicorn directly; delegation is through restart_api.sh. Correct.

### build_on_server.sh — Compliant

- With `--restart`: uses `systemctl is-active rankings-bot-api` and then `sudo systemctl restart rankings-bot-api`. Does not start uvicorn directly. Correct.

### full_deploy.sh, rebuild_website_now.sh, update_frontend.sh, setup_website_no_restart.sh

- They call `restart_api.sh`, which delegates to systemd when the service exists. No duplicate starter introduced. Correct.

### diagnose_login.sh, diagnose_rankings_bot_gateway.sh

- They suggest “restart_api.sh or systemctl …” for operator actions. That is consistent with “either script (which delegates) or systemctl directly.” No change required.

---

## 3. CODING_STANDARDS.md deployment section

### Current state

- **Docker & Deployment Standards** exists (Dockerfile, Docker Compose). No explicit “Host API / process manager / single owner” subsection.

### Assessment

- Docker/Compose content matches common practice (restart policy, health checks, etc.). The refactor did not add a dedicated “Process manager for host API” or “Single owner per service” subsection. Optional improvement: add a short bullet under Docker & Deployment or a new subsection stating that production host services run under a process manager (e.g. systemd), one owner per service/port, and scripts must delegate when the service is managed (reference STANDARD_DEPLOYMENT and PRODUCTION_API_OWNERSHIP). Not required for compliance but would tie CODING_STANDARDS to the deployment refactor.

---

## 4. Cursor rule

### Current state

- Only `.cursor/rules/standard-driven-changes.mdc` was found. No separate deployment- or process-ownership-specific rule file.

### Recommendation

- Add a Cursor rule (e.g. `.cursor/rules/deployment-standards.mdc` or equivalent) so that:
  - Deployment and process ownership follow industry standards: one process manager, single owner per service/port; no duplicate starters.
  - Docs and code must not present “systemd or script” as equal production options; production uses the process manager; scripts delegate when the service exists.
- This makes the deployment standard the default for this project in Cursor. If the refactor intended this but the file was not created, add it per the above.

---

## 5. Consistency check

| Item | STANDARD_DEPLOYMENT | restart_api.sh | start_api.sh | start_rankings_bot_all |
|------|---------------------|----------------|--------------|-------------------------|
| Production = systemd | Yes | Delegates to systemd | Delegates to systemd | Via restart_api.sh |
| Scripts delegate when service exists | Yes | Yes | Yes | N/A (calls restart_api.sh) |
| No direct uvicorn when systemd present | Yes | Yes | Yes | Yes |
| Twelve-Factor / single owner cited | Yes | In comments | In comments | Via restart_api.sh |

Consistency is good across the refactored deployment doc and scripts.

---

## 6. Conclusion

- **Industry standards:** Twelve-Factor (process manager), FastAPI/uvicorn (process manager in production), and single-owner principle are reflected in PRODUCTION_DEPLOYMENT.md and in the API start/restart scripts. Docker Compose manages all services.
- **Clarity:** Production vs development and the “scripts delegate” behavior are clear. One duplicate block was removed from PRODUCTION_DEPLOYMENT.md.
- **Consistency:** Doc and scripts agree; all API restarts go through Docker Compose.
- **Follow-up:** (1) Add a Cursor rule for deployment/process ownership if you want it as project default. (2) Optionally add a brief “process manager / single owner” note to CODING_STANDARDS.md and fix the CODING_STANDARDS link path in PRODUCTION_DEPLOYMENT if needed.
