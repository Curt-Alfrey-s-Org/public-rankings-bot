# Docker: shared base image and avoiding full rebuilds for small edits

You asked: *Can we have a generic/base container with code all bots need, plus bot-specific containers, so we don’t rebuild one entire container for a few edits? Are we using the smartest config right now?*

**Short answers:**  
- **Yes, it’s possible** — shared base image + bot-specific layers, and/or mounting frequently changed content (e.g. frontend) so small edits don’t require a container rebuild.  
- **Rankings Bot now uses Option B:** frontend **`dist/`** is **mounted** from the host (not copied into the API image). Website-only edits = **`./scripts/build_frontend_with_docker.sh`** (Docker-only; no host npm) + restart the API container if needed — **no API image rebuild** for pure frontend changes.

Below: current approach, then two patterns that reduce rebuilds, and a practical recommendation.

---

## Current setup

- **Rankings Bot:** Uses **Option B** — `frontend/dist` is **mounted** at run time (see `production/docker-compose.prod.yml`). Website-only changes = **`./scripts/build_frontend_with_docker.sh`** + restart container if your stack requires it, no API image rebuild. DB and logs are volumes.
- **Other bots** (contracts-bot, credit-check-bot, rankings-bot): Still monolithic (each copies its code and, if any, frontend into the image). No shared base image.

---

## Option A: Shared base image + bot-specific layers

**Idea:** One “generic” image with everything **all** bots need (Python version, system packages, common libs, shared code like auth/health/logging). Each bot image is `FROM bots-common-base` and only adds that bot’s app code and frontend.

**Benefits:**

- Change **generic** code (e.g. shared auth) → rebuild **base** once; then each bot image rebuild is fast (base layers cached).
- Change **one bot** → rebuild only **that** bot’s image; other bots and base are unchanged.

**Rough layout:**

```dockerfile
# e.g. bots-common/Dockerfile (build once, rarely)
FROM python:3.10-slim
RUN apt-get update && apt-get install -y gcc g++ curl && rm -rf /var/lib/apt/lists/*
COPY requirements-common.txt .
RUN pip install --no-cache-dir -r requirements-common.txt
COPY shared/ /app/shared/   # auth, health, logging, etc.
# No CMD — this is a base image
```

```dockerfile
# rankings-bot/Dockerfile
FROM your-registry/bots-common-base:latest
WORKDIR /app
COPY requirements-api.txt requirements.txt ./
RUN pip install --no-cache-dir -r requirements-api.txt -r requirements.txt
COPY api/ /app/api/
COPY scrapers/ /app/scrapers/
COPY frontend/dist/ /app/frontend/dist/
# ...
```

**Cost:** You have to factor out “generic” code into a shared repo or image and keep base and bots in sync. Worth it if many bots share real code and you change that shared code often.

---

## Option B: Mount frontend (and optionally config) — no rebuild for website edits

**Idea:** Don’t bake `frontend/dist` into the image. Build it with a **Docker-based** Node build (this repo: `scripts/build_frontend_with_docker.sh`) or CI equivalent, then **mount** `frontend/dist` into the container. Same for config files if they change often.

**Benefits:**

- **Website / frontend edits:** Run **`./scripts/build_frontend_with_docker.sh`** (or CI Docker build). Restart the container **or** do nothing if the app picks up new files from the mount. **No API image rebuild.**
- DB and logs are already volumes — no change there.

**Example (Rankings Bot):**

- **Image:** Dockerfile **does not** `COPY frontend/dist/`. Image only has API + deps.
- **Compose / run:** Mount the host’s built frontend into the container:

  ```yaml
  volumes:
    - ./frontend/dist:/app/frontend/dist:ro
  ```

- **Deploy after a frontend change:**  
  `./scripts/build_frontend_with_docker.sh` → then `docker restart rankings-bot-api` (or reload the process that serves static files). No `docker build` of the API image.

**Tradeoff:** The container is no longer fully self-contained; it depends on the host (or a volume) for `frontend/dist`. For a single server or known deploy path, this is usually acceptable and very convenient for small edits.

---

## Option C: Base image + mounted frontend (best of both)

- Use a **shared base image** (Option A) so “generic” changes are one base rebuild + fast bot rebuilds.
- **Mount** `frontend/dist` (Option B) so website-only changes never require an image rebuild.

Then:

- **Generic code change** → rebuild base, then rebuild bot images (fast).
- **One bot’s backend change** → rebuild that bot’s image only.
- **Website/frontend change** → Docker-based frontend build, restart container (or serve from mount); **no API image rebuild.**

---

## Recommendation

