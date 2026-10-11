/**
 * Tournament Activity Heatmap Component
 * Displays tournament participation over time using a calendar-style heatmap
 */

import { useMemo } from 'react'
import type { ReactNode } from 'react'

interface HeatmapDataPoint {
  month: number // 1-12
  week: number // 1-4
  count: number
}

interface TournamentActivityHeatmapProps {
  /** Array of heatmap data points (month, week, count) */
  data: HeatmapDataPoint[]
  /** Title of the chart */
  title?: string | ReactNode
  /** Optional plain-text title for empty states */
  titleText?: string
  /** Width in pixels */
  width?: number
  /** Height in pixels */
  height?: number
  /** Max count for color scaling */
  maxCount?: number
}

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/**
 * Get color based on activity count (white to sky-500 gradient)
 */
function getColorForCount(count: number, maxCount: number): string {
  if (count === 0) return '#f8fafc' // slate-50
  if (maxCount === 0) return '#0ea5e9' // sky-500

  const ratio = Math.min(count / maxCount, 1)

  // Gradient from white to sky-500
  if (ratio < 0.25) return '#e0f2fe' // sky-pool_opt_in
  if (ratio < 0.5) return '#bae6fd' // sky-200
  if (ratio < 0.75) return '#7dd3fc' // sky-300
  return '#0ea5e9' // sky-500
}

/**
 * TournamentActivityHeatmap - Calendar-style heatmap of tournament activity
 * @param props Component props
 * @returns Rendered heatmap component
 */
export default function TournamentActivityHeatmap({
  data,
  title = 'Tournament Activity',
  titleText = 'Tournament Activity',
  width = 800,
  height = 300,
  maxCount: providedMaxCount,
}: TournamentActivityHeatmapProps) {
  const resolvedTitleText = typeof title === 'string' ? title : titleText
  // Calculate max count and organize data
  const { gridData, maxCount } = useMemo(() => {
    if (!Array.isArray(data) || data.length === 0) {
      return { gridData: new Map<string, number>(), maxCount: 1 }
    }

    const map = new Map<string, number>()
    let max = providedMaxCount ?? 0

    data.forEach(({ month, week, count }) => {
      const key = `${month}-${week}`
      map.set(key, count)
      if (!providedMaxCount && count > max) {
        max = count
      }
    })

    return {
      gridData: map,
      maxCount: (providedMaxCount !== undefined) ? providedMaxCount : (max || 1),
    }
  }, [data, providedMaxCount])

  if (gridData.size === 0) {
    return (
      <div className="w-full p-6 bg-slate-800 rounded-lg border border-slate-700 text-center">
        <p className="text-slate-400 text-sm">{resolvedTitleText} - No data available</p>
      </div>
    )
  }

  const cellWidth = 30
  const cellHeight = 30
  const cellPadding = 2
  const labelWidth = 40
  const labelHeight = 20

  return (
    <div className="w-full p-6 bg-slate-800 rounded-lg border border-slate-700 overflow-x-auto">
      <h3 className="text-lg font-semibold text-white mb-4">{title}</h3>

      <svg width={width} height={height} className="min-w-full">
        {/* Month labels */}
        {MONTH_NAMES.map((month, index) => (
          <text
            key={`label-${month}`}
            x={labelWidth + (index + 0.5) * (cellWidth + cellPadding)}
            y={labelHeight - 5}
            textAnchor="middle"
            className="text-xs font-semibold fill-slate-300"
          >
            {month}
          </text>
        ))}

        {/* Week labels and cells */}
        {[1, 2, 3, 4].map((week) => (
          <g key={`week-${week}`}>
            <text
              x={labelWidth - 10}
              y={labelHeight + (week + 0.5) * (cellHeight + cellPadding) + 4}
              textAnchor="end"
              className="text-xs font-semibold fill-slate-300"
            >
              W{week}
            </text>

            {MONTH_NAMES.map((_, monthIndex) => {
              const month = monthIndex + 1
              const key = `${month}-${week}`
              const count = gridData.get(key) ?? 0
              const color = getColorForCount(count, maxCount)
              const x = labelWidth + monthIndex * (cellWidth + cellPadding)
              const y = labelHeight + week * (cellHeight + cellPadding)

              return (
                <g key={key}>
                  <rect
                    x={x}
                    y={y}
                    width={cellWidth}
                    height={cellHeight}
                    fill={color}
                    stroke="#94a3b8"
                    strokeWidth="1"
                    rx="2"
                    className="cursor-pointer hover:opacity-80 transition-opacity"
                  />
                  <title>{`${MONTH_NAMES[monthIndex]} Week ${week}: ${count} tournament(s)`}</title>
                  {count > 0 && (
                    <text
                      x={x + cellWidth / 2}
                      y={y + cellHeight / 2}
                      textAnchor="middle"
                      dominantBaseline="middle"
                      className="text-xs font-semibold fill-slate-700"
                    >
                      {count}
                    </text>
                  )}
                </g>
              )
            })}
          </g>
        ))}
      </svg>

      {/* Legend */}
      <div className="mt-4 flex items-center gap-4 text-xs text-slate-300">
        <span className="font-semibold">Scale:</span>
        <div className="flex gap-2 items-center">
          <div className="w-4 h-4 bg-slate-50 border border-slate-400 rounded" />
          <span>None</span>
        </div>
        <div className="flex gap-2 items-center">
          <div className="w-4 h-4 bg-sky-200 border border-slate-400 rounded" />
          <span>Low</span>
        </div>
        <div className="flex gap-2 items-center">
          <div className="w-4 h-4 bg-sky-300 border border-slate-400 rounded" />
          <span>Medium</span>
        </div>
        <div className="flex gap-2 items-center">
          <div className="w-4 h-4 bg-sky-500 border border-slate-400 rounded" />
          <span>High</span>
        </div>
      </div>
    </div>
  )
}
