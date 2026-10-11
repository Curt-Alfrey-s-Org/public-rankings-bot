# Docker build pattern — rankings-bot

**This repo's default:** Pattern A — server-side dep cache at `/srv/dep-cache`.

Every `Dockerfile` / `Dockerfile.base` / `frontend/Dockerfile` and every
build script in this repo must pull its pip / npm / apt deps through the
shared BuildKit cache mounts (ids: `bots-pip`, `bots-apt`, `bots-apt-lists`,
`bots-npm`) or via `npm_config_cache=/srv/dep-cache/npm` for host / `docker
run` builds. No plain `RUN pip install` / `npm ci` without a cache mount.

See the canonical spec for recipes, ids, prerequisites, and verification:

→ [`/home/ansible/docs/DOCKER_BUILD_PATTERNS.md`](../docs/DOCKER_BUILD_PATTERNS.md)
  (section "Pattern A — Server-side dep cache")

## hub hub overlay (LAN / air-gap)

Wheels are **not stored in git** — `build-contexts/wheels-bots/` contains only a
`.gitkeep` placeholder after clone. Build scripts (`scripts/start.sh`, etc.)
automatically call **`alfa-ai/scripts/sync-bot-wheels-preflight.sh`** before
`docker build`, which syncs wheels from the hub `hub` hub when reachable.
**No manual `sync-bot-wheels-from-hub.sh` run is required before building** — it
happens automatically and is **non-fatal**: if the hub is unreachable the build
falls back to PyPI.

API **`Dockerfile.base`** uses **`pip install --find-links /tmp/wheels`**;
frontends use **`NPM_REGISTRY=http://192.0.2.30:4873`** by default — override with
**`docker build --build-arg NPM_REGISTRY=https://registry.npmjs.org`** when Verdaccio is unavailable.
Inventory + seed commands: [`alfa-ai/docs/HUB_ARTIFACTS.md`](../alfa-ai/docs/HUB_ARTIFACTS.md).

## When to ask about pattern B (hub hub) instead

An agent MUST ask the user which pattern to use if the build:

- Pulls CUDA-specific wheels, HuggingFace model shards, Ollama blobs, or any
  single artifact ≥ 200 MB.
- Will run on a cluster worker that must not touch the public internet.

Otherwise, stay on pattern A (server cache).

## Quick verification

```bash
/srv/dep-cache/bin/dep-cache status   # sizes + last-used per shared cache
```

After any rebuild, `bots-pip` / `bots-npm` / `bots-apt*` should grow (new pin)
or stay flat (everything cached). If those lanes are stuck at 0, the cache
mount wasn't applied — check the `# syntax=docker/dockerfile:1` header and
the `--mount=type=cache,id=bots-*` lines.
