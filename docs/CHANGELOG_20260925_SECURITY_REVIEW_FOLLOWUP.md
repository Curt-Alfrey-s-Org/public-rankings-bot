# Changelog 2026-09-25 (follow-up): remaining Medium/Low review items + PR #21 leftovers

Follows [CHANGELOG_20260925_SECURITY_REVIEW_FIXES.md](CHANGELOG_20260925_SECURITY_REVIEW_FIXES.md)
(PR #21: env-only bootstrap users, server-side must_change_password, env files untracked,
API-key middleware registered). Nothing from PR #21 is reverted.

## Security / correctness

- **Spoofable client IP (MEDIUM).** Login/rankings rate limits (`api/rate_limiter.py`), the
  public AI demo limits (`api/routes/ai_narrative.py`) and the login lockout / honeypot IP
  block / registration cooldown (`api/routes/auth.py`) used the *first* `X-Forwarded-For`
  value, which clients control. They now use the proxy-resolved `request.client.host`
  (`api/client_ip.py`). `scripts/docker-api-cmd.sh` runs Uvicorn with `--proxy-headers
  --forwarded-allow-ips "$FORWARDED_ALLOW_IPS"` (default: loopback + private ranges, i.e. the
  nginx containers). Uvicorn honours the header only from a trusted peer and takes the
  right-most untrusted hop. `AI_NARRATIVE_TRUST_FORWARDED_FOR` is obsolete. `requirements-api.txt`
  now needs `uvicorn[standard]>=0.31.1` (CIDR support in `--forwarded-allow-ips`).
- **Unbounded in-memory rate limiter (MEDIUM).** Stale keys are swept every minute and the
  store is capped (`RATE_LIMIT_MAX_KEYS`, default 50000, LRU eviction). Limits are still per
  Uvicorn worker (see Deferred).
- **Predict route / models (MEDIUM).** `Dockerfile` now copies `models/` into the image, and
  `requirements-deps.txt` declares `scikit-learn>=1.8,<1.9`. The committed `models/*.pkl` files
  are scikit-learn LogisticRegression pickles saved with scikit-learn 1.8.0.
- **Prod SUPER_ADMIN_PASSWORD / self-test (MEDIUM).** Already fixed by PR #21 (startup aborts in
  production; the self-test reports the real result). No change here.
