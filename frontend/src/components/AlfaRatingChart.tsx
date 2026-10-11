/**
 * Rating chart component - sparkline-style visualization
 */

import React, { useMemo } from 'react'
import type { RatingHistoryPoint } from '@/types/alfa.types'

export interface RatingChartProps {
  data: RatingHistoryPoint[]
  height?: number
  width?: number
  showLabels?: boolean
  trend?: 'up' | 'down' | 'neutral'
}

export const AlfaRatingChart: React.FC<RatingChartProps> = ({
  data,
  height = 40,
  width = 100,
  showLabels = false,
  trend,
}) => {
  const { minRating, maxRating, points, svgPoints } = useMemo(() => {
    if (!data || data.length === 0) {
      return { minRating: 0, maxRating: 1, points: [], svgPoints: '' }
    }

    const ratings = data.map((p) => p.rating)
    const min = Math.min(...ratings)
    const max = Math.max(...ratings)
    const range = max - min || 1

    const padding = 4
    const graphWidth = width - padding * 2
    const graphHeight = height - padding * 2

    const points = data.map((point, index) => ({
      x: (index / (data.length - 1)) * graphWidth + padding,
      y: height - padding - ((point.rating - min) / range) * graphHeight,
      rating: point.rating,
    }))

    const svgPoints = points.map((p) => `${p.x},${p.y}`).join(' ')

    return {
      minRating: min,
      maxRating: max,
      points,
      svgPoints,
    }
  }, [data, height, width])

  if (data.length < 2) {
    return (
      <svg width={width} height={height} className="w-full">
        <text x="50%" y="50%" textAnchor="middle" dy="0.3em" className="text-xs fill-slate-500">
          No data
        </text>
      </svg>
    )
  }

  const trendColor =
    trend === 'up' ? '#10b981' : trend === 'down' ? '#ef4444' : '#0ea5e9'

  return (
    <svg width={width} height={height} className="w-full" viewBox={`0 0 ${width} ${height}`}>
      {/* Grid lines */}
      <line x1="0" y1={height / 2} x2={width} y2={height / 2} stroke="#475569" strokeWidth="0.5" />

      {/* Line */}
      <polyline
        points={svgPoints}
        fill="none"
        stroke={trendColor}
        strokeWidth="1.5"
        vectorEffect="non-scaling-stroke"
      />

      {/* Points */}
      {points.map((point, index) => (
        <circle
          key={index}
          cx={point.x}
          cy={point.y}
          r="1.5"
          fill={trendColor}
          opacity={index === points.length - 1 ? 1 : 0.5}
        />
      ))}

      {/* Labels */}
      {showLabels && (
        <>
          <text x="2" y="12" className="text-xs fill-slate-500">
            {maxRating.toFixed(0)}
          </text>
          <text x="2" y={height - 2} className="text-xs fill-slate-500">
            {minRating.toFixed(0)}
          </text>
        </>
      )}
    </svg>
  )
}

export default AlfaRatingChart
