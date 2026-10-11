# USPBF — Production-Readiness Roadmap

**Status date:** 2026-06-09 (researched on `apps`; containers inspected live).
**Companion docs:** [`NEXT_STEPS.md`](NEXT_STEPS.md) (research + audit subagent pass), [`README.md`](README.md).

## Current state (verified)

- Stack is **up and healthy** on `apps`: `uspbf-nginx` (healthy), `uspbf_wordpress_1`,
  `uspbf_db_1` (healthy), `cf-uspbf` tunnel. Compose is the single process owner —
  compliant with [Twelve-Factor VI](https://12factor.net/processes) and
  `deployment-process-ownership.mdc`.
- **Public apex is still in MAINTENANCE mode** — the live container's
  `/etc/nginx/conf.d/default.conf` is the maintenance config. Visitors to
  `example.com` / `www` see the maintenance page; the full marketing site is only on
  the LAN dev preview (`:8089`).
- Static marketing site (`nginx-config/site/`) is content-complete (about, join,
  players, rankings, rules, tournaments) and baked into the nginx image.
- WordPress + MySQL run but are **not used by the public site** (kept for future CMS).
- Live versions: WordPress **6.9.1** (`wordpress:latest`), MySQL **8.4.8**
  (`mysql:8`), PHP 8.3.30. `cloudflared` pinned to `2026.3.0` in
  `scripts/start_cf_uspbf.sh` (good).
- No TODO/FIXME markers; git tree clean; no CI, no backup tooling, no monitoring
  integration found in this repo.

## Next step: post-merge host steps from the 2026-09-26 review (PR #3 fixes, PR #4 deps)

Open for review, not merged: [#3](https://github.com/example-owner-s-Org/USPBF/pull/3) (fixes, `fix/review-2026-09-26`) and [#4](https://github.com/example-owner-s-Org/USPBF/pull/4) (deps, `deps/update-2026-09-26`). The host steps for both PRs are here; this section is committed on the #3 branch. No env changes.

Host: `probilliards`, `/home/operator/USPBF`. That's the canonical host per [REPO_HOST_MAPPING.md](https://github.com/example-owner-s-Org/contracts-bot/blob/main/docs/REPO_HOST_MAPPING.md); `/home/ansible/USPBF` on `apps` is a backup clone. The repo scripts call `sudo docker compose`, so prefix the compose commands below with `sudo` if your user isn't in the `docker` group.

**Merge order:** the PRs share no files, so either order works. Recommended: #3 first, so the backup taken before #4 already uses the fixed `backup.sh` (no truncated backups).

### Before pulling
- [ ] #3: nothing to back up.
- [ ] #4: back up first with `cd /home/operator/USPBF && ./scripts/backup.sh`. It needs `uspbf_db_1` and `uspbf_wordpress_1` running and `.env` with `MYSQL_*`. Check that the newest `backups/uspbf_db_*.sql.gz` and the wp-content tar are non-empty.

### After merging PR #3
- [ ] `cd /home/operator/USPBF && git pull`
- [ ] Rebuild `uspbf-nginx` (the nginx templates are baked into the image):
  - While the apex is still in maintenance: `./start.sh --no-cache --maintenance`
  - Once the site is live: `./start.sh --no-cache --production`
  - If `--production` switched the apex by mistake: `./scripts/switch-site.sh maintenance`
- [ ] Verify caching:
  - `curl -sI -H 'Host: app.example.com' http://127.0.0.1:8089/sw.js | grep -i cache-control` should show `no-cache`.
  - Any `/api/assets/serve/<file>.png` URL should no longer return `max-age=31536000, public, immutable`.
- [ ] Optional: purge the Cloudflare cache once for `https://app.example.com/sw.js`, `https://app.example.com/registerSW.js` and `https://app.example.com/api/assets/serve/*` (by URL, or by prefix if your plan allows). This refreshes objects cached under the old 1-year header.
- [ ] Browser check: typing fast in the rankings / players / tournaments search should always show results for the newest filter.
- [ ] After the next `./scripts/backup.sh` run, there should be no `*.partial` files left in `backups/`.
- [ ] Tests locally (GitHub Actions is disabled): `node --test tests/js/*.test.js` (expect 17 pass) and `bash tests/nginx/run.sh` (expect 192 pass).

### After merging PR #4
- [ ] Take the backup above first. Then run `git pull && docker compose pull wordpress && docker compose up -d wordpress`
- [ ] On the existing `uspbf_wp_data` volume, the new image only updates PHP/Apache. WordPress core is updated by its own updater (Dashboard → Updates, or wp-cli).
- [ ] Check the running core version: `docker compose exec wordpress php -r 'include "/var/www/html/wp-includes/version.php"; echo $wp_version, PHP_EOL;'`
- [ ] Also check that `docker compose ps wordpress` shows it up and `/wp-admin` loads.

### Decisions for you
- [ ] WordPress 7.1.x image (`7.1.2-php8.3-apache`). WordPress treats X.Y as a major release, so #4 stays on 7.0.4.
- [ ] Security headers: every nginx `location` that sets its own `add_header` (/api/, /js/, /css/, /flags/, /branding/, the app server) drops the server-level `X-Content-Type-Options` / `X-Frame-Options` / `X-XSS-Protection`. Fix with a shared snippet or `add_header_inherit merge` (nginx ≥ 1.29.3) in its own PR?
- [ ] `scripts/backup.sh` passes the MySQL password on the `mysqldump` command line, where host users can see it in `ps`. Move it to an option file inside the container? Low risk on a single-admin host.
- [ ] `.github/workflows/tests.yml` uses Node 20 (EOL). Bump it to 22 yourself (needs `workflow` scope).
- [ ] For information only: player names containing `/` or `..` get a 400 from the traversal guard. That's intended.

## Next step: post-merge host steps from the 2026-09-25 security review

From [#1](https://github.com/example-owner-s-Org/USPBF/pull/1) (merged 2026-09-25). Deploy together with Rankings-Bot [#21](https://github.com/example-owner-s-Org/Rankings-Bot/pull/21) / [#22](https://github.com/example-owner-s-Org/Rankings-Bot/pull/22) (shared `BOT_API_KEY`).

- [ ] Set `BOT_API_KEY` in `.env` on `apps` to the **same value as rankings-bot-api**, only `A-Z a-z 0-9 . _ ~ + / = -`. `docker compose` and `uspbf-nginx` now refuse to start without it.
- [ ] Rotate `BOT_API_KEY` (treat as exposed: it was usable anonymously through `example.com/api/*` until this deploy). Generate with `openssl rand -hex 32` and set it in **both** USPBF and rankings-bot-api.
- [ ] Rebuild and redeploy nginx: `./start.sh --no-cache --production` (or `--maintenance` while the apex stays in maintenance).
- [ ] Smoke test:
      `curl -s -o /dev/null -w '%{http_code}\n' -H 'Host: example.com' http://127.0.0.1:8089/api/admin/users` → `404`;
      `curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8089/api/news?limit=1` → `200`;
      homepage, rankings, players and tournaments load data, and the ALFa demo answers.
- [ ] Run the tests locally (`node --test tests/js/*.test.js`, `bash tests/nginx/run.sh`); GitHub Actions is disabled for this repo, so `tests.yml` does not run.

**Keep in mind / open decision:**
- A new static-site `/api/...` call needs an entry in `nginx-config/snippets/uspbf-public-api-allowlist.conf` and `tests/nginx/run.sh`, or it gets 404.
- Decide whether to enable GitHub Actions for this repo or keep running tests locally.

## Production blockers (priority order)

1. **Public site never switched to production.** Everything else is moot while the
   apex serves the maintenance page. Go-live = content sign-off + `./scripts/switch-site.sh production`
   (or `./start.sh --production`).
2. **No database / volume backups.** `uspbf_db_data` and `uspbf_wp_data` are external
   named volumes with no dump or snapshot job anywhere in the repo. A host failure
   loses the WordPress DB irrecoverably.
3. **Unpinned images** (`wordpress:latest`, `mysql:8`). Docker official-image guidance
   is to pin the most specific tag in production; floating tags already caused
   observable drift on this host (USPBF WP 6.9.1 vs example_site WP 7.0 from the *same*
   `wordpress:latest` tag pulled at different times).
4. **Unused WordPress + MySQL are running and attached to `tunnel_network`** —
   unnecessary public-adjacent attack surface for a service nothing depends on.
5. **No uptime monitoring / alerting** for `example.com` or the tunnel.

## Phase 0 — Go-live (blocker #1)

- [ ] Owner sign-off on marketing-site content (review via `http://192.0.2.20:8089/`).
- [ ] Verify Cloudflare tunnel public hostnames (`example.com`, `www`, `app.example.com` →
      `http://uspbf-nginx:80`) per README §2.
- [ ] Switch: `./scripts/switch-site.sh production`. Verify from outside the LAN.
- [ ] Confirm `app.example.com` → rankings-bot SPA works (requires `rankings-bot-api`
      on `tunnel_network`; README Troubleshooting).

## Phase 1 — Backups & disaster recovery (blocker #2)

- [x] Add a scheduled `mysqldump` job (systemd timer on `apps`, single owner — do not
      add a second container) dumping `uspbf_db_1` to a dated file, plus retention.
      MySQL manual: [Ch. 9 Backup and Recovery — mysqldump](https://dev.mysql.com/doc/refman/8.4/en/using-mysqldump.html).
      **Done 2026-06-09:** `scripts/backup.sh` + cron line in `docs/BACKUP_AND_RECOVERY.md` (timer not installed).
- [x] Archive `uspbf_wp_data` (themes/uploads) alongside the dump
      ([WordPress backups guide](https://developer.wordpress.org/advanced-administration/security/backup/)).
      **Done 2026-06-09:** same script tars `wp-content` from `uspbf_wordpress_1`.
- [x] Document restore procedure (new volume + import) and test it once.
      **Done 2026-06-09:** restore steps in `docs/BACKUP_AND_RECOVERY.md` (operator test still pending).
- [ ] Ship copies off-host (e.g. hub hub share) — same pattern as other `apps` stacks.

## Phase 2 — Image/version hygiene (blocker #3, #4)

- [x] Pin `wordpress` to an explicit tag (e.g. `wordpress:6.9.1-php8.3-apache`) and
      `mysql` to `mysql:8.4` (LTS line). Rationale: **MySQL 8.0 is EOL since
      2026-04-21** ([Oracle EOL notice](https://www.mysql.com/support/eol-notice.html));
      the floating `mysql:8` tag currently resolves to 8.4 but is mutable
      ([docker-library/mysql tags](https://github.com/docker-library/docs/blob/master/mysql/README.md)).
      Upgrades become deliberate, reviewed bumps. *(Tag pinning only — no port,
      network, or binding changes; `tunnel_network` and `8089` stay as-is.)*
      **Done 2026-06-09:** `docker-compose.yml` → `wordpress:6.9.1-php8.3-apache`, `mysql:8.4`
      (live: WP 6.9.1, MySQL 8.4.8, PHP 8.3.30).
- [ ] Decide WordPress's fate: if the CMS is not on the near-term plan, stop the
      `wordpress`/`db` services (Compose profile or documented `up` subset) until
      needed. Single source of truth for the public site is the static
      `nginx-config/site/` — keep it that way.
- [ ] If WordPress stays running: complete install (don't leave the installer page
      reachable), set `DISALLOW_FILE_EDIT`, keep auto-updates on per
      [WordPress hardening guide](https://developer.wordpress.org/advanced-administration/security/hardening/).

## Phase 3 — Testing & CI

- [ ] CI job (GitHub Actions): `docker compose config` validation, `nginx -t` inside
      the built image, and an HTML/link checker over `nginx-config/site/`
      (catches broken internal links before a `--no-cache` rebuild ships them).
- [ ] Add a post-start smoke script (curl apex, `:8089` preview, `/health`,
      `/api/ai-narrative/demo-ask` reachability) mirroring
      `example_site-perch/scripts/verify-example_site-edge.sh`.

## Phase 4 — Monitoring & operations

- [ ] Add `example.com` (and `:8089` LAN preview) to the central `monitoring/` stack as
      blackbox_exporter HTTP probes with an alert rule; container-state alerts via the
      existing cAdvisor/node-exporter setup on `apps`.
- [ ] Document the restart path: Compose only (`./start.sh`), plus
      `/home/ansible/scripts/restore-docker-networks.sh` after host reboots (README).

## Phase 5 — AI demo compliance & abuse protection

- [ ] The homepage ALFa AI demo posts to `rankings-bot-api` `/api/ai-narrative/demo-ask`
      with a server-side injected `BOT_API_KEY` (good — key never reaches browsers).
      **Verify** the rankings-bot side routes through the LiteLLM brain on `hub`
      (`http://192.0.2.30:8413`) per workspace standard
      (`engineering-standards-and-drift-control.mdc` §3) rather than a direct Ollama
      path, and that the demo uses a public-appropriate alias/trust zone.
- [ ] Add nginx `limit_req` rate limiting on the public `/api/` demo route
      ([nginx limit_req docs](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html))
      so the public demo cannot exhaust the bot API.

## Phase 6 — Audit pass

- [ ] Run the two-stage research + audit subagent workflow already planned in
      [`NEXT_STEPS.md`](NEXT_STEPS.md) (outputs to `docs/audit/`), then fold Critical
      findings back into this roadmap.

## Official-docs findings (2026-06)

| Component | Finding | Action |
|---|---|---|
| MySQL | 8.0 EOL 2026-04-21; 8.4 is LTS. Running 8.4.8 via mutable `mysql:8` tag. | Pin `mysql:8.4` (Phase 2) |
| WordPress image | `latest` drifts (6.9.1 here vs 7.0 on example_site). Official guidance: pin specific `X.Y.Z-phpX.Y-variant` tags in production. | Pin tag (Phase 2) |
| cloudflared | Already pinned `2026.3.0` in start script. Track Cloudflare release cadence; bump deliberately. | Periodic review |
| nginx | Maintenance/production switch is config-copy + reload (no rebuild) — sound. | Keep |
