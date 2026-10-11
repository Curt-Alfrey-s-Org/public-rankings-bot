/**
 * Meta Metric Badge Component
 * Small badge showing a single metric - used in player/tournament cards
 * 
 * @component
 * @example
 * <MetricBadge label="Rating" value={1850} variant="primary" />
 */

interface MetricBadgeProps {
  /** Badge label */
  label: string
  /** Metric value */
  value: string | number
  /** Visual variant */
  variant?: 'default' | 'primary' | 'success' | 'warning' | 'danger'
  /** Optional icon */
  icon?: React.ReactNode
}

const getVariantColor = (variant?: string): string => {
  switch (variant) {
    case 'primary':
      return 'bg-sky-500/20 text-sky-300 border-sky-500/30'
    case 'success':
      return 'bg-green-500/20 text-green-300 border-green-500/30'
    case 'warning':
      return 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30'
    case 'danger':
      return 'bg-red-500/20 text-red-300 border-red-500/30'
    default:
      return 'bg-slate-800/50 text-slate-300 border-slate-700/50'
  }
}

export default function MetricBadge({
  label,
  value,
  variant = 'default',
  icon,
}: MetricBadgeProps) {
  return (
    <div
      className={`
        inline-flex items-center gap-2 px-2.5 py-1.5 rounded-md
        border text-xs font-medium whitespace-nowrap
        ${getVariantColor(variant)}
      `}
      aria-label={`${label}: ${value}`}
    >
      {icon && <span className="w-3 h-3 flex-shrink-0">{icon}</span>}
      <span className="text-slate-400 text-xs">{label}</span>
      <span className="font-semibold">{value}</span>
    </div>
  )
}
