# Tournament Wizard Auto-Prefill Feature

**Status:** ✅ Implemented  
**Date:** February 15, 2026  
**File:** `frontend/src/pages/TournamentWizard.tsx`

## Overview

The Tournament Wizard now automatically suggests upcoming tournaments from scraped WPBA/WPA data, making it faster for Tournament Directors to create tournament entries.

## Features

### 1. **Auto-Prefill Next Tournament (Single)**

When the wizard loads, it automatically:
- Fetches upcoming tournaments from WPBA/WPA websites (via `/api/events/future`)
- Identifies the next tournament (earliest start date)
- If only **one** tournament is scheduled for that week, **auto-prefills** the form with:
  - Tournament name
  - Start date
  - Location (if available)
- Displays a **green "✓ Auto-filled"** badge

**User Experience:**
```
🎯 Next Tournament                   [Custom Tournament]
┌─────────────────────────────────────────────────────┐
│ 2026 Carolina Women's Classic          ✓ Auto-filled│
│ 📅 2/20/2026                                        │
│ 📍 Charlotte, NC                                    │
│ Source: WPBA                                        │
└─────────────────────────────────────────────────────┘
```

### 2. **Multiple Options (Same Week)**

If **2+ tournaments** land in the same week:
- Shows radio buttons for each tournament
- Director selects which tournament to create
- Prefills form when selected

**User Experience:**
```
🎯 3 Tournaments This Week             [Custom Tournament]

Choose which tournament to create:

○ WPBA Southern Classic
  📅 2/18/2026
  📍 Atlanta, GA
  Source: WPBA

● WPA 9-Ball Championship              ← Selected
  📅 2/20/2026
  📍 Las Vegas, NV
  Source: WPA

○ Regional 8-Ball Open
  📅 2/21/2026
  📍 Orlando, FL
  Source: WPBA
```

### 3. **Custom Tournament Option**

If the tournament wasn't published on WPBA/WPA websites:
- Click **"Custom Tournament"** button
- Clears all prefilled data
- Allows manual entry
- Shows **"✏️ Creating Custom Tournament"** indicator
- Can switch back to suggested tournaments with **"Use Suggested"** button

**User Experience:**
```
✏️ Creating Custom Tournament         [Use Suggested]
```

### 4. **Browse All Events**

Advanced option collapsed by default:
- Click **"🔍 Browse All Upcoming Events"** to expand
- Search by location (e.g., "Ft Lauderdale")
- Dropdown shows next 20 events
- Select any event to prefill

## Technical Details

### Week Detection

Uses ISO week calculation (Monday start):
```typescript
function isSameWeek(date1: string, date2: string): boolean {
  // Returns true if both dates fall in the same ISO week
}
```

### Auto-Prefill Logic

```typescript
useEffect(() => {
  // On mount, find next tournament(s)
  const upcoming = futureEvents
    .filter(e => e.start_date >= today)
    .sort((a, b) => a.start_date.localeCompare(b.start_date))
  
  const nextEvent = upcoming[0]
  const sameWeek = upcoming.filter(e => isSameWeek(e.start_date, nextEvent.start_date))
  
  if (sameWeek.length === 1) {
    // Auto-prefill single tournament
    handlePrefillFromEvent(nextEvent, 0)
  } else {
    // Show multiple options (no auto-prefill)
    setSameWeekEvents(sameWeek)
  }
}, [futureEvents, eventsLoading])
```

### State Management

```typescript
const [selectedEventIndex, setSelectedEventIndex] = useState<number | null>(null)
const [sameWeekEvents, setSameWeekEvents] = useState<FutureEvent[]>([])
const [showCustomMode, setShowCustomMode] = useState(false)
```

## Data Source

**API Endpoint:** `/api/events/future`
- Queries: `events_scraper.py`
- Scrapes: WPBA Events Official + WPA Calendar
- Returns: `{ events: Array<FutureEvent> }`

**FutureEvent Structure:**
```typescript
interface FutureEvent {
  name: string
  start_date: string // YYYY-MM-DD
  end_date: string
  location: string | null
  url: string
  source: 'WPBA' | 'WPA'
}
```

## Benefits

✅ **Saves Time:** Directors don't need to manually type tournament details  
✅ **Reduces Errors:** Auto-filled data matches official WPBA/WPA listings  
✅ **Shows Options:** Handles multiple tournaments gracefully  
✅ **Flexible:** Still allows custom tournaments for local/unlisted events  
✅ **Smart:** Only shows relevant tournaments (next 30 days by default)

## Usage Workflow

**Scenario 1: Single Tournament (Most Common)**
1. Director navigates to `/director/new`
2. Wizard auto-prefills with next tournament
3. Director reviews, adjusts if needed
4. Proceeds to Step 2 (Points Structure)

**Scenario 2: Multiple Tournaments Same Week**
1. Wizard shows radio buttons for all options
2. Director selects correct tournament
3. Form prefills with selection
4. Proceeds to Step 2

**Scenario 3: Custom Tournament**
1. Director clicks "Custom Tournament"
2. Form clears, shows "Creating Custom Tournament"
3. Director manually enters all fields
4. Proceeds to Step 2

## Future Enhancements

**Potential Improvements:**
- Add "Refresh Events" button to re-scrape WPBA/WPA
- Cache scraped events for 1 hour (already implemented via React Query `staleTime: 60000`)
- Show event thumbnails/logos if available
- Allow directors to save favorite venues for faster location entry
- Integrate with tournament history to suggest point structures based on similar past tournaments

## Testing

```bash
# Run frontend dev server
cd /home/ansible/rankings-bot/Rankings-Bot/frontend
npm run dev

# Navigate to:
http://localhost:5173/director/new

# Test scenarios:
1. Load page → Should auto-prefill if 1 tournament next week
2. Click "Custom Tournament" → Should clear form
3. Click "Use Suggested" → Should restore prefill
4. Open "Browse All Events" → Should show dropdown
5. Select different event → Should update form
```

## Related Files

- `frontend/src/pages/TournamentWizard.tsx` - Main wizard component
- `frontend/src/api/events.ts` - Events API client
- `api/routes/events.py` - Events API endpoint
- `api/services/events_scraper.py` - WPBA/WPA scraper
- `BUTTON_REFRESH_ARCHITECTURE.md` - React Query cache invalidation

## Notes

- Events are cached for 60 seconds (`staleTime: 60000`)
- Week calculation uses ISO weeks (Monday start)
- Auto-prefill only triggers when `selectedEventIndex === null && !showCustomMode`
- Tournament directors must have proper authentication/permissions to access `/director/new`
