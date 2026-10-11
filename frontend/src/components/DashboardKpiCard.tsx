/**
 * Dashboard KPI Card Component
 * Displays a single KPI metric with big number, unit, and trend indicator
 * Responsive design: full width on mobile, multiple columns on desktop
 * 
 * @component
 * @example
 * <DashboardKpiCard
 *   title="Total Players"
 *   value={2547}
 *   unit="players"
 *   trend={12.5}
 *   trendDirection="up"
 * />
 */

import React from 'react'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface DashboardKpiCardProps {
  /** Card title/label */
  title: string
  /** Main metric value */
  value: number | string
  /** Unit of measurement (optional) */
  unit?: string
  /** Trend percentage (optional) */
  trend?: number
  /** Trend direction: 'up' (positive), 'down' (negative), 'neutral' */
  trendDirection?: 'up' | 'down' | 'neutral'
  /** Optional icon emoji or component */
  icon?: string | React.ReactNode
  /** Optional click handler */
  onClick?: () => void
  /** Optional CSS class for custom styling */
  className?: string
}

/**
 * Determines color based on trend direction
 */
const getTrendColor = (direction?: 'up' | 'down' | 'neutral'): string => {
  switch (direction) {
    case 'up':
      return 'text-sky-500'
    case 'down':
      return 'text-red-500'
    case 'neutral':
    default:
      return 'text-slate-400'
  }
}

/**
 * Gets the appropriate trend icon based on direction
 */
const getTrendIcon = (direction?: 'up' | 'down' | 'neutral') => {
  const iconClass = `w-4 h-4 ${getTrendColor(direction)}`
  switch (direction) {
    case 'up':
      return <TrendingUp className={iconClass} />
    case 'down':
      return <TrendingDown className={iconClass} />
    case 'neutral':
    default:
      return <Minus className={iconClass} />
  }
}

export default function DashboardKpiCard({
  title,
  value,
  unit,
  trend,
  trendDirection = 'neutral',
  icon,
  onClick,
  className = '',
}: DashboardKpiCardProps) {
  return (
    <div
      onClick={onClick}
      className={`
        bg-slate-900/60 border border-slate-800 rounded-lg p-4 sm:p-6 
        hover:bg-slate-900 hover:border-sky-500/30 hover:shadow-lg hover:shadow-sky-500/10
        transition-all duration-200 flex flex-col h-full
        ${onClick ? 'cursor-pointer' : ''}
        ${className}
      `}
      role="article"
      aria-label={`${title}: ${value}${unit ? ` ${unit}` : ''}`}
    >
      {/* Header with title and icon */}
      <div className="flex items-start justify-between gap-2 mb-4 flex-shrink-0">
        <h3 className="text-xs sm:text-sm font-semibold text-slate-300 leading-tight flex-grow">
          {title}
        </h3>
        {icon && (
          <span className="text-lg sm:text-2xl flex-shrink-0 opacity-60">
            {typeof icon === 'string' ? icon : icon}
          </span>
        )}
      </div>

      {/* Main value and unit */}
      <div className="flex items-baseline gap-2 flex-wrap flex-grow mb-3">
        <p className="text-2xl sm:text-3xl lg:text-4xl font-bold text-white leading-tight">
          {typeof value === 'number' ? value.toLocaleString() : value}
        </p>
        {unit && (
          <span className="text-xs sm:text-sm font-medium text-slate-400">
            {unit}
          </span>
        )}
      </div>

      {/* Trend indicator */}
      {trend !== undefined && (
        <div className={`flex items-center gap-2 pt-3 border-t border-slate-800/50 ${getTrendColor(trendDirection)}`}>
          {getTrendIcon(trendDirection)}
          <span className="text-xs sm:text-sm font-medium">
            {trend > 0 ? '+' : ''}{trend.toFixed(1)}%
          </span>
          <span className="text-xs text-slate-500 ml-auto">
            {trendDirection === 'up' && 'vs. last month'}
            {trendDirection === 'down' && 'decrease'}
            {trendDirection === 'neutral' && 'this period'}
          </span>
        </div>
      )}
    </div>
  )
}
