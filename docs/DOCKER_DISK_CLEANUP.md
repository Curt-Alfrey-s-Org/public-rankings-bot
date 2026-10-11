# Docker and disk cleanup

This repository includes **`scripts/cleanup_docker_disk.sh`** to reclaim space when the root filesystem fills up. A full disk commonly causes Docker builds, Postgres, and helper scripts to fail with errors like **“No space left on device”** or containers that exit immediately after start.

## What the script does

1. Prints **`df -h /`** so you can see usage at a glance.
2. Emits a **WARNING** when **`/`** is **≥90%** used **or** **≤2 GiB** free (so you know to act even if you skip Docker prunes).
3. If the Docker CLI is available **and** the daemon is reachable (uses **`sudo docker`** only if **`docker info`** fails without sudo), it prunes **BuildKit build cache**:
   - **Default:** `docker builder prune -f` — removes unused cache; keeps recent layers.
   - **Aggressive:** `docker builder prune -af` — removes **all** build cache (next builds are slower but frees the most space).
4. Optionally prunes **dangling images** (`docker image prune -f`) or, with explicit safeguards, **all unused images** (`docker image prune -a`).

If Docker is missing or the daemon is not running, the script **skips** prune steps and **exits 0** (so CI or minimal hosts do not fail).

## Usage

From the repository root:

```bash
./scripts/cleanup_docker_disk.sh
./scripts/cleanup_docker_disk.sh --help
```

### Flags

| Flag | Effect |
|------|--------|
| *(none)* | `docker builder prune -f` |
| `--aggressive` | `docker builder prune -af` |
| `--images` | Also run `docker image prune -f` (dangling images only) |
| `--all-images` | Run `docker image prune -a -f` — **dangerous**; see below |

### Environment variables

| Variable | Effect |
|----------|--------|
| `CLEANUP_DOCKER_AGGRESSIVE=1` | Same as `--aggressive` |
| `CLEANUP_DOCKER_IMAGES=1` | Same as `--images` |
| `CLEANUP_DOCKER_CONFIRM_ALL_IMAGES=1` | Required for non-interactive `--all-images` (automation only) |

Examples:

```bash
CLEANUP_DOCKER_AGGRESSIVE=1 ./scripts/cleanup_docker_disk.sh
CLEANUP_DOCKER_IMAGES=1 ./scripts/cleanup_docker_disk.sh
```

## `--all-images` safety

`docker image prune -a` deletes **every image not referenced by a running container**. The next **`docker compose build`** or **`pull`** may re-download large layers.

The script allows `--all-images` only if:

- **`CLEANUP_DOCKER_CONFIRM_ALL_IMAGES=1`** is set **(non-interactive)**, or  
- You run interactively and type **`YES`** when prompted.

There is **no** silent auto-run of `image prune -a` in deploy scripts.

## Rankings-bot: cleanup before `full_deploy` image build

**`./scripts/full_deploy.sh`** can invoke this script **before** `docker compose build` **only when you opt in**. It runs when a new image build is needed (`NEED_BUILD=1`) and:

| `RUN_DOCKER_CLEANUP_BEFORE_BUILD` | Behavior |
|-----------------------------------|----------|
| *(unset)* | Do **not** run cleanup before build (default). |
| `1`, `yes`, `true` | Always run **`cleanup_docker_disk.sh`** before build. |
| `auto` | Run only if **`/` ≥85%** used **or** **≤2 GiB** free (same free-space heuristic as the script’s 2 GiB check, with an earlier 85% threshold for deploy). |

Example:

```bash
RUN_DOCKER_CLEANUP_BEFORE_BUILD=auto ./scripts/full_deploy.sh --production
```

If **`cleanup_docker_disk.sh`** exits non-zero, **`full_deploy`** logs a warning and **continues** (deploy should not hard-fail only on cleanup).

Related entry points that mention this script: **`scripts/start.sh`** header, **`docs/PRODUCTION_DEPLOYMENT.md`**, **`docs/INDEX.md`**.

## After cleanup

- Re-run your usual start or deploy command (e.g. **`./scripts/start.sh`** or **`./scripts/full_deploy.sh`**).
- If the disk was **100% full**, also check **`/var/log`**, **`journalctl`** disk use, and large **`frontend/node_modules`** directories on build hosts.

## See also

- [START_STOP_RESTART.md](START_STOP_RESTART.md) — start/stop scripts  
- [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) — production deploy flow  
