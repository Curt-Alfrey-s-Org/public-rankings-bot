/**
 * Player comparison — GET /api/alfa/comparison/{id1}/{id2} (numeric player ids).
 */

import React from 'react'
import { X } from 'lucide-react'
import { useAlfaPlayerComparison } from '@/hooks/useAlfaRatings'

type ComparisonApi = {
  comparison?: {
    operator_id?: number
    player2_id?: number
    operator_name?: string | null
    player2_name?: string | null
    alfa_diff?: number | null
    predicted_matchup_prob_p1?: number | null
    head_to_head?: {
      total_matches?: number
      operator_wins?: number
      player2_wins?: number
      win_rate_p1?: number
    }
  }
  timestamp?: string
}

export interface PlayerComparisonProps {
  playerId1?: string
  playerId2?: string
  onClose?: () => void
}

export const AlfaPlayerComparison: React.FC<PlayerComparisonProps> = ({
  playerId1,
  playerId2,
  onClose,
}) => {
  const { data: raw, isLoading } = useAlfaPlayerComparison(playerId1, playerId2)
  const comparison = raw as ComparisonApi | undefined
  const c = comparison?.comparison

  if (!playerId1 || !playerId2) {
    return null
  }

  if (isLoading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-slate-800 rounded-lg p-6 text-center text-slate-400">
          Loading comparison...
        </div>
      </div>
    )
  }

  if (!comparison || !c) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
        <div className="bg-slate-800 rounded-lg border border-slate-700 max-w-lg w-full p-6 text-slate-300">
          <p>No comparison data (requires two numeric player ids present in Alfa ratings).</p>
          {onClose && (
            <button type="button" onClick={onClose} className="mt-4 px-4 py-2 bg-slate-700 rounded-lg">
              Close
            </button>
          )}
        </div>
      </div>
    )
  }

  const h2h = c.head_to_head ?? {}
  const n1 = c.operator_name ?? `Player ${c.operator_id}`
  const n2 = c.player2_name ?? `Player ${c.player2_id}`

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 rounded-lg border border-slate-700 max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-slate-700 sticky top-0 bg-slate-800">
          <h2 className="text-2xl font-bold text-slate-pool_opt_in">Player comparison</h2>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-slate-400" />
            </button>
          )}
        </div>

        <div className="p-6 space-y-6 text-slate-200">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-lg bg-slate-700 border border-slate-600">
              <p className="text-xs text-slate-400 mb-1">{n1}</p>
              <p className="text-sm font-mono text-slate-400">id {c.operator_id}</p>
            </div>
            <div className="p-4 rounded-lg bg-slate-700 border border-slate-600">
              <p className="text-xs text-slate-400 mb-1">{n2}</p>
              <p className="text-sm font-mono text-slate-400">id {c.player2_id}</p>
            </div>
          </div>

          <div className="p-4 rounded-lg bg-slate-700 border border-slate-600 space-y-2">
            <p className="text-sm text-slate-400">Alfa rating difference (P1 − P2)</p>
            <p className="text-2xl font-mono text-sky-400">{c.alfa_diff != null ? c.alfa_diff.toFixed(2) : '—'}</p>
            <p className="text-sm text-slate-400">Predicted P1 win probability</p>
            <p className="text-xl font-mono text-amber-400">
              {c.predicted_matchup_prob_p1 != null
                ? `${(c.predicted_matchup_prob_p1 * 100).toFixed(1)}%`
                : '—'}
            </p>
          </div>

          <div className="p-4 rounded-lg bg-slate-700 border border-slate-600">
            <h3 className="text-lg font-semibold text-slate-pool_opt_in mb-3">Head-to-head (tournament history)</h3>
            <ul className="text-sm space-y-1 text-slate-300">
              <li>Total matches: {h2h.total_matches ?? 0}</li>
              <li>
                {n1} wins: {h2h.operator_wins ?? 0}
              </li>
              <li>
                {n2} wins: {h2h.player2_wins ?? 0}
              </li>
              <li>P1 win rate: {h2h.win_rate_p1 != null ? `${(h2h.win_rate_p1 * 100).toFixed(1)}%` : '—'}</li>
            </ul>
          </div>

          {comparison.timestamp && (
            <p className="text-xs text-slate-500 font-mono">Snapshot: {comparison.timestamp}</p>
          )}
        </div>
      </div>
    </div>
  )
}

export default AlfaPlayerComparison
