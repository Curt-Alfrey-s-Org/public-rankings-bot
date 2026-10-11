# Cleanup delete list — repo + server

**Policy:** Cleanup is **manual only**. There is **no** scheduled job, CI step, or deploy hook that runs these steps. Run them when **you** choose, or when you explicitly ask someone to perform cleanup.

Use this as a **checklist**. **Tier A** is usually safe on a dev machine. **Tier B+** needs a quick “still referenced?” check. **Data tiers** can break scrapers, imports, or recovery—confirm backups and jobs first.

---

## Tier A — Safe local hygiene (regenerable / noise)

Run from repo root (`/home/ansible/rankings-bot` or your clone).

| Item | Action | Notes |
|------|--------|--------|
| Python bytecode | `find . -type d -name __pycache__ -prune -exec rm -rf {} +` | Recreated on import |
| Pytest cache | `rm -rf .pytest_cache` | Recreated by pytest |
| Root `*.log` | `rm -f *.log full_deploy_*.log` | Already in `.gitignore` (`*.log`); Admin/UI may recreate `rebuild_website.log` |
| `logs/` directory | `rm -f logs/*.log` (or `rm -rf logs` if only logs) | `.gitignore` has `logs/` |
| `frontend/playwright-report/` | Remove from disk; **do not commit** | Generated E2E output; now ignored in `.gitignore` |
| `frontend/dist/` (dev only) | `rm -rf frontend/dist` | Rebuild with `./scripts/build_frontend_with_docker.sh` |
| Deploy hash files | `rm -f .docker-build-hash .frontend-build-hash` | Scripts regenerate when needed |
| Temp deploy backups | On **server**: `rm -rf /tmp/rankings_deploy_backup_*` | Enhanced-deploy-era backups; only remove if you do not need rollback |

**One-liner (repo root, conservative):**

```bash
cd /path/to/rankings-bot
find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null
rm -rf .pytest_cache
rm -f *.log full_deploy_20*.log 2>/dev/null
rm -f logs/*.log 2>/dev/null
```

---

## Tier B — Stale documentation / session notes (optional)

These are **historical**; they do not change runtime. Deleting frees noise; **git history** keeps old content if they were committed.

| Location | Suggestion |
|----------|------------|
| `docs/archive/` | Bulk-delete folder if you do not need ML/staging/rollout write-ups from archived work |
| Root `*_SUMMARY.md`, `*_COMPLETE.md`, `SESSION_*.md`, `DEPLOYMENT_COMPLETE.md`, etc. | Pick individually or move one “changelog” doc |
| `OBSOLETE_FILES.md` | **Outdated** (e.g. it once told you to delete `restart_api.sh`). **Delete or replace** with a line pointing to `docs/PRODUCTION_DEPLOYMENT.md` and this file |

**Keep unless you are sure:**

- `docs/INDEX.md`, `docs/PRODUCTION_DEPLOYMENT.md`, operational runbooks you still use
- `scripts/archive/README.md` and snippets you still reference (e.g. HOST-API nginx sample)

---

## Tier C — `data/` and `scraped_data/` (review before delete)

| Path | Risk |
|------|------|
| `data/*.json`, `data/*.csv` | Many patterns are **gitignored** but may exist on disk for imports, ALFA prep, or one-off tooling |
| `data/*_archive/` | May be used for backfill or debugging scrapers |
| `scraped_data/*` | Runtime/cache outputs for scrapers; safe to empty **if** you accept re-scrape or cold cache |

**Safer pattern:** archive to NAS/backup, then delete locally; or delete files older than N days with a find command **after** policy agreement.

---

## Tier D — Server-only (not in git)

| Item | Command / note |
|------|----------------|
| Old Docker data | `docker system df` then `docker system prune` / `docker builder prune` (see `docs/DOCKER_DISK_CLEANUP.md`) |
| Stopped containers | `docker container prune` (after confirming names) |
| Journal | `journalctl --vacuum-time=30d` (as root) if disks are tight |
| Orphan bind-mount clutter | Fix ownership with deploy user; avoid root-owned `frontend/dist` (see deploy docs) |

---

## Already applied in repo (Playwright)

- **`frontend/playwright-report/`** was **tracked** (~57MB generated HTML/JS). It should be **removed from the tree** and listed in `.gitignore`. Regenerate locally with Playwright when needed.

---

## Verification after cleanup

```bash
./scripts/smoke_test.sh   # or your health check
python3 -m pytest tests/backend/test_compliance_guardrails.py -q
```

---

## Related

- `docs/DOCKER_DISK_CLEANUP.md` — Docker prune
- `docs/CODE_QUALITY_AUDIT.md` — policy on workarounds / stale paths
- `docs/CONTAINER_DRIFT_PREVENTION.md` — do not “fix” prod with random host files
