# Live Real-Time Updates - Quick Start Guide

## For Developers: Add Live Updates in 30 Seconds

### Copy-Paste Integration

**Step 1: Import the hook** (add to imports at top of your component)
```typescript
import { useLiveUpdates } from '@/hooks/useLiveUpdates'
```

**Step 2: Add one line to your component**
```typescript
export default function MyPage() {
  // Enable live updates for this page
  useLiveUpdates({
    autoRefreshKeys: ['my-data-key'],
    showNotifications: true,
  })
  
  // Rest of your component code...
  return <div>{/* ... */}</div>
}
```

**Done!** Your page now auto-refreshes when scrapers complete.

---

## What Key Should I Use?

Match the query key from your `useQuery` call:

```typescript
// In your page...
const { data } = useQuery({
  queryKey: ['rankings', 'wpba_women'],  // ← This key
  queryFn: () => rankingsApi.getWpbaWomen(),
})

// In useLiveUpdates...
useLiveUpdates({
  autoRefreshKeys: ['rankings', 'wpba_women'],  // ← Use the same key
})
```

---

## Scraper Event Types

When a scraper completes, it publishes one of these event types:

| Event Type | Triggered By | Use These Keys |
|------------|--------------|---|
| `rankings_wpba` | WPBA Women rankings | `['rankings', 'wpba']` |
| `rankings_wpa_women` | WPA Women rankings | `['rankings', 'wpa_women']` |
| `rankings_wpa_men` | WPA Men rankings | `['rankings', 'wpa_men']` |
| `rankings_wpa_artistic` | WPA Artistic ratings | `['rankings', 'artistic']` |
| `tournament` | Tournament history | `['tournament-history']` |
| `fargo` | Fargo ratings sync | `['fargo']` |

---

## Common Use Cases

### Rankings Page (already done)
```typescript
useLiveUpdates({
  autoRefreshKeys: ['rankings', 'metadata'],
  showNotifications: true,
})
```

### Tournament Page (already done)
```typescript
useLiveUpdates({
  autoRefreshKeys: ['tournament-history', 'tournaments'],
  showNotifications: true,
})
```

### Fargo/Ratings Page
```typescript
useLiveUpdates({
  autoRefreshKeys: ['fargo'],
  showNotifications: true,
})
```

### Dashboard (all data)
```typescript
useLiveUpdates({
  autoRefreshKeys: ['rankings', 'tournament-history', 'fargo'],
  showNotifications: true,
})
```

### Custom Logic
```typescript
useLiveUpdates({
  onUpdate: (event) => {
    // Custom handler for scraper events
    if (event.scraper_type === 'fargo') {
      console.log(`${event.rows_updated} players updated`)
      // Play sound, send analytics, etc.
    }
  },
  showNotifications: true,
})
```

---

## Disable Notifications

```typescript
useLiveUpdates({
  autoRefreshKeys: ['rankings'],
  showNotifications: false,  // No banner shown
})
```

---

## Disable Auto-Refresh (Manual Only)

```typescript
useLiveUpdates({
  autoRefreshKeys: [],  // Don't auto-refresh
  showNotifications: true,
  onUpdate: (event) => {
    // You handle the update
    console.log('Scraper completed:', event)
  }
})
```

---

## Full Example: Add to Player Performance Page

**File:** `frontend/src/pages/PlayerPerformance.tsx`

```typescript
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useLiveUpdates } from '@/hooks/useLiveUpdates'  // ← Add this
import { playerApi } from '@/api/player'

export default function PlayerPerformance() {
  const [playerId, setPlayerId] = useState<string>('')
  
  // Enable live updates - refreshes when rankings change
  useLiveUpdates({  // ← Add this block
    autoRefreshKeys: ['player-stats', 'rankings'],
    showNotifications: true,
  })

  // Rest of component code...
  const { data } = useQuery({
    queryKey: ['player-stats', playerId],
    queryFn: () => playerApi.getStats(playerId),
    enabled: !!playerId,
  })

  return (
    <div>
      {/* Your component JSX */}
    </div>
  )
}
```

Done! Now whenever rankings scrapers run, this page auto-refreshes.

---

## Testing Your Integration

### 1. Add the hook to your page
```typescript
useLiveUpdates({ autoRefreshKeys: ['your-key'], showNotifications: true })
```

### 2. Open your page in browser
Go to http://localhost:5173/your-page

### 3. Open DevTools
Press F12 → Console tab

### 4. Trigger a scraper manually
```bash
# From server terminal:
cd /home/ansible/rankings-bot/Rankings-Bot
python3 -c "from api.services.background_scheduler import _job_wpba_rankings_refresh; _job_wpba_rankings_refresh()"
```

### 5. Watch browser
- Console should log: `[LIVE-UPDATES] Received: rankings_wpba success`
- Green banner should appear in bottom-right
- Your page data should refresh automatically
- Banner disappears after 4 seconds

**If this works, you're connected!**

---

## Troubleshooting

### No console logs?
1. Check F12 → Network tab
2. Look for `/api/live/updates` request
3. Should show `101 Switching Protocols` (not 200 OK)
4. Check API is running: `sudo systemctl status rankings-bot-api.service`

