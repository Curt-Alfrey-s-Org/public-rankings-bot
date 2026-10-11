# Recharts Console Warning Fix

## Problem

Recharts logged repeated console warnings at probilliardssoftware.com:

```
The width(-1) and height(-1) of chart should be greater than 0, please check the style of container, 
or the props width(100%) and height(100%), or add a minWidth(0) or minHeight(undefined) or use 
aspect(undefined) to control the height and width.
```

Stack trace pointed to `LineChart`, `setData`, `setOptions`, `onSubscribe`, and `subscribe`.

## Root Cause

**Recharts 3.x bug** ([recharts/recharts#6716](https://github.com/recharts/recharts/issues/6716)): `ResponsiveContainer` has `sizes=undefined` on first render. Its `useEffect` measures the parent via `getBoundingClientRect()` and overwrites `initialDimension`. When the parent is not laid out yet (tabs, accordions, tables, before first paint), dimensions can be 0 or -1, triggering the warning.

## Attempts (Rejected)

| Approach | Result |
|----------|--------|
| `minWidth` / `minHeight` on ResponsiveContainer | Warning persisted |
| `initialDimension` prop | Overwritten by effect before layout; warning persisted |
| `ChartContainer` wrapper (ResizeObserver + conditional render) | Warning persisted |
| `ChartContainer` + explicit `height` + `useLayoutEffect` | Warning persisted |

## Final Fix

**Downgrade Recharts from 3.7.0 to 2.15.0.** The bug does not exist in Recharts 2.x.

## Files Changed

### package.json (Recharts version)

| Path | Change |
|------|--------|
| `rankings-bot/frontend/package.json` | `"recharts": "^3.7.0"` → `"recharts": "^2.15.0"` |
| `.cursor/worktrees/.../vur/frontend/package.json` | Same |
| `.cursor/worktrees/.../owe/frontend/package.json` | Same |
| `.cursor/worktrees/.../knn/frontend/package.json` | Same |
| `.cursor/worktrees/.../qne/frontend/package.json` | Same |

### Code Reverted (ChartContainer removed)

- **Deleted:** `rankings-bot/frontend/src/components/ChartContainer.tsx`
- **Reverted:** All chart components to plain `ResponsiveContainer` (no wrapper)
- **Kept:** `minWidth` and `minHeight` on ResponsiveContainer (harmless, good practice)

### Chart Components (unchanged structure)

- `HotStreak.tsx` – PlacementChart
- `PlayerPerformance.tsx` – 3 LineCharts (Fargo history, rating trends, performance trend)
- `TournamentHistory.tsx` – 1 LineChart
- `PerformanceCharts.tsx` – 5 charts (Line, Area, Bar, Pie)
- `PlayerComparisonChart.tsx` – RadarChart
- `WinRateDistribution.tsx` – BarChart
- `RankingsTrendChart.tsx` – AreaChart

## Deployment

If deploying from a worktree:

```bash
cd <worktree>/frontend
npm install
npm run build
./scripts/deploy_website.sh
```

## References

- [recharts/recharts#6716](https://github.com/recharts/recharts/issues/6716) – Recharts 3: Responsive container logs incorrect warning
- [recharts/recharts#3596](https://github.com/recharts/recharts/pull/3596) – initialDimension PR (does not fix the warning in 3.x)
