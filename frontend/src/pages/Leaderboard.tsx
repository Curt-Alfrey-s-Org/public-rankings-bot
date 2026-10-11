import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTournamentsApi, useTournamentHistoryApi } from '@/contexts/ApiPathContext'
import { useAuth } from '@/contexts/AuthContext'
import PageLoader from '@/components/PageLoader'

type SortField = 'name' | 'tournaments' | 'points' | 'rank' | 'rating'
type SortOrder = 'asc' | 'desc'

type AssociationSystem =
  | 'WPBA_Women'
  | 'WPA_Women'
  | 'WPA_Men'
  | 'WPA_Heyball_Men'
  | 'WPA_Heyball_Women'
  | 'WPA_Artistic'

const ASSOCIATION_BUTTONS: Array<{ system: AssociationSystem; label: string; emoji: string }> = [
  { system: 'WPBA_Women', label: 'WPBA Women', emoji: '👑' },
  { system: 'WPA_Women', label: 'WPA Women', emoji: '🌍' },
  { system: 'WPA_Men', label: 'WPA Men', emoji: '🎱' },
  { system: 'WPA_Heyball_Men', label: 'Heyball Men', emoji: '🎯' },
  { system: 'WPA_Heyball_Women', label: 'Heyball Women', emoji: '🎯' },
  { system: 'WPA_Artistic', label: 'Artistic Pool', emoji: '🎨' },
]

