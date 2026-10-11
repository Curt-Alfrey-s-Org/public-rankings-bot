# Archived / reference scripts

`start_legacy.sh` was a snapshot of **`scripts/start.sh`** from an intermediate refactor (when `start.sh` delegated everything to `full_deploy.sh`).

**Current `scripts/start.sh`** is restored to the **full intelligent starter** (same family as `main`): full stack, deps-only, app-only, dev, tunnel, `--no-cache`, maintenance/production flags.

**Frontend builds:** **`scripts/build_frontend_with_docker.sh`** is the **only** production path (`start.sh`, `full_deploy.sh`, Admin Update website). There is **no** host `npm` fallback in those scripts.
