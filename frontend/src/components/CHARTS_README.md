# Dashboard Chart Components

This directory contains reusable Recharts-based visualization components for the Rankings Bot dashboard.

## Components

### RankingsTrendChart
**File:** `RankingsTrendChart.tsx`

Line chart showing rating trends for top 10 players over time.

**Props:**
- `data: Array<{date, player, rating}>` - Array of data points
- `title?: string` - Chart title (default: "Player Ranking Trends")
- `height?: number` - Chart height in pixels (default: 300)
- `showLegend?: boolean` - Display legend (default: true)
- `responsive?: boolean` - Use ResponsiveContainer (default: true)

**Example:**
```tsx
<RankingsTrendChart
  data={[
    { date: '2026-01-01', player: 'Alice', rating: 1500 },
    { date: '2026-01-02', player: 'Alice', rating: 1510 },
  ]}
  title="Player Trends"
  height={300}
/>
```

**Features:**
- Automatically selects top 10 players by average rating
- Color-coded lines for each player
- Interactive tooltips
- Responsive sizing

### WinRateDistribution
**File:** `WinRateDistribution.tsx`

Bar chart displaying win rate or player distribution by rating range.

**Props:**
- `data: Array<{ratingRange, winRate}>` - Array of rating range data
- `title?: string` - Chart title (default: "Win Rate by Rating Range")
- `height?: number` - Chart height in pixels (default: 300)
- `format?: 'percent' | 'ratio'` - Display format (default: 'percent')

**Example:**
```tsx
<WinRateDistribution
  data={[
    { ratingRange: '0-500', winRate: 0.45 },
    { ratingRange: '500-1000', winRate: 0.52 },
  ]}
  title="Win Rate Distribution"
  format="percent"
/>
```

**Features:**
- Stacked bar chart with optional formatting
- Customizable rating ranges
- Interactive tooltips with formatted values

### TournamentActivityHeatmap
**File:** `TournamentActivityHeatmap.tsx`

Calendar-style heatmap showing tournament participation by month/week.

**Props:**
- `data: Array<{month, week, count}>` - Heatmap data points
- `title?: string` - Chart title (default: "Tournament Activity")
- `width?: number` - SVG width in pixels (default: 800)
- `height?: number` - SVG height in pixels (default: 300)
- `maxCount?: number` - Max count for color scaling (auto-calculated if omitted)

**Example:**
```tsx
<TournamentActivityHeatmap
  data={[
    { month: 1, week: 1, count: 2 },
    { month: 1, week: 2, count: 3 },
  ]}
  title="Tournament Schedule"
/>
```

**Features:**
- Color scale from white (none) to sky-500 (high)
- Interactive tooltips on hover
- Built-in legend
- Month and week labels

### PlayerComparisonChart
**File:** `PlayerComparisonChart.tsx`

Radar chart for comparing statistics between two players.

**Props:**
- `operator: PlayerStats` - First player object
- `player2: PlayerStats` - Second player object
- `title?: string` - Chart title (default: "Player Comparison")
- `height?: number` - Chart height in pixels (default: 400)
- `metrics?: Array<{key, label, max}>` - Custom metrics (auto-defaults to rating/wins/tournaments)

**Example:**
```tsx
<PlayerComparisonChart
  operator={{ name: 'Alice', rating: 1500, wins: 100, tournaments: 20 }}
  player2={{ name: 'Bob', rating: 1400, wins: 80, tournaments: 18 }}
  title="Player Comparison"
/>
```

**Features:**
- Radar chart visualization
- Normalized scaling (0-100% scale)
- Comparison table below chart
- Calculates differences and highlights winners

## Export Utilities

**File:** `utils/exportUtils.ts`

### Functions

#### `exportToCsv(data, filename)`
Exports array of objects to CSV format and triggers download.

```tsx
import { exportToCsv } from '@/utils/exportUtils'

const players = [
  { name: 'Alice', rating: 1500, rank: 1 },
  { name: 'Bob', rating: 1400, rank: 2 },
]
exportToCsv(players, 'rankings')
// Downloads: rankings.csv
```

#### `exportToJson(data, filename)`
Exports array of objects to JSON format and triggers download.

```tsx
import { exportToJson } from '@/utils/exportUtils'

exportToJson(players, 'rankings')
// Downloads: rankings.json
```

#### `getExportFilename(baseFilename, date?)`
Generates a timestamp-based filename.

```tsx
import { getExportFilename } from '@/utils/exportUtils'

const filename = getExportFilename('rankings')
// Returns: "rankings_2026-02-16_103045"
```

## Styling

All components use:
- **Color scheme:** Tailwind CSS (slate-950, slate-800, sky-500)
- **Background:** `bg-slate-800` with `border-slate-700`
- **Text:** `text-white`, `text-slate-400` for secondary
- **Accent:** `sky-500` for primary elements

## Integration

### In Rankings Page
```tsx
import RankingsTrendChart from '@/components/RankingsTrendChart'
import WinRateDistribution from '@/components/WinRateDistribution'
import { exportToCsv } from '@/utils/exportUtils'

// In component
<RankingsTrendChart data={trendData} />
<WinRateDistribution data={rateData} />
<button onClick={() => exportToCsv(rankings, 'rankings')}>
  Export CSV
</button>
```

### In Admin Settings
```tsx
import PlayerComparisonChart from '@/components/PlayerComparisonChart'
import TournamentActivityHeatmap from '@/components/TournamentActivityHeatmap'

// Show KPI dashboard with charts
<PlayerComparisonChart operator={p1} player2={p2} />
<TournamentActivityHeatmap data={schedule} />
```

## Performance Notes

- Charts are fully responsive and use `ResponsiveContainer` from Recharts
- Large datasets (>1000 points) should paginate or aggregate data
- Export functions check for size limits (100MB) to prevent browser crashes
- CSV export handles special characters and escaping

## Quality

Use `npm run lint` and manual verification in the app; the repo does not ship a frontend unit-test suite.

## Accessibility

- ARIA labels on interactive elements
- Color-blind friendly palette (uses shapes + colors)
- Keyboard navigation support
- Semantic HTML structure

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers (iOS Safari, Chrome Android)

## Future Enhancements

- [ ] PDF export with charts using @react-pdf/renderer
- [ ] Custom date range picker for trend charts
- [ ] Real-time data updates via WebSocket
- [ ] Advanced filtering and aggregation
- [ ] Chart customization UI
