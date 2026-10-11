/**
 * Factor breakdown display component
 */

import React, { useMemo } from 'react'

export interface FactorBreakdownProps {
  factors: Record<string, number>
  showPercentage?: boolean
  colors?: Record<string, string>
}

export const AlfaFactorBreakdown: React.FC<FactorBreakdownProps> = ({
  factors,
  showPercentage = true,
  colors,
}) => {
  const { normalizedFactors, segments } = useMemo(() => {
    const vals = Object.values(factors)
    const t = vals.reduce((a, b) => a + b, 0) || 1
    const normalized = Object.entries(factors).map(([key, val]) => ({
      key,
      value: val,
      percentage: (val / t) * 100,
    }))

    let offset = 0
    const segs = normalized.map((item) => {
      const width = (item.percentage / 100) * 100
      const seg = {
        key: item.key,
        x: offset,
        width,
        percentage: item.percentage,
      }
      offset += width
      return seg
    })

    return {
      normalizedFactors: normalized,
      total: t,
      segments: segs,
    }
  }, [factors])

  const defaultColors: Record<string, string> = {
    rating_gap_contribution: '#0ea5e9', // sky-500
    race_to_contribution: '#f59e0b', // amber-500
    context_contribution: '#8b5cf6', // violet-500
  }

  const finalColors = { ...defaultColors, ...colors }

  return (
    <div className="space-y-3">
      {/* Stacked bar */}
      <div className="flex h-8 rounded-lg overflow-hidden bg-slate-700 border border-slate-600">
        {segments.map((segment) => (
          <div
            key={segment.key}
            style={{
              width: `${segment.width}%`,
              backgroundColor: finalColors[segment.key] || '#64748b',
              transition: 'all 0.3s ease',
            }}
            className="relative group"
            title={`${segment.key}: ${segment.percentage.toFixed(1)}%`}
          >
            {segment.width > 10 && (
              <div className="flex items-center justify-center h-full">
                <span className="text-xs font-bold text-white opacity-pool_opt_in group-hover:opacity-pool_opt_in">
                  {showPercentage && `${segment.percentage.toFixed(0)}%`}
                </span>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="grid grid-cols-1 gap-2">
        {normalizedFactors.map((item) => (
          <div key={item.key} className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: finalColors[item.key] || '#64748b' }}
              />
              <span className="text-slate-300">{item.key.replace(/_/g, ' ')}</span>
            </div>
            {showPercentage && (
              <span className="font-mono text-sky-400">{item.percentage.toFixed(1)}%</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default AlfaFactorBreakdown
