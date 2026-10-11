/**
 * Anomaly flag display component
 */

import React from 'react'
import { AlertTriangle, TrendingUp, TrendingDown, AlertCircle } from 'lucide-react'
import type { AnomalyFlag } from '@/types/alfa.types'

export interface AnomalyFlagProps {
  flag: AnomalyFlag
  compact?: boolean
}

const flagIcons: Record<string, React.ReactNode> = {
  sudden_jump: <TrendingUp className="w-4 h-4" />,
  winning_weak_only: <TrendingUp className="w-4 h-4" />,
  losing_strong_only: <TrendingDown className="w-4 h-4" />,
  rating_mismatch: <AlertCircle className="w-4 h-4" />,
  variance: <AlertTriangle className="w-4 h-4" />,
  break_dominance: <AlertTriangle className="w-4 h-4" />,
}

const severityColors = {
  low: 'bg-yellow-900 border-yellow-600 text-yellow-200',
  medium: 'bg-orange-900 border-orange-600 text-orange-200',
  high: 'bg-red-900 border-red-600 text-red-200',
}

const severityIconColors = {
  low: 'text-yellow-400',
  medium: 'text-orange-400',
  high: 'text-red-400',
}

export const AlfaAnomalyFlag: React.FC<AnomalyFlagProps> = ({ flag, compact = false }) => {
  if (compact) {
    return (
      <div className={`inline-flex items-center gap-2 px-3 py-1 rounded border ${severityColors[flag.severity]}`}>
        <span className={severityIconColors[flag.severity]}>{flagIcons[flag.flag_type]}</span>
        <span className="text-xs font-medium">{flag.flag_type}</span>
      </div>
    )
  }

  return (
    <div className={`p-4 rounded-lg border ${severityColors[flag.severity]}`}>
      <div className="flex items-start gap-3">
        <span className={`flex-shrink-0 ${severityIconColors[flag.severity]}`}>
          {flagIcons[flag.flag_type]}
        </span>
        <div className="flex-1 min-w-0">
          <h4 className="font-semibold text-sm mb-1">
            {flag.flag_type.replace(/_/g, ' ').toUpperCase()}
          </h4>
          <p className="text-xs opacity-90 mb-2">{flag.explanation}</p>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="opacity-75">Threshold:</span>
              <span className="font-mono ml-1">{flag.threshold.toFixed(2)}</span>
            </div>
            <div>
              <span className="opacity-75">Actual:</span>
              <span className="font-mono ml-1">{flag.actual_value.toFixed(2)}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default AlfaAnomalyFlag
