/**
 * Win Rate Distribution Component
 * Displays win rate by rating range using Recharts BarChart
 */

import { useMemo } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface WinRateDataPoint {
  ratingRange: string
  winRate: number
}

interface WinRateDistributionProps {
  /** Array of win rate data points */
  data: WinRateDataPoint[]
  /** Title of the chart */
  title?: string
  /** Height in pixels */
  height?: number
  /** Format for display (e.g. '%' or 'ratio') */
  format?: 'percent' | 'ratio'
}

/**
 * WinRateDistribution - Bar chart showing win rate by rating range
 * @param props Component props
 * @returns Rendered chart component
 */
export default function WinRateDistribution({
  data,
  title = 'Win Rate by Rating Range',
  height = 300,
  format = 'percent',
}: WinRateDistributionProps) {
  // Prepare data with formatted values
  const chartData = useMemo(() => {
    if (!Array.isArray(data) || data.length === 0) {
      return []
    }

    return data.map((item) => ({
      ...item,
      displayValue: format === 'percent' ? item.winRate * 100 : item.winRate,
    }))
  }, [data, format])

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
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
          <XAxis
            dataKey="ratingRange"
            tick={{ fill: '#cbd5e1', fontSize: 12 }}
            stroke="#64748b"
          />
          <YAxis
            tick={{ fill: '#cbd5e1', fontSize: 12 }}
            stroke="#64748b"
            label={{
              value: format === 'percent' ? 'Win Rate (%)' : 'Win Rate',
              angle: -90,
              position: 'insideLeft',
            }}
          />
          <Tooltip
            contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569' }}
            labelStyle={{ color: '#cbd5e1' }}
            formatter={(value) => {
              if (typeof value !== 'number') return value
              return format === 'percent' ? `${value.toFixed(1)}%` : value.toFixed(3)
            }}
          />
          <Bar dataKey="displayValue" fill="#0ea5e9" radius={[8, 8, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
