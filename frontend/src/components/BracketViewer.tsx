import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tournamentsApi, type Match } from '@/api/tournaments'
import { alfaApi } from '@/api/alfa'
import { toast } from '@/lib/toast'
import { useAuth } from '@/contexts/AuthContext'
import MatchEntryModal from './MatchEntryModal'
import MatchClocksPanel from './MatchClocksPanel'
import ForfeitModal from './ForfeitModal'
import AlfaInfoPanel from './AlfaInfoPanel'
import { calculateFargoWinProbability } from '@/utils/winProbability'
import { logger } from '@/lib/logger'

interface BracketMatch extends Match {
  operator_name?: string
  player2_name?: string
}

interface BracketViewerProps {
  tournamentId: string
  onOpenTimekeeper?: (matchId: string) => void
}

const DEFAULT_WARNING_MINUTES = [20, 15, 10, 5, 1]

function toDatetimeLocal(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) {
    return ''
  }
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day}T${h}:${min}`
}

export default function BracketViewer({ tournamentId, onOpenTimekeeper }: BracketViewerProps) {
  const queryClient = useQueryClient()
  const { isDirector, isAdmin, isSuperAdmin, isScoreKeeper } = useAuth()
  const directorOrAdmin = isDirector || isAdmin || isSuperAdmin
  const canEditScores = directorOrAdmin || isScoreKeeper
  const [selectedMatch, setSelectedMatch] = useState<BracketMatch | null>(null)
  const [showScoreForm, setShowScoreForm] = useState(false)
  const [score1, setScore1] = useState('')
  const [score2, setScore2] = useState('')
  const [showMatchModal, setShowMatchModal] = useState(false)
  const [showForfeitModal, setShowForfeitModal] = useState(false)
  const [tableNumberInput, setTableNumberInput] = useState('')
  const [callReportBy, setCallReportBy] = useState('')
  const [callTableNum, setCallTableNum] = useState('')

  const { data: matches = [], isLoading, isError, error } = useQuery({
    queryKey: ['tournament-matches', tournamentId],
    queryFn: () => tournamentsApi.getMatches(tournamentId),
    enabled: !!tournamentId,
  })

  // Fetch tournament details for format/table size
  const { data: tournament } = useQuery({
    queryKey: ['tournament-detail', tournamentId],
    queryFn: () => tournamentsApi.getTournament(tournamentId),
    enabled: !!tournamentId,
  })

  // Subscribe to SSE stream for live updates (match_score_update, match_completed, tournament_progress)
  useEffect(() => {
    if (!tournamentId) return
    const url = tournamentsApi.getStreamUrl(tournamentId)
    const es = new EventSource(url)
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data?.type === 'match_score_update' || data?.type === 'match_completed' || data?.type === 'rack_completed' || data?.type === 'tournament_progress') {
          queryClient.invalidateQueries({ queryKey: ['tournament-matches', tournamentId] })
          queryClient.invalidateQueries({ queryKey: ['tournament-progress', tournamentId] })
        }
      } catch (error) {
        logger.warn('Failed to parse tournament stream event payload', undefined, error as Error)
      }
    }
    es.onerror = () => es.close()
    return () => es.close()
  }, [tournamentId, queryClient])

  // Fetch players for avatar info
  const { data: players = [] } = useQuery({
    queryKey: ['tournament-players', tournamentId],
    queryFn: () => tournamentsApi.getPlayers(),
    enabled: !!tournamentId,
  })

  // Fetch ALFa predictions if admin can access (admin feature)
  const { data: alfaPredictions = {} } = useQuery({
    queryKey: ['bracket-alfa-predictions', tournamentId],
    queryFn: async () => {
      if (!matches.length || !tournament) return {}
      
      const predictions: Record<string, { p1Prob: number; p2Prob: number; confidence: number }> = {}
      
      try {
        // Determine format/table size from tournament
        const format = tournament.game_type?.includes('10-ball') ? '10-ball' : '9-ball'
        const tableSize = '9ft' // Default assumption, could be stored in tournament
        const location = 'tournament' // Default location code
        
        // Fetch ALFa ratings first to get ratings for players
        try {
          const alfaRatings = await alfaApi.getRatings()
          const alfaMap = alfaRatings.rankings.reduce(
            (acc, item) => {
              acc[item.player_name.toLowerCase()] = item.alfa_rating
              return acc
            },
            {} as Record<string, number>
          )
          
          // For each match, if we have both players with ALFa ratings, predict
          for (const match of matches) {
            if (!match.operator_id || !match.player2_id || match.status === 'bye') continue
            
            const p1 = players.find(p => p.player_id === match.operator_id)
            const p2 = players.find(p => p.player_id === match.player2_id)
            
            if (!p1 || !p2) continue
            
            const p1Name = `${p1.first_name} ${p1.last_name}`.toLowerCase()
            const p2Name = `${p2.first_name} ${p2.last_name}`.toLowerCase()
            
            const p1AlfaRating = alfaMap[p1Name]
            const p2AlfaRating = alfaMap[p2Name]
            
            // Only predict if both have ALFa ratings
            if (p1AlfaRating !== undefined && p2AlfaRating !== undefined) {
              const pred = await alfaApi.predict({
                operator_id: parseInt(match.operator_id),
                player2_id: parseInt(match.player2_id),
                race_to: match.race_to || 11,
                table_size: tableSize,
                format: format,
                location: location,
                match_id: match.match_id,
              })
              
              predictions[match.match_id] = {
                p1Prob: pred.predicted_win_prob_p1,
                p2Prob: pred.predicted_win_prob_p2,
                confidence: pred.confidence,
              }
            }
          }
        } catch (error) {
          logger.debug('ALFa prediction unavailable for current user or data', { error })
        }
      } catch (error) {
        logger.debug('Could not fetch ALFa predictions', { error })
      }
      
      return predictions
    },
    enabled: !!tournamentId && matches.length > 0 && !!tournament && directorOrAdmin,
    staleTime: 5 * 60 * 1000, // 5 minutes
  })

  // Build player maps for quick lookup
  const playerNames = players.reduce(
    (acc, player) => {
      acc[player.player_id] = `${player.first_name} ${player.last_name}`
      return acc
    },
    {} as Record<string, string>
  )

  const playerAvatars = players.reduce(
    (acc, player) => {
      if (player.avatar_url) {
        acc[player.player_id] = player.avatar_url
      }
      return acc
    },
    {} as Record<string, string>
  )

  const updateScoreMutation = useMutation({
    mutationFn: ({ matchId, p1Score, p2Score }: { matchId: string; p1Score: number; p2Score: number }) =>
      tournamentsApi.updateMatchScore(matchId, p1Score, p2Score),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tournament-matches', tournamentId] })
      queryClient.invalidateQueries({ queryKey: ['tournament-progress', tournamentId] })
      toast.success('Match score updated!')
      resetForm()
    },
    onError: (error) => {
      toast.error(`Failed to update score: ${error instanceof Error ? error.message : 'Unknown error'}`)
    },
  })

  const resetForm = () => {
    setSelectedMatch(null)
    setShowScoreForm(false)
    setScore1('')
    setScore2('')
    setShowMatchModal(false)
  }

  const handleUpdateScore = () => {
    if (!selectedMatch || !score1 || !score2) {
      toast.error('Please enter scores for both players')
      return
    }

    const p1Score = parseInt(score1)
    const p2Score = parseInt(score2)

    if (p1Score < 0 || p2Score < 0 || isNaN(p1Score) || isNaN(p2Score)) {
      toast.error('Scores must be positive numbers')
      return
    }

    updateScoreMutation.mutate({
      matchId: selectedMatch.match_id,
      p1Score,
      p2Score,
    })
  }

  const handleSelectMatch = (match: BracketMatch) => {
    setSelectedMatch(match)
    setScore1(match.operator_games?.toString() || '0')
    setScore2(match.player2_games?.toString() || '0')
    setShowScoreForm(false)
    setTableNumberInput(match.table_number != null ? String(match.table_number) : '')
    setCallTableNum(match.table_number != null ? String(match.table_number) : '')
    const in20 = new Date()
    in20.setMinutes(in20.getMinutes() + 20)
    setCallReportBy(toDatetimeLocal(in20.toISOString()))
  }

  const { data: tableCalls = [] } = useQuery({
    queryKey: ['table-calls', tournamentId],
    queryFn: () => tournamentsApi.getTableCalls(tournamentId),
    enabled: !!tournamentId && directorOrAdmin,
  })

  const updateMatchMutation = useMutation({
    mutationFn: (data: { table_number?: number }) =>
      selectedMatch ? tournamentsApi.updateMatch(selectedMatch.match_id, data) : Promise.reject(new Error('No match')),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tournament-matches', tournamentId] })
      queryClient.invalidateQueries({ queryKey: ['tournament-progress', tournamentId] })
      toast.success('Table assignment saved')
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed to save'),
  })

  const createTableCallMutation = useMutation({
    mutationFn: () => {
      if (!selectedMatch || !callReportBy || !callTableNum) throw new Error('Set report-by time and table number')
      const tableNum = parseInt(callTableNum, 10)
      if (!Number.isFinite(tableNum)) throw new Error('Invalid table number')
      return tournamentsApi.createTableCall(tournamentId, {
        match_id: selectedMatch.match_id,
        table_number: tableNum,
        report_by: new Date(callReportBy).toISOString(),
        warning_minutes: DEFAULT_WARNING_MINUTES,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['table-calls', tournamentId] })
      queryClient.invalidateQueries({ queryKey: ['tournament-matches', tournamentId] })
      queryClient.invalidateQueries({ queryKey: ['tournament-progress', tournamentId] })
      toast.success('Match called to table. Warnings will be sent at 20/15/10/5/1 min before report time.')
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed to call match'),
  })

  const processWarningsMutation = useMutation({
    mutationFn: () => tournamentsApi.processWarnings(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['table-calls', tournamentId] })
      toast.success(`Processed: ${data.sent} sent, ${data.errors} errors`)
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed to process warnings'),
  })

  const getRound = (m: BracketMatch) => m.round ?? (m as { round_number?: number }).round_number ?? 1
  const getPlayerFargo = (playerId: string | null | undefined): number | null => {
    if (!playerId) return null
    const player = players.find(p => p.player_id === playerId)
    return player?.fargo_score ?? null
  }
  const getAlfaOdds = (matchId: string): { p1Prob: number; p2Prob: number; confidence: number } | null => {
    return alfaPredictions[matchId] ?? null
  }
  const getName = (m: BracketMatch, which: 'operator' | 'player2') => {
    const id = which === 'operator' ? m.operator_id : m.player2_id
    const fromMatch = which === 'operator' ? m.operator_name : m.player2_name
    return (id && playerNames[id]) ?? fromMatch ?? (which === 'operator' ? `Player 1 (${id || '?'})` : `Player 2 (${id || '?'})`)
  }
  const getWinnerName = (m: BracketMatch) => {
    if (!m.winner_player_id) return null
    if (m.winner_player_id === m.operator_id) return playerNames[m.operator_id!] ?? m.operator_name ?? 'Player 1'
    return playerNames[m.player2_id!] ?? m.player2_name ?? 'Player 2'
  }

  // Group matches by round
  const matchesByRound: Record<number, BracketMatch[]> = {}
  matches.forEach((match) => {
    const r = getRound(match)
    if (!matchesByRound[r]) matchesByRound[r] = []
    matchesByRound[r].push(match)
  })

  const rounds = Object.keys(matchesByRound)
    .map(Number)
    .sort((a, b) => a - b)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-96">
        <p className="text-slate-400">Loading bracket...</p>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="rounded-lg border border-amber-700 bg-amber-900/20 p-6 text-amber-200">
        <p className="font-semibold">Something went wrong</p>
        <p className="mt-2 text-sm text-slate-300">
          {error instanceof Error ? error.message : 'Could not load bracket. Generate the bracket first or try again.'}
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col lg:flex-row gap-6">
      {/* Bracket View */}
      <div className="flex-1 overflow-x-auto bg-slate-800/50 backdrop-blur rounded-lg border border-slate-700 p-6">
        {matches.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-slate-400">No bracket generated yet. Generate the bracket to view matches.</p>
          </div>
        ) : (
          <div className="flex gap-8 min-w-min pb-4">
            {rounds.map((round) => (
              <div key={round} className="flex flex-col gap-4">
                <h3 className="text-sm font-semibold text-slate-300 text-center w-48">
                  {round === 1 ? 'Round 1' : round === 2 ? 'Round 2' : round === 3 ? 'Finals' : `Round ${round}`}
                </h3>
                <div className="flex flex-col gap-4">
                  {matchesByRound[round].map((match) => (
                    <div
                      key={match.match_id}
                      onClick={() => handleSelectMatch(match)}
                      className={`w-48 border rounded-lg p-3 cursor-pointer transition-all ${
                        match.status === 'bye'
                          ? 'bg-slate-700/30 border-slate-600 opacity-50'
                          : match.status === 'completed'
                            ? 'bg-green-900/20 border-green-700 hover:border-green-600'
                            : selectedMatch?.match_id === match.match_id
                              ? 'bg-blue-900/30 border-blue-600'
                              : 'bg-slate-700/50 border-slate-600 hover:border-slate-500'
                      }`}
                    >
                      {match.status === 'bye' ? (
                        <div className="text-center text-slate-400 text-sm">BYE</div>
                      ) : (
                        <>
                          <div className="flex items-center gap-2 mb-2">
                            {match.forfeit_reason ? (
                              <span
                                className="text-xs px-2 py-1 rounded bg-amber-700/50 text-amber-200"
                                title={match.forfeit_reason}
                              >
                                DQ / WBF
                              </span>
                            ) : (
                              <span className="text-xs px-2 py-1 rounded bg-slate-600 text-slate-200">
                                {match.status === 'completed' ? '✓ Done' : 'Pending'}
                              </span>
                            )}
                          </div>
                          <div className="space-y-2">
                            <div className="flex items-center justify-between text-sm">
                              <span className="text-white font-medium truncate flex-1">
                                {getName(match, 'operator')}
                              </span>
                              <span className="ml-2 font-bold text-blue-200 w-6 text-right">
                                {match.operator_games ?? '-'}
                              </span>
                            </div>
                            <div className="h-px bg-slate-600" />
                            <div className="flex items-center justify-between text-sm">
                              <span className="text-white font-medium truncate flex-1">
                                {getName(match, 'player2')}
                              </span>
                              <span className="ml-2 font-bold text-blue-200 w-6 text-right">
                                {match.player2_games ?? '-'}
                              </span>
                            </div>
                          </div>
                          {(() => {
                            const p1Fargo = getPlayerFargo(match.operator_id)
                            const p2Fargo = getPlayerFargo(match.player2_id)
                            const fargoProbs = match.status !== 'completed' ? calculateFargoWinProbability(p1Fargo, p2Fargo) : null
                            const alfaProbs = getAlfaOdds(match.match_id)
                            const hasLive =
                              match.live_p1_win_prob != null &&
                              match.live_p2_win_prob != null &&
                              Number.isFinite(match.live_p1_win_prob) &&
                              Number.isFinite(match.live_p2_win_prob)

                            if (hasLive || fargoProbs || alfaProbs) {
                              return (
                                <div className="mt-2 pt-2 border-t border-slate-600">
                                  <p className="text-[10px] text-slate-400 mb-1 text-center">Win Odds</p>
                                  {hasLive && (
                                    <div className="flex justify-between text-xs mb-1">
                                      <span className="text-[9px] text-emerald-500/90">Live</span>
                                      <span className="text-emerald-400 font-semibold">
                                        {Math.round((match.live_p1_win_prob as number) * 100)}%
                                      </span>
                                      <span className="text-slate-500">vs</span>
                                      <span className="text-slate-400 font-semibold">
                                        {Math.round((match.live_p2_win_prob as number) * 100)}%
                                      </span>
                                    </div>
                                  )}
                                  {fargoProbs && (
                                    <div className="flex justify-between text-xs mb-1">
                                      <span className="text-[9px] text-slate-500">Fargo</span>
                                      <span className="text-sky-400 font-semibold">{Math.round(fargoProbs[0] * 100)}%</span>
                                      <span className="text-slate-500">vs</span>
                                      <span className="text-slate-400 font-semibold">{Math.round(fargoProbs[1] * 100)}%</span>
                                    </div>
                                  )}
                                  {alfaProbs && directorOrAdmin && (
                                    <div className="flex justify-between text-xs">
                                      <span className="text-[9px] text-slate-500">ALFa</span>
                                      <span className="text-purple-400 font-semibold">{Math.round(alfaProbs.p1Prob * 100)}%</span>
                                      <span className="text-slate-500">vs</span>
                                      <span className="text-slate-400 font-semibold">{Math.round(alfaProbs.p2Prob * 100)}%</span>
                                    </div>
                                  )}
                                </div>
                              )
                            }
                            return null
                          })()}
                          {match.winner_player_id && (
                            <div className="mt-2 text-xs text-center text-green-300 font-semibold">
                              Winner: {getWinnerName(match) ?? '—'}
                              {match.forfeit_reason && (
                                <span className="block text-amber-200/90 text-[10px] mt-0.5" title={match.forfeit_reason}>
                                  ({match.forfeit_reason})
                                </span>
                              )}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Match Details Panel */}
      <div className="lg:w-80 flex-shrink-0">
        {selectedMatch ? (
          <div className="bg-slate-800/50 backdrop-blur rounded-lg border border-slate-700 p-6 sticky top-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-white">Match Details</h2>
              <button
                onClick={() => resetForm()}
                className="text-slate-400 hover:text-white transition-colors"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <p className="text-xs text-slate-400 mb-1">Match ID</p>
                <p className="text-sm text-white font-mono break-all">{selectedMatch.match_id}</p>
              </div>

              {(selectedMatch.handicap_applied && (selectedMatch.operator_handicapped_race != null || selectedMatch.player2_handicapped_race != null)) ? (
                <div>
                  <p className="text-xs text-slate-400 mb-1">Race (Fargo handicap)</p>
                  <p className="text-sm text-white">
                    {getName(selectedMatch, 'operator')}: {selectedMatch.operator_handicapped_race ?? selectedMatch.race_to ?? '—'} · {getName(selectedMatch, 'player2')}: {selectedMatch.player2_handicapped_race ?? selectedMatch.race_to ?? '—'}
                  </p>
                </div>
              ) : selectedMatch.race_to != null ? (
                <div>
                  <p className="text-xs text-slate-400 mb-1">Race to</p>
                  <p className="text-sm text-white">{selectedMatch.race_to}</p>
                </div>
              ) : null}

              {(selectedMatch.projected_start_time || selectedMatch.projected_end_time) && (
                <div>
                  <p className="text-xs text-slate-400 mb-1">Projected time</p>
                  <p className="text-sm text-white">
                    {selectedMatch.projected_start_time
                      ? new Date(selectedMatch.projected_start_time).toLocaleTimeString(undefined, {
                          hour: 'numeric',
                          minute: '2-digit',
                        })
                      : '—'}
                    {selectedMatch.projected_end_time ? (
                      <> – {new Date(selectedMatch.projected_end_time).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}</>
                    ) : null}
                  </p>
                </div>
              )}

              {(() => {
                const p1Fargo = getPlayerFargo(selectedMatch.operator_id)
                const p2Fargo = getPlayerFargo(selectedMatch.player2_id)
                const fargoProbs = selectedMatch.status !== 'completed' ? calculateFargoWinProbability(p1Fargo, p2Fargo) : null
                const alfaProbs = getAlfaOdds(selectedMatch.match_id)
                const hasLive =
                  selectedMatch.live_p1_win_prob != null &&
                  selectedMatch.live_p2_win_prob != null &&
                  Number.isFinite(selectedMatch.live_p1_win_prob) &&
                  Number.isFinite(selectedMatch.live_p2_win_prob)
                const liveP1 = hasLive ? Math.round((selectedMatch.live_p1_win_prob as number) * 100) : null
                const liveP2 = hasLive ? Math.round((selectedMatch.live_p2_win_prob as number) * 100) : null

                if (hasLive || fargoProbs || alfaProbs) {
                  return (
                    <div className="space-y-3">
                      {hasLive && liveP1 != null && liveP2 != null && (
                        <div className="bg-slate-700/50 rounded-lg p-3 border border-emerald-700/50">
                          <p className="text-xs text-emerald-300/90 mb-2 text-center">
                            Live odds (score-state)
                          </p>
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-sm font-semibold text-emerald-400 w-12 text-right">{liveP1}%</span>
                            <div className="flex-1 h-5 rounded-full overflow-hidden bg-slate-700 flex">
                              <div
                                className="bg-emerald-500 transition-all duration-300"
                                style={{ width: `${liveP1}%` }}
                              />
                              <div
                                className="bg-slate-500 transition-all duration-300"
                                style={{ width: `${liveP2}%` }}
                              />
                            </div>
                            <span className="text-sm font-semibold text-slate-400 w-12">{liveP2}%</span>
                          </div>
                          <p className="text-[10px] text-slate-500 text-center">
                            Updates after each rack or score change
                          </p>
                        </div>
                      )}
                      {fargoProbs && (
                        <div className="bg-slate-700/50 rounded-lg p-3 border border-slate-600">
                          <p className="text-xs text-slate-400 mb-2 text-center">Fargo-based Win Probability</p>
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-sm font-semibold text-sky-400 w-12 text-right">{Math.round(fargoProbs[0] * 100)}%</span>
                            <div className="flex-1 h-5 rounded-full overflow-hidden bg-slate-700 flex">
                              <div 
                                className="bg-sky-500 transition-all duration-300"
                                style={{ width: `${Math.round(fargoProbs[0] * 100)}%` }}
                              />
                              <div 
                                className="bg-slate-500 transition-all duration-300"
                                style={{ width: `${Math.round(fargoProbs[1] * 100)}%` }}
                              />
                            </div>
                            <span className="text-sm font-semibold text-slate-400 w-12">{Math.round(fargoProbs[1] * 100)}%</span>
                          </div>
                          <div className="flex justify-between text-xs text-slate-400">
                            <span className="truncate flex-1 text-left">{getName(selectedMatch, 'operator')}</span>
                            <span className="truncate flex-1 text-right">{getName(selectedMatch, 'player2')}</span>
                          </div>
                        </div>
                      )}
                      
                      {alfaProbs && directorOrAdmin && (
                        <div className="bg-purple-900/20 rounded-lg p-3 border border-purple-700/50">
                          <p className="text-xs text-purple-300 mb-2 text-center">ALFa-based Win Probability (Premium)</p>
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-sm font-semibold text-purple-400 w-12 text-right">{Math.round(alfaProbs.p1Prob * 100)}%</span>
                            <div className="flex-1 h-5 rounded-full overflow-hidden bg-slate-700 flex">
                              <div 
                                className="bg-purple-500 transition-all duration-300"
                                style={{ width: `${Math.round(alfaProbs.p1Prob * 100)}%` }}
                              />
                              <div 
                                className="bg-slate-500 transition-all duration-300"
                                style={{ width: `${Math.round(alfaProbs.p2Prob * 100)}%` }}
                              />
                            </div>
                            <span className="text-sm font-semibold text-slate-400 w-12">{Math.round(alfaProbs.p2Prob * 100)}%</span>
                          </div>
                          <div className="flex justify-between text-xs text-slate-400 mb-1">
                            <span className="truncate flex-1 text-left">{getName(selectedMatch, 'operator')}</span>
                            <span className="truncate flex-1 text-right">{getName(selectedMatch, 'player2')}</span>
                          </div>
                          <p className="text-[10px] text-purple-300/70 text-center">Confidence: {Math.round(alfaProbs.confidence * 100)}%</p>
                        </div>
                      )}
                    </div>
                  )
                }
                return null
              })()}

              {directorOrAdmin && <AlfaInfoPanel className="mb-4" adminOnly={true} />}

              <div>
                <p className="text-xs text-slate-400 mb-1">Status</p>
                <span
                  className={`inline-block px-3 py-1 rounded text-sm font-semibold ${
                    selectedMatch.status === 'completed'
                      ? 'bg-green-500/20 text-green-200'
                      : selectedMatch.status === 'bye'
                        ? 'bg-gray-500/20 text-gray-200'
                        : 'bg-yellow-500/20 text-yellow-200'
                  }`}
                >
                  {selectedMatch.status.charAt(0).toUpperCase() + selectedMatch.status.slice(1)}
                </span>
              </div>

              <div className="border-t border-slate-700 pt-4">
                <h3 className="text-sm font-semibold text-slate-200 mb-3">Players</h3>
                <div className="space-y-2">
                  <div>
                    <p className="text-white font-medium">{getName(selectedMatch, 'operator')}</p>
                    <p className="text-lg font-bold text-blue-300">{selectedMatch.operator_games ?? '—'} games</p>
                  </div>
                  <div>
                    <p className="text-white font-medium">{getName(selectedMatch, 'player2')}</p>
                    <p className="text-lg font-bold text-blue-300">{selectedMatch.player2_games ?? '—'} games</p>
                  </div>
                </div>
                {(() => {
                  const p1 = players.find((x) => x.player_id === selectedMatch.operator_id)
                  const p2 = players.find((x) => x.player_id === selectedMatch.player2_id)
                  const prob = calculateFargoWinProbability(p1?.fargo_score, p2?.fargo_score)
                  return prob ? (
                    <p className="mt-2 text-xs text-slate-400">
                      Fargo win probability: {Math.round(prob[0] * 100)}% vs {Math.round(prob[1] * 100)}%
                    </p>
                  ) : null
                })()}
                {selectedMatch.winner_player_id && (
                  <p className="mt-2 text-sm text-green-300 font-semibold">
                    Winner: {getWinnerName(selectedMatch) ?? '—'}
                  </p>
                )}
              </div>

              {directorOrAdmin && selectedMatch.status !== 'completed' && selectedMatch.status !== 'bye' && selectedMatch.operator_id && selectedMatch.player2_id && (
                <div className="border-t border-slate-700 pt-4">
                  <button
                    type="button"
                    onClick={() => setShowForfeitModal(true)}
                    className="w-full px-3 py-2 rounded bg-amber-700/80 text-amber-pool_opt_in text-sm font-medium hover:bg-amber-700"
                  >
                    Mark Forfeit / DQ
                  </button>
                </div>
              )}

              {directorOrAdmin && (
                <div className="border-t border-slate-700 pt-4 space-y-4">
                  <h3 className="text-sm font-semibold text-slate-200">Table assignment &amp; call</h3>
                  <div className="flex gap-2 items-center">
                    <label className="text-xs text-slate-400">Table #</label>
                    <input
                      type="number"
                      min={1}
                      value={tableNumberInput}
                      onChange={(e) => setTableNumberInput(e.target.value)}
                      className="w-20 px-2 py-1.5 bg-slate-700 border border-slate-600 rounded text-white text-sm"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        const n = parseInt(tableNumberInput, 10)
                        if (Number.isFinite(n) && n >= 1)
                          updateMatchMutation.mutate({ table_number: n })
                      }}
                      disabled={updateMatchMutation.isPending}
                      className="px-2 py-1.5 rounded bg-slate-600 text-slate-200 text-xs font-medium hover:bg-slate-500 disabled:opacity-50"
                    >
                      Save
                    </button>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400 mb-1">Call to table (report-by time)</p>
                    <input
                      type="datetime-local"
                      value={callReportBy}
                      onChange={(e) => setCallReportBy(e.target.value)}
                      className="w-full px-2 py-1.5 bg-slate-700 border border-slate-600 rounded text-white text-sm mb-2"
                    />
                    <div className="flex gap-2 items-center mb-2">
                      <label className="text-xs text-slate-400">Table #</label>
                      <input
                        type="number"
                        min={1}
                        value={callTableNum}
                        onChange={(e) => setCallTableNum(e.target.value)}
                        className="w-16 px-2 py-1.5 bg-slate-700 border border-slate-600 rounded text-white text-sm"
                      />
                      <button
                        type="button"
                        onClick={() => createTableCallMutation.mutate()}
                        disabled={createTableCallMutation.isPending || !callReportBy || !callTableNum}
                        className="px-3 py-1.5 rounded bg-amber-600 text-white text-xs font-semibold hover:bg-amber-700 disabled:opacity-50"
                      >
                        Call to table
                      </button>
                    </div>
                    <p className="text-xs text-slate-500">Players get 20, 15, 10, 5, 1 min warnings by email.</p>
                  </div>
                  <div>
                    <button
                      type="button"
                      onClick={() => processWarningsMutation.mutate()}
                      disabled={processWarningsMutation.isPending}
                      className="w-full px-3 py-2 rounded bg-slate-600 text-slate-200 text-sm font-medium hover:bg-slate-500 disabled:opacity-50"
                    >
                      {processWarningsMutation.isPending ? 'Processing…' : 'Send due warnings now'}
                    </button>
                    {tableCalls.length > 0 && (
                      <p className="text-xs text-slate-500 mt-1">{tableCalls.length} active table call(s)</p>
                    )}
                  </div>
                </div>
              )}

              <MatchClocksPanel
                matchId={selectedMatch.match_id}
                tournamentId={tournamentId}
                onOpenTimekeeper={onOpenTimekeeper}
              />

              {canEditScores && selectedMatch.status !== 'completed' && selectedMatch.status !== 'bye' && (
                <>
                  {!showScoreForm ? (
                    <button
                      onClick={() => setShowMatchModal(true)}
                      className="w-full mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition-colors"
                    >
                      ✎ Enter Score
                    </button>
                  ) : (
                    <div className="space-y-3 mt-4 pt-4 border-t border-slate-700">
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Games — {getName(selectedMatch, 'operator')}</label>
                        <input
                          type="number"
                          value={score1}
                          onChange={(e) => setScore1(e.target.value)}
                          min="0"
                          className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Games — {getName(selectedMatch, 'player2')}</label>
                        <input
                          type="number"
                          value={score2}
                          onChange={(e) => setScore2(e.target.value)}
                          min="0"
                          className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
                        />
                      </div>
                      <div className="flex gap-2 pt-2">
                        <button
                          onClick={handleUpdateScore}
                          disabled={updateScoreMutation.isPending}
                          className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-700 disabled:opacity-50 transition-colors"
                        >
                          {updateScoreMutation.isPending ? 'Saving...' : '✓ Save'}
                        </button>
                        <button
                          onClick={() => setShowScoreForm(false)}
                          className="flex-1 px-4 py-2 bg-slate-700 text-white rounded-lg font-semibold hover:bg-slate-600 transition-colors"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        ) : (
          <div className="bg-slate-800/50 backdrop-blur rounded-lg border border-slate-700 p-6 text-center">
            <p className="text-slate-400">Select a match to view details and enter scores</p>
          </div>
        )}
      </div>

      {/* Match Entry Modal */}
      <MatchEntryModal
        match={selectedMatch}
        isOpen={showMatchModal}
        onClose={() => setShowMatchModal(false)}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ['tournament-matches', tournamentId] })
          queryClient.invalidateQueries({ queryKey: ['tournament-progress', tournamentId] })
          resetForm()
        }}
        playerNames={playerNames}
        playerAvatars={playerAvatars}
      />

      <ForfeitModal
        match={selectedMatch}
        tournamentId={tournamentId}
        isOpen={showForfeitModal}
        onClose={() => setShowForfeitModal(false)}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ['tournament-matches', tournamentId] })
          queryClient.invalidateQueries({ queryKey: ['tournament-progress', tournamentId] })
          setShowForfeitModal(false)
        }}
        playerNames={playerNames}
      />
    </div>
  )
}
