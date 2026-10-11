# Tournament Rankings Load - Quick Reference Guide

## For Admins

### Load Tournament Rankings (Standard)
1. Go to Tournament History page
2. Click **"Load Tournament Rankings"** button
3. Wait ~5 seconds
4. See success toast: "Rankings loaded: 2110 results in 38 tournaments"
5. Page automatically refreshes

**Use when:** You want to load existing tournament ranking data into the database

---

### Load with Fresh Scrape
1. Go to Tournament History page
2. **Check the box:** ☑ "📝 Also scrape fresh tournament data"
3. Click **"Load Tournament Rankings"** button
4. Wait ~30 seconds (scraper will fetch latest data)
5. See success toast: "Rankings loaded: XXXX results in XX tournaments (with fresh scrape)"
6. Page automatically refreshes with latest data

**Use when:** You want the latest tournament ranking data from official sources

---

## Refresh Operations Explained

| Button | What it does | When to use | Time |
|--------|-----------|-------------|------|
| **Refresh Past Tournaments** | Imports historical tournament list | Need to add old tournaments to system | ~10s |
| **Load Tournament Rankings** (unchecked) | Loads ranking data into tournaments from existing JSON | JSON file already up-to-date | ~5s |
| **Load Tournament Rankings** (checked) | Scrapes latest data AND loads it | Want absolutely fresh data | ~30s |

---

## Troubleshooting

### "Load Rankings failed" error
**Solutions:**
1. Try again (might be temporary)
2. Try with checkbox checked (will scrape fresh data)
3. Contact admin if persists

### Nothing happens after clicking
**Check:**
- You're logged in as admin
- Page isn't frozen (check browser console F12)
- Internet connection is stable
- Wait a moment, operation might be slow

### Data seems stale
**Solution:**
Check the ☑ "Also scrape fresh data" box and click Load Rankings
This will fetch latest data from official sources

---

## Data Refresh Schedule

**Automatic (No action needed):**
- Rankings refresh: Every hour (staggered by 15-min intervals)
- Basic tournaments: Auto-imported when added

**Manual (Use buttons above):**
- Refresh past tournaments
- Load tournament rankings (with fresh scrape if needed)

---

## What Gets Updated?

### Refresh Past Tournaments Button
- ✅ Historical tournament list
- ✅ Tournament dates, locations, associations
- ✅ Prize pools and championship status

### Load Tournament Rankings Button
- ✅ Player placement per tournament (1st, 2nd, 3rd, etc.)
- ✅ Points earned per tournament
- ✅ Tournament-specific statistics

**Result:** Players can now see their per-tournament performance history

---

## Tips

💡 **Quick way to get everything fresh:**
1. Click "Refresh Past Tournaments"
2. Click "Load Tournament Rankings" (with ☑ checked)
3. Wait ~40 seconds total
4. All tournament data is now current

💡 **If you only need ranking data:**
Just click "Load Tournament Rankings" (unchecked) - only takes ~5 seconds

💡 **Check box stays checked:**
If you prefer fresh scrapes, checkbox remembers your preference

---

## Example Scenarios

### Scenario: User reports missing tournament results
```
1. Check ☑ "Also scrape fresh data"
2. Click [Load Tournament Rankings]
3. Wait ~30 seconds
4. Ask user to refresh page (Ctrl+R)
5. User should now see results
```

### Scenario: Weekly maintenance
```
1. Click [Refresh Past Tournaments]
2. Wait ~10 seconds
3. Click [Load Tournament Rankings] with ☑ checked
4. Wait ~30 seconds
5. Tournament data is fully current
```

### Scenario: Someone says "data is stale"
```
1. Just click [Load Tournament Rankings] with ☑ checked
2. Fresh scrape will pull latest data
3. Data is now current (no need to refresh page, it auto-updates)
```

---

## Support

**Questions?**
- Check browser console for error messages: F12 → Console
- Look for the success/error toast message that appears
- Check logs if page doesn't update after operation

**Still stuck?**
- Try refreshing the page: Ctrl+R
- Try again (sometimes network glitches)
- Contact system administrator if error persists

---

## Historical Data

**Last successful load:**
- Date: February 18, 2026
- Tournaments updated: 38
- Results upserted: 2,110
- Errors: 0

---

That's it! You now have the most efficient way to manage tournament ranking data. One click (with optional scrape) to load everything! 🎉

