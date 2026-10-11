import { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { tournamentsApi } from '@/api/tournaments'
import BracketGrid from '@/components/BracketGrid'
import BracketVisualization from '@/components/BracketVisualization'
import CheckInQRModal from '@/components/CheckInQRModal'
import { useAuth } from '@/contexts/AuthContext'
import { toast } from '@/lib/toast'

export default function Bracket() {
  const location = useLocation()
  const navigate = useNavigate()
  const { isDirector, isAdmin, isSuperAdmin } = useAuth()
  const isDirectorMode = isDirector || isAdmin || isSuperAdmin
  const stateTournamentId = (location.state as { tournamentId?: string } | null)?.tournamentId

  const basePath = location.pathname.startsWith('/director') ? '/director' : '/tournaments'
  const openTimekeeper = (matchId: string) => {
    navigate(`${basePath}/bracket/timekeeper?matchId=${encodeURIComponent(matchId)}`)
  }
  const [selectedTournamentId, setSelectedTournamentId] = useState<string | null>(stateTournamentId ?? null)
  const [stage2Cutoff, setStage2Cutoff] = useState(16)
  const [stage2SeedStrategy, setStage2SeedStrategy] = useState<'placement' | 'seed' | 'manual'>('placement')
  const [stage2RaceTo, setStage2RaceTo] = useState(7)
  const [stage2AdvancingIds, setStage2AdvancingIds] = useState('')
  const [stage2ByeIds, setStage2ByeIds] = useState('')
  const [stage2ByeSeeds, setStage2ByeSeeds] = useState('')

  const { data: tournaments = [], isLoading } = useQuery({
    queryKey: ['tournaments', { includeTest: isSuperAdmin }],
    queryFn: () => tournamentsApi.getTournaments(undefined, isSuperAdmin),
    // For demonstration, add test tournament if not returned by API
    onSuccess: (data) => {
      if (isSuperAdmin && !data.some((t: any) => t.tournament_name === 'test2')) {
        // Add test tournament for demonstration
        const testTournament = {
          tournament_id: 'test2_tournament_final',
          tournament_name: 'test2',
          tournament_date: '2026-03-05T20:00:00.000000',
          location: 'Shooters, Stuart FL',
          elimination_type: 'double_elimination',
          max_players: 64,
          tables_available: 14,
          entry_fee_cents: 100000, // $1000 in cents
          status: 'completed'
        }
        data.unshift(testTournament)
      }
    }
  })

  const { data: progress } = useQuery({
    queryKey: ['tournament-progress', selectedTournamentId],
    queryFn: () => tournamentsApi.getTournamentProgress(selectedTournamentId!),
    enabled: !!selectedTournamentId,
  })

  const { data: tournamentPlayers = [] } = useQuery({
    queryKey: ['tournament-players', selectedTournamentId],
    queryFn: () => {
      if (selectedTournamentId === 'test2_tournament_final') {
        // Return mock players for test2 tournament
        return Promise.resolve([
          {
            player_id: '1',
            first_name: 'Kristina',
            last_name: 'Tkach',
            nickname: null,
            email: null,
            phone: null,
            license_number: null,
            license_expiry_date: null,
            avatar_url: null,
            fargo_score: 747.0,
            fargo_robustness: null,
            fargo_last_sync: null,
            fargo_source: null,
            nationality: 'AIN',
            hometown: null,
            state: null,
            membership_status: 'active',
            hall_of_fame: false,
            total_tournaments_played: 0,
            total_points: 0.0,
            current_rank: null,
            hot_streak_count: 0,
            tournament_player_id: 'test2_tournament_final_1',
            registered_at: '2026-03-05T20:00:00.000000',
            status: 'registered',
            seed: null,
            group_id: null,
            table_assigned: null,
            checked_in: false,
            checked_in_at: null,
            fargo_handicap: 0
          },
          {
            player_id: '2',
            first_name: 'Kelly',
            last_name: 'Fisher',
            nickname: null,
            email: null,
            phone: null,
            license_number: null,
            license_expiry_date: null,
            avatar_url: null,
            fargo_score: 715.0,
            fargo_robustness: null,
            fargo_last_sync: null,
            fargo_source: null,
            nationality: 'GBR',
            hometown: null,
            state: null,
            membership_status: 'active',
            hall_of_fame: false,
            total_tournaments_played: 0,
            total_points: 0.0,
            current_rank: null,
            hot_streak_count: 0,
            tournament_player_id: 'test2_tournament_final_2',
            registered_at: '2026-03-05T20:00:00.000000',
            status: 'registered',
            seed: null,
            group_id: null,
            table_assigned: null,
            checked_in: false,
            checked_in_at: null,
            fargo_handicap: 0
          }
        ])
      }
      return tournamentsApi.getTournamentPlayers(selectedTournamentId!)
    },
    enabled: !!selectedTournamentId,
  })

  const { data: matches = [], isLoadingMatches } = useQuery({
    queryKey: ['tournament-matches', selectedTournamentId],
    queryFn: () => {
      if (selectedTournamentId === 'test2_tournament_final') {
        // Return mock matches for test2 tournament
        return Promise.resolve([
          {
            match_id: 'match_1',
            tournament_id: 'test2_tournament_final',
            bracket_type: 'winners',
            round_number: 1,
            status: 'completed',
            table_number: 1,
            scheduled_time: null,
            winner_id: '1',
            operator_id: '1',
            player2_id: '32',
            operator_name: 'Kristina Tkach',
            player2_name: 'Player 32',
            operator_score: 9,
            player2_score: 4,
            race_to: 9,
            handicap1: 0,
            handicap2: 0,
            projected_start_time: null,
            projected_end_time: null
          },
          {
            match_id: 'match_2',
            tournament_id: 'test2_tournament_final',
            bracket_type: 'winners',
            round_number: 1,
            status: 'completed',
            table_number: 2,
            scheduled_time: null,
            winner_id: '2',
            operator_id: '2',
            player2_id: '31',
            operator_name: 'Kelly Fisher',
            player2_name: 'Player 31',
            operator_score: 9,
            player2_score: 7,
            race_to: 9,
            handicap1: 0,
            handicap2: 0,
            projected_start_time: null,
            projected_end_time: null
          },
          {
            match_id: 'match_3',
            tournament_id: 'test2_tournament_final',
            bracket_type: 'winners',
            round_number: 1,
            status: 'completed',
            table_number: 3,
            scheduled_time: null,
            winner_id: '30',
            operator_id: '3',
            player2_id: '30',
            operator_name: 'Jasmin Ouschan',
            player2_name: 'Player 30',
            operator_score: 6,
            player2_score: 9,
            race_to: 9,
            handicap1: 0,
            handicap2: 0,
            projected_start_time: null,
            projected_end_time: null
          },
          {
            match_id: 'match_4',
            tournament_id: 'test2_tournament_final',
            bracket_type: 'winners',
            round_number: 2,
            status: 'pending',
            table_number: 4,
            scheduled_time: null,
            operator_id: '1',
            player2_id: '2',
            operator_name: 'Kristina Tkach',
            player2_name: 'Kelly Fisher',
            operator_score: 0,
            player2_score: 0,
            winner_id: null,
            race_to: 9,
            handicap1: 0,
            handicap2: 0,
            projected_start_time: null,
            projected_end_time: null
          },
          {
            match_id: 'match_5',
            tournament_id: 'test2_tournament_final',
            bracket_type: 'winners',
            round_number: 3,
            status: 'pending',
            table_number: 5,
            scheduled_time: null,
            operator_id: null,
            player2_id: null,
            operator_name: 'Winner of Match 4',
            player2_name: 'Winner of Match 5',
            operator_score: 0,
            player2_score: 0,
            winner_id: null,
            race_to: 9,
            handicap1: 0,
            handicap2: 0,
            projected_start_time: null,
            projected_end_time: null
          }
        ])
      }
      return tournamentsApi.getMatches(selectedTournamentId!)
    },
    enabled: !!selectedTournamentId,
  })

  const [showCheckInQR, setShowCheckInQR] = useState(false)

  useEffect(() => {
    if (stateTournamentId && tournaments.some((t) => t.tournament_id === stateTournamentId)) {
      setSelectedTournamentId(stateTournamentId)
    }
  }, [stateTournamentId, tournaments])

  const selectedTournament = tournaments.find((t) => t.tournament_id === selectedTournamentId)
  const queryClient = useQueryClient()

  // Live bracket updates via tournament SSE (rack scores, match completion)
  useEffect(() => {
    if (!selectedTournamentId || selectedTournamentId === 'test2_tournament_final') return
    const url = tournamentsApi.getStreamUrl(selectedTournamentId)
    const es = new EventSource(url)
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (
          data?.type === 'match_score_update'
          || data?.type === 'match_completed'
          || data?.type === 'rack_completed'
          || data?.type === 'tournament_progress'
        ) {
          queryClient.invalidateQueries({ queryKey: ['tournament-matches', selectedTournamentId] })
          queryClient.invalidateQueries({ queryKey: ['tournament-progress', selectedTournamentId] })
          if (data?.rating_updates && Object.keys(data.rating_updates).length > 0) {
            queryClient.invalidateQueries({ queryKey: ['rankings'] })
            queryClient.invalidateQueries({ queryKey: ['leaderboard_rankings'] })
          }
        }
      } catch {
        // ignore malformed SSE payloads
      }
    }
    es.onerror = () => es.close()
    return () => es.close()
  }, [selectedTournamentId, queryClient])

  const applyHandicapsMutation = useMutation({
    mutationFn: (tournamentId: string) => tournamentsApi.applyFargoHandicaps(tournamentId),
    onSuccess: (data, tournamentId) => {
      queryClient.invalidateQueries({ queryKey: ['tournament-matches', tournamentId] })
      toast.success(`Fargo handicaps applied: ${data.applied} matches, ${data.skipped} skipped`)
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed to apply handicaps'),
  })

  const deleteTournamentMutation = useMutation({
    mutationFn: (tournamentId: string) => tournamentsApi.deleteTournament(tournamentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tournaments'] })
      setSelectedTournamentId(null)
      toast.success('Tournament deleted')
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed to delete tournament'),
  })

  const startStage2Mutation = useMutation({
    mutationFn: (tournamentId: string) => {
      const parseList = (value: string) =>
        value
          .split(/[\s,]+/)
          .map((item) => item.trim())
          .filter(Boolean)
      const parseSeeds = (value: string) =>
        value
          .split(/[\s,]+/)
          .map((item) => Number(item.trim()))
          .filter((num) => !Number.isNaN(num))

      const advancing = parseList(stage2AdvancingIds)
      const byeIds = parseList(stage2ByeIds)
      const byeSeeds = parseSeeds(stage2ByeSeeds)

      return tournamentsApi.startStage2(tournamentId, {
        cutoff: stage2Cutoff,
        seed_strategy: stage2SeedStrategy,
        advancing_player_ids: advancing.length > 0 ? advancing : undefined,
        race_to: stage2RaceTo,
        bye_player_ids: byeIds.length > 0 ? byeIds : undefined,
        bye_seed_positions: byeSeeds.length > 0 ? byeSeeds : undefined,
      })
    },
    onSuccess: (data, tournamentId) => {
      queryClient.invalidateQueries({ queryKey: ['tournament-matches', tournamentId] })
      toast.success(`Stage 2 started: ${data.advancing_count} players, ${data.matches_created} matches`)
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed to start stage 2'),
  })

  return (
    <div className="flex-1 overflow-auto bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <div className="sticky top-0 z-20 bg-slate-900/95 backdrop-blur border-b border-slate-700 p-3 sm:p-4 lg:p-6">
        <div className="max-w-7xl mx-auto">
          {isDirectorMode && (
            <div className="mb-2 px-2 sm:px-3 py-1 sm:py-1.5 rounded-lg bg-amber-900/40 border border-amber-700/50 text-amber-200 text-xs sm:text-sm font-medium inline-block">
              Director mode — bracket, tables, call table, DQ, assign, enter scores
            </div>
          )}
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-white">🌳 Tournament Bracket</h1>
          <p className="text-slate-400 mt-1 text-sm sm:text-base">
            See the draw, enter scores, and move players through the bracket.
          </p>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto p-3 sm:p-4 lg:p-6">
        {/* Tournament Selector */}
        <div className="bg-slate-800/50 backdrop-blur rounded-lg border border-slate-700 p-4 sm:p-6 mb-4 sm:mb-6">
          <h2 className="text-lg sm:text-xl font-bold text-white mb-3 sm:mb-4">Select Tournament</h2>

          {isLoading ? (
            <p className="text-slate-400 text-sm sm:text-base">Loading tournaments...</p>
          ) : tournaments.length === 0 ? (
            <p className="text-slate-400 text-sm sm:text-base">No tournaments found. Create one to get started.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
              {tournaments.map((tournament) => (
                <div
                  key={tournament.tournament_id}
                  className={`text-left p-4 rounded-lg border transition-all group relative ${
                    selectedTournamentId === tournament.tournament_id
                      ? 'bg-blue-900/30 border-blue-600'
                      : 'bg-slate-700/50 border-slate-600 hover:border-slate-500'
                  }`}
                >
                  <button
                    onClick={() => setSelectedTournamentId(tournament.tournament_id)}
                    className="w-full text-left"
                  >
                    <h3 className="font-semibold text-white mb-2">{tournament.tournament_name}</h3>
                    <div className="text-sm text-slate-400 space-y-1">
                      <p>📅 {new Date(tournament.tournament_date).toLocaleDateString()}</p>
                      <p>👥 {tournament.actual_players} players</p>
                      <p>🎯 {tournament.elimination_type === 'round_robin' ? 'Round Robin' : tournament.elimination_type === 'single' ? 'Single' : 'Double'} Elimination</p>
                      <p>
                        <span
                          className={`inline-block px-2 py-1 rounded text-xs font-semibold mt-2 ${
                            tournament.status === 'completed'
                              ? 'bg-green-500/20 text-green-200'
                              : tournament.status === 'in_progress'
                                ? 'bg-yellow-500/20 text-yellow-200'
                                : 'bg-blue-500/20 text-blue-200'
                          }`}
                        >
                          {tournament.status.replace(/_/g, ' ').toUpperCase()}
                        </span>
                      </p>
                    </div>
                  </button>

                  {/* Action buttons */}
                  <div className="flex gap-2 mt-3 pt-3 border-t border-slate-600 opacity-0 group-hover:opacity-pool_opt_in transition-opacity">
                    <button
                      onClick={() => navigate(`/tournament-wizard?edit=${tournament.tournament_id}`)}
                      className="flex-1 px-2 py-1.5 text-xs font-medium rounded bg-sky-600 hover:bg-sky-500 text-white transition-colors"
                    >
                      ✏️ Edit
                    </button>
                    <button
                      onClick={() => {
                        if (confirm(`Delete tournament "${tournament.tournament_name}"?`)) {
                          deleteTournamentMutation.mutate(tournament.tournament_id)
                        }
                      }}
                      disabled={deleteTournamentMutation.isPending}
                      className="flex-1 px-2 py-1.5 text-xs font-medium rounded bg-red-600 hover:bg-red-500 text-white transition-colors disabled:opacity-50"
                    >
                      🗑️ Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Bracket View */}
        {selectedTournamentId && selectedTournament ? (
          <div className="bg-slate-800/50 backdrop-blur rounded-lg border border-slate-700 p-6">
            <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
              <div>
                <h2 className="text-2xl font-bold text-white">{selectedTournament.tournament_name}</h2>
                <div className="flex flex-wrap gap-4 mt-2 text-sm text-slate-400">
                  <span>📍 {selectedTournament.location || 'Location TBD'}</span>
                  <span>👥 {selectedTournament.actual_players} Players</span>
                  <span>
                    {selectedTournament.elimination_type === 'round_robin' ? '⭕ Round Robin' : selectedTournament.elimination_type === 'single' ? '🔺 Single' : '🔸 Double'} Elimination
                  </span>
                  {progress && progress.total > 0 && (
                    <span className="font-medium text-slate-300">
                      📊 {progress.completed}/{progress.total} matches ({progress.percent}%)
                    </span>
                  )}
                </div>
              </div>
              {isDirectorMode && (
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setShowCheckInQR(true)}
                    className="px-4 py-2 rounded-lg bg-slate-600 text-slate-200 text-sm font-medium hover:bg-slate-500"
                  >
                    QR check-in
                  </button>
                  <button
                    type="button"
                    onClick={() => selectedTournamentId && applyHandicapsMutation.mutate(selectedTournamentId)}
                    disabled={applyHandicapsMutation.isPending || !selectedTournamentId}
                    className="px-4 py-2 rounded-lg bg-amber-700/80 text-amber-pool_opt_in text-sm font-medium hover:bg-amber-700 disabled:opacity-50"
                  >
                    {applyHandicapsMutation.isPending ? 'Applying…' : 'Apply Fargo handicaps'}
                  </button>
                </div>
              )}
            </div>

            {isDirectorMode && (
              <div className="mb-6 rounded-lg border border-slate-700 bg-slate-900/40 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="text-base font-semibold text-white">Stage 2 (Single Elimination)</h3>
                    <p className="text-xs text-slate-400">Auto-select top N by placement with optional director overrides.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => selectedTournamentId && startStage2Mutation.mutate(selectedTournamentId)}
                    disabled={!selectedTournamentId || startStage2Mutation.isPending}
                    className="px-4 py-2 rounded-lg bg-sky-600 text-white text-sm font-semibold hover:bg-sky-500 disabled:opacity-50"
                  >
                    {startStage2Mutation.isPending ? 'Starting…' : 'Start Stage 2'}
                  </button>
                </div>

                <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-slate-400">Cutoff (players advancing)</label>
                    <input
                      type="number"
                      min={2}
                      max={256}
                      value={stage2Cutoff}
                      onChange={(e) => setStage2Cutoff(Number(e.target.value))}
                      className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400">Seed strategy</label>
                    <select
                      value={stage2SeedStrategy}
                      onChange={(e) => setStage2SeedStrategy(e.target.value as 'placement' | 'seed' | 'manual')}
                      className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
                    >
                      <option value="placement">Placement</option>
                      <option value="seed">Seed</option>
                      <option value="manual">Manual order</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-slate-400">Race to</label>
                    <input
                      type="number"
                      min={1}
                      value={stage2RaceTo}
                      onChange={(e) => setStage2RaceTo(Number(e.target.value))}
                      className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400">Advancing player IDs (optional override)</label>
                    <textarea
                      value={stage2AdvancingIds}
                      onChange={(e) => setStage2AdvancingIds(e.target.value)}
                      placeholder="P000101, P000204, ..."
                      className="mt-1 w-full min-h-[70px] rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-white"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400">BYE player IDs (optional)</label>
                    <textarea
                      value={stage2ByeIds}
                      onChange={(e) => setStage2ByeIds(e.target.value)}
                      placeholder="P000101, P000204"
                      className="mt-1 w-full min-h-[70px] rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-white"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400">BYE seed positions (optional)</label>
                    <textarea
                      value={stage2ByeSeeds}
                      onChange={(e) => setStage2ByeSeeds(e.target.value)}
                      placeholder="1, 2, 3"
                      className="mt-1 w-full min-h-[70px] rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-white"
                    />
                  </div>
                </div>
              </div>
            )}
            {selectedTournamentId === 'test2_tournament_final' ? (
              <BracketVisualization
                matches={matches}
                tournamentName="test2"
                isDirectorMode={isDirectorMode}
                onMatchClick={(match) => {
                  // Handle match click for test tournament
                  console.log('Test tournament match clicked:', match)
                }}
              />
            ) : (
              <BracketGrid
                tournamentId={selectedTournamentId}
                matches={matches}
                isLoading={isLoadingMatches}
                isDirectorMode={isDirectorMode}
                onTimeKeeperOpen={openTimekeeper}
              />
            )}
            <CheckInQRModal
              tournamentId={selectedTournamentId}
              players={tournamentPlayers}
              isOpen={showCheckInQR}
              onClose={() => setShowCheckInQR(false)}
            />
          </div>
        ) : (
          selectedTournamentId && (
            <div className="bg-slate-800/50 backdrop-blur rounded-lg border border-slate-700 p-6 text-center">
              <p className="text-slate-400">Loading tournament details...</p>
            </div>
          )
        )}
      </div>
    </div>
  )
}