- **Right now you’re not using the “smartest” config for minimizing rebuilds** — you’re using the simplest (one image per bot, everything inside the image).
- **Quick win:** For **Rankings Bot** (and any bot where you often change the site), introduce **Option B**: mount `frontend/dist` instead of copying it in the Dockerfile. Then a “few edits” to the website = **`build_frontend_with_docker.sh`** + restart container (or no restart if your stack picks up the new files). No need to refactor all bots or introduce a base image first.
- **Later, if you have real shared code across bots:** Add **Option A** (shared base image) so generic changes are one base rebuild + fast bot rebuilds. Option B (mounted frontend) can stay so frontend-only changes still never rebuild the image.

---

## Summary

| Approach | Small website edit | Small generic (shared) change | One bot backend change |
|----------|--------------------|--------------------------------|-------------------------|
| **Current (monolithic)** | Rebuild bot image + restart | Rebuild each bot image | Rebuild that bot image |
| **Option B (mount frontend)** | Docker frontend build + restart container, **no API image rebuild** | Rebuild each bot image | Rebuild that bot image |
| **Option A (base image)** | Rebuild bot image + restart | Rebuild base once, then bot images (fast) | Rebuild that bot image only |
| **Option C (base + mount)** | Docker frontend build + restart, **no API image rebuild** | Rebuild base + bot images (fast) | Rebuild that bot only |

So: **yes, you can** have a generic base plus bot-specific containers and avoid full rebuilds for small edits — by using a shared base (Option A) and/or by mounting the built frontend (Option B). The most practical next step is **Option B** (mount `frontend/dist`) for the bot you edit most often.

---

## Option B implemented for Rankings Bot

**Dockerfile:** No longer copies `frontend/dist/`; image has an empty `/app/frontend/dist` (API shows “Frontend not deployed” until the volume is mounted).

**Compose:** `production/docker-compose.prod.yml` mounts `../frontend/dist:/app/frontend/dist:ro` for `rankings-bot-api`.

**Manual run (when not using compose):** Include the frontend volume:

```bash
-v "$REPO/frontend/dist:/app/frontend/dist:ro"
```

**After website-only edits:**  
1. `./scripts/build_frontend_with_docker.sh`  
2. `sudo docker restart rankings-bot-api` (if needed)  

No `docker build` or image push. If you use `docker run` by hand, ensure `frontend/dist` exists on the host before starting the container.

---

## Shared dependency cache (`/srv/dep-cache`)

To avoid redownloading pip/npm/apt packages every time a container is rebuilt, all bot repos (rankings-bot, atems, contracts-bot, credit-check-bot, market-pie5-bot) share a single on-disk dep cache at **`/srv/dep-cache`**.

**How it works:**
- `Dockerfile` / `Dockerfile.base` declare BuildKit cache mounts with shared IDs: `bots-pip`, `bots-apt`, `bots-apt-lists`, `bots-npm`. Any bot's build reuses what another bot already downloaded.
- `scripts/build_frontend_with_docker.sh` bind-mounts `/srv/dep-cache/npm` into the `node:20-alpine` build container as the npm cache.
- `scripts/start.sh` exports `BUILDX_BUILDER=alfa-builder` and `COMPOSE_BAKE=true` so every `docker build` / `docker compose build` is routed through the docker-container BuildKit that actually persists cache mounts across builds (the dockerd-integrated BuildKit does not — verified empirically).
- First build populates the cache; every subsequent build of any bot reuses it.

**Manage the cache:**
```bash
/srv/dep-cache/bin/dep-cache ensure-builder         # create/validate alfa-builder (large GC keep policy)
/srv/dep-cache/bin/dep-cache status                 # sizes + last-used per lane, per builder
/srv/dep-cache/bin/dep-cache prune --older-than 30d # purge entries unused ≥ 30 days
/srv/dep-cache/bin/dep-cache clear                  # wipe everything (asks first)
```

### ⚠ Don't pass `--no-cache` to `start.sh` for routine work

`--no-cache` disables the **layer cache**, forcing `RUN pip install -r requirements-*.txt` to re-execute even when `requirements-*.txt` hasn't changed. Even with a fully populated `bots-pip` cache mount, re-running pip's dependency resolver still takes ~5 minutes. Without `--no-cache`, BuildKit skips the pip step entirely when requirements are unchanged and the base image builds in ~5 seconds.

| Situation | Command | Expected time |
|-----------|---------|---------------|
| No code/dep changes | `./scripts/start.sh` | ~5 s (all layers cached) |
| Dep change (edit `requirements-*.txt`) | `./scripts/start.sh` | 1–5 min (cache mount serves wheels; resolver still runs) |
| Forced clean rebuild | `./scripts/start.sh --no-cache` | 3–5 min (use only for troubleshooting) |

Full details and policy: `/srv/dep-cache/README.md`.

Excluded per policy: `alfa-ai` (and any repo using hub-hub).
