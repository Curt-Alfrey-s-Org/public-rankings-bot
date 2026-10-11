import { ChartStyle } from '@/hooks/useChartPreferences'

interface ChartStyleSelectorProps {
  currentStyle: ChartStyle
  onStyleChange: (style: ChartStyle) => void
  label?: string
}

const CHART_STYLES: { style: ChartStyle; label: string; description: string }[] = [
  { style: 'line', label: 'Line', description: 'Simple line chart' },
  { style: 'area', label: 'Area', description: 'Line with filled area' },
  { style: 'bar', label: 'Bar', description: 'Bar chart' },
  { style: 'candlestick', label: 'Candle', description: 'OHLC candlestick' },
  { style: 'hybrid', label: 'Hybrid', description: 'Line + area combo' },
]

export default function ChartStyleSelector({
  currentStyle,
  onStyleChange,
  label = 'Chart Style',
}: ChartStyleSelectorProps) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="text-xs text-muted-foreground font-medium">{label}:</span>
      <div className="flex gap-1 flex-wrap">
        {CHART_STYLES.map(({ style, label: styleLabel, description }) => (
          <button
            key={style}
            onClick={() => onStyleChange(style)}
            className={`px-2 py-1 text-xs rounded transition-colors ${
              currentStyle === style
                ? 'bg-primary/20 border border-primary text-primary font-semibold'
                : 'bg-muted hover:bg-muted/80 border border-border text-muted-foreground hover:text-foreground'
            }`}
            title={description}
          >
            {styleLabel}
          </button>
        ))}
      </div>
    </div>
  )
}
