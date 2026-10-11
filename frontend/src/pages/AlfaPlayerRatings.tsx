/**
 * Player Ratings View - Paginated table with filtering and sorting
 */

import React, { useState } from 'react'
import { Download } from 'lucide-react'
import { useAlfaPlayerRatings, useAlfaExportRatings } from '@/hooks/useAlfaRatings'

export const AlfaPlayerRatings: React.FC = () => {
  const [page, setPage] = useState(1)
  const [sortBy, setSortBy] = useState<'rating' | 'games' | 'change'>('rating')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [experienceFilter, setExperienceFilter] = useState<string>('all')
  const [, setSelectedPlayer] = useState<string | null>(null)

  const { data: players, isLoading } = useAlfaPlayerRatings({
    page,
    page_size: 20,
    sort_by: sortBy,
    sort_order: sortOrder,
    experience_level: experienceFilter !== 'all' ? experienceFilter : undefined,
  })

  const { mutate: exportRatings } = useAlfaExportRatings('csv')

  const getTrendColor = (change?: number) => {
    if (!change) return 'text-slate-400'
    if (change > 10) return 'text-emerald-400'
    if (change > 0) return 'text-sky-400'
    if (change < -10) return 'text-red-600'
    return 'text-orange-400'
  }

  const getExperienceBadgeColor = (level: string) => {
    switch (level) {
      case 'new':
        return 'bg-emerald-900 text-emerald-200'
      case 'intermediate':
        return 'bg-blue-900 text-blue-200'
      case 'experienced':
        return 'bg-slate-700 text-slate-200'
      default:
        return 'bg-slate-700 text-slate-200'
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-pool_opt_in">Player Ratings</h1>
          <p className="text-slate-400 mt-1">{players?.total || 0} players total</p>
        </div>
        <button
          onClick={() => exportRatings()}
          className="flex items-center gap-2 px-4 py-2 bg-sky-600 hover:bg-sky-700 rounded-lg text-white font-medium transition-colors"
        >
          <Download className="w-4 h-4" />
          Export CSV
        </button>
      </div>

      {/* Filters */}
      <div className="p-4 bg-slate-800 rounded-lg border border-slate-700 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Experience Level</label>
            <select
              value={experienceFilter}
              onChange={(e) => {
                setExperienceFilter(e.target.value)
                setPage(1)
              }}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-pool_opt_in focus:border-sky-500 outline-none"
            >
              <option value="all">All Players</option>
              <option value="new">New</option>
              <option value="intermediate">Intermediate</option>
              <option value="experienced">Experienced</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Sort By</label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-pool_opt_in focus:border-sky-500 outline-none"
            >
              <option value="rating">Rating</option>
              <option value="games">Games Played</option>
              <option value="change">Rating Change</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Order</label>
            <select
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value as any)}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-pool_opt_in focus:border-sky-500 outline-none"
            >
              <option value="desc">Descending</option>
              <option value="asc">Ascending</option>
            </select>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-slate-400">Loading players...</div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-900 border-b border-slate-700">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-400">Player</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-400">Rating</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-400">Fargo Equiv</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-400">Games</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-400">Change</th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-400">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700">
                  {players?.data && players.data.length > 0 ? (
                    players.data.map((player) => (
                      <tr
                        key={player.player_id}
                        onClick={() => setSelectedPlayer(player.player_id)}
                        className="hover:bg-slate-700 transition-colors cursor-pointer"
                      >
                        <td className="px-6 py-4 text-sm font-medium text-slate-pool_opt_in">{player.name}</td>
                        <td className="px-6 py-4 text-sm font-mono text-sky-400">{player.current_rating.toFixed(1)}</td>
                        <td className="px-6 py-4 text-sm text-slate-300">{player.fargo_equivalent.toFixed(0)}</td>
                        <td className="px-6 py-4 text-sm text-slate-300">{player.games_played}</td>
                        <td className={`px-6 py-4 text-sm font-medium ${getTrendColor(player.rating_change)}`}>
                          {player.rating_change ? (player.rating_change > 0 ? '+' : '') + player.rating_change.toFixed(2) : '—'}
                        </td>
                        <td className="px-6 py-4">
                          <span className={`px-2 py-1 text-xs font-semibold rounded ${getExperienceBadgeColor(player.experience_level)}`}>
                            {player.experience_level}
                          </span>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} className="px-6 py-8 text-center text-slate-400">
                        No players found
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {players && players.pages > 1 && (
              <div className="flex items-center justify-between px-6 py-4 border-t border-slate-700">
                <button
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page === 1}
                  className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-slate-200 text-sm font-medium"
                >
                  Previous
                </button>
                <span className="text-sm text-slate-400">
                  Page {page} of {players.pages}
                </span>
                <button
                  onClick={() => setPage(Math.min(players.pages, page + 1))}
                  disabled={page === players.pages}
                  className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 disabled:opacity-50 text-slate-200 text-sm font-medium"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default AlfaPlayerRatings
