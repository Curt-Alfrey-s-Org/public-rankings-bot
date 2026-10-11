# Faster Update / Response Times

## What’s in place

- **Cache-Control for rankings and Fargo**  
  GET `/api/rankings` and GET `/api/fargo` responses include `Cache-Control: public, max-age=60`. Browsers and CDNs can cache for 60 seconds, so repeat loads are faster.

- **Client-side**  
  The frontend already uses React Query with `staleTime` (e.g. 5 minutes) so refetches are throttled. Rankings last-update refetches every 30 seconds.

## Speed tests and bottlenecks

### Request timing (optional)

Set **`PERF_LOG_SLOW_MS`** (e.g. `300`) to enable request timing middleware:

- Every response gets an **`X-Response-Time`** header (e.g. `X-Response-Time: 45.2ms`).
- Any request that takes **≥ PERF_LOG_SLOW_MS** is logged at WARNING with method, path, and duration.

Example:

```bash
export PERF_LOG_SLOW_MS=300
# start API; then check logs for [PERF] Slow request ...
```

Use this to see which endpoints are slow in production or staging without changing app behavior.

### Speed test script

From the project root (with the API running):

```bash
# Default: 5 runs per endpoint, base URL http://127.0.0.1:8000
python scripts/speed_test.py

# Custom base URL and runs
python scripts/speed_test.py --base-url http://localhost:8000 --runs 10

# Also time in-process DB calls (get_all_rankings_from_db, get_movement)
# Requires DATABASE_URL and running from project root
python scripts/speed_test.py --db

# Flag endpoints whose median exceeds 500ms (default)
python scripts/speed_test.py --slow-ms 300
```

The script hits: `/api/health`, `/api/rankings`, `/api/rankings/wpba-women`, `/api/rankings/movement`, `/api/rankings/last-update`, `/api/rankings/types`, `/api/fargo/org/WPBA`. It prints **min / median / avg / p95** per endpoint and marks **\[SLOW]** when median ≥ `--slow-ms`. Use the output to find bottlenecks (e.g. DB-heavy endpoints) and then optimize those (indexes, caching, async).

## Optional improvements

- **CDN**  
  Put a CDN (e.g. Cloudflare) in front of the API and cache GET `/api/rankings` and `/api/fargo` with a short TTL (e.g. 60s) for faster global response.

- **Server-side cache**  
  Add Redis or in-memory cache for `get_all_rankings_from_db()` and Fargo org endpoints if DB latency is high; invalidate on refresh/import.

- **Async / background**  
  Keep heavy work (Fargo sync, rankings refresh) as background jobs or cron; API stays responsive.

- **Target**  
  Aim for &lt; 100 ms for cached reads so the app feels instant.
