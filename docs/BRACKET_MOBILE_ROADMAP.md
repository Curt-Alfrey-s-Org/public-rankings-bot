# Bracket UI — Mobile Roadmap

## Current Implementation (Web-First, Feb 2026)

The bracket display is now optimized for **desktop/tablet in landscape mode**:

- **Rounds as columns**: Winners and Losers brackets render as horizontal scrollable grids
- **Match cards** show:
  - Player names
  - Table number (badge)
  - Match status (Pending / In Progress / Done)
  - Scheduled time (if available)
  - Score (when completed)
- **Director controls**: Score entry and timekeeper buttons on each match card
- **Matches grouped by**: Bracket type (Winners/Losers) and round number

---

## Mobile Roadmap (Future Phases)

### Phase 1: Portrait Mode Optimization (Not Required for v1)
- **Match List View**: Simple list of all matches, filterable by:
  - Status (pending, in progress, completed)
  - Table number
  - Player search
- **Quick Match Details**: Tap a match to see full details in a modal
- **Location Display**: Show "Find my match" with table number prominent

### Phase 2: Landscape Mode (Partial Desktop View)
- Use narrower columns for rounds
- Match cards with condensed layout
- Horizontal scrolling enabled from the start
- Match details remain accessible (tap-to-expand)

### Phase 3: Native App Considerations
- Deep linking to specific tournament/match
- Background notification for match updates
- QR code check-in optimization for mobile
- Offline bracket caching

---

## Design Principles

- **Mobile list view**: Prioritize findability (my table, my match, upcoming)
- **Landscape scrollable grid**: Mirror desktop but optimized for smaller viewport
- **Touch targets**: Minimum 48px buttons for reliable mobile interaction
- **Consistent styling**: Match website color scheme (slate-950, slate-800, sky-500)
- **No redundant info**: Avoid repeating player names across tabs; show context-specific data

---

## Testing Scenarios (Future)

When mobile support is implemented, test:
1. Portrait: Find match by table number within 2 taps
2. Landscape: Scroll to final round without zooming
3. Director flow: Score entry on 6" screen
4. Timekeeper: Large timer display on phone
5. QR check-in: Camera access and feedback

---

## Related Files

- [BracketGrid.tsx](../frontend/src/components/BracketGrid.tsx) — Current round/match renderer
- [Bracket.tsx](../frontend/src/pages/Bracket.tsx) — Tournament selector + bracket view
- Tournament API: `tournamentsApi.getMatches()` provides match data including scheduled_time, table_number
