# Server-wide repository sync — 2026-04-02

This note records a coordinated **document → commit → backup tag → push** pass across git checkouts under `/home/ansible`.

## Repositories updated

| Repository | Branch | Remote | Commit message prefix | Backup tag |
|------------|--------|--------|----------------------|------------|
| `atems` | `main` | `example-owner-s-Org/ATEMS` | `chore: server sync 2026-04-02` | `backup/server-2026-04-02` |
| `contracts-bot` | `main` | `contracts-bot` | same | same |
| `credit-check-bot` | `master` | `credit-check-bot` | same | same |
| `market-pie5-bot` | `main` | `market-pie5-bot` | same | same |
| `rankings-bot` | `main` | `Rankings-Bot` | same | same |
| `rv-auto-finder` | `main` | `auto-rv` | same (+ `.gitignore`, SSH `origin`) | same |

Each repo now includes **`docs/SERVER_COMMIT_2026-04-02.md`**, generated immediately before `git add`, listing status, diff stats, and untracked paths at commit time.

## Repositories not changed

| Path | Reason |
|------|--------|
| ALFa AI (`alfa-ai/`) | Working tree was already clean; `origin` was switched from HTTPS to **SSH** and **`master` was pushed** to `origin` (new branch on remote). |
| `temp-repo` | Empty working tree, **no commits**, `origin/main` gone — not safe to push without manual repair. |
| `archives/rankings-bot/rankings-bot.backup.20260222_1439` | **Intentionally skipped.** Nested snapshot under `Rankings-Bot/`, **behind `origin/main` by 100+ commits**, contains database dumps and stale tree. Pushing would not be a backup of current work; use `/home/ansible/rankings-bot` as canonical. |

## Security / hygiene

- **`rv-auto-finder`**: `origin` was using an HTTPS URL with an embedded token; it was reset to **`git@github.com:example-owner-s-Org/auto-rv.git`**. If that token was ever exposed, **revoke it** in GitHub and use SSH or a credential helper.
- **ALFa AI** (`alfa-ai/` repo): Same HTTPS → SSH change so pushes do not require interactive username/password.

## Rankings-bot highlights (this wave)

Includes (among other work): Externalpool migration, Ollama/AI monitor and narratives, tournament analytics API (`tournament-analytics` by period), Player Performance UI period buttons, monitoring assets, migrations, CI Grok suggest workflow, and compliance tests. See `git log` and `docs/SERVER_COMMIT_2026-04-02.md` in this repo for the full file list.
