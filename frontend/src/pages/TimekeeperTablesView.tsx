/**
 * Time keeper: view all tables on screen. Tap a table to open full-detail popup.
 * For timekeepers to monitor all tables and drill into any table's details.
 * Director table view: quick score entry in table popup.
 */

import { useState, useMemo, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tournamentsApi, type Match } from '@/api/tournaments'
import MatchClocksPanel from '@/components/MatchClocksPanel'
import { useAuth } from '@/contexts/AuthContext'
import { toast } from '@/lib/toast'

function getPlayerName(m: Match, player: 'operator' | 'player2'): string {
  const id = player === 'operator' ? m.operator_id : m.player2_id
  const name = player === 'operator' ? m.operator_name : m.player2_name
  return name ?? id ?? 'TBD'
}

interface TableDetailModalProps {
  tournamentId: string
  tableNumber: number
  matches: Match[]
  onClose: () => void
  canEditScores?: boolean
}

function TableDetailModal({ tournamentId, tableNumber, matches, onClose, canEditScores = false }: TableDetailModalProps) {
  const queryClient = useQueryClient()
  const [score1, setScore1] = useState('')
  const [score2, setScore2] = useState('')

  const pending = matches.filter((m) => m.status !== 'completed' && m.status !== 'bye')
  const currentMatch = pending[0] ?? null
  const completed = matches.filter((m) => m.status === 'completed')

  useEffect(() => {
    if (currentMatch) {
      setScore1(String(currentMatch.operator_games ?? currentMatch.operator_score ?? 0))
      setScore2(String(currentMatch.player2_games ?? currentMatch.player2_score ?? 0))
    }
  }, [currentMatch?.match_id])

  const updateScoreMutation = useMutation({
    mutationFn: ({ matchId, p1, p2 }: { matchId: string; p1: number; p2: number }) =>
      tournamentsApi.updateMatchScore(matchId, p1, p2),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tournament-matches', tournamentId] })
      toast.success('Score updated')
      setScore1('')
      setScore2('')
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed to update score'),
  })

  const handleScoreSave = () => {
    if (!currentMatch) return
    const p1 = parseInt(score1, 10)
    const p2 = parseInt(score2, 10)
    if (isNaN(p1) || isNaN(p2) || p1 < 0 || p2 < 0) {
      toast.error('Enter valid scores')
      return
    }
    updateScoreMutation.mutate({ matchId: currentMatch.match_id, p1, p2 })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <div
        className="bg-slate-800 rounded-xl border border-slate-600 shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 bg-slate-800 border-b border-slate-600 p-4 flex items-center justify-between">
          <h2 className="text-xl font-bold text-white">Table {tableNumber}</h2>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700"
            aria-label="Close"
          >
            ✕
          </button>
        </div>
        <div className="p-4 space-y-4">
          {/* Current match */}
          {currentMatch && (
            <div className="rounded-lg border border-slate-600 bg-slate-700/50 p-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-2">Current match</h3>
              <p className="text-white font-medium mb-2">
                {getPlayerName(currentMatch, 'operator')} vs {getPlayerName(currentMatch, 'player2')}
              </p>
              <p className="text-xs text-slate-400 mb-2">
                Round {currentMatch.round ?? currentMatch.round_number ?? '—'} • Race to {currentMatch.race_to ?? '—'}
              </p>
              <MatchClocksPanel matchId={currentMatch.match_id} tournamentId={tournamentId} />
              {canEditScores && (
                <div className="mt-4 pt-4 border-t border-slate-600 space-y-3">
                  <p className="text-xs font-semibold text-slate-300">Quick score entry</p>
                  <div className="flex gap-2 items-center">
                    <input
                      type="number"
                      min={0}
                      value={score1}
                      onChange={(e) => setScore1(e.target.value)}
                      className="w-16 px-2 py-1.5 bg-slate-700 border border-slate-600 rounded text-white text-sm"
                    />
                    <span className="text-slate-400">–</span>
                    <input
                      type="number"
                      min={0}
                      value={score2}
                      onChange={(e) => setScore2(e.target.value)}
                      className="w-16 px-2 py-1.5 bg-slate-700 border border-slate-600 rounded text-white text-sm"
                    />
                    <button
                      type="button"
                      onClick={handleScoreSave}
                      disabled={updateScoreMutation.isPending}
                      className="px-3 py-1.5 rounded bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
                    >
                      {updateScoreMutation.isPending ? 'Saving…' : 'Save'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Completed matches at this table */}
          {completed.length > 0 && (
            <div className="rounded-lg border border-slate-600 bg-slate-700/30 p-4">
              <h3 className="text-sm font-semibold text-slate-300 mb-2">Completed at this table</h3>
              <ul className="space-y-2">
                {completed.map((m) => (
                  <li key={m.match_id} className="text-sm text-slate-200">
                    {getPlayerName(m, 'operator')} vs {getPlayerName(m, 'player2')} —{' '}
                    <span className="text-green-300 font-medium">
                      {m.operator_games ?? m.operator_score ?? 0}–{m.player2_games ?? m.player2_score ?? 0}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {!currentMatch && completed.length === 0 && (
            <p className="text-slate-400 text-sm">No matches at this table.</p>
          )}
        </div>
      </div>
    </div>
  )
}

export default function TimekeeperTablesView() {
  const { isDirector, isAdmin, isSuperAdmin, isScoreKeeper } = useAuth()
  const canAccess = isDirector || isAdmin || isSuperAdmin || isScoreKeeper

  const [selectedTournamentId, setSelectedTournamentId] = useState<string | null>(null)
  const [selectedTable, setSelectedTable] = useState<number | null>(null)

  const { data: tournaments = [] } = useQuery({
    queryKey: ['tournaments'],
    queryFn: () => tournamentsApi.getTournaments(),
    enabled: canAccess,
  })

  const { data: matches = [], isLoading } = useQuery({
    queryKey: ['tournament-matches', selectedTournamentId],
    queryFn: () => (selectedTournamentId ? tournamentsApi.getMatches(selectedTournamentId) : Promise.resolve([])),
    enabled: !!selectedTournamentId && canAccess,
  })

  const tablesWithMatches = useMemo(() => {
    const byTable = new Map<number, Match[]>()
    for (const m of matches) {
      const tn = m.table_number ?? 0
      if (tn > 0) {
        const list = byTable.get(tn) ?? []
        list.push(m)
        byTable.set(tn, list)
      }
    }
    return Array.from(byTable.entries())
      .sort(([a], [b]) => a - b)
      .map(([tableNum, ms]) => ({ tableNumber: tableNum, matches: ms }))
  }, [matches])

  if (!canAccess) {
    return (
      <div className="p-6 text-center text-slate-400">
        <p>Time keeper view is only available to directors and score keepers.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full overflow-auto bg-slate-900">
      <header className="sticky top-0 z-10 bg-slate-800/95 border-b border-slate-700 p-4">
        <h1 className="text-2xl font-bold text-white">Time keeper — All tables</h1>
        <p className="text-slate-400 text-sm mt-1">Tap a table to see full details</p>
      </header>

      <div className="p-4 space-y-6 max-w-4xl mx-auto w-full">
        <div className="bg-slate-800/50 rounded-lg border border-slate-700 p-4">
          <label className="block text-sm font-semibold text-slate-300 mb-2">Tournament</label>
          <select
            value={selectedTournamentId ?? ''}
            onChange={(e) => {
              setSelectedTournamentId(e.target.value || null)
              setSelectedTable(null)
            }}
            className="w-full px-4 py-2.5 bg-slate-700 border border-slate-600 rounded-lg text-white"
          >
            <option value="">Select tournament</option>
            {tournaments
              .filter((t) => t.status === 'in_progress' || t.status === 'registration')
              .map((t) => (
                <option key={t.tournament_id} value={t.tournament_id}>
                  {t.tournament_name}
                </option>
              ))}
          </select>
        </div>

        {!selectedTournamentId ? (
          <p className="text-slate-500 text-center py-12">Select a tournament to see tables.</p>
        ) : isLoading ? (
          <p className="text-slate-400 text-center py-12">Loading matches…</p>
        ) : tablesWithMatches.length === 0 ? (
          <p className="text-slate-400 text-center py-12">No tables with matches yet.</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            {tablesWithMatches.map(({ tableNumber, matches: tableMatches }) => {
              const pending = tableMatches.filter((m) => m.status !== 'completed' && m.status !== 'bye')
              const current = pending[0]
              const isActive = current != null

              return (
                <button
                  key={tableNumber}
                  type="button"
                  onClick={() => setSelectedTable(tableNumber)}
                  className={`min-h-[100px] p-4 rounded-xl border-2 text-left transition-all touch-manipulation ${
                    isActive
                      ? 'bg-felt/20 border-felt/60 hover:bg-felt/30'
                      : 'bg-slate-700/50 border-slate-600 hover:bg-slate-600/50'
                  }`}
                >
                  <div className="font-bold text-lg text-white">Table {tableNumber}</div>
                  {current ? (
                    <p className="text-sm text-slate-300 mt-1 truncate" title={`${getPlayerName(current, 'operator')} vs ${getPlayerName(current, 'player2')}`}>
                      {getPlayerName(current, 'operator')} vs {getPlayerName(current, 'player2')}
                    </p>
                  ) : (
                    <p className="text-xs text-slate-500 mt-1">No active match</p>
                  )}
                  <p className="text-xs text-slate-500 mt-1">
                    {tableMatches.filter((m) => m.status === 'completed').length} completed
                  </p>
                </button>
              )
            })}
          </div>
        )}
      </div>

      {selectedTable != null && selectedTournamentId && (
        <TableDetailModal
          tournamentId={selectedTournamentId}
          tableNumber={selectedTable}
          matches={tablesWithMatches.find((t) => t.tableNumber === selectedTable)?.matches ?? []}
          onClose={() => setSelectedTable(null)}
          canEditScores={canAccess}
        />
      )}
    </div>
  )
}
