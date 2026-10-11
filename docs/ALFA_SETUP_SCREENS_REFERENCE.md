# ALFA-Style Setup Screens — Reference for Implementation

**Purpose:** Guide for building External Pool-inspired setup screens with ALFA styling and layout. Use when implementing tournament wizard, events, league landing, and stats pages.

---

## External Pool vs ALFA: Screen Mapping

| External Pool Screen | Main Elements | ALFA Equivalent |
|-------------------|---------------|-----------------|
| Tournament Type | Smart vs Free cards, feature checklists | Add Type step to Tournament Wizard |
| Settings | 7-step sidebar, form fields | Expand Tournament Wizard |
| Events | Search, filters, event cards | New Events page |
| League Manager | Find leagues, Players, Operators cards | League landing page |
| Stats | Match history, win percentages | Stats page |
| Pro Rankings | Multi-column table | Rankings table |

---

## ALFA Design Tokens

From `frontend/src/index.css` and `tailwind.config.js`:

| Token | Value | Usage |
|-------|-------|-------|
| Background | `slate-950`, `slate-900` | Page and card backgrounds |
| Cards | `bg-slate-800`, `border-slate-700`, `rounded-lg` | Panels, metric cards |
| Primary accent | `sky-500`, `sky-600` | Buttons, links, focus |
| Success | `emerald-400`, `emerald-600` | Positive states |
| Felt | `--felt` (HSL 142 45% 28%) | Pool/billiards accent |
| Typography | Inter, `text-slate-pool_opt_in`, `text-slate-400` | Headings and body |
| Gradient | `from-slate-900 via-slate-800 to-slate-900` | Page backgrounds |
| Step indicators | `bg-sky-600` (current), `bg-emerald-600` (done), `bg-slate-700` (pending) | Wizard progress |

---

## Tournament Wizard Improvements

### Current: 4 steps (Basic Info, Points, Players, Review)

### Proposed: Add/expand steps

1. **Step 0 — Type (new)**  
   - Two cards: "Standard Tournament" vs "Fargo-Rated Tournament"  
   - Use `AlfaMetricCard`-style: `bg-slate-800 border-slate-700`, `hover:border-sky-500`  
   - Feature lists with checkmarks

2. **Step 1 — Basic Info**  
   - Add Private/Public toggle  
   - Inputs: `bg-slate-700 border-slate-600`, `focus:border-sky-500 focus:ring-sky-500/20`

3. **Step 2 — Settings (expanded)**  
   - Add: venue search, event/tour association, game type  
   - Add: Fargo format (Standard / Fargo Rated / USAPL)  
   - Add: Winners/Losers/Finals race-to, bracket ordering (Random / Seeded / Set order)  
   - Layout: left sidebar with step numbers, main form right

4. **Step 3 — Players**  
   - Add Fargo score display and optional robustness filter

5. **Step 4 — Tables (new)**  
   - Add tables with optional "Live streaming table" flag  
   - Per-table scoring URL (for future tablet scoring)

6. **Step 5 — Review**  
   - Summary cards with `bg-slate-800 border-slate-700`

---

## Layout Patterns

| Pattern | External Pool | ALFA equivalent |
|---------|-------------|------------------|
| Step sidebar | Numbered steps on left | Same, `sky-500` active, `emerald-500` done |
| Feature checklist | Checkmarks in cards | Same, `text-emerald-400` for ✓ |
| Info banner | Blue tip banner | `bg-sky-950/30 border-sky-700` |
| Card grid | 3–4 cards | `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6` |
| Form layout | Labels above inputs | `block text-sm font-medium text-slate-200 mb-2` |
| Primary CTA | Blue button | `bg-sky-600 hover:bg-sky-500 text-white` |

---

## Events Page (ALFA style)

- Page: `bg-slate-950`, `space-y-8`
- Search: `bg-slate-800 border-slate-700 rounded-lg`
- Filters: `border-slate-700` dropdowns
- Event cards: `bg-slate-800 border-slate-700 rounded-lg p-6`, `hover:border-sky-500/50`
- Use `TournamentCard`-style layout with `felt` or `sky-500` accents for dates

---

## League / Find Landing (ALFA style)

- Three `AlfaMetricCard`-style cards in a grid
- Colors: `sky-400`, `emerald-400`, `felt` for variety
- Base: `bg-slate-800 border-slate-700`

---

## Stats Page (ALFA style)

- Use `AlfaMetricCard` for totals
- Charts: `chart-1` through `chart-5` from `index.css`
- Panels: `bg-slate-800 border-slate-700 rounded-lg p-6`

---

## Files to Modify

| File | Role |
|------|------|
| `frontend/src/pages/TournamentWizard.tsx` | Add steps, fields, ALFA styling |
| `frontend/src/index.css` | Optional wizard tokens |
| `frontend/src/components/AlfaMetricCard.tsx` | Reuse for type/feature cards |
| `frontend/src/pages/CurrentTournaments.tsx` | Add Events-style view if needed |
| New: `EventsPage.tsx`, `LeagueLanding.tsx` | New ALFA-style pages |

---

## Related Docs

- [EXTERNALPOOL_ANALYSIS.md](../EXTERNALPOOL_ANALYSIS.md) — Full competitor analysis
- [LEAGUE_MANAGER.md](LEAGUE_MANAGER.md) — League Manager reference
- [docs/screenshots/externalpool/](screenshots/externalpool/README.md) — Reference screenshots
