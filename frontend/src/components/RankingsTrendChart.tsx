/**
 * Rankings Trend Chart Component
 * Displays rating trends for top 10 players over time using Recharts
 * Supports multi-year historical data with year filtering
 */

import { useMemo, useState } from 'react'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

interface TrendDataPoint {
  date: string
  [playerName: string]: string | number | null
}

interface RankingsTrendChartProps {
  /** Array of data points with date and player ratings */
  data: Array<{
    date: string
    player: string
    rating: number
  }> | TrendDataPoint[]
  /** Title of the chart */
  title?: string
  /** Height in pixels */
  height?: number
  /** Show legend */
  showLegend?: boolean
  /** Responsive container */
  responsive?: boolean
  /** Available years for filtering (if applicable) */
  availableYears?: number[]
  /** Ordered list of player names (from API) - ensures consistent colors */
  playerNames?: string[]
}

const COLORS = [
  '#0ea5e9', // sky-500
  '#06b6d4', // cyan-500
  '#10b981', // emerald-500
  '#f59e0b', // amber-500
  '#ef4444', // red-500
  '#8b5cf6', // violet-500
  '#ec4899', // pink-500
  '#14b8a6', // teal-500
  '#3b82f6', // blue-500
  '#f97316', // orange-500
]

/**
 * RankingsTrendChart - Area chart showing how top players' ratings change over time
 * Supports both flat data format and pre-aggregated historical format
 * @param props Component props
 * @returns Rendered chart component
 */
export default function RankingsTrendChart({
  data,
  title = 'Player Ranking Trends',
  height = 300,
  showLegend = true,
  responsive = true,
  availableYears = [],
  playerNames = [],
}: RankingsTrendChartProps) {
  const [selectedYear, setSelectedYear] = useState<number | null>(null)

  // Transform data and detect format (flat vs historical)
  const { chartData, topPlayers } = useMemo(() => {
    if (!Array.isArray(data) || data.length === 0) {
      return { chartData: [], topPlayers: [] }
    }

    // Check if this is flat format (date, player, rating) or historical format (date, playerName: rating)
    const firstEntry = data[0] as any
    const isFlat = 'player' in firstEntry && 'rating' in firstEntry && !('date' in firstEntry && typeof firstEntry.date === 'string' && Object.keys(firstEntry).length > 2)
    
    if (isFlat) {
      // Flat format: convert to historical format
      const dateMap = new Map<string, Record<string, number>>()
      
      for (const entry of data as any[]) {
        if (!dateMap.has(entry.date)) {
          dateMap.set(entry.date, {})
        }
        const dateData = dateMap.get(entry.date)!
        dateData[entry.player] = entry.rating
      }

      const transformed = Array.from(dateMap.entries())
        .map(([date, players]) => ({
          date,
          ...players,
        } as TrendDataPoint))
        .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

      // Get top players by average rating
      const playerRatings = new Map<string, number[]>()
      for (const entry of data as any[]) {
        if (!playerRatings.has(entry.player)) {
          playerRatings.set(entry.player, [])
        }
        const ratings = playerRatings.get(entry.player)!
        if (entry.rating) ratings.push(entry.rating)
      }

      const topPlayersList = Array.from(playerRatings.entries())
        .map(([player, ratings]) => ({
          player,
          avgRating: ratings.reduce((a, b) => a + b, 0) / ratings.length,
        }))
        .sort((a, b) => b.avgRating - a.avgRating)
        .slice(0, 10)
        .map((p) => p.player)

      return { chartData: transformed, topPlayers: topPlayersList }
    } else {
      // Historical format: already aggregated by date (from API)
      const transformed = (data as TrendDataPoint[])
        .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())

      // Use provided playerNames (from API) for consistent ordering and coloring
      // If not provided, extract from data keys (fallback)
      let orderedPlayers = playerNames
      if (!orderedPlayers || orderedPlayers.length === 0) {
        const playerSet = new Set<string>()
        for (const entry of transformed) {
          for (const key of Object.keys(entry)) {
            if (key !== 'date') {
              playerSet.add(key)
            }
          }
        }
        orderedPlayers = Array.from(playerSet)
      }

      return { chartData: transformed, topPlayers: orderedPlayers }
    }
  }, [data])

  // Filter by year if selected
  const filteredChartData = useMemo(() => {
    if (!selectedYear || chartData.length === 0) {
      return chartData
    }
    
    return chartData.filter((entry) => {
      const year = new Date(entry.date).getFullYear()
      return year === selectedYear
    })
  }, [chartData, selectedYear])

  if (chartData.length === 0) {
    return (
      <div className="w-full p-6 bg-slate-800 rounded-lg border border-slate-700 text-center">
        <p className="text-slate-400 text-sm">{title} - No data available</p>
      </div>
    )
  }

  const Chart = (
    <ResponsiveContainer width="100%" height={height} minWidth={200} minHeight={200}>
      <AreaChart data={filteredChartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
        <XAxis
          dataKey="date"
          tick={{ fill: '#cbd5e1', fontSize: 12 }}
          stroke="#64748b"
        />
        <YAxis
          tick={{ fill: '#cbd5e1', fontSize: 12 }}
          stroke="#64748b"
          label={{ value: 'Rating', angle: -90, position: 'insideLeft' }}
        />
        <Tooltip
          contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569' }}
          labelStyle={{ color: '#cbd5e1' }}
          formatter={(value) => typeof value === 'number' ? value.toFixed(1) : value === null ? 'N/A' : value}
        />
        {showLegend && (
          <Legend
            wrapperStyle={{ paddingTop: '20px' }}
            iconType="line"
          />
        )}
        {topPlayers.map((player, index) => (
          <Area
            key={player}
            type="monotone"
            dataKey={player}
            stroke={COLORS[index % COLORS.length]}
            fill={COLORS[index % COLORS.length]}
            fillOpacity={0.3}
            dot={false}
            isAnimationActive={false}
            strokeWidth={2}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  )

  return (
    <div className="w-full p-6 bg-slate-800 rounded-lg border border-slate-700">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        {availableYears && availableYears.length > 0 && (
          <div className="flex gap-2">
            <button
              onClick={() => setSelectedYear(null)}
              className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                selectedYear === null
                  ? 'bg-sky-600 text-white'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
              }`}
            >
              All
            </button>
            {availableYears.map((year) => (
              <button
                key={year}
                onClick={() => setSelectedYear(year)}
                className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                  selectedYear === year
                    ? 'bg-sky-600 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                {year}
              </button>
            ))}
          </div>
        )}
      </div>
      {responsive ? Chart : (
        <div style={{ width: '100%', height }}>
          {Chart}
        </div>
      )}
    </div>
  )
}
