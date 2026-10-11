/**
 * Tournament History Page
 * Browse tournament history (2022-2025) and view player tournament records
 */

import { useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { useAuth } from '@/contexts/AuthContext'
import { useTournamentsApi, useTournamentHistoryApi, useApiPathPrefixes } from '@/contexts/ApiPathContext'
import PageLoader from '@/components/PageLoader'
import TournamentSourceTabs from '@/components/TournamentSourceTabs'
import { useAlfaAskAiRegistration } from '@alfa-ai/chat-widget'
import { formatLocalDate } from '@/utils/formatLocalDate'
import './TournamentHistory.css'

/** Best-effort game type for sorting/filtering (no dedicated DB column on tournament_history). */
function inferGameType(t: {
  name?: string
  championship?: string
  association?: string
}): string {
  const assocRaw = String(t.association || '').trim()
  // WPBA (Women's Professional Billiard Association) tour is 9-ball only.
  if (/^wpba\b/i.test(assocRaw)) return '9-ball'
  const assoc = assocRaw.toUpperCase()
  if (assoc.includes('HEYBALL')) return 'Heyball'
  const s = `${t.name || ''} ${t.championship || ''}`.toLowerCase()
  if (/\b10[\s-]?ball\b|\bten ball\b/i.test(s)) return '10-ball'
  if (/\b9[\s-]?ball\b|\bnine[\s-]?ball\b/i.test(s)) return '9-ball'
  if (/\b8[\s-]?ball\b|\beight[\s-]?ball\b/i.test(s)) return '8-ball'
  if (/\bartistic\b/i.test(s)) return 'Artistic'
  if (/\bstraight[\s-]?pool|strait[\s-]?pool|one[\s-]?pocket|bank[\s-]?pool/i.test(s)) return 'Other'
  return 'Other'
}

function parsePrizeUsd(raw?: string): number | null {
  if (!raw || typeof raw !== 'string') return null
  const m = raw.replace(/,/g, '').match(/(\d+(?:\.\d+)?)\s*([kKmM])?\b/i)
  if (!m) return null
  let n = parseFloat(m[1])
  const suf = (m[2] || '').toUpperCase()
  if (suf === 'K') n *= 1_000
  if (suf === 'M') n *= 1_000_000
  return Number.isFinite(n) ? n : null
}

function matchesPrizeTier(prizePool: string | undefined, tier: string): boolean {
  if (!tier) return true
  const usd = parsePrizeUsd(prizePool)
  if (usd == null) return true
  switch (tier) {
    case 'major':
      return usd >= 50_000
    case 'large':
      return usd >= 10_000 && usd < 50_000
    case 'medium':
      return usd >= 5_000 && usd < 10_000
    case 'small':
      return usd < 5_000
    default:
      return true
  }
}

/** Prefer real `date`; else end of `year` for stable ordering. */
function tournamentDateMs(t: { date?: string; year?: number }): number {
  if (t.date) {
    const ms = new Date(t.date).getTime()
    if (Number.isFinite(ms)) return ms
  }
  const y = Number(t.year)
  if (Number.isFinite(y) && y > 1900) return Date.UTC(y, 11, 31, 23, 59, 59)
  return 0
}

function compareStringsCase(a: string, b: string, sortDir: 'asc' | 'desc'): number {
  const c = a.localeCompare(b, undefined, { sensitivity: 'base' })
  return sortDir === 'asc' ? c : -c
}

type TourneyRow = {
  name?: string
  year?: number
  date?: string
  association?: string
  championship?: string
  prize_pool?: string
}

/** Newest first: date, then year, then DB id, then tournament_id for stable order. */
function compareNewestTournamentFirst(
  a: TourneyRow & { id?: number; tournament_id?: string },
  b: TourneyRow & { id?: number; tournament_id?: string }
): number {
  const da = tournamentDateMs(a)
  const db = tournamentDateMs(b)
  if (db !== da) return db - da
  const ya = Number(a.year)
  const yb = Number(b.year)
  if (Number.isFinite(yb) && Number.isFinite(ya) && yb !== ya) return yb - ya
  const ida = typeof a.id === 'number' ? a.id : NaN
  const idb = typeof b.id === 'number' ? b.id : NaN
  if (Number.isFinite(idb) && Number.isFinite(ida) && idb !== ida) return idb - ida
  return String(b.tournament_id || '').localeCompare(String(a.tournament_id || ''))
}

function compareTournamentsForSort(
  a: TourneyRow,
  b: TourneyRow,
  sortBy: 'date' | 'year' | 'association' | 'name' | 'game_type' | 'prize_pool',
  sortDir: 'asc' | 'desc'
): number {
  let primary = 0
  switch (sortBy) {
    case 'year': {
      const ya = Number(a.year)
      const yb = Number(b.year)
      const fa = Number.isFinite(ya) ? ya : 0
      const fb = Number.isFinite(yb) ? yb : 0
      primary = sortDir === 'asc' ? fa - fb : fb - fa
      break
    }
    case 'association':
      primary = compareStringsCase(String(a.association || ''), String(b.association || ''), sortDir)
      break
    case 'name':
      primary = compareStringsCase(String(a.name || ''), String(b.name || ''), sortDir)
      break
    case 'game_type': {
      primary = compareStringsCase(inferGameType(a), inferGameType(b), sortDir)
      break
    }
    case 'prize_pool': {
      const pa = parsePrizeUsd(a.prize_pool)
      const pb = parsePrizeUsd(b.prize_pool)
      const hasA = pa != null
      const hasB = pb != null
      if (!hasA && !hasB) primary = 0
      else if (!hasA) primary = sortDir === 'desc' ? 1 : -1
      else if (!hasB) primary = sortDir === 'desc' ? -1 : 1
      else primary = sortDir === 'asc' ? pa - pb : pb - pa
      break
    }
    case 'date':
    default: {
      const da = tournamentDateMs(a)
      const db = tournamentDateMs(b)
      primary = sortDir === 'asc' ? da - db : db - da
      break
    }
  }
  if (primary !== 0) return primary
  if (sortBy === 'date' && sortDir === 'desc') {
    return compareNewestTournamentFirst(
      a as TourneyRow & { id?: number; tournament_id?: string },
      b as TourneyRow & { id?: number; tournament_id?: string }
    )
  }
  const tie = tournamentDateMs(b) - tournamentDateMs(a)
  if (tie !== 0) return tie
  return compareStringsCase(String(a.name || ''), String(b.name || ''), 'asc')
}

export default function TournamentHistory() {
  const tournamentsApi = useTournamentsApi()
  const tournamentHistoryApi = useTournamentHistoryApi()
  const { scope: apiScope } = useApiPathPrefixes()
  const { isAdmin, user: authUser } = useAuth()
  const authHeaders = useMemo((): HeadersInit | undefined => {
    const token = authUser?.token ?? localStorage.getItem('access_token') ?? localStorage.getItem('auth_token')
    try {
      if (!token && localStorage.getItem('rankings_bot_auth')) {
        const raw = JSON.parse(localStorage.getItem('rankings_bot_auth')!)
        if (raw?.token) return { Authorization: `Bearer ${raw.token}` }
      }
    } catch {
      /* ignore */
    }
    return token ? { Authorization: `Bearer ${token}` } : undefined
  }, [authUser?.token])
  const { data: myPlayerInfo } = useQuery<{ player_name: string }>({
    queryKey: ['player-performance-me'],
    queryFn: async () => {
      const r = await fetch('/api/player-performance/me', { headers: authHeaders })
      if (!r.ok) return { player_name: (authUser?.user ?? '').trim() }
      const data = await r.json()
      return { player_name: (data?.player_name ?? authUser?.user ?? '').trim() }
    },
    enabled: !!authHeaders?.Authorization,
  })
  const myPlayerName = (myPlayerInfo?.player_name ?? authUser?.user ?? '').trim()

  const [selectedYear, setSelectedYear] = useState<number | undefined>(undefined)
  const [selectedAssociation, setSelectedAssociation] = useState<string | undefined>(undefined)
  const [selectedGameType, setSelectedGameType] = useState<string>('')
  const [selectedPrizePool, setSelectedPrizePool] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedTournament, setSelectedTournament] = useState<{ tournament_id: string; name: string; year: number; date: string; location: string; association: string; championship: string; prize_pool?: string; status?: string } | null>(null)
  const [selectedPlayer, setSelectedPlayer] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'tournaments' | 'player'>('tournaments')

  // Fetch available years (live-update: refetch every 30s)
  const { data: yearsData, isError: yearsError, error: yearsErrorObj, refetch: refetchYears } = useQuery({
    queryKey: [apiScope, 'tournament-history-years'],
    queryFn: async () => {
      const result = await tournamentHistoryApi.getAvailableYears()
      return result.years || []
    },
    refetchInterval: 30_000,
  })

  /** Year filter: newest calendar year first (coerce API strings/Decimals; dedupe). */
  const yearsNewestFirst = useMemo(() => {
    const raw = yearsData ?? []
    const nums = raw
      .map((y) => {
        const n = typeof y === 'number' && Number.isFinite(y) ? y : parseInt(String(y).trim(), 10)
        return Number.isFinite(n) && n >= 1990 && n <= 2100 ? n : NaN
      })
      .filter((y) => Number.isFinite(y))
    return [...new Set(nums)].sort((a, b) => b - a)
  }, [yearsData])

  // Fetch scraped tournament history (WPBA/WPA)
  const {
    data: scrapedTournaments = [],
    isLoading: tournamentsLoading,
    isError: tournamentsError,
    error: tournamentsErrorObj,
    refetch: refetchTournaments,
  } = useQuery({
    queryKey: [apiScope, 'tournament-history', selectedYear, selectedAssociation],
    queryFn: async () => {
      const result = await tournamentHistoryApi.getTournaments(selectedYear, selectedAssociation)
      return result.tournaments || []
    },
    refetchInterval: 30_000,
  })

  // Fetch director-run completed tournaments (Local) — merged so super_admin and director both see them
  const {
    data: localTournaments = [],
    isError: localTournamentsError,
    error: localTournamentsErrorObj,
    refetch: refetchLocalTournaments,
  } = useQuery({
    queryKey: [apiScope, 'tournament-history-local', authUser?.role],
    queryFn: async () => {
      const list = await tournamentsApi.getTournaments('completed')
      return (list || []).map((t) => ({
        tournament_id: t.tournament_id,
        name: t.tournament_name,
        year: t.tournament_date ? new Date(t.tournament_date).getFullYear() : new Date().getFullYear(),
        date: t.tournament_date || '',
        location: t.location || '',
        association: 'Local',
        championship: 'Director-run tournament',
      }))
    },
    enabled: !!authUser,
    refetchInterval: 30_000,
  })

  // Merge: show Local when "All Associations" or "Local"; exclude Local when filtering by WPBA/WPA/etc
  const tournamentsData = useMemo(() => {
    const includeLocal = !selectedAssociation || selectedAssociation === 'Local'
    const scraped = scrapedTournaments || []
    const local = includeLocal ? (localTournaments || []) : []
    return [...scraped, ...local]
  }, [scrapedTournaments, localTournaments, selectedAssociation])

  /** Year dropdown: API list plus years inferred from loaded rows (if /years fails or returns empty). */
  const yearFilterOptions = useMemo(() => {
    const merged = new Set<number>(yearsNewestFirst)
    for (const t of tournamentsData) {
      const raw = t.year
      const y =
        typeof raw === 'number' && Number.isFinite(raw)
          ? raw
          : parseInt(String(raw ?? '').trim(), 10)
      if (Number.isFinite(y) && y >= 1990 && y <= 2100) merged.add(y)
    }
    return [...merged].sort((a, b) => b - a)
  }, [yearsNewestFirst, tournamentsData])

  /** Search, game type, prize filters + sort (most recent first) */
  const displayTournaments = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    let list = tournamentsData.filter((t) => {
      if (q) {
        const blob = `${t.name || ''} ${t.championship || ''} ${t.location || ''} ${t.association || ''}`.toLowerCase()
        if (!blob.includes(q)) return false
      }
      if (selectedGameType) {
        const gt = inferGameType(t)
        const want = selectedGameType.toLowerCase()
        if (want === 'heyball') {
          if (gt !== 'Heyball') return false
        } else if (gt.toLowerCase() !== want) return false
      }
      if (selectedPrizePool && !matchesPrizeTier(t.prize_pool, selectedPrizePool)) return false
      return true
    })

    list = [...list].sort((a, b) =>
      compareNewestTournamentFirst(
        a as TourneyRow & { id?: number; tournament_id?: string },
        b as TourneyRow & { id?: number; tournament_id?: string }
      )
    )

    return list
  }, [tournamentsData, searchQuery, selectedGameType, selectedPrizePool])

  // Fetch tournament details — use tournaments API for Local, tournament_history for scraped
  const isLocalTournament = selectedTournament?.association === 'Local'
  const {
    data: tournamentDetails,
    isLoading: detailsLoading,
    isError: detailsError,
    error: detailsErrorObj,
    refetch: refetchDetails,
  } = useQuery({
    queryKey: [apiScope, 'tournament-history-details', selectedTournament?.tournament_id, isLocalTournament],
    queryFn: async () => {
      if (!selectedTournament?.tournament_id) return null
      if (isLocalTournament) {
        const t = await tournamentsApi.getTournament(selectedTournament.tournament_id)
        const completed = await tournamentsApi.getCompletedResults(100)
        const thisOne = completed.tournaments?.find((c) => c.tournament_id === selectedTournament.tournament_id)
        const results = [
          ...(thisOne?.first_place_name ? [{ player_name: thisOne.first_place_name, placement: 1, points: null }] : []),
          ...(thisOne?.second_place_name ? [{ player_name: thisOne.second_place_name, placement: 2, points: null }] : []),
          ...(thisOne?.third_place_name ? [{ player_name: thisOne.third_place_name, placement: 3, points: null }] : []),
        ]
        return {
          success: true,
          tournament: { name: t.tournament_name, year: new Date(t.tournament_date).getFullYear(), date: t.tournament_date, location: t.location, association: 'Local', championship: 'Director-run tournament' },
          results,
          total_participants: t.actual_players ?? results.length,
        }
      }
      return tournamentHistoryApi.getTournamentDetails(selectedTournament.tournament_id)
    },
    enabled: !!selectedTournament?.tournament_id,
    refetchInterval: 30_000,
  })

  const {
    data: tournamentPerformance,
    isLoading: performanceLoading,
  } = useQuery({
    queryKey: [apiScope, 'tournament-history-performance', selectedTournament?.tournament_id],
    queryFn: async () => {
      if (!selectedTournament?.tournament_id) return null
      return tournamentsApi.getTournamentPerformance(selectedTournament.tournament_id)
    },
    enabled: !!selectedTournament?.tournament_id && !isLocalTournament,
    retry: 1,
  })

  const {
    data: tabCoverage,
    isLoading: coverageLoading,
  } = useQuery({
    queryKey: [apiScope, 'tournament-history-tab-coverage', selectedTournament?.tournament_id],
    queryFn: async () => {
      if (!selectedTournament?.tournament_id) return null
      return tournamentsApi.getTournamentTabCoverage(selectedTournament.tournament_id, {
        includePayload: true,
      })
    },
    enabled: !!selectedTournament?.tournament_id && !isLocalTournament,
    retry: 1,
  })

  const { data: historyMatchesData, isLoading: historyMatchesLoading } = useQuery({
    queryKey: [apiScope, 'tournament-history-matches', selectedTournament?.tournament_id],
    queryFn: async () => {
      if (!selectedTournament?.tournament_id) return null
      return tournamentHistoryApi.getTournamentMatches(selectedTournament.tournament_id)
    },
    enabled: !!selectedTournament?.tournament_id && !isLocalTournament,
    retry: 1,
  })

  const {
    data: tabCoverageListData,
  } = useQuery({
    queryKey: [apiScope, 'tournament-history-tab-coverage-list', selectedYear, selectedAssociation],
    queryFn: async () =>
      tournamentsApi.getTournamentTabCoverageList({
        limit: 300,
        year: selectedYear,
        association:
          selectedAssociation && selectedAssociation !== 'Local'
            ? selectedAssociation
            : undefined,
        incomplete_only: false,
      }),
    // Local tournaments do not use archived tournament-tab payloads.
    enabled: selectedAssociation !== 'Local',
    retry: 1,
  })

  const tabCoverageByTournamentId = useMemo(() => {
    const map = new Map<string, any>()
    for (const row of tabCoverageListData?.items || []) {
      map.set(row.tournament_id, row)
    }
    return map
  }, [tabCoverageListData])

  const displayTournamentIds = useMemo(
    () => (displayTournaments || []).map((t: any) => t.tournament_id).filter(Boolean),
    [displayTournaments],
  )

  const { data: resultsCounts } = useQuery({
    queryKey: [apiScope, 'tournament-results-counts', displayTournamentIds],
    queryFn: () => tournamentHistoryApi.getResultsCounts(displayTournamentIds),
    enabled: displayTournamentIds.length > 0,
    staleTime: 60_000,
  })

  // Fetch player tournament history (live-update: refetch every 30s while viewing)
  const {
    data: playerHistory,
    isError: playerError,
    error: playerErrorObj,
    refetch: refetchPlayer,
  } = useQuery({
    queryKey: [apiScope, 'tournament-history-player', selectedPlayer],
    queryFn: async () => {
      if (!selectedPlayer) return null
      const result = await tournamentHistoryApi.getPlayerTournamentHistory(selectedPlayer)
      return result
    },
    enabled: !!selectedPlayer && viewMode === 'player',
    refetchInterval: 30_000,
  })

  const alfaThRegistration = useMemo(() => {
    if (viewMode !== 'player' || !selectedPlayer?.trim() || !playerHistory) return null
    return {
      page: 'tournament-history' as const,
      playerName: selectedPlayer.trim(),
      context: {
        statistics: playerHistory.statistics,
        tournament_results: playerHistory.tournament_results.slice(0, 20),
        narrative: playerHistory.narrative,
      } as Record<string, unknown>,
    }
  }, [viewMode, selectedPlayer, playerHistory])
  useAlfaAskAiRegistration(alfaThRegistration)

  const handleTournamentClick = (tournament: any) => {
    setSelectedTournament(tournament)
  }

  const handlePlayerClick = (playerName: string) => {
    setSelectedPlayer(playerName)
    setViewMode('player')
  }

  const handleBackFromDetails = () => {
    setSelectedTournament(null)
  }

  const handleBackFromPlayer = () => {
    setSelectedPlayer(null)
    setViewMode('tournaments')
  }

  if (viewMode === 'player' && selectedPlayer && playerHistory) {
    return (
      <div className="tournament-history-page">
        <div className="container mx-auto px-4 py-8">
          <div className="flex flex-wrap items-center gap-3 mb-6">
            <button
              onClick={handleBackFromPlayer}
              className="inline-flex items-center gap-2 px-4 py-2 text-purple-300 hover:text-purple-pool_opt_in rounded-lg border border-purple-300/30 hover:border-purple-300/60 transition-all"
            >
              ← Back to Tournaments
            </button>
            {isAdmin && selectedPlayer && (
              <Link
                to={`/player-performance?player=${encodeURIComponent(selectedPlayer)}`}
                className="inline-flex items-center gap-2 px-4 py-2 bg-accent text-white rounded-lg hover:opacity-90 transition-opacity"
              >
                Open in Player Performance →
              </Link>
            )}
          </div>

          <div className="player-history-card">
            <div className="player-history-header">
              <h2 className="text-3xl font-bold text-white">{selectedPlayer}</h2>
              {playerHistory.narrative && (
                <div className="mt-4 mb-2 border-l-2 border-slate-500 pl-3 space-y-1">
                  {playerHistory.narrative_unchanged && (
                    <p className="text-xs text-slate-500 uppercase tracking-wide">Summary unchanged</p>
                  )}
                  <p
                    className={`text-sm ${playerHistory.narrative_unchanged ? 'text-slate-400' : 'text-slate-300/95'}`}
                  >
                    {playerHistory.narrative}
                  </p>
                </div>
              )}
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mt-4">
                <div className="stat-box">
                  <div className="stat-value">{playerHistory.statistics.total_tournaments}</div>
                  <div className="stat-label">Tournaments</div>
                </div>
                <div className="stat-box">
                  <div className="stat-value">{playerHistory.statistics.first_place_finishes}</div>
                  <div className="stat-label">1st Place</div>
                </div>
                <div className="stat-box">
                  <div className="stat-value">{playerHistory.statistics.top_3_finishes}</div>
                  <div className="stat-label">Top 3</div>
                </div>
                {playerHistory.statistics.average_placement && (
                  <div className="stat-box">
                    <div className="stat-value">
                      {playerHistory.statistics.average_placement.toFixed(1)}
                    </div>
                    <div className="stat-label">Avg Placement</div>
                  </div>
                )}
                {/* New enhanced statistics */}
                {(() => {
                  const winRate = playerHistory.statistics.total_tournaments > 0
                    ? ((playerHistory.statistics.first_place_finishes / playerHistory.statistics.total_tournaments) * 100).toFixed(1)
                    : '0.0'
                  const top3Rate = playerHistory.statistics.total_tournaments > 0
                    ? ((playerHistory.statistics.top_3_finishes / playerHistory.statistics.total_tournaments) * 100).toFixed(1)
                    : '0.0'

                  return (
                    <>
                      <div className="stat-box">
                        <div className="stat-value">{winRate}%</div>
                        <div className="stat-label">Win Rate</div>
                      </div>
                      <div className="stat-box">
                        <div className="stat-value">{top3Rate}%</div>
                        <div className="stat-label">Top 3 Rate</div>
                      </div>
                    </>
                  )
                })()}
              </div>
            </div>

            {/* Performance Analytics Section */}
            <div className="performance-analytics mt-8">
              <h3 className="text-xl font-semibold text-white mb-6 flex items-center gap-2">
                <span>📊</span> Performance Analytics
              </h3>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Performance Trend Chart */}
                <div className="analytics-card">
                  <h4 className="text-lg font-semibold text-white mb-4">Tournament Performance Trend</h4>
                  <div className="performance-chart-placeholder" style={{ minHeight: 280 }}>
                    {(() => {
                      const results = [...playerHistory.tournament_results]
                        .filter((r) => r.date != null)
                        .sort(
                          (a, b) =>
                            new Date(a.date as string).getTime() - new Date(b.date as string).getTime()
                        )
                      const chartData = results.map((r, i) => ({
                        index: i + 1,
                        date: r.date
                          ? formatLocalDate(String(r.date), {
                              month: 'short',
                              day: 'numeric',
                              year: '2-digit',
                            })
                          : '',
                        placement: r.placement,
                        points: r.points ?? 0,
                      }))
                      if (chartData.length === 0) {
                        return (
                          <div className="text-center py-8 text-slate-400">
                            <p>No dated results to chart</p>
                          </div>
                        )
                      }
                      return (
                        <ResponsiveContainer width="100%" height={260} minWidth={200} minHeight={260}>
                          <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.3)" />
                            <XAxis
                              dataKey="date"
                              tick={{ fill: '#94a3b8', fontSize: 11 }}
                              tickLine={{ stroke: 'rgba(148,163,184,0.3)' }}
                            />
                            <YAxis
                              reversed
                              domain={['dataMin - 1', 'dataMax + 1']}
                              tick={{ fill: '#94a3b8', fontSize: 11 }}
                              tickLine={{ stroke: 'rgba(148,163,184,0.3)' }}
                            />
                            <Tooltip
                              contentStyle={{
                                background: 'rgba(30,41,59,0.95)',
                                border: '1px solid rgba(148,163,184,0.3)',
                                borderRadius: 8,
                              }}
                              labelStyle={{ color: '#e2e8f0' }}
                              content={({ active, payload, label }) =>
                                active && payload?.length ? (
                                  <div className="px-3 py-2 text-sm">
                                    <div className="text-slate-300">{label}</div>
                                    <div>Placement: #{payload[0].value}</div>
                                    {payload[0].payload?.points != null && (
                                      <div>Points: {payload[0].payload.points}</div>
                                    )}
                                  </div>
                                ) : null
                              }
                            />
                            <Line
                              type="monotone"
                              dataKey="placement"
                              stroke="#a78bfa"
                              strokeWidth={2}
                              dot={{ fill: '#c4b5fd', r: 4 }}
                              activeDot={{ r: 6 }}
                            />
                          </LineChart>
                        </ResponsiveContainer>
                      )
                    })()}
                  </div>
                </div>

                {/* Tournament Insights */}
                <div className="analytics-card">
                  <h4 className="text-lg font-semibold text-white mb-4">Tournament Insights</h4>
                  <div className="insights-grid">
                    {(() => {
                      const results = playerHistory.tournament_results
                      const bestPlacement = Math.min(...results.map(r => r.placement))
                      const worstPlacement = Math.max(...results.map(r => r.placement))
                      const byNewest = [...results].sort(
                        (a, b) =>
                          tournamentDateMs({ date: b.date, year: b.year }) -
                          tournamentDateMs({ date: a.date, year: a.year })
                      )
                      const recentResults = byNewest.slice(0, 5)
                      const recentAvg = recentResults.length > 0
                        ? (recentResults.reduce((sum, r) => sum + r.placement, 0) / recentResults.length).toFixed(1)
                        : 'N/A'

                      return (
                        <>
                          <div className="insight-item">
                            <div className="insight-label">Best Placement</div>
                            <div className="insight-value text-green-400">#{bestPlacement}</div>
                          </div>
                          <div className="insight-item">
                            <div className="insight-label">Worst Placement</div>
                            <div className="insight-value text-red-400">#{worstPlacement}</div>
                          </div>
                          <div className="insight-item">
                            <div className="insight-label">Recent Avg (Last 5)</div>
                            <div className="insight-value text-blue-400">#{recentAvg}</div>
                          </div>
                          <div className="insight-item">
                            <div className="insight-label">Consistency Score</div>
                            <div className="insight-value text-purple-400">
                              {results.length > 1
                                ? Math.max(0, 100 - (worstPlacement - bestPlacement) * 10).toFixed(0)
                                : 'N/A'}%
                            </div>
                          </div>
                        </>
                      )
                    })()}
                  </div>
                </div>
              </div>
            </div>

            <div className="player-results-list">
              <h3 className="text-xl font-semibold text-white mb-4">Tournament Results</h3>
              {playerHistory.tournament_results.length === 0 ? (
                <div className="empty-state text-gray-400">
                  No tournament history found for this player.
                </div>
              ) : (
                <div className="results-table">
                  <div className="table-header">
                    <div className="col-tournament">Tournament</div>
                    <div className="col-date">Date</div>
                    <div className="col-placement">Placement</div>
                    <div className="col-points">Points</div>
                  </div>
                  {[...playerHistory.tournament_results]
                    .sort(
                      (a, b) =>
                        tournamentDateMs({ date: b.date, year: b.year }) -
                        tournamentDateMs({ date: a.date, year: a.year })
                    )
                    .map((result, idx) => (
                    <div key={`${result.tournament_id}-${idx}`} className="table-row">
                      <div className="col-tournament">
                        <div className="font-semibold text-white">{result.tournament_name}</div>
                        <div className="text-xs text-gray-400">{result.championship}</div>
                      </div>
                      <div className="col-date">
                        {result.date
                          ? formatLocalDate(String(result.date), {
                              year: 'numeric',
                              month: 'short',
                              day: 'numeric',
                            })
                          : 'N/A'}
                      </div>
                      <div className="col-placement">
                        <span
                          className={`placement-badge ${
                            result.placement === 1
                              ? 'gold'
                              : result.placement === 2
                              ? 'silver'
                              : result.placement === 3
                              ? 'bronze'
                              : 'default'
                          }`}
                        >
                          #{result.placement}
                        </span>
                      </div>
                      <div className="col-points">{result.points || '-'}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (viewMode === 'player' && selectedPlayer && playerError) {
    return (
      <div className="tournament-history-page">
        <div className="container mx-auto px-4 py-8">
          <button onClick={handleBackFromPlayer} className="mb-4 px-3 py-2 rounded border border-slate-600 text-slate-200">
            Back
          </button>
          <div className="rounded-lg border border-red-500/30 bg-red-900/20 p-4 text-red-pool_opt_in">
            <p className="mb-3">Failed to load player history: {playerErrorObj instanceof Error ? playerErrorObj.message : 'Unknown error'}</p>
            <button onClick={() => refetchPlayer()} className="px-3 py-2 rounded bg-red-700/60 text-white">Retry</button>
          </div>
        </div>
      </div>
    )
  }

  if (selectedTournament && tournamentDetails && !selectedPlayer) {
    return (
      <div className="tournament-history-page">
        <div className="container mx-auto px-4 py-8">
          <button
            onClick={handleBackFromDetails}
            className="mb-6 inline-flex items-center gap-2 px-4 py-2 text-purple-300 hover:text-purple-pool_opt_in rounded-lg border border-purple-300/30 hover:border-purple-300/60 transition-all"
          >
            ← Back to Tournaments
          </button>

          <div className="tournament-detail-card">
            <div className="tournament-detail-header">
              <div>
                <h2 className="text-4xl font-bold text-white">{tournamentDetails.tournament.name}</h2>
                <p className="text-purple-300 text-lg mt-2">{tournamentDetails.tournament.championship}</p>
              </div>
              <div className="tournament-year-badge">{tournamentDetails.tournament.year}</div>
            </div>

            <div className="tournament-detail-info">
              {tournamentDetails.tournament.date && (
                <div className="info-item">
                  <span>📅</span>
                  <span>{formatLocalDate(String(tournamentDetails.tournament.date))}</span>
                </div>
              )}
              {tournamentDetails.tournament.location && (
                <div className="info-item">
                  <span>📍</span>
                  <span>{tournamentDetails.tournament.location}</span>
                </div>
              )}
              <div className="info-item">
                <span>👥</span>
                <span>{tournamentDetails.total_participants} Participants</span>
              </div>
              <div className="info-item">
                <span>🏆</span>
                <span>{tournamentDetails.tournament.association === 'HEYBALL' ? 'Heyball' : tournamentDetails.tournament.association}</span>
              </div>
            </div>

            <div className="tournament-results">
              <h3 className="text-2xl font-bold text-white mb-4">Final Rankings</h3>
              {detailsLoading ? (
                <PageLoader />
              ) : tournamentDetails.results.length === 0 ? (
                <div className="empty-state text-gray-400 mb-6">
                  No final rankings available yet.
                </div>
              ) : (
                <div className="rankings-container mb-8">
                  {tournamentDetails.results.map((result: any, idx: number) => (
                    <div
                      key={idx}
                      className={`ranking-item ${
                        result.placement === 1 ? 'champion' : result.placement <= 3 ? 'podium' : ''
                      }`}
                    >
                      <div className="ranking-badge">#{result.placement}</div>
                      <div className="ranking-info">
                        <div className="player-name">{result.player_name}</div>
                        <div className="flex flex-wrap gap-2 text-xs text-slate-400 mt-0.5">
                          {result.points != null && result.points !== 0 && (
                            <span className="points text-slate-300">{result.points} pts</span>
                          )}
                          {result.seed != null && <span>Seed {result.seed}</span>}
                          {result.race_to != null && <span>Race to {result.race_to}</span>}
                          {result.current_round && <span>{result.current_round}</span>}
                          {result.player_status && <span>{result.player_status}</span>}
                          {result.is_eliminated === true && (
                            <span className="text-amber-400/90">Eliminated</span>
                          )}
                        </div>
                      </div>
                      {(isAdmin || (myPlayerName && String(result.player_name || '').trim().toLowerCase() === myPlayerName.toLowerCase())) && (
                        <button
                          onClick={() => handlePlayerClick(result.player_name)}
                          className="view-history-btn"
                        >
                          View History
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {!isLocalTournament && (
                <div className="mb-8 rounded-lg border border-slate-700/60 bg-slate-900/40 p-4">
                  <h4 className="text-lg font-semibold text-white mb-3">
                    Matches / bracket
                    {historyMatchesData?.total != null ? (
                      <span className="ml-2 text-sm font-normal text-slate-400">
                        ({historyMatchesData.total})
                      </span>
                    ) : null}
                  </h4>
                  {historyMatchesLoading ? (
                    <p className="text-sm text-slate-400">Loading matches…</p>
                  ) : !historyMatchesData?.matches?.length ? (
                    <p className="text-sm text-slate-500">
                      No harvested match rows for this event yet.
                    </p>
                  ) : (
                    <div className="overflow-x-auto max-h-80 overflow-y-auto">
                      <table className="min-w-full text-left text-sm text-slate-200">
                        <thead className="text-xs text-slate-400 sticky top-0 bg-slate-900/95">
                          <tr>
                            <th className="px-2 py-1">Round</th>
                            <th className="px-2 py-1">Player 1</th>
                            <th className="px-2 py-1">Score</th>
                            <th className="px-2 py-1">Player 2</th>
                            <th className="px-2 py-1">Winner</th>
                          </tr>
                        </thead>
                        <tbody>
                          {historyMatchesData.matches.slice(0, 200).map((m, i) => (
                            <tr key={m.id ?? i} className="border-t border-slate-800">
                              <td className="px-2 py-1 text-xs text-slate-400">
                                {m.round_num || m.match_num || '—'}
                              </td>
                              <td className="px-2 py-1">{m.operator_name || '—'}</td>
                              <td className="px-2 py-1 font-mono text-xs">
                                {m.operator_score ?? '—'}–{m.player2_score ?? '—'}
                              </td>
                              <td className="px-2 py-1">{m.player2_name || '—'}</td>
                              <td className="px-2 py-1 text-emerald-300/90 text-xs">
                                {m.winner_name || '—'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* Only show external-platform source tabs when actual harvest data exists */}
              {!isLocalTournament && tabCoverage && (tabCoverage.players_count > 0 || tabCoverage.bracket_matches_count > 0 || tabCoverage.matches_count > 0) && (
                <div className="mb-6">
                  <div className="text-xs text-slate-500 mb-2 flex flex-wrap gap-4">
                    <span>Players in archive: {tabCoverage.players_count}</span>
                    <span>Bracket rows: {tabCoverage.bracket_matches_count}</span>
                    <span>Matches: {tabCoverage.matches_count}</span>
                    {tabCoverage.captured_at && (
                      <span>Captured: {new Date(tabCoverage.captured_at).toLocaleString()}</span>
                    )}
                  </div>
                  <TournamentSourceTabs
                    coverage={{
                      has_overview: tabCoverage.has_overview,
                      has_bracket: tabCoverage.has_bracket,
                      has_live_scores: tabCoverage.has_live_scores,
                      has_matches: tabCoverage.has_matches,
                      has_schedule: tabCoverage.has_schedule,
                      has_players: tabCoverage.has_players,
                      has_stats: tabCoverage.has_stats,
                      has_performance: tabCoverage.has_performance,
                      tab_overview: tabCoverage.tab_overview ?? null,
                      tab_players: tabCoverage.tab_players ?? null,
                      tab_brackets: tabCoverage.tab_brackets ?? null,
                      tab_matches: tabCoverage.tab_matches ?? null,
                    }}
                  />
                </div>
              )}

              {!isLocalTournament && (
                <div className="mb-6 rounded-lg border border-slate-700/60 bg-slate-900/40 p-4">
                  <h4 className="text-lg font-semibold text-white mb-3">Performance Summary</h4>
                  {performanceLoading ? (
                    <div className="text-sm text-slate-400">Loading performance...</div>
                  ) : tournamentPerformance?.players?.length ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-slate-300 border-b border-slate-700">
                            <th className="text-left py-2 pr-3">Player</th>
                            <th className="text-left py-2 pr-3">Place</th>
                            <th className="text-left py-2 pr-3">Win Rate</th>
                            <th className="text-left py-2 pr-3">W-L</th>
                            <th className="text-left py-2 pr-3">Score Diff</th>
                            <th className="text-left py-2 pr-3">Finish %</th>
                          </tr>
                        </thead>
                        <tbody>
                          {tournamentPerformance.players.slice(0, 12).map((p) => (
                            <tr key={p.player_name} className="border-b border-slate-800/80 text-slate-200">
                              <td className="py-2 pr-3">{p.player_name}</td>
                              <td className="py-2 pr-3">{p.placement ?? '-'}</td>
                              <td className="py-2 pr-3">{p.win_rate != null ? `${p.win_rate}%` : '-'}</td>
                              <td className="py-2 pr-3">{p.matches_won}-{p.matches_lost}</td>
                              <td className="py-2 pr-3">{p.score_diff}</td>
                              <td className="py-2 pr-3">{p.finish_percentile != null ? `${p.finish_percentile}%` : '-'}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-sm text-slate-400">No performance data available yet.</div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (selectedTournament && detailsError && !selectedPlayer) {
    return (
      <div className="tournament-history-page">
        <div className="container mx-auto px-4 py-8">
          <button onClick={handleBackFromDetails} className="mb-4 px-3 py-2 rounded border border-slate-600 text-slate-200">
            Back
          </button>
          <div className="rounded-lg border border-red-500/30 bg-red-900/20 p-4 text-red-pool_opt_in">
            <p className="mb-3">Failed to load tournament details: {detailsErrorObj instanceof Error ? detailsErrorObj.message : 'Unknown error'}</p>
            <button onClick={() => refetchDetails()} className="px-3 py-2 rounded bg-red-700/60 text-white">Retry</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="tournament-history-page">
      <div className="container mx-auto px-4 py-8">
        {/* Hero Section */}
        <div className="hero-section mb-8">
          <h1 className="text-4xl md:text-5xl font-bold text-white mb-4">Tournament history</h1>
          <p className="text-purple-300 text-lg">
            Browse past events, filter by year or tour, and dig into how players finished.
          </p>
        </div>
        {(yearsError || tournamentsError || localTournamentsError) && (
          <div className="mb-6 rounded-lg border border-red-500/30 bg-red-900/20 p-4 text-red-pool_opt_in">
            <p className="mb-3">
              We couldn&apos;t load this page right now.
              {' '}
              {(tournamentsErrorObj instanceof Error && tournamentsErrorObj.message)
                || (yearsErrorObj instanceof Error && yearsErrorObj.message)
                || (localTournamentsErrorObj instanceof Error && localTournamentsErrorObj.message)
                || 'Please try again in a moment.'}
            </p>
            <div className="flex flex-wrap gap-2">
              <button onClick={() => refetchYears()} className="px-3 py-2 rounded bg-red-700/60 text-white">Retry years</button>
              <button onClick={() => refetchTournaments()} className="px-3 py-2 rounded bg-red-700/60 text-white">Retry scraped</button>
              <button onClick={() => refetchLocalTournaments()} className="px-3 py-2 rounded bg-red-700/60 text-white">Retry local</button>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="filters-section mb-8">
          <div className="filters-grid">
            <div className="filter-group">
              <label className="filter-label" htmlFor="th-filter-year">
                Year
              </label>
              <select
                id="th-filter-year"
                value={selectedYear || ''}
                onChange={(e) => setSelectedYear(e.target.value ? parseInt(e.target.value) : undefined)}
                className="filter-select"
              >
                <option value="">All Years</option>
                {yearFilterOptions.map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>
            </div>

            <div className="filter-group">
              <label className="filter-label" htmlFor="th-filter-association">
                Association
              </label>
              <select
                id="th-filter-association"
                value={selectedAssociation || ''}
                onChange={(e) => setSelectedAssociation(e.target.value || undefined)}
                className="filter-select"
              >
                <option value="">All Associations</option>
                <option value="Local">Local</option>
                <option value="WPBA">WPBA</option>
                <option value="WPA Men">WPA Men</option>
                <option value="WPA Women">WPA Women</option>
                <option value="WPA Artistic">WPA Artistic</option>
                <option value="Heyball">Heyball</option>
              </select>
            </div>

            <div className="filter-group">
              <label className="filter-label">Game Type</label>
              <select
                value={selectedGameType}
                onChange={(e) => setSelectedGameType(e.target.value)}
                className="filter-select"
              >
                <option value="">All Games</option>
                <option value="9-ball">9-Ball</option>
                <option value="10-ball">10-Ball</option>
                <option value="8-ball">8-Ball</option>
                <option value="Artistic">Artistic</option>
                <option value="Heyball">Heyball</option>
                <option value="Other">Other</option>
              </select>
            </div>

            <div className="filter-group">
              <label className="filter-label">Prize Pool</label>
              <select
                value={selectedPrizePool}
                onChange={(e) => setSelectedPrizePool(e.target.value)}
                className="filter-select"
              >
                <option value="">Any Prize Pool</option>
                <option value="major">$50K+</option>
                <option value="large">$10K–$50K</option>
                <option value="medium">$5K–$10K</option>
                <option value="small">Under $5K</option>
              </select>
            </div>

            <div className="filter-group">
              <label className="filter-label">Search</label>
              <div className="search-input-wrapper">
                <span className="search-icon">🔍</span>
                <input
                  type="text"
                  placeholder="Search tournaments..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="search-input"
                />
              </div>
            </div>
          </div>
          <div className="mt-3 text-sm text-slate-400">
            <Link to="/rankings" className="text-sky-400 hover:text-sky-300 transition-colors">
              Open Rankings
            </Link>
            {' '}for current WPBA and WPA standings tables.
          </div>
        </div>

        {/* Tournament Activity Summary */}
        <div className="tournament-summary mb-8">
          <div className="summary-cards grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="summary-card">
              <div className="summary-value">{displayTournaments?.length || 0}</div>
              <div className="summary-label">Tournaments Found</div>
            </div>
            <div className="summary-card">
              <div className="summary-value">
                {displayTournaments.length ? new Set(displayTournaments.map((t) => t.year)).size : 0}
              </div>
              <div className="summary-label">Years Covered</div>
            </div>
            <div className="summary-card">
              <div className="summary-value">
                {displayTournaments.length ? new Set(displayTournaments.map((t) => t.location)).size : 0}
              </div>
              <div className="summary-label">Locations</div>
            </div>
          </div>
        </div>

        {/* Tournaments List */}
        <div className="tournaments-section">
          {tournamentsLoading ? (
            <PageLoader />
          ) : displayTournaments && displayTournaments.length > 0 ? (
            <div className="tournaments-grid">
              {displayTournaments.map((tournament) => (
                <div
                  key={tournament.tournament_id}
                  className="tournament-card"
                  onClick={() => handleTournamentClick(tournament)}
                >
                  <div className="tournament-card-header">
                    <span className="text-gold">🏆</span>
                    <span className="tournament-year">{tournament.year}</span>
                  </div>
                  <h3 className="tournament-card-title">{tournament.name}</h3>
                  <p className="tournament-card-subtitle">{tournament.championship}</p>
                  <div className="tournament-card-footer">
                    {(() => {
                      if (tournament.association === 'Local') return null
                      const rc = resultsCounts?.[tournament.tournament_id] ?? 0
                      if (rc > 0) {
                        return (
                          <div className="footer-item">
                            <span className="px-2 py-1 rounded border text-xs border-emerald-500/40 text-emerald-300 bg-emerald-900/20">
                              {rc} {rc === 1 ? 'player' : 'players'}
                            </span>
                          </div>
                        )
                      }
                      return (
                        <div className="footer-item">
                          <span className="px-2 py-1 rounded border border-slate-600 text-slate-400 text-xs">
                            No results yet
                          </span>
                        </div>
                      )
                    })()}
                    <div className="footer-item">
                      {tournament.date && (
                        <>
                          📅
                          {formatLocalDate(String(tournament.date), {
                            month: 'short',
                            day: 'numeric',
                          })}
                        </>
                      )}
                    </div>
                    <div className="footer-item">
                      <span className={`association-badge ${(tournament.association || '').toLowerCase()}`}>
                        {tournament.association === 'HEYBALL' ? 'Heyball' : (tournament.association || '')}
                      </span>
                    </div>
                    <div className="footer-item">
                      <span className="text-xs text-slate-400 border border-slate-600 rounded px-2 py-0.5">
                        {inferGameType(tournament)}
                      </span>
                    </div>
                    {tournament.prize_pool && (
                      <div className="footer-item">
                        <span className="prize-pool-badge">
                          💰 {tournament.prize_pool}
                        </span>
                      </div>
                    )}
                    <div className="footer-item">
                      <span className="location-badge">
                        📍 {tournament.location}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <div className="text-4xl mb-4">🏆</div>
              <p className="text-gray-400">No tournaments found for the selected filters.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
