import { useQuery } from '@tanstack/react-query'
import { statsApi } from '@/api/stats'
import { useBotStatus } from '@/hooks/useBotStatus'
import { useMemo } from 'react'
import ChartStyleSelector from './ChartStyleSelector'
import { useChartPreferences, type ChartStyle } from '@/hooks/useChartPreferences'

interface MonthlyReturnsChartProps {
  height?: number
}

export default function MonthlyReturnsChart({ height = 300 }: MonthlyReturnsChartProps) {
  const { data: botStatus } = useBotStatus()
  const { preferences, updateChartStyle } = useChartPreferences()
  const chartStyle: ChartStyle = preferences.monthlyReturns
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['stats'],
    queryFn: statsApi.getStats,
    refetchInterval: 5000,
    retry: 1,
    retryDelay: 1000,
    staleTime: 500,
  })

  const chartData = useMemo(() => {
    if (!stats || !stats.monthly_returns || stats.monthly_returns.length === 0) {
      return []
    }
    return stats.monthly_returns.map((ret, index) => ({
      month: ret.month,
      returnPct: Number(ret.return_pct) || 0,
      index
    }))
  }, [stats])

  // Professional investor benchmark: 3-4% per month
  const PROFESSIONAL_BENCHMARK_MIN = 3.0
  const PROFESSIONAL_BENCHMARK_MAX = 4.0

  if (isLoading) {
    return (
      <div className="w-full rounded-lg p-4 sm:p-6 flex items-center justify-center min-h-[250px] sm:min-h-[300px]">
        <p className="text-muted-foreground">Loading chart data...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="w-full rounded-lg p-4 sm:p-6 flex items-center justify-center min-h-[250px] sm:min-h-[300px]">
        <p className="text-muted-foreground">No chart data available</p>
      </div>
    )
  }

  if (!stats || chartData.length === 0) {
    return (
      <div className="w-full rounded-lg p-4 sm:p-6 flex flex-col items-center justify-center min-h-[250px] sm:min-h-[300px]">
        <p className="text-muted-foreground">No monthly return data available</p>
        <p className="text-xs text-muted-foreground mt-2">Monthly returns will appear after trades are executed</p>
      </div>
    )
  }

  const maxReturn = Math.max(...chartData.map(d => d.returnPct), PROFESSIONAL_BENCHMARK_MAX)
  const minReturn = Math.min(...chartData.map(d => d.returnPct), -5) // Allow for negative returns
  const range = maxReturn - minReturn || 1
  const chartHeight = height || 300

  // Calculate average monthly return
  const avgMonthlyReturn = chartData.reduce((sum, d) => sum + d.returnPct, 0) / chartData.length

  return (
    <div className="w-full flex flex-col h-full">
      <div className="flex items-center justify-between mb-3 sm:mb-4 flex-col sm:flex-row gap-3 sm:gap-0">
        <h3 className="text-base sm:text-lg font-semibold">Monthly Returns (%)</h3>
        <div className="flex items-center gap-2 sm:gap-4 flex-col sm:flex-row w-full sm:w-auto">
          <div className="flex items-center gap-2 flex-wrap">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded bg-green-500/20 border border-green-500"></div>
              <span className="text-muted-foreground text-xs">Goal: 3-4%</span>
            </div>
            <div className="text-muted-foreground text-xs">
              Avg: <span className={avgMonthlyReturn >= PROFESSIONAL_BENCHMARK_MIN ? 'text-green-500 font-semibold' : 'text-yellow-500 font-semibold'}>
                {Number(avgMonthlyReturn).toFixed(2)}%
              </span>
            </div>
          </div>
          <ChartStyleSelector
            currentStyle={chartStyle}
            onStyleChange={(style) => updateChartStyle('monthlyReturns', style)}
            label="Chart"
          />
        </div>
      </div>
      
      <div className="relative flex-grow min-h-[250px] sm:min-h-[300px]">
        <svg width="100%" height={chartHeight} className="overflow-visible">
          {/* Professional benchmark zone (3-4%) */}
          <rect
            x="0"
            y={chartHeight - ((PROFESSIONAL_BENCHMARK_MAX - minReturn) / range) * chartHeight}
            width="100%"
            height={((PROFESSIONAL_BENCHMARK_MAX - PROFESSIONAL_BENCHMARK_MIN) / range) * chartHeight}
            fill="rgba(34, 197, 94, 0.1)"
            stroke="rgba(34, 197, 94, 0.3)"
            strokeWidth={1}
            strokeDasharray="4 4"
          />
          
          {/* Zero line */}
          <line
            x1="0"
            y1={chartHeight - ((0 - minReturn) / range) * chartHeight}
            x2="100%"
            y2={chartHeight - ((0 - minReturn) / range) * chartHeight}
            stroke="currentColor"
            strokeOpacity={0.3}
            strokeWidth={1}
            strokeDasharray="2 2"
          />
          
          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((ratio) => (
            <line
              key={ratio}
              x1="0"
              y1={ratio * chartHeight}
              x2="100%"
              y2={ratio * chartHeight}
              stroke="currentColor"
              strokeOpacity={0.1}
              strokeWidth={1}
            />
          ))}
          
          {/* Render chart based on selected style */}
          {chartStyle === 'bar' && renderBarChart()}
          {chartStyle === 'line' && renderLineChart()}
          {chartStyle === 'area' && renderAreaChart()}
          {chartStyle === 'candlestick' && renderCandlestickChart()}
          {chartStyle === 'hybrid' && renderHybridChart()}
        </svg>
        
        {/* Y-axis labels */}
        <div className="absolute left-0 top-0 bottom-0 flex flex-col justify-between text-xs text-muted-foreground px-1 sm:px-2">
          <span>+{Number(maxReturn).toFixed(1)}%</span>
          <span className="text-green-500 font-semibold">{PROFESSIONAL_BENCHMARK_MAX}%</span>
          <span className="text-green-500 font-semibold">{PROFESSIONAL_BENCHMARK_MIN}%</span>
          <span>0%</span>
          <span>{Number(minReturn).toFixed(1)}%</span>
        </div>
      </div>
      
      {/* X-axis labels (months) */}
      <div className="flex justify-between mt-2 text-xs text-muted-foreground px-1 sm:px-2">
        {chartData.length > 0 && (
          <>
            <span>{chartData[0].month}</span>
            {chartData.length > 1 && (
              <span>{chartData[Math.floor(chartData.length / 2)].month}</span>
            )}
            <span>{chartData[chartData.length - 1].month}</span>
          </>
        )}
      </div>
      
      {/* Status indicator */}
      <div className="mt-3 sm:mt-4 pt-3 sm:pt-4 border-t border-border/50">
        <div className="flex items-center justify-between text-xs sm:text-sm flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <span className="text-muted-foreground">Performance vs Goal:</span>
            {avgMonthlyReturn >= PROFESSIONAL_BENCHMARK_MIN ? (
              <span className="text-green-500 font-semibold">✓ Meeting Goal ({Number(avgMonthlyReturn).toFixed(2)}% avg)</span>
            ) : avgMonthlyReturn > 0 ? (
              <span className="text-yellow-500 font-semibold">⚠ Below Goal ({Number(avgMonthlyReturn).toFixed(2)}% avg, target: 3-4%)</span>
            ) : (
              <span className="text-red-500 font-semibold">✗ Negative Returns ({Number(avgMonthlyReturn).toFixed(2)}% avg)</span>
            )}
          </div>
        </div>
      </div>
    </div>
  )

  function getBarColor(returnPct: number) {
    const isInGoalRange = returnPct >= PROFESSIONAL_BENCHMARK_MIN && returnPct <= PROFESSIONAL_BENCHMARK_MAX
    const isPositive = returnPct >= 0
    return {
      fill: isInGoalRange 
        ? 'rgba(34, 197, 94, 0.6)' 
        : isPositive 
          ? 'rgba(59, 130, 246, 0.6)' 
          : 'rgba(239, 68, 68, 0.6)',
      stroke: isInGoalRange 
        ? 'rgb(34, 197, 94)' 
        : isPositive 
          ? 'rgb(59, 130, 246)' 
          : 'rgb(239, 68, 68)',
    }
  }

  function renderBarChart() {
    return (
      <g key={`bars-${chartData.length}`}>
        {chartData.map((d, i) => {
          const barWidth = (100 / chartData.length) * 0.8
          const barX = (i / chartData.length) * 100 + (100 / chartData.length) * 0.1
          const barY = chartHeight - ((d.returnPct - minReturn) / range) * chartHeight
          const isPositive = d.returnPct >= 0
          const colors = getBarColor(d.returnPct)
          
          return (
            <g key={i}>
              <rect
                x={`${barX}%`}
                y={isPositive ? barY : chartHeight - ((0 - minReturn) / range) * chartHeight}
                width={`${barWidth}%`}
                height={isPositive 
                  ? chartHeight - barY 
                  : (chartHeight - ((0 - minReturn) / range) * chartHeight) - barY
                }
                fill={colors.fill}
                stroke={colors.stroke}
                strokeWidth={1}
              />
              <text
                x={`${barX + barWidth / 2}%`}
                y={isPositive ? barY - 5 : barY + 15}
                textAnchor="middle"
                className="text-xs font-medium fill-foreground"
              >
                {Number(d.returnPct).toFixed(1)}%
              </text>
            </g>
          )
        })}
      </g>
    )
  }

  function renderLineChart() {
    const points = chartData
      .map((d, i) => {
        const x = (i / (chartData.length - 1 || 1)) * 100
        const y = chartHeight - ((d.returnPct - minReturn) / range) * chartHeight
        return `${x}%,${y}`
      })
      .join(' ')
    
    return (
      <polyline
        key={`line-${chartData.length}`}
        points={points}
        fill="none"
        stroke="hsl(var(--primary))"
        strokeWidth={2.5}
      />
    )
  }

  function renderAreaChart() {
    const points = chartData
      .map((d, i) => {
        const x = (i / (chartData.length - 1 || 1)) * 100
        const y = chartHeight - ((d.returnPct - minReturn) / range) * chartHeight
        return `${x}%,${y}`
      })
      .join(' ')
    
    return (
      <>
        <polyline
          key={`area-line-${chartData.length}`}
          points={points}
          fill="none"
          stroke="hsl(var(--primary))"
          strokeWidth={2}
        />
        <polygon
          key={`area-fill-${chartData.length}`}
          points={`0,${chartHeight} ${points} 100%,${chartHeight}`}
          fill="hsl(var(--primary))"
          fillOpacity={0.15}
        />
      </>
    )
  }

  function renderCandlestickChart() {
    const period = Math.ceil(chartData.length / 10)
    
    return (
      <g key={`candles-${chartData.length}`}>
        {chartData
          .filter((_, i) => i % period === 0 || i === chartData.length - 1)
          .map((d, _, filtered) => {
            const actualIndex = chartData.indexOf(d)
            const x = (actualIndex / (chartData.length - 1 || 1)) * 100
            const close = d.returnPct
            const open = actualIndex > 0 ? chartData[actualIndex - 1].returnPct : d.returnPct
            const high = d.returnPct
            const low = d.returnPct
            
            const highY = chartHeight - ((high - minReturn) / range) * chartHeight
            const lowY = chartHeight - ((low - minReturn) / range) * chartHeight
            const openY = chartHeight - ((open - minReturn) / range) * chartHeight
            const closeY = chartHeight - ((close - minReturn) / range) * chartHeight
            
            const isGreen = close >= open
            const colors = getBarColor(close)
            
            return (
              <g key={actualIndex}>
                <line
                  x1={`${x}%`}
                  y1={highY}
                  x2={`${x}%`}
                  y2={lowY}
                  stroke={colors.stroke}
                  strokeWidth={1}
                />
                <rect
                  x={`${x - 1}%`}
                  y={Math.min(openY, closeY)}
                  width="2%"
                  height={Math.abs(closeY - openY) || 1}
                  fill={colors.fill}
                  stroke={colors.stroke}
                />
              </g>
            )
          })}
      </g>
    )
  }

  function renderHybridChart() {
    const barWidth = (100 / chartData.length) * 0.6
    const pointsData = chartData.map((d, i) => {
      const x = (i / (chartData.length - 1 || 1)) * 100
      const y = chartHeight - ((d.returnPct - minReturn) / range) * chartHeight
      return { x, y, d, i }
    })

    return (
      <>
        {/* Bars in background */}
        <g key={`hybrid-bars-${chartData.length}`} opacity={0.3}>
          {pointsData.map(({ x, y, d, i }) => {
            const isPositive = d.returnPct >= 0
            return (
              <rect
                key={`hbar-${i}`}
                x={`${x - barWidth / 2}%`}
                y={isPositive ? y : chartHeight - ((0 - minReturn) / range) * chartHeight}
                width={`${barWidth}%`}
                height={isPositive 
                  ? chartHeight - y 
                  : (chartHeight - ((0 - minReturn) / range) * chartHeight) - y
                }
                fill={'hsl(var(--primary))'}
              />
            )
          })}
        </g>

        {/* Line on top */}
        <polyline
          key={`hybrid-line-${chartData.length}`}
          points={pointsData.map(({ x, y }) => `${x}%,${y}`).join(' ')}
          fill="none"
          stroke="hsl(var(--primary))"
          strokeWidth={2.5}
        />
      </>
    )
  }
}