export default function Leaderboard() {
  const tournamentsApi = useTournamentsApi()
  const tournamentHistoryApi = useTournamentHistoryApi()
  const { isSuperAdmin } = useAuth()
  const [sortField, setSortField] = useState<SortField>('rank')
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc')
  const [selectedSystem, setSelectedSystem] = useState<AssociationSystem>('WPBA_Women')

  // Rankings for the selected association (same systems as Rankings page)
  const { data: players = [], isLoading: rankingsLoading } = useQuery({
    queryKey: ['leaderboard_rankings', selectedSystem],
    queryFn: () => tournamentsApi.getCurrentRankings(selectedSystem),
  })

  const { data: completedResults } = useQuery({
    queryKey: ['leaderboard_completed_tournaments'],
    queryFn: () => tournamentsApi.getCompletedResults(15),
    staleTime: 60_000,
  })
  const { data: historyByAssociation } = useQuery({
    queryKey: ['leaderboard_tournament_history_by_association'],
    queryFn: () => tournamentHistoryApi.getLeaderboardResultsByAssociation(3),
    staleTime: 60_000,
  })

  const { data: inProgressTournaments = [] } = useQuery({
    queryKey: ['leaderboard_in_progress'],
    queryFn: () => tournamentsApi.getTournaments('in_progress'),
    staleTime: 60_000,
  })

  const isLoading = rankingsLoading

  // Sort players
  const sortedPlayers = [...players].sort((a, b) => {
    let aValue: number | string = 0
    let bValue: number | string = 0

    switch (sortField) {
      case 'rank':
        aValue = a.current_rank ?? 999999
        bValue = b.current_rank ?? 999999
        break
      case 'name':
        aValue = `${a.first_name} ${a.last_name}`
        bValue = `${b.first_name} ${b.last_name}`
        break
      case 'tournaments':
        aValue = a.total_tournaments_played || 0
        bValue = b.total_tournaments_played || 0
        break
      case 'points':
        aValue = a.total_points || 0
        bValue = b.total_points || 0
        break
      case 'rating':
        aValue = a.fargo_score || 0
        bValue = b.fargo_score || 0
        break
      default:
        aValue = 0
        bValue = 0
    }

    if (typeof aValue === 'string' && typeof bValue === 'string') {
      return sortOrder === 'asc' ? aValue.localeCompare(bValue) : bValue.localeCompare(aValue)
    }

    const numA = Number(aValue) || 0
    const numB = Number(bValue) || 0
    return sortOrder === 'asc' ? numA - numB : numB - numA
  })

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortOrder('asc')
    }
  }

  if (isLoading) return <PageLoader />

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header: overall standings + tournaments in progress + past results */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">🏅 Leaderboard</h1>
          <p className="text-slate-400 max-w-2xl">
            See who is leading in points for each major tour. Pick a category below, then scroll for recent finishes and events in progress.
          </p>
        </div>

        {/* Association buttons */}
        <div className="mb-6 flex flex-wrap gap-3">
          {ASSOCIATION_BUTTONS.map((button) => {
            const isSelected = selectedSystem === button.system
            const baseClasses = 'rounded-xl py-3 px-4 min-h-[48px] font-bold text-sm sm:text-base transition-all shadow-md'
            const selectedClasses = isSelected
              ? 'bg-slate-600 border-2 border-sky-400 text-white'
              : 'bg-slate-700/50 border-2 border-slate-600/30 text-white hover:border-slate-500/60 hover:bg-slate-600/50'
            return (
              <button
                key={button.system}
                type="button"
                onClick={() => setSelectedSystem(button.system)}
                className={`${baseClasses} ${selectedClasses}`}
              >
                {button.emoji} {button.label}
              </button>
            )
          })}
        </div>

        {/* Player standings: same tours as Rankings page (WPBA, WPA Women/Men, Heyball) */}
        <div className="mb-2">
          <h2 className="text-xl font-bold text-white">
            Player standings — {ASSOCIATION_BUTTONS.find((b) => b.system === selectedSystem)?.label || selectedSystem}
          </h2>
          <p className="text-slate-500 text-sm">
            Ranked by points in {ASSOCIATION_BUTTONS.find((b) => b.system === selectedSystem)?.label || selectedSystem} only. Same tours as the Rankings page.
          </p>
        </div>
        {sortedPlayers.length > 0 ? (
          <div className="bg-slate-700 bg-opacity-50 rounded-lg border border-slate-600 overflow-hidden shadow-lg">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-slate-800 bg-opacity-80 border-b border-slate-600 sticky top-0">
                    <th className="px-6 py-4 text-left">
                      <button
                        onClick={() => handleSort('rank')}
                        className="text-sm font-semibold text-slate-300 hover:text-white flex items-center gap-2"
                      >
                        Rank {sortField === 'rank' && (sortOrder === 'asc' ? '↑' : '↓')}
                      </button>
                    </th>
                    <th className="px-6 py-4 text-left">
                      <button
                        onClick={() => handleSort('name')}
                        className="text-sm font-semibold text-slate-300 hover:text-white flex items-center gap-2"
                      >
                        Player {sortField === 'name' && (sortOrder === 'asc' ? '↑' : '↓')}
                      </button>
                    </th>
                    <th className="px-6 py-4 text-center">
                      <button
                        onClick={() => handleSort('tournaments')}
                        className="text-sm font-semibold text-slate-300 hover:text-white flex items-center justify-center gap-2 w-full"
                      >
                        Tournaments {sortField === 'tournaments' && (sortOrder === 'asc' ? '↑' : '↓')}
                      </button>
                    </th>
                    <th className="px-6 py-4 text-center">
                      <button
                        onClick={() => handleSort('points')}
                        className="text-sm font-semibold text-slate-300 hover:text-white flex items-center justify-center gap-2 w-full"
                      >
                        Points {sortField === 'points' && (sortOrder === 'asc' ? '↑' : '↓')}
                      </button>
                    </th>
                    <th className="px-6 py-4 text-center">
                      <button
                        onClick={() => handleSort('rating')}
                        className="text-sm font-semibold text-slate-300 hover:text-white flex items-center justify-center gap-2 w-full"
                      >
                        Fargo Rating {sortField === 'rating' && (sortOrder === 'asc' ? '↑' : '↓')}
                      </button>
                    </th>
                    {isSuperAdmin && (
                      <th className="px-6 py-4 text-center">
                        <div>
                          <div className="text-sm font-semibold text-slate-300">Est Rating</div>
                          <div className="text-[10px] font-normal opacity-80">estimated strength</div>
                        </div>
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {sortedPlayers.map((player, index) => (
                    <tr
                      key={player.player_id}
                      className={`border-b border-slate-600 transition-colors ${
                        index % 2 === 0 ? 'bg-slate-700 bg-opacity-30' : 'bg-slate-600 bg-opacity-20'
                      } hover:bg-slate-600 hover:bg-opacity-40`}
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <div
                            className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm ${
                              player.current_rank === 1
                                ? 'bg-yellow-500 text-slate-900'
                                : player.current_rank === 2
                                  ? 'bg-slate-400 text-slate-900'
                                  : player.current_rank === 3
                                    ? 'bg-orange-500 text-white'
                                    : 'bg-slate-600 text-slate-300'
                            }`}
                          >
                            {player.current_rank ?? '—'}
                          </div>
                          {player.current_rank === 1 && <span className="text-xl tracking-wide" aria-hidden>🥇</span>}
                          {player.current_rank === 2 && <span className="text-xl tracking-wide" aria-hidden>🥈</span>}
                          {player.current_rank === 3 && <span className="text-xl tracking-wide" aria-hidden>🥉</span>}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          {player.avatar_url && (
                            <img
                              src={player.avatar_url}
                              alt=""
                              className="w-8 h-8 rounded-full object-cover"
                              onError={(e) => {
                                e.currentTarget.style.display = 'none'
                              }}
                            />
                          )}
                          <div>
                            <div className="text-white font-medium">
                              {player.first_name} {player.last_name}
                              {player.hall_of_fame && <span className="ml-2 text-amber-400" title="Hall of Fame">⭐</span>}
                            </div>
                            <div className="text-xs text-slate-400 mt-1">
                              {player.nickname || (player.license_number && !String(player.license_number).startsWith('RANK-') ? player.license_number : '')}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span className="text-white font-semibold">{player.total_tournaments_played}</span>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span className="text-white font-semibold">{player.total_points}</span>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <div className="text-white font-bold">{player.fargo_score != null ? player.fargo_score : 'none'}</div>
                        <div className="text-xs text-slate-400 mt-1">
                          {player.membership_status === 'lifetime' ? '👑 Lifetime' : player.membership_status}
                        </div>
                      </td>
                      {isSuperAdmin && (
                        <td className="px-6 py-4 text-center">
                          <div className="text-white font-bold">{player.est_rating != null ? Math.round(player.est_rating) : '—'}</div>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="bg-slate-700 bg-opacity-50 rounded-lg border border-slate-600 overflow-hidden shadow-lg">
            <div className="p-6 text-center border-b border-slate-600">
              <h3 className="text-lg font-semibold text-slate-300 mb-2">No Players Available</h3>
              <p className="text-slate-400">No players have been registered yet.</p>
            </div>
            <div className="overflow-x-auto opacity-60">
              <table className="w-full">
                <thead>
                  <tr className="bg-slate-800 bg-opacity-80 border-b border-slate-600">
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-400">Rank</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-400">Player</th>
                    <th className="px-6 py-4 text-center text-sm font-semibold text-slate-400">Tournaments</th>
                    <th className="px-6 py-4 text-center text-sm font-semibold text-slate-400">Points</th>
                    <th className="px-6 py-4 text-center text-sm font-semibold text-slate-400">Fargo Rating</th>
                    {isSuperAdmin && (
                      <th className="px-6 py-4 text-center text-sm font-semibold text-slate-400">Est Rating</th>
                    )}
                  </tr>
                </thead>
                <tbody className="text-slate-500">
                  <tr className="border-b border-slate-600 bg-slate-700/30">
                    <td className="px-6 py-4"><div className="flex items-center gap-2"><div className="w-8 h-8 rounded-full bg-slate-500 flex items-center justify-center font-bold text-sm text-slate-400">1</div><span className="text-xl tracking-wide opacity-60">🥇</span></div></td>
                    <td className="px-6 py-4"><div className="font-medium">Example</div><div className="text-xs text-slate-500 mt-1">—</div></td>
                    <td className="px-6 py-4 text-center font-semibold">12</td>
                    <td className="px-6 py-4 text-center font-semibold">450</td>
                    <td className="px-6 py-4 text-center font-bold">720</td>
                    {isSuperAdmin && <td className="px-6 py-4 text-center font-bold">—</td>}
                  </tr>
                  <tr className="border-b border-slate-600 bg-slate-600/20">
                    <td className="px-6 py-4"><div className="flex items-center gap-2"><div className="w-8 h-8 rounded-full bg-slate-500 flex items-center justify-center font-bold text-sm text-slate-400">2</div><span className="text-xl tracking-wide opacity-60">🥈</span></div></td>
                    <td className="px-6 py-4"><div className="font-medium">Example</div><div className="text-xs text-slate-500 mt-1">—</div></td>
                    <td className="px-6 py-4 text-center font-semibold">10</td>
                    <td className="px-6 py-4 text-center font-semibold">380</td>
                    <td className="px-6 py-4 text-center font-bold">698</td>
                    {isSuperAdmin && <td className="px-6 py-4 text-center font-bold">—</td>}
                  </tr>
                  <tr className="border-b border-slate-600 bg-slate-700/30">
                    <td className="px-6 py-4"><div className="flex items-center gap-2"><div className="w-8 h-8 rounded-full bg-slate-500 flex items-center justify-center font-bold text-sm text-slate-400">3</div><span className="text-xl tracking-wide opacity-60">🥉</span></div></td>
                    <td className="px-6 py-4"><div className="font-medium">Example</div><div className="text-xs text-slate-500 mt-1">—</div></td>
                    <td className="px-6 py-4 text-center font-semibold">9</td>
                    <td className="px-6 py-4 text-center font-semibold">320</td>
                    <td className="px-6 py-4 text-center font-bold">675</td>
                    {isSuperAdmin && <td className="px-6 py-4 text-center font-bold">—</td>}
                  </tr>
                  <tr className="border-b border-slate-600 bg-slate-600/20">
                    <td className="px-6 py-4"><div className="w-8 h-8 rounded-full bg-slate-500 flex items-center justify-center font-bold text-sm text-slate-400">4</div></td>
                    <td className="px-6 py-4"><div className="font-medium">Example</div><div className="text-xs text-slate-500 mt-1">—</div></td>
                    <td className="px-6 py-4 text-center font-semibold">8</td>
                    <td className="px-6 py-4 text-center font-semibold">290</td>
                    <td className="px-6 py-4 text-center font-bold">662</td>
                    {isSuperAdmin && <td className="px-6 py-4 text-center font-bold">—</td>}
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="text-slate-500 text-sm text-center py-3">Example. Add active players to see real rankings.</p>
          </div>
        )}

        {/* Tournaments in progress: list of events being played now (not player stats) */}
        <div className="mt-8">
          <h2 className="text-xl font-bold text-white mb-1">Tournaments in progress</h2>
          <p className="text-slate-500 text-sm mb-4">Events being played right now. When one concludes, it appears in Past Tournament Results below.</p>
          {inProgressTournaments.length > 0 ? (
            <div className="bg-slate-700 bg-opacity-50 rounded-lg border border-slate-600 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="bg-slate-800 bg-opacity-80 border-b border-slate-600">
                      <th className="px-6 py-3 text-left text-sm font-semibold text-slate-300">Tournament</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-slate-300">Date</th>
                      <th className="px-6 py-3 text-left text-sm font-semibold text-slate-300">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {inProgressTournaments.map((t) => (
                      <tr key={t.tournament_id} className="border-b border-slate-600 hover:bg-slate-600/30">
                        <td className="px-6 py-4 text-white font-medium">{t.tournament_name}</td>
                        <td className="px-6 py-4 text-slate-300">
                          {t.tournament_date
                            ? new Date(t.tournament_date).toLocaleDateString('en-US', {
                                year: 'numeric',
                                month: 'short',
                                day: 'numeric',
                              })
                            : '—'}
                        </td>
                        <td className="px-6 py-4 text-amber-400 font-medium">In progress</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <div className="bg-slate-700 bg-opacity-50 rounded-lg border border-slate-600 overflow-hidden">
              <div className="p-6 text-center border-b border-slate-600">
                <p className="text-slate-400">None at this time.</p>
              </div>
              <div className="overflow-x-auto opacity-60">
                <table className="w-full">
                  <thead>
                    <tr className="bg-slate-800 bg-opacity-80 border-b border-slate-600">
                    <th className="px-6 py-3 text-left text-sm font-semibold text-slate-400">Tournament</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-slate-400">Date</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold text-slate-400">Status</th>
                  </tr>
                  </thead>
                  <tbody className="text-slate-500">
                    <tr className="border-b border-slate-600 hover:bg-slate-600/20">
                      <td className="px-6 py-4 font-medium">Example</td>
                      <td className="px-6 py-4">Mar 15, 2025</td>
                      <td className="px-6 py-4 text-amber-400/80 font-medium">In progress</td>
                    </tr>
                    <tr className="border-b border-slate-600 hover:bg-slate-600/20">
                      <td className="px-6 py-4 font-medium">Example</td>
                      <td className="px-6 py-4">Mar 22, 2025</td>
                      <td className="px-6 py-4 text-amber-400/80 font-medium">In progress</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className="text-slate-500 text-sm text-center py-3">Example. Tournaments you start and set to “in progress” will appear here.</p>
            </div>
          )}
        </div>

        {/* Past Tournament Results: top 3 per association (WPBA, WPA Men, WPA Women, Heyball, Artistic) + Local. Single source: tournament_history. */}
        {(() => {
          const isRealTournament = (t: { tournament_id?: string; tournament_name?: string }) => {
            const id = (t.tournament_id ?? '').toLowerCase()
            const name = (t.tournament_name ?? '').trim()
            const nameLower = name.toLowerCase()
            if (id.startsWith('rankings_snapshot_')) return false
            if (name.includes(' Rankings (')) return false
            if (nameLower.includes(' news')) return false
            if (nameLower.endsWith(' events')) return false
            if (['wpba events', 'latest wpa news', 'wpa news', 'wpba news'].includes(nameLower)) return false
            return true
          }
          const localTournaments = (completedResults?.tournaments ?? []).filter(isRealTournament).slice(0, 3).map((t) => ({
            tournament_id: (t as { tournament_id?: string }).tournament_id ?? '',
            tournament_name: (t as { tournament_name?: string }).tournament_name ?? '',
            tournament_date: String((t as { tournament_date?: string }).tournament_date ?? ''),
            first_place_name: (t as { first_place_name?: string }).first_place_name ?? (t as { winner_name?: string }).winner_name ?? '',
            second_place_name: (t as { second_place_name?: string }).second_place_name ?? (t as { runner_up_name?: string }).runner_up_name ?? '',
            third_place_name: (t as { third_place_name?: string }).third_place_name ?? '',
          }))
          const byAssoc = historyByAssociation?.by_association ?? {}
          const assocLabels: Record<string, string> = {
            'WPBA': 'WPBA',
            'WPA Men': 'WPA Men',
            'WPA Women': 'WPA Women',
            'WPA Heyball Men': 'Heyball Men',
            'WPA Heyball Women': 'Heyball Women',
            'WPA Heyball': 'Heyball',
            'WPA Artistic': 'Artistic',
          }
          const assocOrder = ['WPBA', 'WPA Men', 'WPA Women', 'WPA Heyball Men', 'WPA Heyball Women', 'WPA Heyball', 'WPA Artistic']
          const extraAssocs = Object.keys(byAssoc).filter((a) => !assocOrder.includes(a))
          const displayOrder = [...assocOrder, ...extraAssocs]
          const hasAny = Object.keys(byAssoc).some((a) => byAssoc[a]?.length) || localTournaments.length > 0
          if (!hasAny) return null
          return (
            <div className="mt-8">
              <h2 className="text-2xl font-bold text-white mb-4">Past Tournament Results</h2>
              <p className="text-slate-500 text-sm mb-4">Top 3 most recent per association. Data from Tournament History.</p>
              <div className="space-y-6">
                {displayOrder.map((key) => {
                  const tournaments = byAssoc[key]
                  if (!tournaments?.length) return null
                  const label = assocLabels[key] ?? key
                  return (
                    <div key={key} className="bg-slate-700 bg-opacity-50 rounded-lg border border-slate-600 overflow-hidden">
                      <div className="px-6 py-3 bg-slate-800 bg-opacity-80 border-b border-slate-600">
                        <h3 className="text-lg font-semibold text-white">{label}</h3>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full">
                          <thead>
                            <tr className="bg-slate-800/50 border-b border-slate-600">
                              <th className="px-6 py-2 text-left text-sm font-semibold text-slate-300">Tournament</th>
                              <th className="px-6 py-2 text-left text-sm font-semibold text-slate-300">Date</th>
                              <th className="px-6 py-2 text-left text-sm font-semibold text-slate-300"><span className="text-lg">🥇</span> 1st</th>
                              <th className="px-6 py-2 text-left text-sm font-semibold text-slate-300"><span className="text-lg">🥈</span> 2nd</th>
                              <th className="px-6 py-2 text-left text-sm font-semibold text-slate-300"><span className="text-lg">🥉</span> 3rd</th>
                            </tr>
                          </thead>
                          <tbody>
                            {tournaments.map((t) => (
                              <tr key={`${t.tournament_id}-${t.tournament_date}`} className="border-b border-slate-600 hover:bg-slate-600/30">
                                <td className="px-6 py-3 text-white font-medium">{t.tournament_name}</td>
                                <td className="px-6 py-3 text-slate-300">
                                  {new Date(t.tournament_date || 0).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}
                                </td>
                                <td className="px-6 py-3 text-slate-pool_opt_in">{t.first_place_name || '—'}</td>
                                <td className="px-6 py-3 text-slate-300">{t.second_place_name || '—'}</td>
                                <td className="px-6 py-3 text-slate-400">{t.third_place_name || '—'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )
                })}
                {localTournaments.length > 0 && (
                  <div className="bg-slate-700 bg-opacity-50 rounded-lg border border-slate-600 overflow-hidden">
                    <div className="px-6 py-3 bg-slate-800 bg-opacity-80 border-b border-slate-600">
                      <h3 className="text-lg font-semibold text-white">Local</h3>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="bg-slate-800/50 border-b border-slate-600">
                            <th className="px-6 py-2 text-left text-sm font-semibold text-slate-300">Tournament</th>
                            <th className="px-6 py-2 text-left text-sm font-semibold text-slate-300">Date</th>
                            <th className="px-6 py-2 text-left text-sm font-semibold text-slate-300"><span className="text-lg">🥇</span> 1st</th>
                            <th className="px-6 py-2 text-left text-sm font-semibold text-slate-300"><span className="text-lg">🥈</span> 2nd</th>
                            <th className="px-6 py-2 text-left text-sm font-semibold text-slate-300"><span className="text-lg">🥉</span> 3rd</th>
                          </tr>
                        </thead>
                        <tbody>
                          {localTournaments.map((t) => (
                            <tr key={`${t.tournament_id}-${t.tournament_date}`} className="border-b border-slate-600 hover:bg-slate-600/30">
                              <td className="px-6 py-3 text-white font-medium">{t.tournament_name}</td>
                              <td className="px-6 py-3 text-slate-300">
                                {new Date(t.tournament_date || 0).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })}
                              </td>
                              <td className="px-6 py-3 text-slate-pool_opt_in">{t.first_place_name || '—'}</td>
                              <td className="px-6 py-3 text-slate-300">{t.second_place_name || '—'}</td>
                              <td className="px-6 py-3 text-slate-400">{t.third_place_name || '—'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )
        })()}

        {/* Statistics Section */}
        {sortedPlayers.length > 0 && (
          <div className="mt-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-slate-700 bg-opacity-50 rounded-lg p-6 border border-slate-600">
              <div className="text-slate-400 text-sm font-medium"><span className="text-xl">🥇</span> Champion</div>
              <div className="text-white text-xl font-bold mt-2">
                {sortedPlayers[0]?.first_name} {sortedPlayers[0]?.last_name}
              </div>
              <div className="text-slate-400 text-xs mt-2">
                Rank #{sortedPlayers[0]?.current_rank} • {sortedPlayers[0]?.total_tournaments_played} tournaments
              </div>
            </div>
            <div className="bg-slate-700 bg-opacity-50 rounded-lg p-6 border border-slate-600">
              <div className="text-slate-400 text-sm font-medium">📊 Total Players</div>
              <div className="text-white text-xl font-bold mt-2">{sortedPlayers.length}</div>
              <div className="text-slate-400 text-xs mt-2">
                Active: {sortedPlayers.filter((p) => p.membership_status === 'active').length}
              </div>
            </div>
            <div className="bg-slate-700 bg-opacity-50 rounded-lg p-6 border border-slate-600">
              <div className="text-slate-400 text-sm font-medium">🎯 Avg Fargo Rating</div>
              <div className="text-white text-xl font-bold mt-2">
                {Math.round(
                  sortedPlayers.filter((p) => p.fargo_score).reduce((sum, p) => sum + (p.fargo_score || 0), 0) /
                    sortedPlayers.filter((p) => p.fargo_score).length
                )}
              </div>
              <div className="text-slate-400 text-xs mt-2">
                Based on {sortedPlayers.filter((p) => p.fargo_score).length} players
              </div>
            </div>
            <div className="bg-slate-700 bg-opacity-50 rounded-lg p-6 border border-slate-600">
              <div className="text-slate-400 text-sm font-medium">🎰 Hall of Fame</div>
              <div className="text-white text-xl font-bold mt-2">
                {sortedPlayers.filter((p) => p.hall_of_fame).length}
              </div>
              <div className="text-slate-400 text-xs mt-2">Legendary players</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
