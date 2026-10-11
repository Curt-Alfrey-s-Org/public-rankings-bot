# 4 parallel agent jobs (no overlap)

Run **one** job per agent. Each job touches **one file** in **one repo** so they do not interfere.

---

## Job A — Rankings-bot README (this agent)

**Repo:** `market-pie5-bot`  
**File:** `Rankings-Bot/README.md` only  

**Task:** Expand the existing "Screenshots / demo" section. Add a short bullet list of suggested captures (e.g. Rankings page, Movement page, Login screen) and the exact folder path `docs/screenshots/`. Keep it to 3–5 lines. Do not edit any other file.

---

## Job B — Rankings-bot SMOKE_CHECK credentials note (another agent)

**Repo:** `market-pie5-bot`  
**File:** `Rankings-Bot/docs/SMOKE_CHECK.md` only  

**Task:** In the "Script (quick run)" section, after the third code block (the one with `ADMIN_USERNAME` and `ADMIN_PASSWORD`), add one sentence:  
**"Credentials come from the project `.env` (e.g. `ADMIN_USERNAME`, `ADMIN_PASSWORD`); see `.env.example` if not set."**  
Do not edit any other file.

---

## Job C — market-pie5-bot ROADMAP smoke-check bullet (another agent)

**Repo:** `market-pie5-bot`  
**File:** `ROADMAP.md` only  

**Task:** Near the "9b. Option B … TOMORROW" line (or in the same low-priority / deployment section), add **one** new bullet:  
**"After deploy: run a smoke-check or health check (see market-pie5-bot docs/SMOKE_CHECK.md for script pattern)."**  
Do not edit any other file.

---

## Job D — contracts-bot ROADMAP smoke-check bullet (another agent)

**Repo:** `contracts-bot`  
**File:** `ROADMAP.md` only  

**Task:** Same as Job C: near "9b. Option B … TOMORROW" (or same deployment section), add **one** new bullet:  
**"After deploy: run a smoke-check or health check (see market-pie5-bot docs/SMOKE_CHECK.md for script pattern)."**  
Do not edit any other file.

---

## Summary

| Job | Repo         | File                          | Agent |
|-----|--------------|-------------------------------|--------|
| A   | market-pie5-bot | Rankings-Bot/README.md         | (this one) |
| B   | market-pie5-bot | Rankings-Bot/docs/SMOKE_CHECK.md | Agent 2 |
| C   | market-pie5-bot | ROADMAP.md                 | Agent 3 |
| D   | contracts-bot  | ROADMAP.md                 | Agent 4 |
