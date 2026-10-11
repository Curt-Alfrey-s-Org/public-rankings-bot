/**
 * Reusable metric card component for displaying Alfa dashboard statistics
 */

import React from 'react'

export interface MetricCardProps {
  title: string
  value: string | number
  change?: {
    value: number
    percentage: boolean
  }
  icon?: React.ReactNode
  color?: 'default' | 'success' | 'warning' | 'danger'
  loading?: boolean
  onClick?: () => void
  subtitle?: string
}

const colorClasses = {
  default: 'bg-slate-800 border-slate-700',
  success: 'bg-slate-800 border-emerald-600',
  warning: 'bg-slate-800 border-yellow-600',
  danger: 'bg-slate-800 border-red-600',
}

const textColorClasses = {
  default: 'text-sky-400',
  success: 'text-emerald-400',
  warning: 'text-yellow-400',
  danger: 'text-red-400',
}

export const AlfaMetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  change,
  icon,
  color = 'default',
  loading = false,
  onClick,
  subtitle,
}) => {
  if (loading) {
    return (
      <div className={`p-6 rounded-lg border ${colorClasses[color]} animate-pulse`}>
        <div className="h-4 bg-slate-700 rounded w-24 mb-4" />
        <div className="h-8 bg-slate-700 rounded w-16" />
      </div>
    )
  }

  return (
    <div
      className={`p-6 rounded-lg border ${colorClasses[color]} transition-colors hover:border-opacity-pool_opt_in ${
        onClick ? 'cursor-pointer hover:bg-slate-700' : ''
      }`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <p className="text-sm font-medium text-slate-400">{title}</p>
          {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
        </div>
        {icon && <div className={`text-xl ${textColorClasses[color]}`}>{icon}</div>}
      </div>

      <div className="flex items-baseline gap-3">
        <p className={`text-2xl font-bold ${textColorClasses[color]}`}>{value}</p>
        {change && (
          <span
            className={`text-sm font-medium ${
              change.value >= 0 ? 'text-emerald-400' : 'text-red-400'
            }`}
          >
            {change.value >= 0 ? '+' : ''}
            {change.value}
            {change.percentage ? '%' : ''}
          </span>
        )}
      </div>
    </div>
  )
}

export default AlfaMetricCard
