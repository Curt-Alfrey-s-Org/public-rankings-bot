/**
 * Future Tournaments Page
 * Displays upcoming events scraped from WPBA and WPA.
 * Admin can refresh to scrape latest events.
 */

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { tournamentHistoryApi, type UpcomingEvent } from '@/api/tournamentHistory'
import { useAuth } from '@/contexts/AuthContext'
import { upcomingEventKey } from '@/lib/upcomingEventPrefill'
import PageLoader from '@/components/PageLoader'
import './FutureTournaments.css'

type FutureView = 'menu' | 'list'
type DrillLevel = 'top' | 'wpa' | 'heyball'
type AssociationLeaf =
  | 'WPBA'
  | 'WPA Men'
  | 'WPA Women'
  | 'WPA Mixed'
  | 'Heyball Men'
  | 'Heyball Women'
  | 'Artistic'
type UpcomingEventExtended = UpcomingEvent & {
  start_date?: string | null
  end_date?: string | null
  venue_address?: string | null
  prize_pool?: string | null
  format?: string | null
  bracket_url?: string | null
  registration_url?: string | null
}

type DrillItem =
  | { kind: 'drill'; id: DrillLevel; label: string; style: 'wpba' | 'wpa' | 'heyball' | 'artistic' }
  | { kind: 'leaf'; association: AssociationLeaf; label: string; style: 'wpba' | 'wpa' | 'heyball' | 'artistic' }

function parseEventDate(value?: string | null): Date | null {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  date.setHours(0, 0, 0, 0)
  return date
}

function isFutureEvent(evt: UpcomingEventExtended): boolean {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const date = parseEventDate(evt.start_date) ?? parseEventDate(evt.date)
  if (!date) return false
  return date >= today
}

function classifyEvent(evt: UpcomingEventExtended): AssociationLeaf | null {
  const assoc = (evt.association || '').toUpperCase()
  const name = (evt.name || '').toUpperCase()
  const text = `${assoc} ${name}`
  const hasWpba = text.includes('WPBA')
  const hasWpaWord = /\bWPA\b/.test(text)
  const isMixedTeamTitle =
    name.includes('MIXED') ||
    name.includes(' TEAM ') ||
    name.includes(' TEAMS ') ||
    name.includes('DOUBLES') ||
    name.includes('SCOTCH')

  // Trust explicit association first.
  if (assoc.includes('WPBA') || hasWpba) {
    return 'WPBA'
  }
  if (assoc.includes('WPA ARTISTIC')) {
    return 'Artistic'
  }
  if (assoc.includes('WPA HEYBALL')) {
    if (assoc.includes('WOMEN')) return 'Heyball Women'
    return 'Heyball Men'
  }
  if (assoc.includes('WPA WOMEN')) {
    return 'WPA Women'
  }
  if (isMixedTeamTitle) {
    return 'WPA Mixed'
  }
  if (assoc.includes('WPA MEN')) {
    return 'WPA Men'
  }
  // Infer from event naming when association field is not specific enough.
  if (text.includes('ARTISTIC')) {
    return 'Artistic'
  }

  if (text.includes('HEYBALL')) {
    if (text.includes('WOMEN') || text.includes('LADIES') || text.includes('WOMAN')) {
      return 'Heyball Women'
    }
    return 'Heyball Men'
  }

  if (hasWpaWord) {
    if (text.includes('WOMEN') || text.includes('LADIES') || text.includes('WOMAN')) {
      return 'WPA Women'
    }
    // Mixed means true mixed/team events only.
    if (
      text.includes('MIXED') ||
      text.includes('TEAM') ||
      text.includes('TEAMS') ||
      text.includes('DOUBLES') ||
      text.includes('SCOTCH')
    ) {
      return 'WPA Mixed'
    }
    if (text.includes('MEN') || text.includes('MAN')) {
      return 'WPA Men'
    }
    // Default uncategorized WPA events to Men bucket (not Mixed).
    return 'WPA Men'
  }

  if (text.includes('WOMEN') || text.includes('LADIES') || text.includes('WOMAN')) {
    return 'WPA Women'
  }
  if (text.includes('MEN') || text.includes('MAN')) {
    return 'WPA Men'
  }
  return null
}

