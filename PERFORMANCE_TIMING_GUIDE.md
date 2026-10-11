# Performance Timing and Bottleneck Analysis Guide

## Overview

All key processes now have timestamps and timing information to help identify performance bottlenecks. Check the logs to measure execution times.

## Log Format

### Request Timing
```
[PERF] 2026-02-17T17:35:42.123Z [OK] GET /api/rankings → 200 | 156.3ms
[PERF] 2026-02-17T17:35:43.456Z [SLOW] POST /api/predict → 200 | 5234.1ms
```

- `[OK]` = Request completed normally (< 5000ms)
- `[SLOW]` = Request exceeded threshold (default 5000ms)
- `[ERROR]` = HTTP error response (4xx, 5xx)
- Last number = total request duration in milliseconds

### Cache Operations
```
[CACHE] 2026-02-17T17:35:42.123Z [GET HIT] Redis rankings_wpba: 2.3ms
[CACHE] 2026-02-17T17:35:42.124Z [GET MISS] Redis rankings_wpba: 1.1ms
[CACHE] 2026-02-17T17:35:42.125Z [GET STALE] Redis rankings_wpba: 1.2ms
[CACHE] 2026-02-17T17:35:42.126Z [SET] Redis rankings_wpba: 15.4ms
```

- `[GET HIT]` = Cache hit (data fresh)
- `[GET STALE]` = Cache hit (data stale, refresh triggered)
- `[GET MISS]` = Cache miss (data fetched from source)
- `[SET]` = Data written to cache
- Duration in milliseconds

### Startup/Shutdown
```
[STARTUP] 2026-02-17T17:35:42.000Z API startup began
[STARTUP] Database tables created/verified
[STARTUP] Rankings refresh completed in 2345ms
[STARTUP] 2026-02-17T17:35:47.123Z Background startup completed

[SHUTDOWN] 2026-02-17T17:40:00.000Z API shutdown began
[SHUTDOWN] Background scheduler stopped
[SHUTDOWN] 2026-02-17T17:40:01.234Z API shutdown completed
```

## Configuration

### Enable Performance Logging

Set environment variable before starting API:
```bash
export PERF_LOG_SLOW_MS=1000  # Log requests over 1 second
```

Default: 5000ms (only requests over 5 seconds logged)

### View Logs

**All logs (INFO level minimum):**
```bash
tail -f /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log
```

**Just performance logs:**
```bash
grep "\[PERF\]" /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log
grep "\[CACHE\]" /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log
grep "\[STARTUP\]\|\[SHUTDOWN\]" /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log
```

**Real-time monitoring:**
```bash
tail -f /home/ansible/rankings-bot/Rankings-Bot/rankings_bot.log | grep "\[PERF\]"
```

## Finding Bottlenecks

### 1. Slow HTTP Requests
**Look for:** `[SLOW]` entries with high millisecond values

**Example:**
```
[PERF] 2026-02-17T17:35:42.123Z [SLOW] GET /api/rankings/wpba → 200 | 4523.2ms
```

**Next steps:**
1. Note the endpoint and time
2. Look for corresponding cache operations around that timestamp
3. If cache MISS appears before slow request → database query is slow
4. If cache HIT appears → something else is slow (serialization, network, etc)

### 2. Cache Performance
**Look for:** Multiple `[GET MISS]` for same key

**Example pattern (problematic):**
```
[CACHE] 2026-02-17T17:35:42.100Z [GET MISS] Redis rankings_wpba: 1.1ms
[CACHE] 2026-02-17T17:35:42.200Z [GET MISS] Redis rankings_wpba: 1.2ms
[CACHE] 2026-02-17T17:35:42.300Z [GET MISS] Redis rankings_wpba: 1.1ms
```

**Indicates:** Cache not being set or expiring too quickly

**Fix:** Check cache TTL configuration or if data is being invalidated

### 3. Startup Performance
**Look for:** Startup phase duration

**Example:**
```
[STARTUP] 2026-02-17T17:35:42.000Z API startup began
[STARTUP] 2026-02-17T17:35:52.345Z Background startup completed
```

**Duration:** ~10 seconds total startup time

**If slow (> 30s):**
1. Check database queries during startup
2. Check if FairMatch scraper is running
3. Check if cache warmup is slow
4. Review logs for `[PERF]` entries during that window

