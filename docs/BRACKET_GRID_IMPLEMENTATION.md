# Bracket Grid UI Implementation — Web-First (Feb 2026)

## Summary

Rebuilt the tournament bracket display with a **modern column-based grid layout** optimized for desktop/tablet viewing.

## Changes Made

### 1. Updated Match API Interface
**File**: [frontend/src/api/tournaments.ts](../frontend/src/api/tournaments.ts#L110-L132)

The `Match` interface now includes all backend fields:
- `operator_name` / `player2_name` — Player names (populated by API)
- `scheduled_time` — Match start time (ISO datetime, optional)
- `table_number` — Table assignment (optional int)
- `winner_id` / `loser_id` — Match outcome tracking
- `race_to` — Game goal (e.g., race-to-7)
- `round_number` — Stage in tournament (was `round`)
- Removed old fields: `operator_games`, `player2_games`, `winner_player_id`, `created_at`, `updated_at`

### 2. New BracketGrid Component
**File**: [frontend/src/components/BracketGrid.tsx](../frontend/src/components/BracketGrid.tsx) (NEW)

Modern bracket display with:

#### Layout
- **Separate sections** for Winners and Losers brackets
- **Rounds as columns**: Each bracket type flows left-to-right (R1 → R2 → Finals, etc.)
- **Horizontal scrolling** for large tournaments (32, 64+ players)
- **Sticky round headers** for orientation

#### Match Cards (`<MatchCard />`):
- **Player names** (top priority) — shows real names, not IDs
- **Table badge** — `T5` style indicator for quick table lookup
- **Match time** — Shows `🕐 11:30 AM` if scheduled
- **Status indicator**:
  - ✓ Done (green)
  - ⏱ Live (amber)
  - Pending (slate)
  - BYE (grayed out)
- **Score display** — Shows only when completed
- **Winner highlighting** — Winning player row gets green tint when match is done

#### Director Controls (when `isDirectorMode=true`):
- **📊 Score button** — Opens MatchEntryModal for score entry
- **⏱️ Timer button** — Opens timekeeper view (calls `onTimeKeeperOpen`)

#### Data Flow:
```
Bracket.tsx
  ↓ getMatches() API call
  ↓ matches: Match[]
  BracketGrid
    ├── Groups matches by (bracket_type, round_number)
    ├── Renders Winners bracket (if any)
    └── Renders Losers bracket (if any)
```

### 3. Updated Bracket.tsx
**File**: [frontend/src/pages/Bracket.tsx](../frontend/src/pages/Bracket.tsx)

- **Replaced `BracketViewer`** with new `BracketGrid`
- **Added matches query**:
  ```typescript
  const { data: matches = [], isLoadingMatches } = useQuery({
    queryKey: ['tournament-matches', selectedTournamentId],
    queryFn: () => tournamentsApi.getMatches(selectedTournamentId!),
  })
  ```
- **Passes to BracketGrid**:
  - `matches` — data
  - `isDirectorMode` — enable/disable director controls
  - `onTimeKeeperOpen` — callback to open timekeeper
  - `isLoading` — show loading state

### 4. Mobile Roadmap Documentation
**File**: [docs/BRACKET_MOBILE_ROADMAP.md](../docs/BRACKET_MOBILE_ROADMAP.md) (NEW)

Outlines future mobile enhancements (not implemented):
- Phase 1: Portrait match list view with search/filter
- Phase 2: Landscape responsive grid
- Phase 3: Native app considerations

## Design Highlights

### Color & Styling
- **Slate theme**: `slate-900`, `slate-800`, `slate-700` for backgrounds
- **Sky accents**: `sky-500` for interactive elements (table badges, active selections)
- **Status colors**: Green for completed, amber for in-progress
- **Consistent with website**: Matches existing button/layout patterns

### Accessibility
- **Semantic HTML**: Proper button and div roles
- **Touch targets**: Director buttons are 48px+ for reliable mobile clicking
- **Screen readers**: Status indicators in text, not just color
- **Contrast**: White text on dark + accent colors meet WCAG AA

### Performance
- **Lazy rendering**: Only visible rounds render fully
- **Horizontal scroll**: No page reflow as tournament grows
- **Query caching**: React Query handles match data caching

## What Next?

1. **Test with director workflow**:
   - Select tournament → view bracket
   - Click match → enter score
   - Check timekeeper flow

2. **Verify API provides**:
   - Player names in match responses
   - Scheduled times (will come from director input)
   - Table assignments

3. **Mobile refinement (future)**:
   - Add list view for portrait mode
   - Optimize for smaller screens
   - Test landscape rotation

---

## Files Changed

- ✅ [tournaments.ts](../frontend/src/api/tournaments.ts) — Updated Match interface
- ✅ [BracketGrid.tsx](../frontend/src/components/BracketGrid.tsx) — NEW component
- ✅ [Bracket.tsx](../frontend/src/pages/Bracket.tsx) — Integrated BracketGrid
- ✅ [BRACKET_MOBILE_ROADMAP.md](../docs/BRACKET_MOBILE_ROADMAP.md) — Future roadmap

---

## Example: 16-Player Single Elimination

```
Winners Bracket                                Winners Finals
┌─────────────────┐                          ┌──────────────┐
│ P1 vs P16       │ R1 Winners  →→            │     P1 vs P8 │  Finals
│ 🕐 10:00 AM T1  │                          │ 🕐 2:00 PM T4 │
│ T1 🔵 P1: 7     │                          │ ✓ Done: 7-5  │
│ T1 🔵 P16: 5    │                          │ 🏆 P1 wins   │
└─────────────────┘                          └──────────────┘
       ↓
   (8 matches total)
   
Losers Bracket
├─ Losers R1: (8 matches from R1 losers)
├─ Losers R2: (4 matches)
├─ Losers Finals: (1 match)
└─ Grand Finals: (P1 vs Losers winner, if bracket drop applies)
```

---

## API Contract

Backend provides (from `GET /tournaments/{id}/matches`):

```json
{
  "match_id": "m123",
  "tournament_id": "t456",
  "round_number": 1,
  "match_number": 1,
  "bracket_type": "winners",
  "operator_id": "p789",
  "player2_id": "p012",
  "operator_name": "Alice Smith",
  "player2_name": "Bob Johnson",
  "operator_score": 7,
  "player2_score": 5,
  "winner_id": "p789",
  "status": "completed",
  "race_to": 7,
  "scheduled_time": "2026-02-22T10:00:00Z",
  "table_number": 1
}
```

Bracket grid consumes this directly—no additional API calls needed once matches are loaded.
