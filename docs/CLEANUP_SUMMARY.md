# Repo Cleanup Summary (Feb 2026)

## Roadmap

- **Consolidated** 4 roadmap files into single [docs/ROADMAP.md](ROADMAP.md)
- **Removed** root `Roadmap.md` (duplicate)
- **Thin pointer** at `Rankings-Bot/Roadmap.md` → docs/ROADMAP.md
- **Added** Features & Improvements backlog, Tech Debt section

## Documentation

- **Created** `docs/archive/` for completion reports and implementation summaries
- **Moved** 40+ completion/summary docs to `docs/archive/`
- **Moved** `FARGO_QUICK_REFERENCE.md` to `docs/` (operational reference)
- **Updated** [docs/INDEX.md](INDEX.md) with archive link and Fargo quick ref

## GitHub Convention

- **Created** [CONTRIBUTING.md](../CONTRIBUTING.md) — dev setup, testing, PR guidelines
- **Updated** root README — project structure, doc links

## Dead Code

- **Removed** `api/services/fargo_client_old.py` (backup from refactor; rollback via git)

## Logs & Gitignore

- **Added** explicit log patterns to `.gitignore`: `rebuild_website.log`, `rankings_bot.log`, etc.
- Logs in `logs/` already ignored

## Files Moved to Archive

See [docs/archive/](archive/) for full list. Examples: `*_COMPLETE.md`, `*_SUMMARY.md`, `*_COMPLETION_REPORT.md`, rollout deliverables, optimization checklists.
