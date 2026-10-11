import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { tournamentsApi, type Match } from '@/api/tournaments'
import BracketViewer from '@/components/BracketViewer'

function getScore(match: Match, side: 'operator' | 'player2') {
  if (side === 'operator') {
    return match.operator_games ?? match.operator_score ?? 0
  }
  return match.player2_games ?? match.player2_score ?? 0
}

export default function CurrentTournament() {
  const queryClient = useQueryClient()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['current-tournament'],
    queryFn: () => tournamentsApi.getCurrentTournament(),
    refetchInterval: 10000,
  })

  const tournament = data?.tournament ?? null
  const players = data?.players ?? []
  const matches = data?.matches ?? []

  useEffect(() => {
    if (!tournament?.tournament_id) return
    const es = new EventSource(tournamentsApi.getStreamUrl(tournament.tournament_id))
    es.onmessage = () => {
      queryClient.invalidateQueries({ queryKey: ['current-tournament'] })
      queryClient.invalidateQueries({ queryKey: ['tournament-matches', tournament.tournament_id] })
    }
    es.onerror = () => es.close()
    return () => es.close()
  }, [queryClient, tournament?.tournament_id])

  if (isLoading) {
    return (
      <div className="flex-1 overflow-auto bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="max-w-6xl mx-auto p-6">
          <p className="text-slate-400">Loading current tournament...</p>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex-1 overflow-auto bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="max-w-6xl mx-auto p-6">
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6 text-slate-300">
            Unable to load the current tournament. Please try again.
          </div>
        </div>
      </div>
    )
  }

  if (!tournament) {
    return (
      <div className="flex-1 overflow-auto bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="max-w-6xl mx-auto p-6">
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-8 text-center text-slate-400">
            <h1 className="text-2xl font-semibold text-white mb-2">Current Tournament</h1>
            <p className="mb-4">No active tournament right now.</p>
            <div className="flex flex-wrap justify-center gap-3">
              <Link
                to="/tournament-wizard?mode=new"
                className="inline-flex items-center justify-center px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90"
              >
                Start new tournament
              </Link>
              <Link
                to="/tournament-wizard?mode=scheduled"
                className="inline-flex items-center justify-center px-4 py-2 rounded-lg border border-emerald-600 text-emerald-300 text-sm font-medium hover:bg-emerald-950/40"
              >
                Set up scheduled event
              </Link>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const liveMatches = matches.filter((m) => m.status === 'in_progress' || m.status === 'completed')

  return (
    <div className="flex-1 overflow-auto bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="max-w-6xl mx-auto p-4 md:p-6 space-y-6">
        <header className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
          <div className="flex flex-col gap-2">
            <h1 className="text-3xl font-bold text-white">Current Tournament</h1>
            <div className="text-slate-400 text-sm flex flex-wrap gap-4">
              <span>🏆 {tournament.tournament_name}</span>
              <span>📅 {new Date(tournament.tournament_date).toLocaleDateString()}</span>
              <span>👥 {tournament.actual_players} / {tournament.max_players}</span>
              {tournament.location && <span>📍 {tournament.location}</span>}
              {tournament.tables_available ? <span>🎱 Tables: {tournament.tables_available}</span> : null}
              <span className="capitalize">{tournament.status.replace(/_/g, ' ')}</span>
            </div>
          </div>
        </header>

        <section className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
          <h2 className="text-xl font-semibold text-white mb-4">Bracket</h2>
          <BracketViewer tournamentId={tournament.tournament_id} />
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <h2 className="text-lg font-semibold text-white mb-3">Players</h2>
            {players.length === 0 ? (
              <p className="text-slate-400">No players registered yet.</p>
            ) : (
              <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
                {players.map((p) => (
                  <li key={p.player_id} className="rounded bg-slate-900/50 border border-slate-700 px-3 py-2 text-slate-200">
                    {p.first_name} {p.last_name}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-6">
            <h2 className="text-lg font-semibold text-white mb-3">Live Scores</h2>
            {liveMatches.length === 0 ? (
              <p className="text-slate-400">No matches scored yet.</p>
            ) : (
              <div className="space-y-3">
                {liveMatches.map((m) => (
                  <div key={m.match_id} className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2">
                    <div className="flex items-center justify-between text-sm text-slate-300">
                      <span className="truncate">
                        {m.operator_name || 'TBD'} vs {m.player2_name || 'TBD'}
                      </span>
                      <span className="text-slate-400">Table {m.table_number ?? '—'}</span>
                    </div>
                    <div className="mt-1 text-sm text-white font-medium">
                      {getScore(m, 'operator')} - {getScore(m, 'player2')}
                      <span className="ml-2 text-xs text-slate-400">{m.status.replace(/_/g, ' ')}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
