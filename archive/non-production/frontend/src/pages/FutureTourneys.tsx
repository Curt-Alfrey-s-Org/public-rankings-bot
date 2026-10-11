/**
 * Future Tournaments: WPA and WPBA events (scraped) plus upcoming tournaments in the system.
 * Same data as Home tab with full details.
 */

import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { eventsApi, type FutureEvent } from '@/api/events'
import { tournamentsApi, type Tournament } from '@/api/tournaments'

function formatEventDateRange(start: string, end: string): string {
  const s = new Date(start)
  const e = new Date(end)
  if (Number.isNaN(s.getTime()) || Number.isNaN(e.getTime())) {
    return start
  }
  if (start === end) {
    return s.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })
  }
  return `${s.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })} – ${e.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`
}

function formatDate(s: string): string {
  const date = new Date(s)
  if (Number.isNaN(date.getTime())) {
    return s
  }
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

function isUpcoming(t: Tournament): boolean {
  const status = t.status?.toLowerCase()
  if (status === 'cancelled' || status === 'completed') return false
  const d = new Date(t.tournament_date)
  if (Number.isNaN(d.getTime())) {
    return true
  }
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  d.setHours(0, 0, 0, 0)
  return d >= today
}

export default function FutureTourneys() {
  const { data: events = [], isLoading: eventsLoading, error: eventsError, refetch: refetchEvents, isFetching } = useQuery({
    queryKey: ['events', 'future'],
    queryFn: () => eventsApi.getFutureEvents(100, { skip_cache: true }).then((r) => r.events),
    staleTime: 300_000,
  })

  const { data: tournaments = [], isLoading: tournamentsLoading } = useQuery({
    queryKey: ['tournaments'],
    queryFn: () => tournamentsApi.getTournaments(),
    staleTime: 60_000,
  })

  const upcoming = tournaments
    .filter(isUpcoming)
    .sort((a, b) => new Date(a.tournament_date).getTime() - new Date(b.tournament_date).getTime())

  const bySource = (source: string) => events.filter((e: FutureEvent) => e.source === source)
  const wpba = bySource('WPBA')
  const wpaMen = bySource('WPA Men')
  const wpaWomen = bySource('WPA Women')

  return (
    <div className="p-6 md:p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold text-white mb-2">Future Tournaments</h1>
      <p className="text-slate-400 text-sm mb-8">
        Upcoming events from WPA and WPBA websites plus tournaments in the system. Full details and links below.
      </p>

      <section className="mb-10">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
          <div>
            <h2 className="text-xl font-semibold text-white flex items-center gap-2">
              <span>🌐</span> Future Tournaments (WPA &amp; WPBA)
            </h2>
            <p className="text-slate-400 text-sm mt-1">
              Upcoming events from WPA and WPBA websites. Click any event for full details on the official site.
            </p>
          </div>
          <button
            type="button"
            onClick={() => refetchEvents()}
            disabled={isFetching}
            className="px-4 py-2 rounded-lg border border-slate-600 bg-slate-800/60 text-slate-200 text-sm font-medium hover:bg-slate-700/80 disabled:opacity-50 flex items-center gap-2"
          >
            {isFetching ? <span className="animate-spin">⟳</span> : null}
            Refresh events
          </button>
        </div>
        {eventsLoading && <p className="text-slate-400">Loading…</p>}
        {eventsError && (
          <div className="space-y-2">
            <p className="text-amber-400">Could not load events. Sites may have changed or be temporarily unavailable.</p>
            <button
              type="button"
              onClick={() => refetchEvents()}
              className="px-3 py-2 rounded-lg bg-amber-900/30 text-amber-200 text-sm hover:bg-amber-900/50"
            >
              Retry
            </button>
          </div>
        )}
        {!eventsLoading && !eventsError && events.length === 0 && (
          <p className="text-slate-400">No future events available from WPA or WPBA websites.</p>
        )}
        {!eventsLoading && events.length > 0 && (
          <div className="space-y-8">
            {wpba.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                  <span>🏆</span> WPBA
                </h3>
                <ul className="space-y-3">
                  {wpba.map((ev, idx) => (
                    <EventCard key={`wpba-${idx}-${ev.url}`} event={ev} />
                  ))}
                </ul>
              </div>
            )}
            {wpaWomen.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                  <span>🌐</span> WPA Women
                </h3>
                <ul className="space-y-3">
                  {wpaWomen.map((ev, idx) => (
                    <EventCard key={`wpa-w-${idx}-${ev.url}`} event={ev} />
                  ))}
                </ul>
              </div>
            )}
            {wpaMen.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                  <span>🌐</span> WPA Men
                </h3>
                <ul className="space-y-3">
                  {wpaMen.map((ev, idx) => (
                    <EventCard key={`wpa-m-${idx}-${ev.url}`} event={ev} />
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </section>

      <section>
        <h2 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
          <span>📅</span> Upcoming tournaments (in system)
        </h2>
        <p className="text-slate-400 text-sm mb-4">
          Tournaments you&apos;ve created that are not yet completed. Open bracket to manage matches.
        </p>
        {tournamentsLoading ? (
          <p className="text-slate-400">Loading…</p>
        ) : upcoming.length === 0 ? (
          <p className="text-slate-400">
            No upcoming tournaments in the system. Create one from{' '}
            <Link to="/tournaments/new" className="text-primary hover:underline">
              Tournaments → New Tournament
            </Link>
            .
          </p>
        ) : (
          <ul className="space-y-3">
            {upcoming.map((t) => (
              <li key={t.tournament_id}>
                <Link
                  to="/tournaments/bracket"
                  className="flex flex-wrap items-center gap-x-4 gap-y-1 p-4 rounded-xl bg-slate-800/60 border border-slate-700 hover:border-slate-500 hover:bg-slate-800/80 transition-colors"
                >
                  <span className="font-medium text-white">{t.tournament_name}</span>
                  <span className="text-sm text-slate-400">{formatDate(t.tournament_date)}</span>
                  {t.location && (
                    <span className="text-sm text-slate-500">📍 {t.location}</span>
                  )}
                  <span className="text-sm text-slate-400">
                    👥 {t.actual_players} / {t.max_players} players
                  </span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${
                      t.status === 'registration'
                        ? 'bg-amber-500/20 text-amber-200'
                        : t.status === 'in_progress'
                          ? 'bg-green-500/20 text-green-200'
                          : 'bg-slate-600 text-slate-300'
                    }`}
                  >
                    {t.status?.replace('_', ' ') ?? '—'}
                  </span>
                  <span className="text-slate-500 ml-auto" aria-hidden>View bracket ↗</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-sm text-slate-500">
          <Link to="/tournaments" className="text-primary hover:underline">
            Tournaments
          </Link>
          {' '}→ History, New Tournament, Bracket, Leaderboard
        </p>
      </section>
    </div>
  )
}

function EventCard({ event }: { event: FutureEvent }) {
  return (
    <li>
      <a
        href={event.url}
        target="_blank"
        rel="noopener noreferrer"
        className="block p-4 rounded-xl bg-slate-800/60 border border-slate-700 hover:border-slate-500 hover:bg-slate-800/80 transition-colors"
      >
        <div className="font-semibold text-white mb-1">{event.name}</div>
        <div className="text-sm text-slate-400 mb-1">
          {formatEventDateRange(event.start_date, event.end_date)}
        </div>
        {event.location && (
          <div className="text-sm text-slate-500 mb-1">📍 {event.location}</div>
        )}
        <div className="flex items-center gap-2 mt-2">
          <span className="text-xs px-2 py-0.5 rounded bg-slate-600 text-slate-300">{event.source}</span>
          <span className="text-xs text-primary">Open on official site ↗</span>
        </div>
      </a>
    </li>
  )
}
