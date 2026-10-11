# Alfa Rating System Dashboard - Frontend Documentation

## Overview

The Alfa Rating System Dashboard is a comprehensive React + TypeScript + Vite frontend for administering and monitoring the Alfa premium rating system. It provides real-time insights into player ratings, anomaly detection, prediction explainability, A/B testing results, and system health.

## Project Structure

```
frontend/src/
├── api/
│   ├── alfaDashboard.ts          # API client for dashboard endpoints
│   └── client.ts                 # Base axios client
├── components/
│   ├── AlfaMetricCard.tsx        # Reusable metric card component
│   ├── AlfaRatingChart.tsx       # SVG sparkline chart for rating history
│   ├── AlfaAnomalyFlag.tsx       # Anomaly flag display with icon
│   ├── AlfaFactorBreakdown.tsx   # Stacked bar for factor contributions
│   ├── AlfaComparisonCard.tsx    # Side-by-side comparison display
│   └── AlfaPlayerComparison.tsx  # Player comparison modal
├── hooks/
│   └── useAlfaRatings.ts         # Custom hooks for API data fetching
├── layouts/
│   └── AlfaDashboardLayout.tsx   # Main dashboard layout with sidebar
├── pages/
│   ├── AlfaDashboard.tsx         # Dashboard home/overview
│   ├── AlfaPlayerRatings.tsx     # Paginated player ratings table
│   ├── AlfaAnomalyAlerts.tsx     # Anomaly detection & review interface
│   ├── AlfaPredictionExplain.tsx # Prediction explainability view
│   ├── AlfaABTestResults.tsx     # A/B testing results comparison
│   ├── AlfaSystemStatus.tsx      # System health & monitoring
│   └── AlfaRatingAdjustments.tsx # Admin rating overrides
├── types/
│   └── alfa.types.ts             # TypeScript type definitions
├── __tests__/
│   ├── components/
│   │   └── AlfaComponents.test.tsx
│   └── hooks/
│       └── useAlfaRatings.test.ts
```

## Key Features

### 1. **Dashboard Overview**
- Real-time statistics (total players, new players, anomalies, system health)
- Recent anomalies feed
- System status indicators
- Quick action buttons

### 2. **Player Ratings View**
- Paginated table of all players (20 per page)
- Sortable columns: rating, games played, rating change
- Filterable by experience level
- Color-coded status badges
- Individual player detail cards with rating history

### 3. **Anomaly Detection**
- Alert cards for flagged players
- Multiple anomaly types:
  - `sudden_jump`: Unexpected rating spike
  - `winning_weak_only`: Only beats lower-rated players
  - `losing_strong_only`: Only loses to higher-rated players
  - `rating_mismatch`: Rating doesn't match observed performance
  - `variance`: Unusual win/loss variance
  - `break_dominance`: Sudden dominance change
- Review interface: Accept, Review Later, False Positive
- Severity levels: Low, Medium, High
- Statistics: anomaly rate over time, flag distribution

### 4. **Prediction Explainability**
- Search by match ID or player pair
- Win probability display with confidence
- Factor breakdown (rating gap, race to, context)
- Comparison vs Fargo baseline
- PDF export capability
- Actual result comparison (if game completed)

### 5. **A/B Testing Results**
- Side-by-side model comparison:
  - Fargo (baseline)
  - Logistic Regression
  - Alfa Full System
- Performance metrics:
  - Brier Score
  - Accuracy
  - Calibration RMSE
  - AUC-ROC
  - Log Loss
- Performance by rating gap
- Performance by player type (new, intermediate, experienced)

### 6. **System Health Monitoring**
- Component status: Model, Database, Cache
- API latency percentiles (P50, P95, P99)
- Cache hit rate and memory usage
- Predictions per hour chart
- Recent API error log
- Real-time health score

### 7. **Admin Features**
- Manual rating adjustment form
- Approval workflow (pending, approved, rejected)
- Adjustment history log
- Bulk operations (export/import)

### 8. **Player Comparison**
- Modal/page for comparing two players
- Side-by-side ratings and metrics
- Head-to-head record
- Fair-match recommendations
- Context analysis (table preference, format win rates)

## API Integration

The dashboard connects to backend endpoints via `/api/alfa/*`:

```typescript
// Player Ratings
GET /api/alfa/players
GET /api/alfa/players/{id}
GET /api/alfa/players/{id}/history

// Anomalies
GET /api/alfa/anomalies
POST /api/alfa/anomalies/{id}/review
GET /api/alfa/anomalies/statistics

// Predictions
GET /api/alfa/explain
POST /api/alfa/predict
POST /api/alfa/export/prediction-pdf

// A/B Testing
GET /api/alfa/ab-test/results

// System
GET /api/alfa/system/status
GET /api/alfa/system/health

// Admin
GET /api/alfa/admin/adjustments
POST /api/alfa/admin/adjustments
POST /api/alfa/admin/adjustments/{id}/approve
POST /api/alfa/admin/adjustments/{id}/reject

// Bulk Operations
GET /api/alfa/export/ratings
POST /api/alfa/import/adjustments
POST /api/alfa/notify/players

// Dashboard
GET /api/alfa/dashboard/stats
```

## Component API

### AlfaMetricCard

```tsx
<AlfaMetricCard
  title="Total Players"
  value={1234}
  change={{ value: 5, percentage: false }}
  icon={<Users className="w-5 h-5" />}
  color="default" | "success" | "warning" | "danger"
  loading={false}
  onClick={() => {}}
  subtitle="Optional subtitle"
/>
```

### AlfaRatingChart

```tsx
<AlfaRatingChart
  data={ratingHistoryPoints}
  height={40}
  width={100}
  showLabels={false}
  trend="up" | "down" | "neutral"
/>
```

