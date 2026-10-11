# Live Updates System - Testing Guide

## Quick Start Test (2 minutes)

### 1. Verify Backend is Running
```bash
curl http://127.0.0.1:8003/api/live/status
# Expected: {"status":"active","connected_clients":0}
```

### 2. Connect SSE Client (Terminal 1)
```bash
# Opens SSE stream - will show events as they arrive
curl -N http://127.0.0.1:8003/api/live/updates
```

### 3. Trigger Scraper Job (Terminal 2)
```bash
# SSH into the server
cd /home/ansible/rankings-bot/Rankings-Bot

# Run one scraper job manually to trigger event
python3 -c "
from api.services.background_scheduler import _job_wpba_rankings_refresh
_job_wpba_rankings_refresh()
"
```

### Expected Results

**Terminal 1 should now show:**
```
data: {"scraper_type":"rankings_wpba","status":"success","timestamp":"2026-02-18T21:30:00Z","message":"WPBA Women rankings updated","rows_updated":150,"duration_s":45.2,"error":""}

data: {"scraper_type":"rankings_wpba","status":"success",...}
```

**Terminal 2 logs should show:**
```
INFO: WPBA Women rankings refresh completed
INFO: Event published to N connected clients
```

---

## Frontend Integration Test (Browser)

### 1. Open Developer Tools
```
F12 → Console tab
```

### 2. Visit Rankings Page
```
Navigate to http://localhost:5173/rankings (or production URL)
```

### 3. Open Network Tab
```
F12 → Network tab
```

### 4. Filter for EventSource
```
Type in address bar: /api/live/updates
```

### 5. Verify Connection
- You should see a line with `/api/live/updates` 
- Status: `101 Switching Protocols` (SSE handshake)
- Type: `fetch` (with EventSource as initiator)

### 6. Check Console Logs
```
[LIVE-UPDATES] Connected to live updates
```

### 7. Manually Trigger Scraper (from server)
```bash
# Run scraper job that affects rankings
python3 -c "from api.services.background_scheduler import _job_wpba_rankings_refresh; _job_wpba_rankings_refresh()"
```

### 8. Watch Frontend

**Expected behavior:**
- Console logs: `[LIVE-UPDATES] Received: rankings_wpba success`
- Banner appears in bottom-right: "✓ RANKINGS WPBA - Updated 150 records..."
- Rankings data refreshes automatically
- Banner auto-hides after 4 seconds

---

## Integration Test (All Components)

### Setup
1. Terminal 1: SSH to server
2. Terminal 2: Open browser DevTools console
3. Terminal 3: Keep for test commands

### Test Sequence

#### Step 1: Verify Connected Clients
```bash
# Terminal 3
curl http://127.0.0.1:8003/api/live/status
# Should show connected_clients: 1 (from your browser)
```

#### Step 2: Trigger Multiple Scrapers
```bash
# Terminal 3 - run each with 5-second delay
python3 << 'EOF'
from api.services.background_scheduler import (
    _job_wpba_rankings_refresh,
    _job_wpa_women_rankings_refresh,
    _job_tournament_refresh
)
from time import sleep

# Stagger them to see multiple notifications
_job_wpba_rankings_refresh()
print("WPBA job complete, waiting...")
sleep(5)

_job_wpa_women_rankings_refresh()
print("WPA Women job complete, waiting...")
sleep(5)

_job_tournament_refresh()
print("Tournament job complete")
EOF
```

#### Step 3: Observe in Browser

Terminal 2 console should show:
```javascript
[LIVE-UPDATES] Received: rankings_wpba success
[LIVE-UPDATES] Received: rankings_wpa_women success
[LIVE-UPDATES] Received: tournament success
```

Browser should show 3 banners (one after each job):
1. "✓ RANKINGS WPBA - Updated XXX records..."
2. "✓ RANKINGS WPA WOMEN - Updated XXX records..."
3. "✓ TOURNAMENT - Updated XXX records..."

Each banner appears for 4 seconds then auto-hides.

---

## Stress Test (10+ Clients)

### 1. Open Browser in Multiple Windows
```
Open 5+ browser tabs pointing to http://localhost:5173/rankings
```

### 2. Check Connected Clients
```bash
curl http://127.0.0.1:8003/api/live/status
# Should show connected_clients: 5+ (one per tab)
```

### 3. Trigger Scraper
```bash
python3 -c "from api.services.background_scheduler import _job_wpba_rankings_refresh; _job_wpba_rankings_refresh()"
```

### 4. Expected Results
- All 5+ tabs receive notification simultaneously
- No lag or timeout errors
- Status shows: `connected_clients: 5` during stream

---

## Error Scenario Tests

### Scenario 1: Scraper Job Fails
```bash
python3 << 'EOF'
# Force an error in a scraper
from api.services.live_updates import publish_scraper_event

publish_scraper_event(
    scraper_type="rankings_wpba",
    status="failed",
    duration_s=2.5,
    error="Database connection timeout"
)
EOF
```

