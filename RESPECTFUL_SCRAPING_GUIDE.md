# Respectful Web Scraping Setup

**Goal:** Scrape wpapool.com and other sites responsibly without getting banned.

## Changes Made

### 1. **Increased Rate Limit: 2s → 10s**
- **File:** `scrapers/tournament_scraper_improved.py`
- **Change:** `RATE_LIMIT_DELAY = 10.0` (was 2.0)
- **Effect:** Waits 10 seconds between requests instead of 2
- **Why:** Prevents traffic spikes and looks more like human usage

### 2. **Added Rotating Proxy Support**
- **File:** `scrapers/proxy_rotator.py` (NEW)
- **Features:**
  - Rotate through multiple proxy IPs
  - Support for paid and free proxies
  - Easy enable/disable
- **Usage:**
  ```python
  from scrapers.proxy_rotator import ProxyRotator
  rotator = ProxyRotator(proxy_list=['http://proxy1:port', 'http://proxy2:port'])
  proxies = rotator.get_next_proxy()
  ```

### 3. **Staggered Scraper Schedule**
- **File:** `scripts/scraper_scheduler.py` (NEW)
- **Schedule:**
  - 02:00 - WPBA Rankings (niche, less frequent)
  - 06:30 - WPA Rankings (main scraper)
  - 11:00 - Tournament History (core data, 10s delay)
  - 15:30 - Fargo Ratings (supplementary)
  - 20:00 - Heyball/Artistic (niche)

- **Why:** Distributes requests 4-6 hours apart to avoid patterns

---

## Quick Setup

### Option A: Use Only Rate Limiting (Recommended for now)
**Safest approach - no external proxy needed**

```bash
# Already done - just use the increased 10s delay
cd /home/ansible/rankings-bot
python3 -m scrapers.tournament_scraper_improved --rate-limit 10
```

### Option B: Add Rotating Proxies
**For extra protection - requires paid proxy service**

#### Step 1: Choose Proxy Service

**Best Options:**
1. **Smartproxy** ($29/month) - Affordable, good uptime
2. **ProxyMesh** ($99/month) - Reliable residential
3. **Phone Hotspot** (FREE!) - Rotate via mobile connection
   - Just toggle hotspot on/off between scrape runs
   - Each connection gets new IP
   - Legitimate and free

#### Step 2: Configure Proxies

**Method 1: Environment Variable**
```bash
export SCRAPER_PROXIES="http://user:pass@proxy1.com:8080,http://user:pass@proxy2.com:8080"
```

**Method 2: Create proxies.json**
```json
{
  "proxies": [
    "http://user:pass@proxy1.com:8080",
    "http://user:pass@proxy2.com:8080",
    "http://user:pass@proxy3.com:8080"
  ]
}
```

#### Step 3: Enable in Scraper
```python
# In tournament_scraper_improved.py
USE_ROTATING_PROXY = True  # Set to True
```

### Option C: Install Cron Schedule
**Automate scraping at staggered times**

```bash
# Show the schedule
python3 scripts/scraper_scheduler.py show

# Install into crontab
python3 scripts/scraper_scheduler.py install

# Then run the install command it suggests
crontab /tmp/scraper_crontab.txt

# Verify installation
crontab -l
```

---

## Testing Before Full Deployment

### 1. Test with 10s Delay (No Proxy)
```bash
cd /home/ansible/rankings-bot
python3 -m scrapers.tournament_scraper_improved --limit 5 --rate-limit 10
```

### 2. Test with Proxy (if configured)
```bash
python3 -c "from scrapers.proxy_rotator import setup_proxy_recommended; setup_proxy_recommended()"
```

### 3. Monitor Results
```bash
# Check scraper logs
tail -f logs/scrapers.log

# Test if wpapool.com responds
curl -v https://wpapool.com/rankings/ --max-time 5
```

---

## Expected Behavior

### With 10s Delay Only:
- ✓ Much more respectful to server
- ✓ Looks like human browsing pace
- ✓ Single IP (Starlink) but infrequent requests
- ✓ Works on your phone too (different IP)
- ⚠ Starlink IP may still be on some blocklists

### With Proxies + Delay:
- ✓ All of the above
- ✓ Rotates IPs with each request
- ✓ Much harder to block
- ✗ Requires paid proxy service ($30-100/month)

### With Cron Schedule:
- ✓ All of the above
- ✓ Automatic scraping at optimal times
- ✓ 4+ hour gaps prevent detection
- ✓ Spreads load throughout day

---

## If You Get Blocked

**Signs of being blocked:**
- HTTP 429 (Rate Limited)
- Connection timeout
- HTTP 403 (Forbidden)
- HTTP 403.16 (Restricted)

**Recovery Steps:**
1. **Stop immediately** - Wait 24-48 hours
2. **Increase delays** - Try 30s between requests
3. **Add proxy rotation** - Different IPs help
4. **Contact the site** - Ask for API access or permission
5. **Use cron schedule** - Spread requests over time

**Contact wpapool.com:**
```
Email: user3@example.com (or similar)
Message: "Hi, I'm running an automated tournament tracker 
and would like permission to scrape rankings data. 
I'm using respectful rate limiting (10+ seconds between requests) 
and prefer an API if available."
```

---

## Current Configuration Status

| Feature | Status | Setting |
|---------|--------|---------|
| Rate Limit | ✓ Updated | 10 seconds |
| Proxy Support | ✓ Available | Disabled (optional) |
| Cron Schedule | ✓ Created | Not installed yet |
| Daily Scraping | ✓ Supported | Not scheduled yet |

---

## Logs & Monitoring

**Check scraper health:**
```bash
# Main scraper log
tail -f /home/ansible/rankings-bot/logs/scrapers.log

# Scheduler log (if using cron)
tail -f /home/ansible/rankings-bot/logs/scraper_scheduler.log

# Individual scraper logs
tail -f /home/ansible/rankings-bot/logs/scraper_*.log
```

---

## Recommendations (In Order)

1. **Right now:** Use 10s delay (already done)
2. **Week 1:** Monitor for errors, check if site responds
3. **Week 2:** If still responsive, install cron schedule
4. **Month 1:** Consider rotating proxies if blocking occurs
5. **Long term:** Contact wpapool.com for official API

---

## References

- [Rate Limiting Best Practices](https://developers.google.com/blog/posts/rate-limiting-strategies-protect-api)
- [Robots.txt](https://en.wikipedia.org/wiki/Robots.txt) - Check if site allows scraping
- [Web Scraping Ethics](https://blog.apifier.com/web-scraping-ethical-issues/)
- [ProxyMesh Docs](https://proxymesh.com/docs)

---

## See Also

- `scrapers/fetch_utils.py` - Retry & timeout handling
- `scripts/scraper_scheduler.py` - Schedule automation
- `scrapers/proxy_rotator.py` - Proxy rotation
