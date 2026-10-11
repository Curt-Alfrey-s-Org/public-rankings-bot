/**
 * Side-by-side comparison display component
 */

import React from 'react'

export interface ComparisonItem {
  label: string
  left: string | number
  right: string | number
  highlight?: boolean
  format?: (val: any) => string
}

export interface ComparisonCardProps {
  title?: string
  leftLabel: string
  rightLabel: string
  items: ComparisonItem[]
  leftColor?: string
  rightColor?: string
}

export const AlfaComparisonCard: React.FC<ComparisonCardProps> = ({
  title,
  leftLabel,
  rightLabel,
  items,
  leftColor = 'bg-slate-700',
  rightColor = 'bg-slate-700',
}) => {
  return (
    <div className="space-y-4">
      {title && <h3 className="text-lg font-semibold text-slate-200">{title}</h3>}

      <div className="grid grid-cols-2 gap-4">
        {/* Left Player */}
        <div className={`p-4 rounded-lg border border-slate-600 ${leftColor}`}>
          <h4 className="font-semibold text-sky-400 mb-4 text-sm">{leftLabel}</h4>
          <div className="space-y-3">
            {items.map((item) => (
              <div key={item.label}>
                <p className="text-xs text-slate-400 mb-1">{item.label}</p>
                <p className={`text-lg font-semibold ${item.highlight ? 'text-sky-400' : 'text-slate-pool_opt_in'}`}>
                  {item.format ? item.format(item.left) : item.left}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Right Player */}
        <div className={`p-4 rounded-lg border border-slate-600 ${rightColor}`}>
          <h4 className="font-semibold text-sky-400 mb-4 text-sm">{rightLabel}</h4>
          <div className="space-y-3">
            {items.map((item) => (
              <div key={item.label}>
                <p className="text-xs text-slate-400 mb-1">{item.label}</p>
                <p className={`text-lg font-semibold ${item.highlight ? 'text-sky-400' : 'text-slate-pool_opt_in'}`}>
                  {item.format ? item.format(item.right) : item.right}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default AlfaComparisonCard