### AlfaAnomalyFlag

```tsx
<AlfaAnomalyFlag
  flag={anomalyFlag}
  compact={false} // true for inline badge
/>
```

### AlfaFactorBreakdown

```tsx
<AlfaFactorBreakdown
  factors={{
    rating_gap_contribution: 50,
    race_to_contribution: 30,
    context_contribution: 20,
  }}
  showPercentage={true}
  colors={{
    rating_gap_contribution: '#0ea5e9',
    // ...
  }}
/>
```

### AlfaComparisonCard

```tsx
<AlfaComparisonCard
  title="Ratings & Progress"
  leftLabel="Player 1"
  rightLabel="Player 2"
  items={[
    {
      label: 'Current Rating',
      left: 1500,
      right: 1600,
      highlight: true,
      format: (val) => `${val.toFixed(1)}`,
    },
    // ...
  ]}
  leftColor="bg-slate-700"
  rightColor="bg-slate-700"
/>
```

## Custom Hooks

### useAlfaPlayerRatings

```tsx
const { data, isLoading, isError } = useAlfaPlayerRatings({
  page: 1,
  page_size: 20,
  sort_by: 'rating',
  sort_order: 'desc',
  experience_level: 'all',
})
```

### useAlfaAnomalies

```tsx
const { data, isLoading } = useAlfaAnomalies({
  page: 1,
  page_size: 15,
  severity: 'high',
  flag_type: 'sudden_jump',
  date_range_days: 7,
})
```

### useAlfaDashboardStats

```tsx
const { data: stats } = useAlfaDashboardStats()
// Returns: { total_players, new_players, anomalies_detected, predictions_today, avg_rating_change, system_health_score }
```

### useAlfaSystemStatus

```tsx
const { data: status } = useAlfaSystemStatus()
// Refetches every 30 seconds for real-time updates
```

### useAlfaPredictionExplain

```tsx
const { data: prediction } = useAlfaPredictionExplain(matchId, playerId1, playerId2)
```

### Mutation Hooks

```tsx
// Review anomalies
const { mutate: reviewAnomaly } = useAlfaReviewAnomaly()
reviewAnomaly({ playerId, status: 'accepted' | 'false_positive' | 'review_later' })

// Export ratings
const { mutate: exportRatings } = useAlfaExportRatings('csv' | 'json')

// Make predictions
const { mutate: predictMatch } = useAlfaPredictMatch()

// Admin adjustments
const { mutate: submitAdjustment } = useAlfaSubmitAdjustment()
const { mutate: approveAdjustment } = useAlfaApproveAdjustment()
const { mutate: rejectAdjustment } = useAlfaRejectAdjustment()
```

## Type Definitions

Key types available in `@/types/alfa.types`:

```typescript
interface AlfaPlayer {
  player_id: string
  name: string
  current_rating: number
  fargo_equivalent: number
  games_played: number
  rating_change?: number
  experience_level: 'new' | 'intermediate' | 'experienced'
  converged_percentage: number
  is_anomaly: boolean
}

interface AnomalyAlert {
  player_id: string
  name: string
  anomaly_score: number // 0-1 scale
  severity: 'low' | 'medium' | 'high'
  flags: AnomalyFlag[]
  review_status: 'pending' | 'accepted' | 'false_positive' | 'review_later'
}

interface PredictionExplanation {
  match_id: string
  operator: { id, name, rating }
  player2: { id, name, rating }
  predicted_probability: { operator_win, player2_win, confidence }
  factors: { rating_gap_contribution, race_to_contribution, context_contribution }
}
```

## Styling

- **Theme**: Dark mode (slate-950, slate-800, slate-700 backgrounds)
- **Accent Colors**: 
  - Primary: Sky-500 (sky-400 text)
  - Success: Emerald-500
  - Warning: Yellow/Orange-500
  - Danger: Red-500
- **Typography**: Inter font (via Tailwind)
- **Responsive**: Mobile-first design with md/lg breakpoints

## Testing

Run tests with:

```bash
npm run test
```

Test coverage includes:
- Component rendering and props
- User interactions (clicks, form submissions)
- API call integration (with mocked axios)
- Loading and error states
- React Hook behavior (useQuery, useMutation)

**Target coverage**: 80%+

## Performance Optimizations

1. **React Query Caching**:
   - Player ratings: 5 minute cache
   - System status: 30 second cache + auto-refetch
   - Predictions: 30 minute cache

2. **Code Splitting**: Pages lazy-loaded via React.lazy()

3. **Memoization**: Components use React.memo for expensive renders

4. **Debounced Searches**: API calls debounced to prevent spam

## Browser Support

- Chrome/Edge (latest 2 versions)
- Firefox (latest 2 versions)
- Safari 14+

## Deployment

Build the dashboard:

```bash
cd frontend
npm install
npm run build
```

The built files in `dist/` are served by the Nginx reverse proxy.

## Environment Variables

```env
VITE_API_URL=/api           # API base URL
VITE_API_KEY=               # Optional API key for endpoints
```

## Troubleshooting

### "API call failed" errors
- Check VITE_API_URL is correctly configured
- Verify backend API endpoints are available
- Check Authorization token in sessionStorage

### Chart not rendering
- Ensure data meets minimum requirements (2+ data points)
- Check browser DevTools console for SVG errors

### Performance issues
- Check React DevTools Profiler for slow renders
- Verify API response times aren't causing hangs
- Look for N+1 query problems in useEffect dependencies

## Future Enhancements

1. WebSocket support for real-time updates
2. Advanced charting with Recharts
3. Dark/light theme toggle
4. User preferences/saved filters
5. Audit logging for admin actions
6. Advanced anomaly detection visualization
7. Mobile app (React Native)
8. Email alerts for high-severity anomalies
