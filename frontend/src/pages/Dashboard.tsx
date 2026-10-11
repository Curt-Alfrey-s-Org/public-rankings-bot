/**
 * Home Page (Dashboard)
 * Global metrics + upcoming events + personal snapshot + Fargo disambiguation.
 */

import { useMemo, useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { tournamentHistoryApi } from '@/api/tournamentHistory'
import { fargoApi, type FargoPlayer } from '@/api/fargo'
import TournamentCard from '@/components/TournamentCard'
import DataCard from '@/components/DataCard'
import TournamentActivityHeatmap from '@/components/TournamentActivityHeatmap'
import DraggableDashboard from '@/components/DraggableDashboard'
import { useBotStatus } from '@/hooks/useBotStatus'
import { useMemo } from 'react'
import { useAuth } from '@/contexts/AuthContext'

type TournamentStatus = 'upcoming' | 'in-progress' | 'completed' | 'cancelled'

export default function Dashboard({ sidebarOpen = true, onSidebarToggle }: DashboardProps) {
  // Invalidate stats/trades when WebSocket sends stats or trade so numbers and curves update
  useRealtimeStats()
  const { data: botStatus } = useBotStatus()
  const { user } = useAuth()
  const isSuperAdmin = user?.role === 'super_admin'

  const pageKey = 'dashboard'
  const layout = (uiEditing ? uiDraft.layouts[pageKey] : uiData.layouts[pageKey]) ?? []

  const currentPlayerName = (user?.user ?? '').trim()
  const authHeaders = useMemo((): HeadersInit | undefined => {
    let token = user?.token
      || localStorage.getItem('access_token')
      || localStorage.getItem('auth_token')
    if (!token) {
      try {
        const raw = localStorage.getItem('rankings_bot_auth')
        if (raw) {
          const parsed = JSON.parse(raw)
          token = parsed?.token
        }
      } catch (error) {
        console.warn('Failed to parse rankings_bot_auth in Dashboard auth headers:', error)
        token = undefined
      }
    }
    return token ? { Authorization: `Bearer ${token}` } : undefined
  }, [user?.token])
  const hasAuth = !!authHeaders?.Authorization

  const { data: myPlayerInfo } = useQuery({
    queryKey: ['player-performance-me'],
    queryFn: async () => {
      const response = await fetch('/api/player-performance/me', { headers: authHeaders })
      if (!response.ok) {
        return { player_name: currentPlayerName, source: 'username' }
      }
      return response.json()
    },
    enabled: !!currentPlayerName && hasAuth,
    retry: 1,
    staleTime: 120_000,
  })

  const effectivePlayerName = (myPlayerInfo?.player_name ?? currentPlayerName).trim()

  const searchFargoMutation = useMutation({
    mutationFn: async (name: string) => {
      return await fargoApi.searchPlayers(name)
    },
    onSuccess: (players) => {
      if (players.length === 0) {
        toast.error('No Fargo players found')
      } else if (players.length === 1) {
        // Only one match - could auto-save or still show modal for confirmation
        setFargoSearchResults(players)
        setShowDisambiguationModal(true)
      } else {
        // Multiple matches - show disambiguation modal
        setFargoSearchResults(players)
        setShowDisambiguationModal(true)
      }
    },
    onError: (error) => {
      const errMsg = error instanceof Error ? error.message : 'Failed to search Fargo players'
      toast.error(errMsg)
    },
  })

  const handleLinkFargoPlayer = () => {
    const searchName = effectivePlayerName || currentPlayerName
    if (!searchName) {
      toast.error('No player name available')
      return
    }
    searchFargoMutation.mutate(searchName)
  }

  const { data: upcomingEvents } = useQuery({
    queryKey: ['dashboard-upcoming-events'],
    queryFn: async () => {
      const response = await tournamentHistoryApi.getUpcomingEvents(undefined, 50)
      return response?.events ?? []
    },
    retry: 1,
    staleTime: 300_000,
  })

  const { data: myOverview, isLoading: myOverviewLoading, error: myOverviewError } = useQuery({
    queryKey: ['dashboard-my-overview', effectivePlayerName],
    queryFn: async () => {
      const response = await fetch(`/api/player-performance/${encodeURIComponent(effectivePlayerName)}/overview`, { headers: authHeaders })
      if (!response.ok) {
        const text = await response.text()
        throw new Error(text || 'Failed to load player overview')
      }
      return response.json()
    },
    enabled: !!effectivePlayerName && hasAuth,
    retry: 1,
    staleTime: 120_000,
  })

  const { data: myTournaments } = useQuery({
    queryKey: ['dashboard-my-tournaments', effectivePlayerName],
    queryFn: async () => {
      const response = await fetch(`/api/player-performance/${encodeURIComponent(effectivePlayerName)}/tournaments?limit=5`, { headers: authHeaders })
      if (!response.ok) {
        return { tournaments: [] }
      }
      return response.json()
    },
    enabled: !!effectivePlayerName && hasAuth,
    retry: 1,
    staleTime: 120_000,
  })

  const tournamentHeatmapData = ((): Array<{ month: number; week: number; count: number }> => {
    const bucket = new Map<string, { month: number; week: number; count: number }>()
    const today = new Date()
    for (const event of upcomingEvents ?? []) {
      const date = event.date ? new Date(event.date) : null
      if (!date || isNaN(date.getTime()) || date < today) continue
      const month = date.getMonth() + 1
      const day = date.getDate()
      const week = Math.min(4, Math.max(1, Math.ceil(day / 7)))
      const key = `${month}-${week}`
      const current = bucket.get(key)
      if (current) {
        current.count += 1
      } else {
        bucket.set(key, { month, week, count: 1 })
      }
    }
    return Array.from(bucket.values())
  })()

  const tournamentCards = (upcomingEvents ?? []).slice(0, 6).map((event, index) => ({
    id: String(event.event_id ?? event.id ?? `${event.name}-${index}`),
    name: event.name,
    date: event.date ?? 'TBD',
    playerCount: 0,
    trophyCount: 1,
    status: 'upcoming' as TournamentStatus,
    location: event.location ?? undefined,
    format: event.association,
  }))

  const handleNavigateTournament = (_tournament: { id: string }) => {
    navigate('/future-tournaments')
  }

  const handleLayoutChange = (nextLayout: string[]) => {
    if (uiEditing) {
      setDraftLayout(pageKey, nextLayout)
    }
  }

  const dashboardWidgets = [
    {
      id: 'tournaments',
      title: 'Featured Tournaments',
      defaultOrder: 1,
      component: (
        <section className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Calendar className="w-6 h-6 text-sky-500" />
              <h2 className="text-2xl font-bold text-white">
                <EditableText
                  textKey="dashboard.section.tournaments.title"
                  defaultText="Featured Tournaments"
                  className="block"
                  inputClassName="bg-transparent border border-sky-500/40 rounded px-1 py-0.5 text-inherit"
                />
              </h2>
            </div>
            <EditableButton
              buttonKey="dashboard.tournaments.view_all"
              defaultLabel="View All"
              onClick={() => navigate('/future-tournaments')}
              className="flex items-center gap-2 px-4 py-2 bg-sky-500/20 text-sky-300 border border-sky-500/30 rounded-lg hover:bg-sky-500/30 transition-colors text-sm font-medium"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {tournamentCards.length > 0 ? (
              tournamentCards.map((tournament) => (
                <TournamentCard
                  key={tournament.id}
                  tournament={tournament}
                  onClick={handleNavigateTournament}
                />
              ))
            ) : (
              <div className="col-span-full text-center py-8 text-slate-400">
                <p>No tournament data available</p>
              </div>
            )}
          </div>
        </section>
      ),
    },
    {
      id: 'events-activity',
      title: 'Events & Calendar',
      defaultOrder: 2,
      component: (
        <section className="space-y-6">
          <div className="flex items-center gap-3">
            <Users className="w-6 h-6 text-sky-500" />
            <h2 className="text-2xl font-bold text-white">
              <EditableText
                textKey="dashboard.section.events.title"
                defaultText="Events & Calendar"
                className="block"
                inputClassName="bg-transparent border border-sky-500/40 rounded px-1 py-0.5 text-inherit"
              />
            </h2>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <DataCard
              header={(
                <EditableText
                  textKey="dashboard.events.upcoming.title"
                  defaultText="Upcoming Events"
                  className="text-sm sm:text-base font-semibold text-white truncate"
                  inputClassName="bg-transparent border border-sky-500/40 rounded px-1 py-0.5 text-inherit"
                />
              )}
              className="lg:col-span-1"
            >
              <div className="space-y-3">
                {(upcomingEvents ?? []).length > 0 ? (
                  upcomingEvents?.slice(0, 6).map((event) => (
                    <div key={`${event.name}-${event.date}`} className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-white">{event.name}</p>
                        <p className="text-xs text-slate-400">{event.location ?? 'Location TBD'}</p>
                      </div>
                      <span className="text-xs text-slate-300">
                        {event.date ? new Date(event.date).toLocaleDateString() : 'TBD'}
                      </span>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-400">No upcoming events found.</p>
                )}
              </div>
            </DataCard>

            <div className="lg:col-span-2">
              <TournamentActivityHeatmap
                data={tournamentHeatmapData}
                title={(
                  <EditableText
                    textKey="dashboard.events.heatmap.title"
                    defaultText="Upcoming Tournament Activity"
                    className="text-lg font-semibold text-white"
                    inputClassName="bg-transparent border border-sky-500/40 rounded px-1 py-0.5 text-inherit"
                  />
                )}
                titleText="Upcoming Tournament Activity"
                height={240}
              />
            </div>
          </div>
        </section>
      ),
    },
    {
      id: 'my-stats',
      title: 'My Stats',
      defaultOrder: 3,
      component: (
        <section className="space-y-6">
          <h2 className="text-2xl font-bold text-white">
            <EditableText
              textKey="dashboard.section.my_stats.title"
              defaultText="My Stats"
              className="block"
              inputClassName="bg-transparent border border-sky-500/40 rounded px-1 py-0.5 text-inherit"
            />
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <DataCard
              header={(
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm sm:text-base font-semibold text-white">My Ranking Snapshot</span>
                  {currentPlayerName && isAdmin && (
                    <button
                      type="button"
                      onClick={handleLinkFargoPlayer}
                      disabled={searchFargoMutation.isPending}
                      className="flex items-center gap-1.5 px-2 py-1 text-xs font-medium rounded bg-sky-600 hover:bg-sky-500 text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      title="Admin only: Link a user's account to the correct Fargo player"
                    >
                      <LinkIcon className="w-3 h-3" />
                      {searchFargoMutation.isPending ? 'Searching...' : 'Link Fargo'}
                    </button>
                  )}
                </div>
              )}
              className="lg:col-span-2"
            >
              {!effectivePlayerName ? (
                <p className="text-sm text-slate-400">Sign in to view your personal ranking snapshot.</p>
              ) : myOverviewLoading ? (
                <p className="text-sm text-slate-400">Loading your stats…</p>
              ) : myOverviewError ? (
                <p className="text-sm text-amber-400">Could not load your stats yet. Try again in a moment.</p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {['wpba', 'wpa_women', 'wpa_men'].map((key) => {
                    const labelMap: Record<string, string> = {
                      wpba: 'WPBA Women',
                      wpa_women: 'WPA Women',
                      wpa_men: 'WPA Men',
                    }
                    const data = (myOverview as any)?.[key]
                    return (
                      <div key={key} className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
                        <p className="text-xs text-slate-400">{labelMap[key]}</p>
                        {data ? (
                          <div className="space-y-1 mt-2">
                            <p className="text-lg font-semibold text-white">#{data.rank ?? '—'}</p>
                            <p className="text-xs text-slate-300">Points: {data.rating ?? data.points ?? '—'}</p>
                            <p className="text-xs text-slate-300">Fargo: {data.fargo_rating ?? '—'}</p>
                          </div>
                        ) : (
                          <p className="text-xs text-slate-500 mt-2">No record</p>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </DataCard>
            <DataCard
              header={(
                <span className="text-sm sm:text-base font-semibold text-white">My Recent Tournaments</span>
              )}
            >
              {(myTournaments?.tournaments ?? []).length > 0 ? (
                <div className="space-y-3">
                  {myTournaments?.tournaments?.slice(0, 4).map((t: any) => (
                    <div key={`${t.tournament_name}-${t.start_date}`} className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-white">{t.tournament_name}</p>
                        <p className="text-xs text-slate-400">{t.association ?? '—'} • {t.location ?? '—'}</p>
                      </div>
                      <span className="text-xs text-slate-300">#{t.placement ?? '—'}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-400">No recent tournament results found.</p>
              )}
              <button
                type="button"
                onClick={() => navigate('/player-performance')}
                className="mt-4 w-full px-4 py-2 text-xs font-semibold rounded-lg border border-slate-700 text-slate-200 hover:bg-slate-800 transition-colors"
              >
                View full player performance
              </button>
            </DataCard>
          </div>
        </section>
      ),
    },

  ]

  const fullWidthIds = dashboardWidgets.map((widget) => widget.id)

  return (
    <div className="flex flex-col h-screen bg-black/90 text-foreground overflow-hidden">
      {/* Header */}
      <header className="bg-card/50 backdrop-blur-sm border-b border-border px-4 sm:px-6 py-4 flex items-center justify-between flex-shrink-0 z-10">
        <div className="flex items-center gap-4">
          {onSidebarToggle && (
            <button
              onClick={onSidebarToggle}
              className="p-2 hover:bg-accent rounded-lg transition-colors flex-shrink-0"
              aria-label="Toggle menu"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          )}
        </div>
        <div className="flex items-center gap-3 sm:gap-4 flex-shrink-0">
          <ConnectionStatus />
          <BotControls />
        </div>
      </header>

      {/* Dashboard Content */}
      <main className="flex-1 overflow-y-auto overflow-x-hidden">
        <div className="w-full p-4 sm:p-6 md:p-8">
          <div className="max-w-screen-2xl mx-auto">
            <StatusBanner />
            <div className="mb-6 sm:mb-8">
              <h1 className="text-2xl sm:text-3xl font-bold mb-2">Dashboard</h1>
              <p className="text-xs sm:text-sm text-muted-foreground">
                {isSuperAdmin
                  ? 'Hover over any widget to see the drag handle, then drag to rearrange. Your layout is saved automatically.'
                  : 'Dashboard widgets are in a fixed layout. Contact super admin to customize.'}
              </p>
            </div>
            <DraggableDashboard widgets={widgets} isDraggable={isSuperAdmin} />
          </div>

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12 space-y-12">
          <DraggableDashboard
            widgets={dashboardWidgets}
            layout={layout}
            onLayoutChange={handleLayoutChange}
            isDraggable={uiEditing}
            fullWidthIds={fullWidthIds}
          />
        </div>
        </div>
      </main>

      {/* Fargo Player Disambiguation Modal */}
      <PlayerDisambiguationModal
        isOpen={showDisambiguationModal}
        onClose={() => setShowDisambiguationModal(false)}
        players={fargoSearchResults}
        searchName={effectivePlayerName || currentPlayerName}
        username={currentPlayerName}
        onSelection={(player) => {
          toast.success(`Linked to Fargo player: ${player.name} (${player.rating})`)
          setShowDisambiguationModal(false)
        }}
      />
    </div>
  )
}
