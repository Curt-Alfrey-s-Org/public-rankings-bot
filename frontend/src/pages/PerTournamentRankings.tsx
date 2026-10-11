/**
 * Per-Tournament Rankings Page
 * Shows WPA Men, WPA Women, WPBA Women with points per event.
 * Organized, intuitive, easy to find — more data, well structured.
 */

import { useState, useMemo, Fragment } from 'react'
import { useQuery } from '@tanstack/react-query'
import { rankingsApi, type PerTournamentRankingsResponse, type PerTournamentPlayer, type PerTournamentDivision } from '@/api/rankings'

type DivisionKey = 'wpa_men' | 'wpa_women' | 'wpba_women'

const DIVISION_LABELS: Record<DivisionKey, string> = {
  wpa_men: 'WPA Men',
  wpa_women: 'WPA Women',
  wpba_women: 'WPBA Women',
}

function PlayerTournamentChart({ player, tournaments }: { player: PerTournamentPlayer; tournaments: string[] }) {
  const data = useMemo(() => {
    return tournaments
      .map((t) => ({ name: t, pts: player.tournament_points[t] ?? 0 }))
      .filter((d) => d.pts > 0)
  }, [player, tournaments])

  if (data.length === 0) return null
  const maxPts = Math.max(...data.map((d) => d.pts), 1)

  return (
    <div className="mt-3 space-y-2">
      <p className="text-xs font-medium text-slate-400">Points by tournament</p>
      <div className="flex flex-wrap gap-2">
        {data.map((d) => (
          <div key={d.name} className="flex items-center gap-2 min-w-0">
            <div
              className="h-6 rounded bg-sky-500/60 min-w-[4px]"
              style={{ width: `${Math.max(24, (d.pts / maxPts) * 120)}px` }}
              title={`${d.name}: ${d.pts.toLocaleString()} pts`}
            />
            <span className="text-xs text-slate-300 truncate max-w-[140px]" title={d.name}>
              {d.name.replace(/^\d{4}\s+/, '')}
            </span>
            <span className="text-xs tabular-nums text-sky-400">{d.pts.toLocaleString()}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function DivisionTable({
  division,
  search,
  sortBy,
  sortAsc,
  onSort,
  expandedPlayer,
  onExpand,
}: {
  division: PerTournamentDivision
  search: string
  sortBy: 'rank' | 'name' | 'points' | 'events'
  sortAsc: boolean
  onSort: (field: 'rank' | 'name' | 'points' | 'events') => void
  expandedPlayer: string | null
  onExpand: (name: string | null) => void
}) {
  const filtered = useMemo(() => {
    let list = division.players ?? []
    if (search.trim()) {
      const q = search.trim().toLowerCase()
      list = list.filter((p) => p.name.toLowerCase().includes(q) || (p.country ?? '').toLowerCase().includes(q))
    }
    const cmp = (a: PerTournamentPlayer, b: PerTournamentPlayer) => {
      let va: string | number
      let vb: string | number
      switch (sortBy) {
        case 'rank':
          va = a.rank
          vb = b.rank
          break
        case 'name':
          va = a.name.toLowerCase()
          vb = b.name.toLowerCase()
          break
        case 'points':
          va = a.points
          vb = b.points
          break
        case 'events':
          va = Object.keys(a.tournament_points ?? {}).filter((k) => (a.tournament_points[k] ?? 0) > 0).length
          vb = Object.keys(b.tournament_points ?? {}).filter((k) => (b.tournament_points[k] ?? 0) > 0).length
          break
        default:
          va = a.rank
          vb = b.rank
      }
      if (typeof va === 'number' && typeof vb === 'number') return sortAsc ? va - vb : vb - va
      const s = String(va).localeCompare(String(vb))
      return sortAsc ? s : -s
    }
    return [...list].sort(cmp)
  }, [division.players, search, sortBy, sortAsc])

  const tournaments = division.tournaments ?? []

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-700 bg-slate-900/50">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-700 bg-slate-800/80">
            <th className="px-4 py-3 text-left font-semibold text-slate-200 w-12">
              <button onClick={() => onSort('rank')} className="hover:text-white">
                # {sortBy === 'rank' && (sortAsc ? '↑' : '↓')}
              </button>
            </th>
            <th className="px-4 py-3 text-left font-semibold text-slate-200">
              <button onClick={() => onSort('name')} className="hover:text-white">
                Player {sortBy === 'name' && (sortAsc ? '↑' : '↓')}
              </button>
            </th>
            <th className="px-4 py-3 text-right font-semibold text-slate-200">
              <button onClick={() => onSort('points')} className="hover:text-white">
                Points {sortBy === 'points' && (sortAsc ? '↑' : '↓')}
              </button>
            </th>
            {division.players[0]?.played != null && (
              <th className="px-4 py-3 text-right font-semibold text-slate-200">
                <button onClick={() => onSort('events')} className="hover:text-white">
                  Played {sortBy === 'events' && (sortAsc ? '↑' : '↓')}
                </button>
              </th>
            )}
            <th className="px-4 py-3 text-left font-semibold text-slate-200">Country</th>
            <th className="px-4 py-3 w-12" />
          </tr>
        </thead>
        <tbody>
          {filtered.map((p) => {
            const eventsPlayed =
              p.played ?? Object.keys(p.tournament_points ?? {}).filter((k) => (p.tournament_points[k] ?? 0) > 0).length
            const isExpanded = expandedPlayer === p.name
            const colCount = division.players[0]?.played != null ? 7 : 6
            return (
              <Fragment key={p.name}>
                <tr
                  key={p.name}
                  className={`border-b border-slate-800/80 hover:bg-slate-800/50 transition-colors ${
                    isExpanded ? 'bg-slate-800/70' : ''
                  }`}
                >
                  <td className="px-4 py-3 font-medium text-slate-300">#{p.rank}</td>
                  <td className="px-4 py-3 font-medium text-white">{p.name}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-sky-400">
                    {Number(p.points).toLocaleString()}
                  </td>
                  {division.players[0]?.played != null && (
                    <td className="px-4 py-3 text-right tabular-nums text-slate-300">{eventsPlayed}</td>
                  )}
                  <td className="px-4 py-3 text-slate-400">{p.country ?? '—'}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => onExpand(isExpanded ? null : p.name)}
                      className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white"
                      aria-label={isExpanded ? 'Collapse' : 'Expand'}
                    >
                      {isExpanded ? '−' : '+'}
                    </button>
                  </td>
                </tr>
                {isExpanded && (
                  <tr className="border-b border-slate-800/80 bg-slate-900/80">
                    <td colSpan={colCount} className="px-4 py-4">
                      <div className="pl-4 border-l-2 border-sky-500/50">
                        <PlayerTournamentChart player={p} tournaments={tournaments} />
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
      {filtered.length === 0 && (
        <div className="py-12 text-center text-slate-400">No players match your search.</div>
      )}
    </div>
  )
}

export default function PerTournamentRankings() {
  const [division, setDivision] = useState<DivisionKey>('wpba_women')
  const [search, setSearch] = useState('')
  const [sortBy, setSortBy] = useState<'rank' | 'name' | 'points' | 'events'>('rank')
  const [sortAsc, setSortAsc] = useState(true)
  const [expandedPlayer, setExpandedPlayer] = useState<string | null>(null)

  const { data, isLoading, error, refetch } = useQuery<PerTournamentRankingsResponse>({
    queryKey: ['per-tournament-rankings'],
    queryFn: () => rankingsApi.getPerTournament(),
    staleTime: 1000 * 60 * 5,
  })

  const handleSort = (field: 'rank' | 'name' | 'points' | 'events') => {
    if (sortBy === field) setSortAsc((a) => !a)
    else setSortBy(field)
  }

  const divData = data?.[division]
  const playerCount = divData?.players?.length ?? 0
  const tournamentCount = divData?.tournaments?.length ?? 0

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background p-6">
        <div className="max-w-7xl mx-auto">
          <div className="animate-pulse space-y-4">
            <div className="h-10 bg-slate-800 rounded w-1/3" />
            <div className="h-64 bg-slate-800 rounded" />
          </div>
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-background p-6">
        <div className="max-w-7xl mx-auto">
          <div className="rounded-lg border border-amber-800 bg-amber-950/30 p-6 text-center">
            <p className="text-amber-200 mb-2">Could not load per-tournament rankings.</p>
            <p className="text-sm text-muted-foreground mb-4">
              {error instanceof Error ? error.message : 'Data not found. Run scripts/scrape_per_tournament_rankings.py to generate.'}
            </p>
            <button
              type="button"
              onClick={() => refetch()}
              className="px-4 py-2 rounded-lg bg-primary text-primary-foreground font-medium hover:opacity-90"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-4xl font-bold text-white mb-2">
          <span className="text-accent">Per-Tournament</span> Rankings
        </h1>
        <p className="text-muted-foreground mb-6">
          Points per event for WPA Men, WPA Women, and WPBA Women. Expand a row to see the breakdown by tournament.
        </p>

        {/* Division tabs */}
        <div className="flex flex-wrap gap-2 mb-4">
          {(Object.keys(DIVISION_LABELS) as DivisionKey[]).map((key) => {
            const d = data[key]
            if (!d) return null
            return (
              <button
                key={key}
                onClick={() => {
                  setDivision(key)
                  setExpandedPlayer(null)
                }}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  division === key
                    ? 'bg-sky-600 text-white'
                    : 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white'
                }`}
              >
                {DIVISION_LABELS[key]} ({d.players?.length ?? 0})
              </button>
            )
          })}
        </div>

        {/* Search and summary */}
        <div className="flex flex-wrap items-center gap-4 mb-4">
          <input
            type="search"
            placeholder="Search player or country..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-slate-800 border border-slate-600 rounded-lg px-4 py-2 text-white placeholder-slate-500 min-w-[200px] focus:ring-2 focus:ring-sky-500 focus:border-sky-500"
          />
          <span className="text-sm text-slate-400">
            {playerCount} players • {tournamentCount} tournaments
          </span>
          {divData?.source && (
            <span className="text-xs text-slate-500" title="Data source">
              Source: {divData.source}
            </span>
          )}
        </div>

        {/* Table */}
        {divData ? (
          <DivisionTable
            division={divData}
            search={search}
            sortBy={sortBy}
            sortAsc={sortAsc}
            onSort={handleSort}
            expandedPlayer={expandedPlayer}
            onExpand={setExpandedPlayer}
          />
        ) : (
          <div className="rounded-lg border border-slate-700 bg-slate-900/50 p-12 text-center text-slate-400">
            No data for this division.
          </div>
        )}

        {/* Tournament list reference */}
        {divData && divData.tournaments && divData.tournaments.length > 0 && (
          <details className="mt-6 rounded-lg border border-slate-700 bg-slate-900/30">
            <summary className="px-4 py-3 cursor-pointer text-slate-300 hover:text-white font-medium">
              Tournament list ({divData.tournaments.length})
            </summary>
            <div className="px-4 pb-4 flex flex-wrap gap-2">
              {divData.tournaments.map((t) => (
                <span
                  key={t}
                  className="px-2 py-1 rounded bg-slate-800 text-slate-400 text-xs"
                  title={t}
                >
                  {t.length > 40 ? t.slice(0, 37) + '…' : t}
                </span>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  )
}
