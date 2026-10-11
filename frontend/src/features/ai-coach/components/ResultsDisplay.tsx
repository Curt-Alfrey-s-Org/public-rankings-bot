/**
 * ResultsDisplay - Shows analysis scores, drills, and feedback
 * @module features/ai-coach/components/ResultsDisplay
 */

import type { ResultsDisplayProps, AnalysisResult } from '@/features/ai-coach/types'

/** Displays coaching analysis results: scores, drills, focus area */
export function ResultsDisplay({
  result,
  status = 'completed',
  progress = 0,
  errorMessage = null,
}: ResultsDisplayProps) {
  if (status === 'pending' || status === 'processing') {
    return (
      <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <p className="text-sky-400">Analyzing frames... {progress}%</p>
        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-700">
          <div
            className="h-full bg-sky-500 transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    )
  }

  if (status === 'failed') {
    return (
      <div className="rounded-lg border border-red-800 bg-red-900/30 p-4">
        <p className="font-medium text-red-200">Analysis failed</p>
        <p className="mt-1 text-sm text-red-300">{errorMessage ?? 'Unknown error'}</p>
      </div>
    )
  }

  if (!result) {
    return (
      <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4 text-slate-400">
        No results to display.
      </div>
    )
  }

  const r = result as AnalysisResult
  return (
    <div className="space-y-4 rounded-lg border border-slate-700 bg-slate-800/50 p-4">
      <h3 className="text-lg font-semibold text-sky-400">Coaching Analysis</h3>
      {r.critical_focus_area && (
        <p className="text-slate-200">
          <span className="font-medium text-amber-400">Focus area: </span>
          {r.critical_focus_area}
        </p>
      )}
      {r.overall_assessment?.skill_estimate && (
        <p className="text-slate-300">Skill estimate: {r.overall_assessment.skill_estimate}</p>
      )}
      {r.daily_drills && r.daily_drills.length > 0 && (
        <div>
          <h4 className="font-medium text-slate-300">Daily drills</h4>
          <ul className="mt-1 list-inside list-disc space-y-1 text-slate-400">
            {r.daily_drills.map((d, i) => (
              <li key={i}>{d.name ?? d.objective ?? 'Drill'}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