function MenuOptionButton({ item, onClick }: { item: DrillItem; onClick: () => void }) {
  const style = item.style
  const base = 'rounded-xl py-3 sm:py-4 px-3 sm:px-4 min-h-[48px] sm:min-h-[56px] font-bold text-sm sm:text-base lg:text-lg transition-all shadow-md w-full sm:w-auto'
  const wpba = 'bg-slate-700/50 border-2 border-felt/30 text-white hover:border-felt/60 hover:bg-slate-600/50'
  const wpa = 'bg-slate-700/50 border-2 border-felt/30 text-white hover:border-felt/60 hover:bg-slate-600/50'
  const heyball = 'bg-slate-700/50 border-2 border-purple-400/30 text-white hover:border-purple-400/60 hover:bg-slate-600/50'
  const artistic = 'bg-slate-700/50 border-2 border-amber-400/30 text-white hover:border-amber-400/60 hover:bg-slate-600/50'
  const cn = style === 'wpa' ? wpa : style === 'heyball' ? heyball : style === 'artistic' ? artistic : wpba
  return (
    <button type="button" onClick={onClick} className={`${base} ${cn}`}>
      {item.label}
    </button>
  )
}

export default function FutureTournaments() {
  const { isDirector, isAdmin, isSuperAdmin } = useAuth()
  const canCreateTournament = isDirector || isAdmin || isSuperAdmin
  const [viewMode, setViewMode] = useState<FutureView>('menu')
  const [navStack, setNavStack] = useState<DrillLevel[]>(['top'])
  const [selectedAssociation, setSelectedAssociation] = useState<AssociationLeaf | null>(null)

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['future-tournaments'],
    queryFn: () => tournamentHistoryApi.getUpcomingEvents(undefined, 500),
  })

  const events = ((data?.events ?? []) as UpcomingEventExtended[]).filter(isFutureEvent)

  const groupedEvents = useMemo<Record<AssociationLeaf, UpcomingEventExtended[]>>(() => {
    return events.reduce<Record<AssociationLeaf, UpcomingEventExtended[]>>((acc, evt) => {
      const key = classifyEvent(evt)
      if (key) {
        acc[key].push(evt)
      }
      return acc
    }, {
      WPBA: [],
      'WPA Men': [],
      'WPA Women': [],
      'WPA Mixed': [],
      'Heyball Men': [],
      'Heyball Women': [],
      Artistic: [],
    } as Record<AssociationLeaf, UpcomingEventExtended[]>)
  }, [events])

  const wpbaEvents = groupedEvents.WPBA
  const wpaMenEvents = groupedEvents['WPA Men']
  const wpaWomenEvents = groupedEvents['WPA Women']
  const wpaMixedEvents = groupedEvents['WPA Mixed']
  const heyballMenEvents = groupedEvents['Heyball Men']
  const heyballWomenEvents = groupedEvents['Heyball Women']
  const artisticEvents = groupedEvents.Artistic

  const visibleEvents =
    selectedAssociation === 'WPBA'
      ? wpbaEvents
      : selectedAssociation === 'WPA Men'
        ? wpaMenEvents
        : selectedAssociation === 'WPA Women'
          ? wpaWomenEvents
          : selectedAssociation === 'WPA Mixed'
            ? wpaMixedEvents
            : selectedAssociation === 'Heyball Men'
              ? heyballMenEvents
              : selectedAssociation === 'Heyball Women'
                ? heyballWomenEvents
                : selectedAssociation === 'Artistic'
                  ? artisticEvents
          : []

  const topMenuItems: DrillItem[] = [
    { kind: 'leaf', association: 'WPBA', label: `👑 WPBA (${wpbaEvents.length})`, style: 'wpba' },
    { kind: 'drill', id: 'wpa', label: `🌍 WPA (${wpaMenEvents.length + wpaWomenEvents.length + wpaMixedEvents.length})`, style: 'wpa' },
    { kind: 'drill', id: 'heyball', label: `🎯 Heyball (${heyballMenEvents.length + heyballWomenEvents.length})`, style: 'heyball' },
    { kind: 'leaf', association: 'Artistic', label: `🎨 Artistic (${artisticEvents.length})`, style: 'artistic' },
  ]
  const wpaMenuItems: DrillItem[] = [
    { kind: 'leaf', association: 'WPA Women', label: `🌍 WPA Women (${wpaWomenEvents.length})`, style: 'wpa' },
    { kind: 'leaf', association: 'WPA Men', label: `🎱 WPA Men (${wpaMenEvents.length})`, style: 'wpa' },
    { kind: 'leaf', association: 'WPA Mixed', label: `🤝 WPA Mixed (${wpaMixedEvents.length})`, style: 'wpa' },
  ]
  const heyballMenuItems: DrillItem[] = [
    { kind: 'leaf', association: 'Heyball Women', label: `🎯 Heyball Women (${heyballWomenEvents.length})`, style: 'heyball' },
    { kind: 'leaf', association: 'Heyball Men', label: `🎱 Heyball Men (${heyballMenEvents.length})`, style: 'heyball' },
  ]

  const currentLevel = navStack[navStack.length - 1]
  const menuItems = currentLevel === 'top' ? topMenuItems : currentLevel === 'wpa' ? wpaMenuItems : heyballMenuItems

  const handleMenuAction = (item: DrillItem) => {
    if (item.kind === 'drill') {
      setNavStack((prev) => [...prev, item.id])
      return
    }
    setSelectedAssociation(item.association)
    setViewMode('list')
  }

  const handleBack = () => {
    if (viewMode === 'list') {
      setViewMode('menu')
      setSelectedAssociation(null)
      return
    }
    if (navStack.length > 1) {
      setNavStack((prev) => prev.slice(0, -1))
    }
  }

  return (
    <div className="future-tournaments-page">
      <div className="container mx-auto px-4 py-8">
        <div className="hero-section mb-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="text-4xl md:text-5xl font-bold text-white mb-4">
                Future tournaments
              </h1>
              <p className="text-purple-300 text-lg">
                Upcoming WPBA and WPA events in one place. Directors can start a local event from{' '}
                <strong>New Tournament</strong> when you&apos;re ready to run your own.
              </p>
            </div>
          </div>
        </div>

        <section
          className="rounded-2xl border-2 border-felt/30 backdrop-blur-sm p-4 sm:p-6 md:p-8 shadow-xl bg-gradient-to-br from-slate-900 to-slate-800 mb-6"
          aria-label={viewMode === 'list' ? 'Current future tournaments filter' : 'Choose association'}
        >
          <div className="flex items-center gap-3 mb-4">
            {(viewMode === 'list' || navStack.length > 1) && (
              <button
                type="button"
                onClick={handleBack}
                className="flex items-center gap-2 rounded-xl py-2.5 px-3 sm:px-4 min-h-[44px] font-semibold text-sm sm:text-base bg-slate-700/60 hover:bg-slate-600/60 text-white border border-slate-500/50 transition-colors"
                aria-label="Back"
              >
                <svg className="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
                <span className="hidden sm:inline">Back</span>
              </button>
            )}
            {viewMode === 'menu' ? (
              <h2 className="text-lg sm:text-2xl font-bold text-white tracking-tight">
                {currentLevel === 'top' ? '🏆 Which tour?' : '🏆 Pick a list'}
              </h2>
            ) : (
              <h2 className="text-lg sm:text-2xl font-bold text-white tracking-tight">
                🏆 {selectedAssociation} Future Tournaments
              </h2>
            )}
          </div>

          {viewMode === 'menu' && (
            <div className="flex flex-wrap gap-2 sm:gap-3">
              {menuItems.map((item) => (
                <MenuOptionButton
                  key={item.kind === 'drill' ? item.id : item.association}
                  item={item}
                  onClick={() => handleMenuAction(item)}
                />
              ))}
            </div>
          )}
        </section>

        {isLoading ? (
          <PageLoader />
        ) : isError ? (
          <div className="empty-state">
            <div className="text-4xl mb-4">⚠️</div>
            <p className="text-gray-300 mb-3">
              Could not load upcoming events: {error instanceof Error ? error.message : 'Unknown error'}
            </p>
            <button
              onClick={() => refetch()}
              className="px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90"
            >
              Retry
            </button>
          </div>
        ) : events.length === 0 ? (
          <div className="empty-state">
            <div className="text-4xl mb-4">📅</div>
            <p className="text-gray-400">
              Nothing is on the calendar yet. An administrator can refresh upcoming events from Settings.
            </p>
          </div>
        ) : viewMode === 'menu' ? (
          <div className="empty-state">
            <div className="text-4xl mb-4">🧭</div>
            <p className="text-gray-400">Choose a category above to see scheduled events.</p>
          </div>
        ) : visibleEvents.length === 0 ? (
          <div className="empty-state">
            <div className="text-4xl mb-4">📭</div>
            <p className="text-gray-400">
              No upcoming events in {selectedAssociation} right now.
            </p>
          </div>
        ) : (
          <div className="events-grid">
            {visibleEvents.map((evt) => (
              <EventCard
                key={evt.event_id ?? evt.id ?? evt.name}
                evt={evt}
                canCreateTournament={canCreateTournament}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function EventCard({
  evt,
  canCreateTournament,
}: {
  evt: UpcomingEventExtended
  canCreateTournament: boolean
}) {
  const registerTo = `/tournaments/register?eventName=${encodeURIComponent(evt.name)}`
  const wizardTo = `/tournament-wizard?event=${encodeURIComponent(upcomingEventKey(evt))}`
  const newsHints = evt.enrichment?.matched_articles ?? []
  return (
    <div className="event-card">
      <div className="event-card-header">
        <span className={`association-badge ${(evt.association || '').toLowerCase()}`}>
          {evt.association}
        </span>
        {(evt.start_date ?? evt.date) && (
          <span className="event-date">
            {evt.start_date === evt.end_date
              ? evt.date
              : `${evt.start_date ?? evt.date} – ${evt.end_date ?? evt.date}`}
          </span>
        )}
      </div>
      <h3 className="event-card-title">{evt.name}</h3>
      {(evt.venue_address ?? evt.location) && (
        <p className="event-card-location">
          📍 {evt.venue_address ?? evt.location}
        </p>
      )}
      {evt.max_players != null && evt.max_players > 0 && (
        <p className="text-sm text-slate-400">
          👥 {evt.max_players} players
          {newsHints.length > 0 ? ' (from news/calendar — verify before create)' : ''}
        </p>
      )}
      {evt.prize_pool && (
        <p className="event-card-prize text-sm text-slate-400">
          💰 {evt.prize_pool}
        </p>
      )}
      {evt.format && (
        <p className="event-card-format text-sm text-slate-400">
          {evt.format}
        </p>
      )}
      <div className="event-card-links flex flex-wrap gap-2 mt-2">
        {canCreateTournament && (
          <Link
            to={wizardTo}
            className="event-card-link text-emerald-400 font-semibold"
          >
            Set up tournament →
          </Link>
        )}
        <Link
          to={registerTo}
          className="event-card-link text-primary"
        >
          Register in app →
        </Link>
        {evt.url && (
          <a
            href={evt.url}
            target="_blank"
            rel="noopener noreferrer"
            className="event-card-link"
          >
            View source →
          </a>
        )}
        {evt.bracket_url && (
          <a
            href={evt.bracket_url}
            target="_blank"
            rel="noopener noreferrer"
            className="event-card-link"
          >
            Bracket →
          </a>
        )}
        {evt.registration_url && (
          <a
            href={evt.registration_url}
            target="_blank"
            rel="noopener noreferrer"
            className="event-card-link text-primary"
          >
            Official registration ↗
          </a>
        )}
      </div>
    </div>
  )
}
