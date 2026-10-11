/**
 * Score keeper mode: view matches for a single table, enter scores, show timers.
 * For score_keeper (and director/admin) to use on a tablet at the table.
 */

import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { tournamentsApi, type Match } from '@/api/tournaments'
import MatchEntryModal from '@/components/MatchEntryModal'
import { useAuth } from '@/contexts/AuthContext'

export default function ScoreKeeperView() {
  const queryClient = useQueryClient()
  const { isScoreKeeper, isDirector, isAdmin, isSuperAdmin } = useAuth()
  const canAccess = isScoreKeeper || isDirector || isAdmin || isSuperAdmin

  const [selectedTournamentId, setSelectedTournamentId] = useState<string | null>(null)
  const [tableNumber, setTableNumber] = useState<number>(1)
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null)
  const [showScoreModal, setShowScoreModal] = useState(false)

  const { data: tournaments = [] } = useQuery({
    queryKey: ['tournaments'],
    queryFn: () => tournamentsApi.getTournaments(),
    enabled: canAccess,
  })

  const { data: tableMatches = [], isLoading } = useQuery({
    queryKey: ['tournament-matches-by-table', selectedTournamentId, tableNumber],
    queryFn: () =>
      selectedTournamentId
        ? tournamentsApi.getMatchesByTable(selectedTournamentId, tableNumber)
        : Promise.resolve([]),
    enabled: !!selectedTournamentId && canAccess,
  })

  const { data: players = [] } = useQuery({
    queryKey: ['tournament-players', selectedTournamentId],
    queryFn: () => tournamentsApi.getPlayers(),
    enabled: !!selectedTournamentId,
  })

  const playerNames = players.reduce(
    (acc, p) => {
      acc[p.player_id] = `${p.first_name} ${p.last_name}`
      return acc
    },
    {} as Record<string, string>
  )
  const playerAvatars = players.reduce(
    (acc, p) => {
      if (p.avatar_url) acc[p.player_id] = p.avatar_url
      return acc
    },
    {} as Record<string, string>
  )

  const pendingMatches = tableMatches.filter(
    (m) => m.status !== 'completed' && m.status !== 'bye'
  )
  const currentMatch = pendingMatches[0] ?? null

  if (!canAccess) {
    return (
      <div className="p-6 text-center text-slate-400">
        <p>Score keeper mode is only available to score keepers and directors.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full overflow-auto bg-slate-900">
      <header className="sticky top-0 z-10 bg-slate-800/95 border-b border-slate-700 p-3">
        <h1 className="text-xl font-bold text-white">Score keeper</h1>
        <div className="flex flex-wrap gap-2 mt-2">
          <select
            value={selectedTournamentId ?? ''}
            onChange={(e) => setSelectedTournamentId(e.target.value || null)}
            className="px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm min-w-[140px]"
          >
            <option value="">Tournament</option>
            {tournaments
              .filter((t) => t.status === 'in_progress' || t.status === 'registration')
              .map((t) => (
                <option key={t.tournament_id} value={t.tournament_id}>
                  {t.tournament_name}
                </option>
              ))}
          </select>
          <input
            type="number"
            min={1}
            value={tableNumber}
            onChange={(e) => setTableNumber(parseInt(e.target.value, 10) || 1)}
            className="w-16 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white text-sm"
            aria-label="Table number"
          />
          <span className="self-center text-slate-400 text-sm">Table</span>
        </div>
      </header>

      <div className="flex-1 flex flex-col items-center justify-center p-6 max-w-xl mx-auto w-full">
        {!selectedTournamentId ? (
          <p className="text-slate-500 text-center">Select a tournament above.</p>
        ) : isLoading ? (
          <p className="text-slate-400 text-center">Loading…</p>
        ) : !currentMatch ? (
          <p className="text-slate-400 text-center">
            {tableMatches.length === 0 ? `No matches at table ${tableNumber}.` : 'No active match.'}
          </p>
        ) : (
          <div className="w-full space-y-6">
            <p className="text-slate-400 text-center text-sm">
              {currentMatch.operator_name ?? playerNames[currentMatch.operator_id!] ?? 'TBD'} vs{' '}
              {currentMatch.player2_name ?? playerNames[currentMatch.player2_id!] ?? 'TBD'}
            </p>
            <button
              type="button"
              onClick={() => {
                setSelectedMatch(currentMatch)
                setShowScoreModal(true)
              }}
              className="w-full min-h-[80px] py-6 rounded-2xl bg-felt text-slate-900 text-2xl font-bold hover:bg-felt/90 active:scale-[0.98] transition-all touch-manipulation"
            >
              Enter score
            </button>
          </div>
        )}
      </div>

      <MatchEntryModal
        match={selectedMatch}
        isOpen={showScoreModal}
        simpleMode
        onClose={() => {
          setShowScoreModal(false)
          setSelectedMatch(null)
        }}
        onSuccess={() => {
          queryClient.invalidateQueries({
            queryKey: ['tournament-matches-by-table', selectedTournamentId, tableNumber],
          })
          queryClient.invalidateQueries({ queryKey: ['tournament-matches', selectedTournamentId ?? ''] })
          setShowScoreModal(false)
          setSelectedMatch(null)
        }}
        playerNames={playerNames}
        playerAvatars={playerAvatars}
      />
    </div>
  )
}
