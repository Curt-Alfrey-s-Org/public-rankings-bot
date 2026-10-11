import { useQuery } from '@tanstack/react-query'
import { statsApi } from '@/api/stats'
import { useMemo, useState, useEffect } from 'react'
import { useBotStatus } from '@/hooks/useBotStatus'
import ChartStyleSelector from './ChartStyleSelector'
import { useChartPreferences, type ChartStyle } from '@/hooks/useChartPreferences'

const MAX_POINTS = 60

interface PerformanceChartProps {
  type: 'equity' | 'pnl'
  height?: number
}

export default function PerformanceChart({ type, height = 300 }: PerformanceChartProps) {
  const { data: botStatus } = useBotStatus()
  const { preferences, updateChartStyle } = useChartPreferences()
  const chartStyle: ChartStyle = preferences.performanceChart
  const { data: stats, isLoading, error, dataUpdatedAt } = useQuery({
    queryKey: ['stats'],
    queryFn: statsApi.getStats,
    refetchInterval: 5000,
    retry: 1,
    retryDelay: 1000,
    staleTime: 500,
  })
  const [series, setSeries] = useState<{ date: Date; value: number }[]>([])

  // Append a point on every stats refetch so the curve updates even when values are unchanged
  useEffect(() => {
    if (!stats) return
    const now = new Date()
    const raw = type === 'equity' ? stats.capital : stats.total_pnl
    const value = typeof raw === 'number' && Number.isFinite(raw) ? raw : 0
    setSeries((prev) => [...prev, { date: now, value }].slice(-MAX_POINTS))
  }, [stats, dataUpdatedAt, type])

  const chartData = useMemo(() => {
    if (series.length > 0) return series
    if (stats) {
      const raw = type === 'equity' ? stats.capital : stats.total_pnl
      const value = typeof raw === 'number' && Number.isFinite(raw) ? raw : 0
      return [{ date: new Date(), value }]
    }
    return []
  }, [series, stats, type])

  if (isLoading) {
    return (
      <div className="w-full rounded-lg p-4 sm:p-6 flex items-center justify-center min-h-[250px] sm:min-h-[300px]">
        <p className="text-muted-foreground">Loading chart data...</p>
      </div>
    )
  }

  // Show empty state instead of error messages
  if (error) {
    return (
      <div className="w-full rounded-lg p-4 sm:p-6 flex items-center justify-center min-h-[250px] sm:min-h-[300px]">
        <p className="text-muted-foreground">No chart data available</p>
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="w-full rounded-lg p-4 sm:p-6 flex items-center justify-center min-h-[250px] sm:min-h-[300px]">
        <p className="text-muted-foreground">No data available</p>
      </div>
    )
  }

  const divisor = Math.max(1, chartData.length - 1)
  const values = chartData.map((d) => (typeof d.value === 'number' && Number.isFinite(d.value) ? d.value : 0))
  const maxValue = values.length ? Math.max(...values) : 0
  const minValue = values.length ? Math.min(...values) : 0
  const range = maxValue - minValue || 1
  const chartHeight = height || 300

  return (
    <div className="w-full flex flex-col h-full" key={`chart-${type}-${chartData.length}`}>
      <div className="flex items-center justify-between mb-3 sm:mb-4 flex-col sm:flex-row gap-3 sm:gap-0">
        <h3 className="text-base sm:text-lg font-semibold">
          {type === 'equity' ? 'Equity Curve' : 'P&L Trend'}
        </h3>
        <div className="flex items-center justify-between gap-4 w-full sm:w-auto">
          <span className="text-xs text-muted-foreground">{chartData.length} point{chartData.length !== 1 ? 's' : ''}</span>
          <ChartStyleSelector
            currentStyle={chartStyle}
            onStyleChange={(style) => updateChartStyle('performanceChart', style)}
            label="Chart"
          />
        </div>
      </div>
      <div className="relative flex-grow min-h-[250px] sm:min-h-[300px]">
        <svg width="100%" height={chartHeight} className="overflow-visible">
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
          {chartStyle === 'line' && renderLineChart()}
          {chartStyle === 'area' && renderAreaChart()}
          {chartStyle === 'bar' && renderBarChart()}
          {chartStyle === 'candlestick' && renderCandlestickChart()}
          {chartStyle === 'hybrid' && renderHybridChart()}
        </svg>

        {/* Y-axis labels */}
        <div className="absolute left-0 top-0 bottom-0 flex flex-col justify-between text-xs text-muted-foreground px-1 sm:px-2">
          <span>{type === 'equity' ? `$${Number(maxValue).toFixed(0)}` : `+$${Number(maxValue).toFixed(0)}`}</span>
          <span>{type === 'equity' ? `$${Number(minValue).toFixed(0)}` : `-$${Math.abs(Number(minValue)).toFixed(0)}`}</span>
        </div>
      </div>
      
      <p className="text-xs text-muted-foreground mt-2 sm:mt-3 text-center">
        {type === 'equity' 
          ? `Current Capital: $${(Number(stats.capital) || 0).toFixed(2)}`
          : `Total P&L: $${(Number(stats.total_pnl) || 0).toFixed(2)}`}
      </p>
    </div>
  )

  function renderLineChart() {
    return (
      <polyline
        key={`line-${chartData.length}-${chartData[chartData.length - 1]?.value ?? 0}`}
        points={chartData
          .map((d, i) => {
            const x = (i / divisor) * 100
            const y = chartHeight - ((d.value - minValue) / range) * chartHeight
            return `${x}%,${y}`
          })
          .join(' ')}
        fill="none"
        stroke="hsl(var(--primary))"
        strokeWidth={2.5}
      />
    )
  }

  function renderAreaChart() {
    return (
      <>
        <polyline
          key={`area-line-${chartData.length}`}
          points={chartData
            .map((d, i) => {
              const x = (i / divisor) * 100
              const y = chartHeight - ((d.value - minValue) / range) * chartHeight
              return `${x}%,${y}`
            })
            .join(' ')}
          fill="none"
          stroke="hsl(var(--primary))"
          strokeWidth={2}
        />
        <polygon
          key={`area-fill-${chartData.length}`}
          points={`0,${chartHeight} ${chartData
            .map((d, i) => {
              const x = (i / divisor) * 100
              const y = chartHeight - ((d.value - minValue) / range) * chartHeight
              return `${x}%,${y}`
            })
            .join(' ')} 100%,${chartHeight}`}
          fill="hsl(var(--primary))"
          fillOpacity={0.15}
        />
      </>
    )
  }

  function renderBarChart() {
    const barWidth = Math.max(2, (100 / chartData.length) * 0.7)
    return (
      <g key={`bars-${chartData.length}`}>
        {chartData.map((d, i) => {
          const x = (i / divisor) * 100
          const y = chartHeight - ((d.value - minValue) / range) * chartHeight
          const color = d.value >= 0 ? 'hsl(var(--primary))' : 'hsl(0, 84%, 60%)'
          return (
            <rect
              key={`bar-${i}`}
              x={`${x - barWidth / 2}%`}
              y={y}
              width={`${barWidth}%`}
              height={chartHeight - y}
              fill={color}
              fillOpacity={0.7}
            />
          )
        })}
      </g>
    )
  }

  function renderCandlestickChart() {
    const wickWidth = Math.max(0.5, (100 / chartData.length) * 0.1)
    const bodyWidth = Math.max(1.5, (100 / chartData.length) * 0.4)
    const period = Math.ceil(chartData.length / 10) // Show ~10 candles
    
    return (
      <g key={`candles-${chartData.length}`}>
        {chartData
          .filter((_, i) => i % period === 0 || i === chartData.length - 1)
          .map((d, idx, filtered) => {
            const actualIndex = chartData.indexOf(d)
            const x = (actualIndex / divisor) * 100
            const close = d.value
            const open = actualIndex > 0 ? chartData[actualIndex - 1].value : d.value
            const period_high = d.value
            const period_low = d.value
            const high = (period_high - minValue) / range
            const low = (period_low - minValue) / range
            const o = (open - minValue) / range
            const c = (close - minValue) / range
            const isGreen = close >= open
            
            const highY = chartHeight - high * chartHeight
            const lowY = chartHeight - low * chartHeight
            const openY = chartHeight - o * chartHeight
            const closeY = chartHeight - c * chartHeight
            
            return (
              <g key={`candle-${actualIndex}`}>
                {/* Wick */}
                <line
                  x1={`${x}%`}
                  y1={highY}
                  x2={`${x}%`}
                  y2={lowY}
                  stroke={isGreen ? 'hsl(var(--primary))' : 'hsl(0, 84%, 60%)'}
                  strokeWidth={wickWidth}
                />
                {/* Body */}
                <rect
                  x={`${x - bodyWidth / 2}%`}
                  y={Math.min(openY, closeY)}
                  width={`${bodyWidth}%`}
                  height={Math.abs(closeY - openY) || 1}
                  fill={isGreen ? 'hsl(var(--primary))' : 'hsl(0, 84%, 60%)'}
                  fillOpacity={0.8}
                />
              </g>
            )
          })}
      </g>
    )
  }

  function renderHybridChart() {
    return (
      <>
        {/* Bar area in background */}
        <g key={`hybrid-bars-${chartData.length}`} opacity={0.3}>
          {chartData.map((d, i) => {
            const x = (i / divisor) * 100
            const y = chartHeight - ((d.value - minValue) / range) * chartHeight
            const barWidth = Math.max(1.5, (100 / chartData.length) * 0.6)
            return (
              <rect
                key={`hbar-${i}`}
                x={`${x - barWidth / 2}%`}
                y={y}
                width={`${barWidth}%`}
                height={chartHeight - y}
                fill="hsl(var(--primary))"
              />
            )
          })}
        </g>
        
        {/* Line on top */}
        <polyline
          key={`hybrid-line-${chartData.length}`}
          points={chartData
            .map((d, i) => {
              const x = (i / divisor) * 100
              const y = chartHeight - ((d.value - minValue) / range) * chartHeight
              return `${x}%,${y}`
            })
            .join(' ')}
          fill="none"
          stroke="hsl(var(--primary))"
          strokeWidth={2.5}
        />
      </>
    )
  }
}