### Data not refreshing?
1. Check that `autoRefreshKeys` matches your `useQuery` key
2. Example:
   ```typescript
   // This must match...
   const { data } = useQuery({ queryKey: ['rankings', 'wpba'] })
   
   // With this...
   useLiveUpdates({ autoRefreshKeys: ['rankings', 'wpba'] })
   ```

### Banner not showing?
1. Check `showNotifications: true` is set
2. Check browser console for errors: `F12 → Console`
3. Trigger a manual scraper event (see Testing section)

### Keep getting reconnection messages?
That's normal - exponential backoff when connection drops. Should stabilize.

---

## API Reference

```typescript
interface UseLiveUpdatesOptions {
  /** Custom callback for every scraper event */
  onUpdate?: (event: LiveUpdateEvent) => void
  
  /** React Query keys to invalidate when events arrive */
  autoRefreshKeys?: string[]
  
  /** Show toast notifications for events */
  showNotifications?: boolean
}

interface LiveUpdateEvent {
  scraper_type: string        // 'rankings_wpba', 'tournament', etc.
  status: 'success' | 'failed'
  timestamp: string           // ISO 8601
  message: string             // Human-readable description
  rows_updated: number        // Records affected
  duration_s: number          // How long scraper took
  error: string               // Error message if failed
}
```

---

## Performance

✅ **Zero polling:** Events pushed from server (efficient)
✅ **Minimal overhead:** ~1KB memory per hook instance
✅ **No network spam:** Only transmits when event occurs
✅ **Auto-cleanup:** Disconnects gracefully on unmount

---

## Browser Compatibility

- ✅ Chrome 6+
- ✅ Firefox 6+
- ✅ Safari 5.1+
- ✅ Edge 12+
- ❌ IE (not supported)

---

## Implementation Checklist

Use this when adding live updates to a new page:

- [ ] Import useLiveUpdates hook
- [ ] Call hook in component body
- [ ] Set autoRefreshKeys to match your useQuery keys
- [ ] Test with manual scraper trigger
- [ ] Verify console logs show [LIVE-UPDATES] messages
- [ ] Verify banner appears when scraper completes
- [ ] Verify data refreshes (React Query refetch)
- [ ] Test on real scraper run (hourly schedule)

---

## Frequently Asked Questions

### Q: Do I need to modify my useQuery calls?
**A:** No, leave them as-is. The hook handles invalidation automatically.

### Q: What if my page uses different caching?
**A:** The hook only invalidates React Query. For other caching, use the `onUpdate` callback.

### Q: Can I use this on the same page twice?
**A:** It's fine, but redundant. Just call the hook once per component.

### Q: What if a scraper fails?
**A:** Event still published with `status="failed"` and error message. Banner shows red instead of green.

### Q: Does this work offline?
**A:** No, requires server connection. Falls back to manual refresh if needed.

### Q: Can I customize the banner appearance?
**A:** Yes, edit `frontend/src/components/LiveUpdatesBanner.tsx` - it uses TailwindCSS classes.

---

## Real-World Examples

### Example 1: Simple Page Integration
```typescript
// File: frontend/src/pages/Leaderboard.tsx
import { useLiveUpdates } from '@/hooks/useLiveUpdates'

export default function Leaderboard() {
  useLiveUpdates({  // ← One hook call
    autoRefreshKeys: ['leaderboard'],
    showNotifications: true,
  })
  
  // Rest of existing code...
}
```

### Example 2: Multiple Data Types
```typescript
// File: frontend/src/pages/Dashboard.tsx
export default function Dashboard() {
  useLiveUpdates({
    autoRefreshKeys: [
      'rankings',
      'tournament-history',
      'fargo-ratings',
    ],
    showNotifications: true,
  })
  
  // Shows all updates to any of these data types
}
```

### Example 3: Custom Notification
```typescript
// File: frontend/src/pages/AdminPanel.tsx
export default function AdminPanel() {
  useLiveUpdates({
    onUpdate: (event) => {
      
      // Custom analytics tracking
      analytics.trackEvent('scraper_completed', {
        type: event.scraper_type,
        status: event.status,
        rows: event.rows_updated,
      })
      
      // Play sound for important updates
      if (event.scraper_type === 'fargo') {
        playNotificationSound()
      }
    },
    showNotifications: false,  // No banner, custom handling only
  })
}
```

---

## Documentation Links

- 📖 **Complete Docs:** [LIVE_UPDATES_DOCUMENTATION.md](../LIVE_UPDATES_DOCUMENTATION.md)
- 🧪 **Testing Guide:** [LIVE_UPDATES_TESTING_GUIDE.md](../LIVE_UPDATES_TESTING_GUIDE.md)
- 📊 **Implementation Summary:** [LIVE_UPDATES_IMPLEMENTATION_SUMMARY.md](../LIVE_UPDATES_IMPLEMENTATION_SUMMARY.md)
- ✓ **Integration Checklist:** [LIVE_UPDATES_INTEGRATION_CHECKLIST.md](../LIVE_UPDATES_INTEGRATION_CHECKLIST.md)

---

## Support

If something doesn't work:
1. Check the **Troubleshooting** section above
2. Run the **Testing** steps to verify components
3. Check API logs: `sudo journalctl -u rankings-bot-api.service -f`
4. Check browser console: `F12 → Console` for errors

---

**That's it!** You're ready to add live updates to any page. 🚀

30 seconds to integration. Zero configuration needed beyond query keys.