### 4. Request Performance Breakdown
**Scenario:** GET /api/rankings/wpba takes 4523ms

**Analysis:**

1. Check cache logs around that timestamp
   - If `MISS`: Data not cached
   - If `STALE`: Refresh happened in background
   - If `HIT`: Request serialization/network is slow

2. If MISS:
   - Database query likely slow
   - Check if indexes exist on `rankings` and `players` tables
   - Example query: `SELECT ... FROM rankings WHERE ranking_system = 'WPBA_Women'`

3. If HIT:
   - Check request response time header: `X-Response-Time`
   - If header shows 150ms but log shows 4500ms → network/client-side issue
   - If header shows 4500ms → caching worked but query was slow

## Performance Targets

### Optimal Performance
| Operation | Target |
|-----------|--------|
| API startup | < 15s |
| GET /api/rankings | 100-300ms (fresh) |
| GET /api/rankings (cached) | < 50ms |
| Cache HIT | < 5ms |
| Cache MISS (DB query) | < 2s |
| Database insert/update | < 1s |

### Warning Signs
| Condition | Threshold | Action |
|-----------|-----------|--------|
| Request > 5s | SLOW logged | Investigate caching/query |
| Startup > 30s | Logged | Check background tasks |
| Cache MISS rate > 20% | Repeated MISSes | Check TTL settings |
| Response time variation > 2x | Same endpoint | Check database load |

## Debugging Example

**Problem:** GET /api/rankings/wpba sometimes slow (2-5s), sometimes fast (150ms)

**Step 1: Monitor logs**
```bash
tail -f rankings_bot.log | grep "/rankings/wpba"
```

**Step 2: Collect data**
```
Fast request (150ms):
[PERF] 2026-02-17T17:35:42.123Z [OK] GET /api/rankings/wpba → 200 | 156.3ms
[CACHE] 2026-02-17T17:35:42.100Z [GET HIT] Redis rankings_wpba: 2.3ms

Slow request (4523ms):
[PERF] 2026-02-17T17:35:55.234Z [SLOW] GET /api/rankings/wpba → 200 | 4523.1ms
[CACHE] 2026-02-17T17:35:55.200Z [GET MISS] Redis rankings_wpba: 1.1ms
```

**Step 3: Analysis**
- Fast = cache HIT (served from Redis)
- Slow = cache MISS (database query executed)
- **Conclusion:** Database query variable, not cache TTL issue

**Step 4: Fix**
- Check if FairMatch API is slow when rankings are stale
- Check database query performance with slow query log
- Consider increasing cache TTL or warming cache earlier

## Performance Utilities

### Adding Timing to New Code

**Using context manager:**
```python
from api.utils.performance import timed

with timed("My operation"):
    # Do something
    pass
```

Logs: `[PERF] 2026-02-17T17:35:42.123Z [OK] My operation: 125.4ms`

**Using decorator:**
```python
from api.utils.performance import timing_decorator

@timing_decorator("Database query operation")
def my_slow_function():
    # Do something
    pass
```

**Manual timing:**
```python
from api.utils.performance import get_timestamp, log_checkpoint
import time

start = time.perf_counter()
# Do work
log_checkpoint("My step", (time.perf_counter() - start) * 1000)
```

## Key Monitoring Commands

```bash
# Real-time slow requests only
tail -f rankings_bot.log | grep "SLOW"

# Cache hit/miss ratio
grep "CACHE.*\[GET" rankings_bot.log | sort | uniq -c | sort -rn

# Startup time
grep "\[STARTUP\]" rankings_bot.log | head -5 && grep "\[STARTUP\]" rankings_bot.log | tail -5

# Slowest 10 requests
grep "\[PERF\].*\[.*\] GET\|POST" rankings_bot.log | sort -t'|' -k2 -rn | head -10

# Find requests over 3 seconds
grep "\[PERF\]" rankings_bot.log | awk -F'|' '$2 > 3000'
```

## Timestamp Format

All timestamps are UTC ISO 8601 with millisecond precision:
```
2026-02-17T17:35:42.123Z
 └─year──mo─dy─hr─mn─sc─ms
```

This allows:
- Easy chronological sorting
- Direct correlation between log entries
- Precise performance measurement within milliseconds
