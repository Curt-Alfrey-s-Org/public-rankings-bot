/**
 * Player Comparison Chart Component
 * Displays comparison between two players using a radar chart
 */

import { useMemo } from 'react'
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend, Tooltip, ResponsiveContainer } from 'recharts'

interface PlayerStats {
  name: string
  rating: number
  wins: number
  tournaments: number
  [key: string]: string | number
}

interface PlayerComparisonChartProps {
  /** First player stats */
  operator: PlayerStats
  /** Second player stats */
  player2: PlayerStats
  /** Title of the chart */
  title?: string
  /** Height in pixels */
  height?: number
  /** Which metrics to compare */
  metrics?: Array<{
    key: keyof PlayerStats
    label: string
    max: number
  }>
}

/**
 * PlayerComparisonChart - Radar chart comparing two players
 * @param props Component props
 * @returns Rendered chart component
 */
export default function PlayerComparisonChart({
  operator,
  player2,
  title = 'Player Comparison',
  height = 400,
  metrics,
}: PlayerComparisonChartProps) {
  // Default metrics if not provided
  const defaultMetrics: Array<{ key: keyof PlayerStats; label: string; max: number }> = [
    { key: 'rating', label: 'Rating', max: Math.max(operator.rating ?? 0, player2.rating ?? 0) * 1.1 || 1000 },
    { key: 'wins', label: 'Wins', max: Math.max(operator.wins ?? 0, player2.wins ?? 0) * 1.1 || 100 },
    { key: 'tournaments', label: 'Tournaments', max: Math.max(operator.tournaments ?? 0, player2.tournaments ?? 0) * 1.1 || 50 },
  ]

  const comparisonMetrics = metrics || defaultMetrics

  // Prepare chart data
  const chartData = useMemo(() => {
    return comparisonMetrics.map(({ key, label, max }) => ({
      metric: label,
      [operator.name]: Math.min(((operator[key] as number) ?? 0) / max, 1) * 100,
      [player2.name]: Math.min(((player2[key] as number) ?? 0) / max, 1) * 100,
      fullMetric: `${label} (0-${max})`,
    }))
  }, [operator, player2, comparisonMetrics])

  if (chartData.length === 0) {
    return (
      <div className="w-full p-6 bg-slate-800 rounded-lg border border-slate-700 text-center">
        <p className="text-slate-400 text-sm">{title} - No data available</p>
      </div>
    )
  }

  return (
    <div className="w-full p-6 bg-slate-800 rounded-lg border border-slate-700">
      <h3 className="text-lg font-semibold text-white mb-4">{title}</h3>

      <ResponsiveContainer width="100%" height={height} minWidth={200} minHeight={200}>
        <RadarChart data={chartData}>
          <PolarGrid stroke="#475569" />
          <PolarAngleAxis
            dataKey="metric"
            tick={{ fill: '#cbd5e1', fontSize: 12 }}
          />
          <PolarRadiusAxis
            tick={{ fill: '#cbd5e1', fontSize: 11 }}
            domain={[0, 100]}
          />
          <Radar
            name={operator.name}
            dataKey={operator.name}
            stroke="#0ea5e9"
            fill="#0ea5e9"
            fillOpacity={0.25}
            isAnimationActive={false}
          />
          <Radar
            name={player2.name}
            dataKey={player2.name}
            stroke="#10b981"
            fill="#10b981"
            fillOpacity={0.25}
            isAnimationActive={false}
          />
          <Tooltip
            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569' }}
            labelStyle={{ color: '#cbd5e1' }}
            formatter={(value) => typeof value === 'number' ? `${value.toFixed(1)}%` : value}
          />
          <Legend
            wrapperStyle={{ paddingTop: '20px' }}
            iconType="circle"
          />
        </RadarChart>
      </ResponsiveContainer>

      {/* Stats comparison table */}
      <div className="mt-6 overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-slate-700">
              <th className="text-left px-3 py-2 text-slate-300 font-semibold">Metric</th>
              <th className="text-right px-3 py-2 text-slate-300 font-semibold">{operator.name}</th>
              <th className="text-right px-3 py-2 text-slate-300 font-semibold">{player2.name}</th>
              <th className="text-right px-3 py-2 text-slate-300 font-semibold">Difference</th>
            </tr>
          </thead>
          <tbody>
            {comparisonMetrics.map(({ key, label }) => {
              const val1 = operator[key] as number
              const val2 = player2[key] as number
              const diff = (val1 ?? 0) - (val2 ?? 0)
              const winner = diff > 0 ? 1 : diff < 0 ? 2 : 0

              return (
                <tr key={String(key)} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                  <td className="text-left px-3 py-2 text-slate-300">{label}</td>
                  <td className={`text-right px-3 py-2 font-semibold ${winner === 1 ? 'text-sky-400' : 'text-slate-400'}`}>
                    {typeof val1 === 'number' ? val1.toFixed(1) : val1}
                  </td>
                  <td className={`text-right px-3 py-2 font-semibold ${winner === 2 ? 'text-emerald-400' : 'text-slate-400'}`}>
                    {typeof val2 === 'number' ? val2.toFixed(1) : val2}
                  </td>
                  <td className={`text-right px-3 py-2 font-semibold ${diff > 0 ? 'text-sky-400' : diff < 0 ? 'text-emerald-400' : 'text-slate-400'}`}>
                    {diff > 0 ? '+' : ''}{typeof diff === 'number' ? diff.toFixed(1) : diff}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
