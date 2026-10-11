/**
 * Stats Summary Component
 * Displays 4-6 KPI cards in a responsive grid
 * Mobile: 1 column, Tablet: 2 columns, Desktop: 3-4 columns
 * 
 * @component
 * @example
 * <StatsSummary
 *   stats={[
 *     { label: 'Total Players', value: 2547, trend: 12.5 },
 *     { label: 'Active Tournaments', value: 24, trend: -5 }
 *   ]}
 * />
 */

import DashboardKpiCard from './DashboardKpiCard'

interface Stat {
  label: string
  value: number | string
  unit?: string
  trend?: number
  trendDirection?: 'up' | 'down' | 'neutral'
  icon?: string
}

interface StatsSummaryProps {
  /** Array of statistics to display */
  stats: Stat[]
  /** Optional title for the section */
  title?: string
  /** Optional CSS class */
  className?: string
}

export default function StatsSummary({
  stats,
  title,
  className = '',
}: StatsSummaryProps) {
  return (
    <section className={`space-y-4 ${className}`}>
      {title && (
        <h2 className="text-xl sm:text-2xl font-bold text-white px-0">
          {title}
        </h2>
      )}
      
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {stats.map((stat, index) => (
          <DashboardKpiCard
            key={index}
            title={stat.label}
            value={stat.value}
            unit={stat.unit}
            trend={stat.trend}
            trendDirection={stat.trendDirection}
            icon={stat.icon}
          />
        ))}
      </div>
    </section>
  )
}
