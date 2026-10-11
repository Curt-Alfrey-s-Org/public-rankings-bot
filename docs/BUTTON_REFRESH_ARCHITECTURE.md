# Button Refresh Architecture - Rankings Bot

## Status: ✅ PROPERLY CONFIGURED

All scraper and rankings buttons **already automatically refresh website data** after operations complete. The "Update Website" button serves a different purpose (frontend rebuild/redeploy).

## Current Implementation Analysis

### 1. Rankings Refresh Button (`/api/rankings/refresh`)

**Location:** [SettingsAdmin.tsx](../frontend/src/pages/SettingsAdmin.tsx#L170)

**What it does:**
- Scrapes WPBA Women, WPA Women, WPA Men rankings
- Saves to database
- **Automatically invalidates queries:**
  ```tsx
  queryClient.invalidateQueries({ queryKey: ['rankings'] })
  queryClient.invalidateQueries({ queryKey: ['rankings-last-update'] })
  queryClient.invalidateQueries({ queryKey: ['tournament-imports'] })
  ```

**Result:** Frontend immediately refetches fresh rankings data from database and displays it.

### 2. Fargo Sync Button (`/api/fargo/sync`)

**Location:** [SettingsAdmin.tsx](../frontend/src/pages/SettingsAdmin.tsx#L286)

**What it does:**
- Syncs Fargo ratings from Fargo API
- Updates player ratings in database
- **Automatically invalidates queries:**
  ```tsx
  queryClient.invalidateQueries({ queryKey: ['rankings'] })
  queryClient.invalidateQueries({ queryKey: ['rankings-last-update'] })
  queryClient.invalidateQueries({ queryKey: ['health-detailed'] })
  ```

**Result:** Frontend immediately shows updated Fargo ratings on rankings pages.

### 3. Tournament history sync (`POST /api/tournament-history/refresh-past`)

**Location:** [SettingsAdmin.tsx](../frontend/src/pages/SettingsAdmin.tsx) — **Super admin** only; button label **Sync tournament history**.

**What it does (no external HTTP):**
- Rebuilds `tournament_history` / `tournament_results` from data already in Postgres:
  1. **`fill_tournament_history_from_rankings_snapshots`** — every `(ranking_system, snapshot_date)` in `rankings` (populated by live WPBA / WPA / CP scrapers and Admin Refresh) becomes snapshot-style history rows.
  2. **`fill_tournament_history_from_wpba_women_events`** — WPBA per-event tournaments from the latest `WPBA_Women` PDF-backed snapshot and column splits.
- Then **`refresh_materialized_views`**. Live log: `GET /api/tournament-history/refresh-past/log`.

**Not included:** JSON-on-disk CP archives — use **`POST /api/tournament-history/fill-from-cp-archives`** when that ingestion is needed.

**Invalidates in UI (on stream completion):** `tournament-history`, `tournament-history-years`, etc. (see `SettingsAdmin` `tournamentScrapeMutation`).

### 4. Other Scraper Buttons

All scraper operation buttons should follow this pattern:
```tsx
const scraperMutation = useMutation({
  mutationFn: () => apiCall(),
  onSuccess: (data) => {
    // Invalidate all relevant queries
    queryClient.invalidateQueries({ queryKey: ['relevant-data'] })
    queryClient.invalidateQueries({ queryKey: ['rankings'] })
    queryClient.invalidateQueries({ queryKey: ['rankings-last-update'] })
    toast.success('Data refreshed')
  },
  onError: (err) => {
    toast.error('Scrape failed')
  }
})
```

## How It Works

### React Query Architecture

1. **User clicks scraper/refresh button**
2. **API call executes** (scrape WPBA, sync Fargo, etc.)
3. **Data saved to database** (PostgreSQL)
4. **`onSuccess` handler runs:**
   - Calls `queryClient.invalidateQueries()`
   - Marks cached data as "stale"
5. **React Query automatically refetches:**
   - Calls GET `/api/rankings` (or relevant endpoint)
   - Fetches fresh data from database
6. **Frontend re-renders** with new data
7. **User sees updated data** (no page reload needed)

### Frontend Refetch Configuration

**Rankings Page:** [Rankings.tsx](../frontend/src/pages/Rankings.tsx)
```tsx
const { data: rankings } = useQuery({
  queryKey: ['rankings'],
  queryFn: rankingsApi.getAll,
  refetchInterval: 60000,  // Auto-refetch every 60 seconds
  staleTime: 30000,        // Consider stale after 30 seconds
})
```

**Last Update:** Sidebar & Rankings page
```tsx
const { data: lastUpdate } = useQuery({
  queryKey: ['rankings-last-update'],
  queryFn: rankingsApi.getLastUpdate,
  refetchInterval: 5000,   // Auto-refetch every 5 seconds
})
```

## "Update Website" Button - Different Purpose

**Location:** [SettingsAdmin.tsx](../frontend/src/pages/SettingsAdmin.tsx#L253)

**Purpose:** Rebuilds/redeploys the entire frontend application
- Runs **`scripts/rebuild_website_now.sh`** → **`build_frontend_with_docker.sh`** (Docker-only Node build into `frontend/dist/`)
- Restarts containers/processes as configured
-  **NOT for refreshing data** - use Rankings Refresh or specific scraper buttons instead

**When to use:**
- After changing frontend code
- After updating appearance/theme settings
- After modifying configuration files
- **Never needed for data updates** (scrapers handle this automatically)

## Verification Checklist

### ✅ Current Status

- [x] Rankings Refresh button invalidates queries
- [x] Fargo Sync button invalidates queries
- [x] All mutations use React Query's `useMutation`
- [x] `onSuccess` handlers call `queryClient.invalidateQueries()`
- [x] Frontend uses `useQuery` with proper refetch intervals
- [x] Toast notifications confirm success/failure
- [x] No manual page reloads required

### To Verify Any New Scraper Buttons

When adding new scraper buttons, ensure:

1. **Use `useMutation` hook:**
   ```tsx
   import { useMutation, useQueryClient } from '@tanstack/react-query'
   const queryClient = useQueryClient()
   ```

2. **Invalidate relevant queries on success:**
   ```tsx
   onSuccess: (data) => {
     queryClient.invalidateQueries({ queryKey: ['your-data-key'] })
     queryClient.invalidateQueries({ queryKey: ['rankings'] })  // If affects rankings
     queryClient.invalidateQueries({ queryKey: ['rankings-last-update'] })
     toast.success('Data updated')
   }
   ```

3. **Handle errors properly:**
   ```tsx
   onError: (err) => {
     toast.error(err?.message ?? 'Operation failed')
   }
   ```

4. **Backend saves to database:**
   ```python
   @router.post("/scrape-something")
   async def scrape_something():
       # 1. Scrape data
       data = scraper.scrape()
       # 2. Save to database
       db_manager.save_data(data)
       # 3. Return success
       return {"success": True, "count": len(data)}
   ```

## Common Query Keys

These are the main query keys used across the app:

| Query Key | Data Type | Refetch Interval |
|-----------|-----------|------------------|
| `['rankings']` | All rankings data | 60s |
| `['rankings-last-update']` | Last update timestamp | 5s |
| `['tournament-imports']` | Pending imports | Manual |
| `['tournament-history']` | Historical tournaments | Manual |
| `['players']` | Player list | Manual |
| `['health-detailed']` | System health | 5s |
| `['admin', 'users']` | User list | Manual |
| `['system-health']` | Health status | 5s |

## Testing Data Refresh

### Method 1: Use Browser DevTools

1. Open React DevTools
2. Go to "Components" tab
3. Find `QueryClientProvider`
4. View current query cache
5. Click scraper button
6. Watch queries invalidate and refetch

### Method 2: Network Tab

1. Open Browser DevTools → Network tab
2. Click scraper/refresh button
3. Watch for:
   - POST request to scraper endpoint (e.g., `/api/rankings/refresh`)
   - GET requests to data endpoints (e.g., `/api/rankings`)
   - New data appears without page reload

### Method 3: Database Check

```bash
# Before clicking button
cd /home/ansible/rankings-bot/Rankings-Bot
python3 -c "from database import get_database_manager; print(len(get_database_manager().get_wpba_rankings()))"

# Click button in UI

# After clicking button
python3 -c "from database import get_database_manager; print(len(get_database_manager().get_wpba_rankings()))"
```

## Troubleshooting

### Data doesn't update after clicking button

**Check:**
1. API call succeeded (check Network tab for 200 status)
2. `queryClient.invalidateQueries()` is in `onSuccess` handler
3. Query key matches between `useQuery` and `invaldate Queries`
4. No JavaScript errors in console
5. Backend saved data to database successfully

**Fix:**
```tsx
// Ensure this in mutation handler:
onSuccess: (data) => {
  queryClient.invalidateQueries({ queryKey: ['rankings'] })  // ← ADD THIS
  toast.success('Updated')
}
```

### Data updates but UI doesn't refresh

**Check:**
1. Component using `useQuery` with query key
2. Query not disabled: `enabled: true` (or omitted)
3. Not using stale cached data

**Fix:**
```tsx
// Force immediate refetch:
await queryClient.refetchQueries({ queryKey: ['rankings'] })

// Or reset query:
queryClient.resetQueries({ queryKey: ['rankings'] })
```

### "Update Website" button isn't needed for data

**Correct!** The "Update Website" button is **only for deploying code changes**, not for refreshing data.

**For data updates:**
- Use "Rankings Refresh" button (scrapes WPBA/WPA)
- Use "Fargo Sync" button (syncs Fargo ratings)
- Use any specific scraper button
- All these automatically refresh the website data via React Query

## Summary

✅ **System is properly configured** - all scraper and rankings buttons automatically refresh displayed data through React Query's cache invalidation mechanism.

✅ **No "Update Website" needed for data** - that button is for deploying code changes only.

✅ **Frontend updates automatically** - when queries are invalidated, React Query refetches data and components re-render.

✅ **No page reload required** - SPA architecture with React Query handles all data updates seamlessly.

## Future Enhancements (Optional)

1. **Optimistic Updates:** Update UI immediately before API call completes
2. **Background Sync:** Periodically sync data in background without user action
3. **WebSocket Updates:** Real-time data pushes from server to clients
4. **Service Worker:** Offline support and background data sync
5. **Mutation Queue:** Queue multiple scraper operations to run sequentially
