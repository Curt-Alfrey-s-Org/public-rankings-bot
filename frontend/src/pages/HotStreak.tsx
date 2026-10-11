import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LabelList,
} from 'recharts'
import { useTournamentsApi } from '@/contexts/ApiPathContext'
import PageLoader from '@/components/PageLoader'

const ASSOCIATION_TABS = [
  { id: 'wpba', label: 'WPBA', association: 'WPBA' },
  { id: 'wpa_women', label: 'WPA Women', association: 'WPA Women' },
  { id: 'wpa_men', label: 'WPA Men', association: 'WPA Men' },
  { id: 'heyball_men', label: 'Heyball Men', association: 'WPA Heyball Men' },
  { id: 'heyball_women', label: 'Heyball Women', association: 'WPA Heyball Women' },
  { id: 'artistic', label: 'Artistic', association: 'WPA Artistic' },
] as const

function formatResilienceScore(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—'
  return value.toFixed(1)
}

function PlacementChart({ placements }: { placements: number[] }) {
  const chartData = useMemo(
    () =>
      placements.map((placement, i) => ({
        index: i + 1,
        placement,
        label: `Tournament ${i + 1}`,
      })),
    [placements]
  )
  return (
    <ResponsiveContainer width={128} height={64} minWidth={128} minHeight={64}>
      <LineChart data={chartData} margin={{ top: 8, right: 4, left: -20, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
        <XAxis
          dataKey="index"
          tick={{ fill: '#94a3b8', fontSize: 10 }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          reversed
          domain={['dataMin - 1', 'dataMax + 1']}
          tick={{ fill: '#94a3b8', fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          width={24}
        />
        <Tooltip
          contentStyle={{
            background: 'rgba(30,41,59,0.95)',
            border: '1px solid rgba(148,163,184,0.3)',
            borderRadius: 8,
          }}
          labelStyle={{ color: '#e2e8f0' }}
          content={({ active, payload }) =>
            active && payload?.length ? (
              <div className="px-3 py-2 text-sm">
                <div className="text-slate-300">{payload[0].payload?.label}</div>
                <div className="text-white font-medium">Placement: {payload[0].value}</div>
              </div>
            ) : null
          }
        />
        <Line
          type="monotone"
          dataKey="placement"
          stroke="#f97316"
          strokeWidth={2}
          dot={{ fill: '#fb923c', r: 3 }}
          activeDot={{ r: 4 }}
        >
          <LabelList
            dataKey="placement"
            position="top"
            fill="#e2e8f0"
            fontSize={11}
            formatter={(v: number) => v}
          />
        </Line>
      </LineChart>
    </ResponsiveContainer>
  )
}

function FargoChart({
  history,
}: {
  history: Array<{ tournament: string; date: string; rating: number }>
}) {
  const chartData = useMemo(
    () =>
      history.map((item, i) => ({
        index: i + 1,
        rating: item.rating,
        label: item.tournament || `Tournament ${i + 1}`,
      })),
    [history]
  )
  return (
    <ResponsiveContainer width={128} height={64} minWidth={128} minHeight={64}>
      <LineChart data={chartData} margin={{ top: 8, right: 4, left: -20, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
        <XAxis dataKey="index" tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false} />
        <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false} width={30} />
        <Tooltip
          contentStyle={{
            background: 'rgba(30,41,59,0.95)',
            border: '1px solid rgba(148,163,184,0.3)',
            borderRadius: 8,
          }}
          labelStyle={{ color: '#e2e8f0' }}
          content={({ active, payload }) =>
            active && payload?.length ? (
              <div className="px-3 py-2 text-sm">
                <div className="text-slate-300">{payload[0].payload?.label}</div>
                <div className="text-white font-medium">Fargo: {payload[0].value}</div>
              </div>
            ) : null
          }
        />
        <Line
          type="monotone"
          dataKey="rating"
          stroke="#22d3ee"
          strokeWidth={2}
          dot={{ fill: '#67e8f9', r: 3 }}
          activeDot={{ r: 4 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

export default function HotStreak() {
  const tournamentsApi = useTournamentsApi()
  const [selectedTab, setSelectedTab] = useState<(typeof ASSOCIATION_TABS)[number]['id']>('wpba')
  const selectedAssociation = useMemo(
    () => ASSOCIATION_TABS.find((tab) => tab.id === selectedTab)?.association ?? 'WPBA',
    [selectedTab]
  )
  const {
    data: players = [],
    isLoading,
    isError: isRankError,
    error: rankError,
    refetch: refetchRank,
  } = useQuery({
    queryKey: ['hot_streak_players', 3, 3, selectedAssociation],
    queryFn: () =>
      tournamentsApi.getHotStreakPlayers({
        lookback: 3,
        min_tournaments: 3,
        association: selectedAssociation,
      }),
  })
  const {
    data: fargoPlayers = [],
    isLoading: isFargoLoading,
    isError: isFargoError,
    error: fargoError,
    refetch: refetchFargo,
  } = useQuery({
    queryKey: ['fargo_hot_streak_players', 3, 3, selectedAssociation],
    queryFn: () =>
      tournamentsApi.getFargoHotStreakPlayers({
        lookback: 3,
        min_tournaments: 3,
        association: selectedAssociation,
      }),
  })
  const latestFargoSnapshotDate = useMemo(() => {
    let latest: Date | null = null
    for (const player of fargoPlayers) {
      for (const point of player.fargo_history || []) {
        if (!point?.date) continue
        const d = new Date(point.date)
        if (Number.isNaN(d.getTime())) continue
        if (!latest || d > latest) latest = d
      }
    }
    return latest
  }, [fargoPlayers])
  if (isLoading || isFargoLoading) return <PageLoader />
  if (isRankError || isFargoError) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
        <div className="max-w-4xl mx-auto">
          <div className="rounded-lg border border-red-500/40 bg-red-900/20 p-5">
            <h2 className="text-xl font-semibold text-red-200 mb-2">Failed to load hot streak data</h2>
            <div className="text-sm text-red-pool_opt_in/90 space-y-1">
              {isRankError && (
                <p>
                  Rank hot streak error:{' '}
                  {rankError instanceof Error ? rankError.message : 'Unknown error'}
                </p>
              )}
              {isFargoError && (
                <p>
                  Fargo hot streak error:{' '}
                  {fargoError instanceof Error ? fargoError.message : 'Unknown error'}
                </p>
              )}
            </div>
            <div className="mt-4 flex gap-2">
              <button
                type="button"
                onClick={() => refetchRank()}
                className="px-3 py-1.5 rounded-md bg-red-700 text-white text-sm hover:bg-red-600"
              >
                Retry rank
              </button>
              <button
                type="button"
                onClick={() => refetchFargo()}
                className="px-3 py-1.5 rounded-md bg-red-700 text-white text-sm hover:bg-red-600"
              >
                Retry Fargo
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2">Hot Streak</h1>
          <p className="text-slate-400">
            Players who have moved up the most over their last few events. Rank streak looks at finishing places; Fargo streak looks at rating changes.
            &quot;Comeback&quot; scores show how often someone bounces back after a rough event (higher means stronger comebacks).
          </p>
        </div>

        <div className="mb-4 flex flex-wrap gap-2">
          {ASSOCIATION_TABS.map((tab) => {
            const isActive = selectedTab === tab.id
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setSelectedTab(tab.id)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium border transition-colors ${
                  isActive
                    ? 'bg-sky-500/20 border-sky-400/60 text-sky-300'
                    : 'bg-slate-800/60 border-slate-600 text-slate-300 hover:bg-slate-700/70'
                }`}
              >
                {tab.label}
              </button>
            )
          })}
        </div>

        <h2 className="text-xl font-semibold text-white mb-3">Rank Hot Streak</h2>
        {players.length > 0 ? (
          <div className="bg-slate-700 bg-opacity-50 rounded-lg border border-slate-600 overflow-hidden shadow-lg">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-slate-800 bg-opacity-80 border-b border-slate-600 sticky top-0">
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-300">Rank</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-300">Player</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-300">
                      Recent Placements
                    </th>
                    <th className="px-6 py-4 text-center text-sm font-semibold text-slate-300">Trend</th>
                    <th className="px-6 py-4 text-center text-sm font-semibold text-slate-300">
                      Comeback (1 yr)
                    </th>
                    <th className="px-6 py-4 text-center text-sm font-semibold text-slate-300">
                      Comeback (career)
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {players.map((player, index) => (
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
                              index === 0
                                ? 'bg-orange-500 text-white'
                                : index === 1
                                  ? 'bg-orange-400 text-slate-900'
                                  : index === 2
                                    ? 'bg-amber-600 text-white'
                                    : 'bg-slate-600 text-slate-300'
                            }`}
                          >
                            {index + 1}
                          </div>
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
                            </div>
                            <div className="text-xs text-slate-400 mt-1">
                              {player.recent_tournaments_count} tournaments
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        {player.last_placements.length >= 2 ? (
                          <div className="w-32 h-16 min-h-[64px] min-w-[128px] shrink-0">
                            <PlacementChart placements={player.last_placements} />
                          </div>
                        ) : (
                          <span className="text-slate-500 text-sm">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-center">
                        <div
                          className="inline-flex items-center gap-1 px-2 py-1 rounded text-sm font-semibold bg-orange-500 bg-opacity-20 text-orange-300"
                        >
                          +{Math.round(player.trend_score)} spots
                        </div>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <div className="inline-flex items-center gap-1 px-2 py-1 rounded text-sm font-semibold bg-emerald-500/20 text-emerald-300">
                          {formatResilienceScore(player.resilience_1yr)}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <div className="inline-flex items-center gap-1 px-2 py-1 rounded text-sm font-semibold bg-teal-500/20 text-teal-200">
                          {formatResilienceScore(player.resilience_career)}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="bg-slate-700 bg-opacity-50 rounded-lg border border-slate-600 overflow-hidden shadow-lg">
            <div className="p-12 text-center border-b border-slate-600">
              <h3 className="text-lg font-semibold text-slate-300 mb-2">No Players Jumped</h3>
              <p className="text-slate-400">
                No one in this category had a clear climb over their last three events. Try another tab, or check back after more tournaments finish.
              </p>
            </div>
          </div>
        )}

        <h2 className="text-xl font-semibold text-white mt-8 mb-1">Fargo Hot Streak</h2>
        <p className="text-xs text-slate-400 mb-3">
          Fargo ratings as of:{' '}
          {latestFargoSnapshotDate
            ? latestFargoSnapshotDate.toLocaleDateString()
            : 'not available yet'}
        </p>
        {fargoPlayers.length > 0 ? (
          <div className="bg-slate-700 bg-opacity-50 rounded-lg border border-slate-600 overflow-hidden shadow-lg">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-slate-800 bg-opacity-80 border-b border-slate-600 sticky top-0">
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-300">Rank</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-300">Player</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-300">Recent Fargo</th>
                    <th className="px-6 py-4 text-center text-sm font-semibold text-slate-300">Trend</th>
                    <th className="px-6 py-4 text-center text-sm font-semibold text-slate-300">Current Fargo</th>
                  </tr>
                </thead>
                <tbody>
                  {fargoPlayers.map((player, index) => (
                    <tr
                      key={`fargo-${player.player_id}`}
                      className={`border-b border-slate-600 transition-colors ${
                        index % 2 === 0 ? 'bg-slate-700 bg-opacity-30' : 'bg-slate-600 bg-opacity-20'
                      } hover:bg-slate-600 hover:bg-opacity-40`}
                    >
                      <td className="px-6 py-4 text-white">{index + 1}</td>
                      <td className="px-6 py-4 text-white font-medium">
                        {player.first_name} {player.last_name}
                      </td>
                      <td className="px-6 py-4">
                        {player.fargo_history && player.fargo_history.length >= 2 ? (
                          <div className="w-32 h-16 min-h-[64px] min-w-[128px] shrink-0">
                            <FargoChart history={player.fargo_history} />
                          </div>
                        ) : (
                          <span className="text-slate-500 text-sm">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-center">
                        <div className="inline-flex items-center gap-1 px-2 py-1 rounded text-sm font-semibold bg-cyan-500 bg-opacity-20 text-cyan-300">
                          +{Math.round(player.fargo_trend_score ?? 0)}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span className="text-white font-bold">{player.fargo_score != null ? player.fargo_score : '—'}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="bg-slate-700 bg-opacity-50 rounded-lg border border-slate-600 overflow-hidden shadow-lg">
            <div className="p-12 text-center border-b border-slate-600">
              <h3 className="text-lg font-semibold text-slate-300 mb-2">No Fargo Hot Streak</h3>
              <p className="text-slate-400">
                No Fargo rating gains stood out for this category over the last three snapshots.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
