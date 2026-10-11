# Deploy Script Refactoring: Arbitrary Timeouts → Actual Health Checks

## Overview

The `scripts/full_deploy.sh` has been refactored to eliminate arbitrary timeout values and replace them with actual health checks. This improves reliability and deployment speed.

**Key Insight:** "Why wait X seconds when you can wait until the service is actually healthy?"

## What Changed

### Before (Timeout-Based)
```bash
# Guess: wait 180 seconds for API to start
timeout 180 docker-compose up -d
if [ $? -eq 124 ]; then 
  echo "Timed out!"
fi
```

### After (Health-Check Based)
```bash
# Start containers
docker-compose up -d

# Wait for actual health status
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  if docker inspect rankings-bot-api --format '{{.State.Health.Status}}' | grep -q healthy; then
    echo "API healthy (attempt $i/20)"
    break
  fi
  sleep 2
  [ "$i" -eq 20 ] && { echo "API not healthy after 40s"; exit 1; }
done
```

## Services Refactored

| Service | Old Approach | New Approach | Max Wait |
|---------|--------------|--------------|----------|
| PostgreSQL | `sleep 10` | `pg_isready` loop (10 retries) | 20s |
| App Containers | `timeout 180` | `docker inspect health` loop (20 retries) | 40s |
| API Health (Post-Startup) | `sleep 5` + single curl | `wait_for_http_health` (curl until HTTP 200, 2s interval) | 90s |
| Nginx Build | `timeout 600` | No timeout (docker build completes when done) | N/A |
| Nginx Startup | `timeout 120` | `docker inspect health` loop (15 retries) | 30s |
| Nginx Rebuild (full_deploy Part B) | `timeout 120` | `docker inspect health` loop (15 retries) | 30s |
| Final API Verification | Single curl + sleep | `wait_for_http_health` on `127.0.0.1:$API_PORT/api/health` then hash check | 90s |

## Health Check Patterns

### 1. PostgreSQL Readiness (10 retries, 20s max)
```bash
for i in 1 2 3 4 5 6 7 8 9 10; do
  if $DOCKER exec rankings-bot-postgres pg_isready -U ${POSTGRES_USER:-rankingsbot_user} -d ${POSTGRES_DB:-rankingsbot} &>/dev/null 2>&1; then
    log "✅ Postgres and Redis ready."
    break
  fi
  sleep 2
  [ "$i" -eq 10 ] && { err "Postgres did not become ready."; exit 1; }
done
```

### 2. Docker Health Status (20 retries, 40s max)
```bash
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  HEALTH=$(docker inspect rankings-bot-api --format '{{.State.Health.Status}}' 2>/dev/null || echo "")
  if [ "$HEALTH" = "healthy" ]; then
    log "✅ API healthy (attempt $i/20)"
    break
  fi
  sleep 2
  [ "$i" -eq 20 ] && { err "API not healthy after 40s"; exit 1; }
done
```

### 3. HTTP Health Check (15 retries, 30s max)
```bash
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 3 "http://127.0.0.1:8003/api/health" 2>/dev/null || echo "000")
  if [ "$CODE" = "200" ]; then
    log "✅ API responding (attempt $i/15)"
    break
  fi
  sleep 2
  [ "$i" -eq 15 ] && { err "API not responding after 30s (last code: $CODE)"; exit 1; }
done
```

## Advantages

1. **Reliability**: Services are verified actually healthy, not assumed healthy after X seconds
2. **Speed**: No artificial delays; completes as fast as the system allows
3. **Clarity**: Each attempt is logged, making it clear what's being waited for
4. **Debuggability**: Failed health checks show the actual problem (connection refused, timeout, HTTP 503, etc.)
5. **Consistency**: Same pattern used across all services makes code easier to understand

## Trade-offs

| Aspect | Timeout Approach | Health Check Approach |
|--------|------------------|----------------------|
| Max Wait | Fixed | Fixed (via retry limit) |
| Completion Time | Always full timeout | Early exit when healthy |
| Failure Diagnosis | "Timed out" | Actual cause (connection error, 503, etc.) |
| Code Complexity | Simpler | Slightly more complex loops |
| System Variability Handling | Poor (assumes worst case) | Good (waits for actual readiness) |

## Build Timeouts Retained

The `BUILD_TIMEOUT=900` (15 minutes) for npm/docker builds is **retained** because:
- Build processes can legitimately hang (network failures, package lock conflicts)
- We don't have a meaningful way to monitor build progress without parsing logs
- 15 minutes is reasonable for package-heavy builds on slow connections
- This is different from service startup (build is one-shot, not recurring)

## Testing the Refactored Script

To test the new health-check approach:

```bash
# Full deploy from scratch
./scripts/full_deploy.sh --force-docker --no-cache

# Watch the output for new health check messages:
# ✅ Postgres ready (attempt 3/10)
# ✅ API healthy (attempt 8/20)
# ✅ Nginx healthy (attempt 5/15)
# ✅ API responding (attempt 2/15)
```

Expected behavior:
- Services come online faster (no artificial N-second waits)
- Each health check iteration is shown with `(attempt X/N)`
- Failures show clear reasons (connection refused, 503, etc.) not just "timed out"

## Removed Variables

These variables are no longer defined or used:
- `UP_TIMEOUT` (was 180)
- `NGINX_BUILD_TIMEOUT` (was 600)
- `NGINX_UP_TIMEOUT` (was 120)

If scripts reference these, they will need to use the health check loops instead.

## Commit Reference

See commit `878753e` for the complete refactoring:
```bash
git show 878753e
```

## Future Improvements

1. **Celery Worker Health**: Currently reports "unhealthy"; needs proper health check
2. **Build Progress Monitoring**: Parse docker build logs to show progress vs arbitrary timeout
3. **Metrics**: Track actual wait times to inform future timeout values
4. **Exponential Backoff**: Use increasing sleep delays between retries instead of fixed 2s