Expected: Banner appears with red "✗ RANKINGS WPBA" and error message

### Scenario 2: Network Disconnection
```javascript
// In browser console
// Simulate network drop
console.log("Closing SSE connection...")
// Manually close Network tab SSE connection
```

Expected:
- Console: `[LIVE-UPDATES] Connection error, attempting reconnect...`
- Auto-reconnect after 2 seconds
- Console: `[LIVE-UPDATES] Connected to live updates` (after reconnect)

### Scenario 3: Server Restart
```bash
sudo systemctl restart rankings-bot-api.service
```

Expected:
- SSE connection drops
- Auto-reconnect logic kicks in
- Reconnects within 30 seconds
- No data lost (previous events weren't critical)

---

## Performance Test

### Test 1: Event Throughput
```bash
# Trigger 10 events rapidly
python3 << 'EOF'
from api.services.live_updates import publish_scraper_event
import time

for i in range(10):
    publish_scraper_event(
        scraper_type="test",
        status="success",
        duration_s=1.0,
        rows_updated=100+i
    )
    time.sleep(0.1)  # 100ms between events

print("10 events sent")
EOF
```

Expected: All 10 notifications arrive at frontend without loss

### Test 2: Memory Usage
Monitor memory during prolonged connection:
```bash
watch -n 1 'ps aux | grep uvicorn | grep -v grep'
```

Expected: Memory stays stable (no leaks) even after hours of events

---

## Real Scraper Schedule Test

Monitor real hourly schedule:

### Setup Monitoring
```bash
# Terminal 1: Watch API logs
sudo journalctl -u rankings-bot-api.service -f --grep "Received:"

# Terminal 2: Check status periodically
watch -n 60 'curl -s http://127.0.0.1:8003/api/live/status'

# Browser: Keep Rankings page open with console visible
```

### Wait for Next Scraper Run

- 13:00 - WPBA Women rankings runs
- 13:15 - WPA Women rankings runs
- 13:30 - WPA Men rankings runs
- 13:45 - WPA Artistic rankings runs

### Expected During Next Run
- API logs show event published
- Status shows `connected_clients: 1+`
- Browser shows banner and refreshes data
- Console shows: `[LIVE-UPDATES] Received: rankings_wpba success`

---

## Verification Checklist

- [ ] Backend endpoint responds: `curl /api/live/status` → 200 OK
- [ ] SSE connection successful: `curl /api/live/updates` → 101 Switching Protocols
- [ ] Frontend hook connects: Console shows `[LIVE-UPDATES] Connected...`
- [ ] Scraper triggers event: Event JSON appears in browser console
- [ ] Banner appears: Green notification in bottom-right corner
- [ ] Data refreshes: Rankings table updates with new data
- [ ] Auto-hides: Banner disappears after 4 seconds
- [ ] Multiple clients: 5+ tabs all receive event simultaneously
- [ ] Reconnection works: Network drop → auto-reconnect in <30s
- [ ] Performance stable: Memory usage doesn't increase with events

---

## Debugging Tips

### Enable Verbose Logging

**Backend:**
```bash
# Restart API with debug logging
DEBUG=1 sudo systemctl restart rankings-bot-api.service
```

**Frontend:**
```javascript
// In browser console
// Already logging with [LIVE-UPDATES] prefix
// Check local storage for any cached events
console.log(localStorage)
```

### Monitor Event Flow

**Terminal (watch for events):**
```bash
curl -N http://127.0.0.1:8003/api/live/updates | tee /tmp/sse_log.txt
```

Check what events actually arrived:
```bash
grep "scraper_type" /tmp/sse_log.txt
```

### Check Scheduler Jobs

```bash
cd /home/ansible/rankings-bot/Rankings-Bot

# List all scheduled jobs
python3 << 'EOF'
from api.services.background_scheduler import scheduler
import pytz

for job in scheduler.get_jobs():
    print(f"Job: {job.name}")
    print(f"  Next run: {job.next_run_time}")
    print(f"  Function: {job.func}")
    print()
EOF
```

---

## Success Criteria

✅ **All tests pass when:**
1. Fresh browser tab → SSE connects automatically
2. Scraper job runs → Event published within 100ms
3. Event received → Frontend banner appears within 500ms
4. Data refreshes → React Query cache invalidated
5. Multiple clients → All receive event simultaneously
6. Network drop → Auto-reconnect within 30 seconds
7. Server restart → Reconnects automatically
8. Performance → <1% CPU, stable memory, <1s event latency

---

## Next Steps After Testing

1. ✅ **Done:** Backend implementation verified
2. 🔄 **Next:** Wait for next scraper schedule (hourly) to verify real-world
3. 📊 **Monitor:** Check logs during business hours for any issues
4. 🎨 **Enhance:** Add status indicator to sidebar menu
5. 📱 **Extend:** Add live updates to other pages (Fargo, tournaments)

