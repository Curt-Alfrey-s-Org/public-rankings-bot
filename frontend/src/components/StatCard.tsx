interface StatCardProps {
  title: string
  value: string
  change?: number
  changePct?: number
  icon?: string
}

export default function StatCard({ title, value, change, changePct, icon }: StatCardProps) {
  const isPositive = change !== undefined && change >= 0
  const hasChange = change !== undefined && changePct !== undefined

  return (
    <div className="bg-card/60 border border-border/50 rounded-lg p-4 sm:p-5 hover:bg-card hover:border-primary/40 hover:shadow-md transition-all duration-200 flex flex-col h-full">
      <div className="flex items-start justify-between gap-2 mb-3 flex-shrink-0">
        <h3 className="text-xs sm:text-sm font-medium text-muted-foreground leading-tight flex-grow">{title}</h3>
        {icon && <span className="text-lg sm:text-xl flex-shrink-0">{icon}</span>}
      </div>
      <div className="flex items-baseline gap-2 flex-wrap flex-grow">
        <p className="text-xl sm:text-2xl font-bold leading-tight">{value}</p>
        {hasChange && changePct != null && (
          <span
            className={`text-xs sm:text-sm font-medium flex-shrink-0 ${
              isPositive ? 'text-green-500' : 'text-red-500'
            }`}
          >
            {isPositive ? '↑' : '↓'} {Number(changePct).toFixed(1)}%
          </span>
        )}
      </div>
      {hasChange && change != null && (
        <p className="text-xs text-muted-foreground mt-2 pt-2 border-t border-border/30">
          {isPositive ? '+' : ''}${Number(change).toFixed(2)}
        </p>
      )}
    </div>
  )
}
