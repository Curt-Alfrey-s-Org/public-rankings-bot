/**
 * Prediction explainability — POST /api/alfa/explain (match_id only).
 */

import React, { useState } from 'react'
import { Search } from 'lucide-react'
import { toast } from '@/lib/toast'
import { useAlfaPredictionExplain } from '@/hooks/useAlfaRatings'
import AlfaFactorBreakdown from '@/components/AlfaFactorBreakdown'

function factorsToRecord(factors: Array<{ name: string; contribution: number }>): Record<string, number> {
  const out: Record<string, number> = {}
  for (const f of factors ?? []) {
    const k = f.name || 'unknown'
    out[k] = (out[k] ?? 0) + Math.abs(Number(f.contribution) || 0)
  }
  return out
}

export const AlfaPredictionExplain: React.FC = () => {
  const [matchId, setMatchId] = useState('')
  const [activeMatchId, setActiveMatchId] = useState<string | undefined>(undefined)

  const { data: prediction, isLoading: predictLoading } = useAlfaPredictionExplain(activeMatchId)

  const handleSearch = () => {
    const id = matchId.trim()
    if (!id) {
      toast.error('Enter a match ID')
      return
    }
    setActiveMatchId(id)
  }

  const handleExport = () => {
    toast.warning('PDF export is not implemented for Alfa predictions.')
  }

  const md = prediction?.match_details as Record<string, unknown> | undefined
  const p1 = md?.operator_id
  const p2 = md?.player2_id

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-slate-pool_opt_in">Prediction explainability</h1>
        <p className="text-slate-400 mt-1">
          Load a stored prediction by <span className="font-mono text-sky-400">match_id</span> (from{' '}
          <span className="font-mono">POST /api/alfa/predict</span> logs / DB).
        </p>
      </div>

      <div className="bg-slate-800 rounded-lg border border-slate-700 p-6 space-y-4">
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            value={matchId}
            onChange={(e) => setMatchId(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="match_id…"
            className="flex-1 px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-pool_opt_in placeholder-slate-500 focus:border-sky-500 outline-none"
          />
          <button
            type="button"
            onClick={handleSearch}
            className="px-6 py-2 bg-sky-600 hover:bg-sky-700 rounded-lg text-white font-medium transition-colors flex items-center justify-center gap-2"
          >
            <Search className="w-4 h-4" />
            Load
          </button>
        </div>
      </div>

      {prediction && (
        <div className="space-y-6">
          <div className="bg-slate-800 rounded-lg border border-slate-700 p-6 space-y-4">
            <h2 className="text-xl font-semibold text-slate-pool_opt_in">Match</h2>
            <p className="text-sm text-slate-400 font-mono">{prediction.match_id}</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div className="p-3 rounded bg-slate-700 border border-slate-600">
                <p className="text-slate-400 text-xs mb-1">Player 1 id</p>
                <p className="text-slate-pool_opt_in font-mono">{String(p1 ?? '—')}</p>
              </div>
              <div className="p-3 rounded bg-slate-700 border border-slate-600">
                <p className="text-slate-400 text-xs mb-1">Player 2 id</p>
                <p className="text-slate-pool_opt_in font-mono">{String(p2 ?? '—')}</p>
              </div>
            </div>
          </div>

          <div className="bg-slate-800 rounded-lg border border-slate-700 p-6 space-y-4">
            <h2 className="text-xl font-semibold text-slate-pool_opt_in">Win probability</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <p className="text-sm text-slate-400 mb-2">Player 1</p>
                <p className="text-3xl font-bold text-sky-400">
                  {(Number(prediction.predicted_prob_p1) * 100).toFixed(1)}%
                </p>
              </div>
              <div>
                <p className="text-sm text-slate-400 mb-2">Player 2</p>
                <p className="text-3xl font-bold text-amber-400">
                  {(Number(prediction.predicted_prob_p2) * 100).toFixed(1)}%
                </p>
              </div>
            </div>
            <p className="text-sm text-slate-400">
              Confidence:{' '}
              <span className="text-slate-200 font-semibold">
                {(Number(prediction.confidence) * 100).toFixed(1)}%
              </span>
            </p>
            {prediction.actual_result != null && (
              <p className="text-sm text-slate-400">
                Actual result (P1 perspective):{' '}
                <span className="text-slate-200">{String(prediction.actual_result)}</span>
              </p>
            )}
          </div>

          <div className="bg-slate-800 rounded-lg border border-slate-700 p-6 space-y-4">
            <h2 className="text-xl font-semibold text-slate-pool_opt_in">Factors</h2>
            <AlfaFactorBreakdown factors={factorsToRecord(prediction.factors_breakdown ?? [])} />
          </div>

          <button
            type="button"
            onClick={handleExport}
            className="flex items-center gap-2 px-6 py-3 bg-slate-700 hover:bg-slate-600 rounded-lg text-slate-200 font-medium transition-colors border border-slate-600"
          >
            Export as PDF (not implemented)
          </button>
        </div>
      )}

      {!prediction && !predictLoading && activeMatchId && (
        <div className="text-center py-12 text-slate-400">
          <p>No prediction found for this match_id.</p>
        </div>
      )}

      {!activeMatchId && !predictLoading && (
        <div className="text-center py-12 text-slate-400">
          <p>Enter a match ID and click Load.</p>
        </div>
      )}

      {predictLoading && (
        <div className="text-center py-12 text-slate-400">
          <p>Loading…</p>
        </div>
      )}
    </div>
  )
}

export default AlfaPredictionExplain
