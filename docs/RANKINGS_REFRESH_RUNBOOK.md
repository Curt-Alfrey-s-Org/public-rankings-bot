# Rankings refresh runbook (host vs container, maintenance mode)

**Purpose:** Explain why `python3 scripts/refresh_rankings.py` on the **host** often fails while the **web UI works**, and give the **correct** commands for the Docker stack defined in [`production/docker-compose.prod.yml`](production/docker-compose.prod.yml).

**Related:** [HOW_DATA_IS_UPDATED.md](HOW_DATA_IS_UPDATED.md), [SCHEDULED_REFRESH.md](SCHEDULED_REFRESH.md), [MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md](MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md), [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md).

---

## Three runtime contexts

| Context | Who runs the code | Typical `DATABASE_URL` host | Result |
|--------|-------------------|-----------------------------|--------|
| **Browser → API container** | Uvicorn in `rankings-bot-api` | `rankings-bot-postgres` (Docker DNS) | Works: same Docker network as Postgres. |
| **Host shell: `python3 scripts/refresh_rankings.py`** | Your login user, reads `.env` | Often `postgres` or `rankings-bot-postgres` from `.env` | **Fails:** those hostnames do **not** resolve on the host OS. |
| **Inside API container** | Same as row 1 | Set by Compose (`rankings-bot-postgres`) | **Correct** for CLI refresh when Postgres has **no** host port publish. |

The API service **overrides** `DATABASE_URL` in Compose to use the Postgres container hostname (see [`production/docker-compose.prod.yml`](../production/docker-compose.prod.yml)). Postgres in that file is **not** mapped to `localhost:5432` by default, so the host cannot connect with a container-only hostname.

---

## Maintenance mode vs “production” (nginx)

**Maintenance mode** (see [MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md](MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md)) only changes which **nginx** `server` block serves public `www` (static page vs proxy to the API). It does **not** swap compose files: **`rankings-bot-api` and Postgres stay up** on the same networks.

- Use the same `docker compose exec rankings-bot-api ...` commands below whether nginx is in **maintenance** or **production**.
- If the public site shows the maintenance page, test the app via **localhost** (or the path documented in the maintenance workflow), not the static `www` page.

There is **no** separate “maintenance `docker-compose.yml`” for the database in the standard setup; the single stack is still [`production/docker-compose.prod.yml`](../production/docker-compose.prod.yml) (included from the repo-root [`docker-compose.yml`](../docker-compose.yml)).

---

## Canonical: run refresh inside the API container

From the machine where Docker runs the stack:

```bash
cd /path/to/rankings-bot/production
docker compose -f docker-compose.prod.yml exec rankings-bot-api \
  python3 scripts/refresh_rankings.py --wpa-only --force
```

- **`--wpa-only`:** WPA divisions (+ Artistic in the same bundle) only; omit for full WPBA + WPA + Fargo table step.
- **`--force`:** Skips staleness skip logic (`REFRESH_STALE_HOURS`); always runs the scrape phase when the script executes.

Full refresh (WPBA + WPA + Fargo scrape into table):

```bash
docker compose -f docker-compose.prod.yml exec rankings-bot-api \
  python3 scripts/refresh_rankings.py --force
```

Use **`-T`** if the caller has no TTY (e.g. some cron wrappers):

```bash
docker compose -f docker-compose.prod.yml exec -T rankings-bot-api \
  python3 scripts/refresh_rankings.py --wpa-only --force
```

---

## Verify after a run

1. **Exit code:** `0` from the `exec` command (script exits `1` if nothing succeeded).
2. **Logs:**  
   `docker compose -f docker-compose.prod.yml logs rankings-bot-api --tail 200`
3. **Database (optional):** from the Postgres container, check latest snapshot dates for `WPA_Men` / `WPA_Women` (adjust user/db if needed):

```bash
docker compose -f docker-compose.prod.yml exec rankings-bot-postgres \
  psql -U rankingsbot_user -d rankingsbot -c \
  "SELECT ranking_system, MAX(snapshot_date) FROM rankings WHERE ranking_system IN ('WPA_Men','WPA_Women') GROUP BY 1;"
```

4. **UI:** Rankings / Leaderboard for WPA; if nginx is on maintenance, use the **internal** app URL from [MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md](MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md).

---

## Code behavior (reference)

- [`scripts/refresh_rankings.py`](../scripts/refresh_rankings.py): after WPA saves and splits, refreshes **materialized views** when any WPA division saved rows. `--force` only affects the staleness skip at the start of the script.
- [`api/routes/rankings.py`](../api/routes/rankings.py): after the **WPA** individual scraper run, calls **`refresh_materialized_views()`** (aligned with the WPBA scraper path).

---

## When host-side `python3` is OK

Only if Postgres is **reachable from the host** (e.g. you publish port `5432` in Compose **and** set `DATABASE_URL` to `127.0.0.1` or the real host). That is **not** the default in [`production/docker-compose.prod.yml`](../production/docker-compose.prod.yml). Prefer **`docker compose exec`** unless you have deliberately exposed Postgres for local tooling.

---

## Troubleshooting

### Empty WPA scrape / parse errors

Check API logs, upstream WPA HTML changes, and timeouts (`REFRESH_SCRAPER_TIMEOUT_SEC`). Run **`docker compose exec`** from the runbook so `DATABASE_URL` resolves inside the stack.

### `Blocked rankings write ... Set ALLOW_RANKINGS_DROP=1`

[`database/postgres_manager.py`](../database/postgres_manager.py) can refuse saves when the new row count is far below the previous snapshot (drop guard). If the upstream site really has fewer players or you intentionally accept the drop:

```bash
docker compose -f docker-compose.prod.yml exec -e ALLOW_RANKINGS_DROP=1 -T rankings-bot-api \
  python3 scripts/refresh_rankings.py --wpa-only --force
```

Use **`ALLOW_RANKINGS_DROP=1`** only when you understand the risk; then remove it from routine cron lines.
