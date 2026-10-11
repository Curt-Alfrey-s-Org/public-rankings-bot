/**
 * UsageMeter - Tier limit progress bar for AI Coach
 * @module features/ai-coach/components/UsageMeter
 */

import type { UsageMeterProps } from '@/features/ai-coach/types'

/** Displays current tier and usage progress (analyses remaining) */
export function UsageMeter({
  tier,
  analysesUsed,
  analysesLimit,
  analysesRemaining,
  maxVideoDurationSeconds,
  monthResetDate,
}: UsageMeterProps) {
  const limit = analysesLimit ?? 0
  const used = analysesUsed
  const isUnlimited = tier === 'PRO' || (analysesRemaining ?? 0) >= 999999
  const pct = isUnlimited ? 100 : (limit > 0 ? Math.min(100, (used / limit) * 100) : 0)

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-3">
      <p className="text-sm font-medium text-slate-300">
        <span className="text-sky-400">{tier}</span>
        {isUnlimited ? (
          ' · Unlimited'
        ) : (
          <> · {analysesRemaining} analyses remaining{limit > 0 && ` (${used}/${limit})`}</>
        )}
      </p>
      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-700">
        <div
          className="h-full bg-sky-500 transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Video limit: {Math.floor(maxVideoDurationSeconds / 60)} min
        {monthResetDate && ` · Resets: ${monthResetDate}`}
      </p>
    </div>
  )
}
