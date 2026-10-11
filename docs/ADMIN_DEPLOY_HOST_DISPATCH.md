# Admin deploys without docker.sock — host deploy dispatcher

**Since June 2026** the internet-facing `rankings-bot-api` container no longer
bind-mounts `/var/run/docker.sock` and no longer joins the host `docker` group.
Docker documents docker-group/socket access as **root-equivalent on the host**
(<https://docs.docker.com/engine/security/#docker-daemon-attack-surface>), so an
API compromise must not hand an attacker the host Docker daemon.

Admin **Update website** and **Full deploy** still work — the deploy now runs on
the Docker host, triggered through a file queue.

## How it works

```
Admin clicks button
  → POST /api/admin/rebuild-website  (or /rebuild-all-images)
  → API writes logs/deploy-requests/<action>.request   (atomic tmp + rename; JSON)
  → host systemd path unit rankings-bot-deploy.path fires (PathExistsGlob)
  → rankings-bot-deploy.service (oneshot, User=ansible)
  → scripts/deploy_request_dispatcher.sh consumes the queue:
       rebuild_website → scripts/rebuild_website_now.sh  → logs/rebuild_website.log
       full_deploy     → scripts/full_deploy.sh --no-cache → logs/full_deploy.log
  → API streams the same bind-mounted log files to the admin UI (unchanged endpoints)
```

Key properties:

- **The API never holds the Docker socket.** It only writes a small JSON file
  into `logs/deploy-requests/` (inside the existing `../logs:/app/logs` bind mount).
- **Request content is data, never executed.** The dispatcher reads only the
  `action` field and matches it against a fixed allowlist
  (`rebuild_website`, `full_deploy`); anything else is logged and discarded.
- **Single process owner stays with Compose** — the dispatcher runs the same
  repo scripts an operator would run by hand; it does not start a second API.
- **Log streaming is unchanged.** Scripts append to the same `logs/*.log` files
  the API already streams (`GET /api/admin/rebuild-website/log`,
  `GET /api/admin/rebuild-all-images/log`); the dispatcher writes the
  `Done in Xs.` footer the streams stop on.
- systemd queues activations: per `systemd.path(5)`, `PathExistsGlob` is
  re-checked after the service deactivates, so a request queued mid-deploy runs
  next, never lost / never double-run (the dispatcher deletes each request
  before executing it, and holds a `flock`).

## Configuration

| Piece | Where | Value |
|---|---|---|
| `DEPLOY_REQUEST_DIR` | `production/docker-compose.prod.yml` → API `environment:` | `/app/logs/deploy-requests` (container path of `./logs/deploy-requests`) |
| Queue dir (host) | created on demand | `/home/ansible/rankings-bot/logs/deploy-requests/` |
| Dispatcher | repo | `scripts/deploy_request_dispatcher.sh` |
| Units | repo → copy to host | `production/systemd/rankings-bot-deploy.{path,service}` |
| Dispatcher log | host | `logs/deploy_dispatcher.log` |

When `DEPLOY_REQUEST_DIR` is **unset** (development, API on the host), the admin
endpoints fall back to running the scripts directly, as before.

## Install (one-time, on the Docker host)

```bash
sudo cp production/systemd/rankings-bot-deploy.path production/systemd/rankings-bot-deploy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rankings-bot-deploy.path
```

Verify: `systemctl status rankings-bot-deploy.path` shows `active (waiting)`.

Smoke test without touching the stack: `systemctl start rankings-bot-deploy.service`
with an empty queue is a no-op (exits 0).

Requirements: the `ansible` user can run `docker` (same requirement as running
`scripts/full_deploy.sh` manually).

## Rollout note

The compose change (socket mount removed, `DEPLOY_REQUEST_DIR` added) takes
effect at the **next** `docker compose up -d` of `rankings-bot-api`. Install and
enable the path unit **before** that deploy so the admin buttons keep working.

## Related docs

- `docs/PRODUCTION_DEPLOYMENT.md` §5 — Update website policy
- `docs/ENV_VARS.md` — `DEPLOY_REQUEST_DIR`
- `docs/START_STOP_RESTART.md` — frontend build policy
- `Roadmap.md` — June 2026 audit, P0 item "Reduce or isolate the Docker socket mount"