- **Empty `X-User-Role` (from the USPBF fix).** PR #21 already rejects a missing/empty role
  header. The two remaining per-path exemptions (`POST /api/ai-narrative/demo-ask`,
  `/api/test-tournaments/*`) are removed, so every anonymous non-public request needs the API
  key **and** `X-User-Role: user|admin`. The USPBF proxy (USPBF PR #1) always sends
  `X-User-Role: user`. The public GET list is unchanged.
- **`POST /api/media/scrape`** now requires an admin/super_admin JWT (`require_admin`).
- **`force_password_reset`** (set by `/api/auth/setup-email` for Pro/Fargo accounts) is enforced
  server-side the same way as `must_change_password`. Login issues the restricted
  `pwd_change_required` token and `password_change_pending()` checks both flags.
  `POST /api/users/change-password` clears both. The web app already shows the password gate
  for either flag.
- **Hardcoded DB password in scripts.** `scripts/fix_super_admin.py` and
  `scripts/reset_super_admin_password.py` read `DATABASE_URL` from the environment and exit
  immediately when it is unset. The hardcoded host path is gone, and `fix_super_admin.py` no
  longer prints the new password.
- **Staging compose secrets.** `docker-compose-staging.yml`: Postgres password is
  `${STAGING_POSTGRES_PASSWORD:?}` (also used in the staging `DATABASE_URL`). Grafana admin
  password is `${GRAFANA_ADMIN_PASSWORD:?}`. Neither has a default.

## Infra (LOW)

- `production/docker-compose.prod.yml`: `postgres` and the password-less `redis` are only on the
  internal `rankings-bot-network` (removed from the shared `tunnel_network`). `celery-worker`
  joined `rankings-bot-network` so it can still reach them. `scripts/start.sh` creates
  `rankings-bot-network` if it is missing.
- The API port is published as `${API_BIND_ADDR:-127.0.0.1}:8003:8003` instead of all
  interfaces. nginx reaches the API over Docker DNS, and host scripts use `127.0.0.1:8003`.
- `config/super_admin.json` (unused, contained a bcrypt hash) is removed from git and ignored.
- `android/app/debug.keystore` is removed from git (`*.keystore` ignored). Release builds are no
  longer signed with the debug key. They use an upload keystore from
  `RANKINGSBOT_UPLOAD_*` Gradle properties, or stay unsigned.

## Operator actions (next deploy)

1. **Rebuild the base image and the app image** (new pip deps, and `models/` is copied in):
   `docker build -f Dockerfile.base -t rankings-bot-base:local .` (or the bake target), then
   rebuild `rankings-bot-api` / `celery-worker`.
2. **Recreate the stack** so the network and port changes apply:
   `cd production && docker compose -f docker-compose.prod.yml up -d --force-recreate`.
   Check that `docker port rankings-bot-api` shows `127.0.0.1:8003` and that the site still
   works through nginx. If a proxy on *another host* used `<host>:8003`, set `API_BIND_ADDR=0.0.0.0`
   (and firewall it) or point that proxy at the Docker network.
3. **Trusted proxies:** the default `FORWARDED_ALLOW_IPS` trusts loopback + RFC1918 ranges.
   Narrowing it to the `tunnel_network` / `rankings-bot-network` subnets is recommended
   (`docker network inspect tunnel_network -f '{{(index .IPAM.Config 0).Subnet}}'`). After
   deploy, confirm login audit rows / 429s show real client IPs, not the nginx container IP.
4. **Staging:** set `STAGING_POSTGRES_PASSWORD` (URL-safe characters) and `GRAFANA_ADMIN_PASSWORD`
   in the staging env before `docker compose -f docker-compose-staging.yml up`. On an existing
   staging volume the Postgres password does not change automatically: run
   `ALTER USER rankings PASSWORD '...'` inside the container, then restart the API. Grafana only
   applies the variable on a fresh volume, so change an existing password in the Grafana UI.
5. **Rotate credentials that were committed** (they stay in git history): the Postgres password
   that was hardcoded in `scripts/fix_super_admin.py` / `scripts/reset_super_admin_password.py`
   (`rankings_user` role, if that role/password is still used anywhere), the staging Postgres
   password and the Grafana admin password that were defaults in `docker-compose-staging.yml`,
   and the super admin password whose bcrypt hash was in `config/super_admin.json` (if it is
   still in use).
6. **Maintenance scripts** now need `DATABASE_URL` and `SUPER_ADMIN_PASSWORD` exported.
7. **Android developers:** create a local debug keystore before `run-android`, e.g. copy
   `~/.android/debug.keystore` (Android Studio creates it) to `android/app/debug.keystore`, or
   generate one with `keytool -genkeypair -v -keystore android/app/debug.keystore -alias
   androiddebugkey -keyalg RSA -keysize 2048 -validity 10000` using the store/key passwords from
   `signingConfigs.debug` in `android/app/build.gradle`. For releases, put
   `RANKINGSBOT_UPLOAD_STORE_FILE/STORE_PASSWORD/KEY_ALIAS/KEY_PASSWORD` in
   `~/.gradle/gradle.properties` (never commit them).

## Deferred

- Rate limits remain in-memory **per Uvicorn worker** (effective limit is up to workers x limit).
  A shared Redis-backed limiter for login/rankings is a larger change; the AI demo already uses
  Redis when `REDIS_URL` is set.
- Redis still has no password (mitigated by moving it to the internal network). Adding
  `requirepass` needs coordinated `REDIS_URL` changes in `.env`.

## Tests

- New: `tests/backend/test_review_followup_20260925.py` covering client IP (raw XFF ignored, Uvicorn
  right-most-untrusted resolution with the default trusted ranges), bounded rate limiter,
  `force_password_reset` enforcement, admin-only media scrape, and scripts failing fast
  without `DATABASE_URL`.
- Updated: `tests/backend/test_api_access_control.py` (demo-ask / test-center need a role header).
