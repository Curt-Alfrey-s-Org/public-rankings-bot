/**
 * Tournament Card Component
 * Card layout for tournament showing name, date, participants, and status
 * Includes status badge (upcoming, in-progress, completed, cancelled)
 * 
 * @component
 * @example
 * <TournamentCard
 *   tournament={{
 *     id: '456',
 *     name: 'US Open 2026',
 *     date: '2026-02-01',
 *     playerCount: 128,
 *     status: 'upcoming'
 *   }}
 *   onClick={() => navigate('/tournament/456')}
 * />
 */

import { Calendar, Users, Trophy, MapPin } from 'lucide-react'
import MetricBadge from './MetricBadge'

type TournamentStatus = 'upcoming' | 'in-progress' | 'completed' | 'cancelled'

interface TournamentCardMetrics {
  /** Tournament unique identifier */
  id: string
  /** Tournament name */
  name: string
  /** Tournament start date (ISO format) */
  date: string
  /** Number of participants */
  playerCount: number
  /** Number of trophies/prizes (optional) */
  trophyCount?: number
  /** Tournament status */
  status: TournamentStatus
  /** Location (optional) */
  location?: string
  /** Event type/format (optional) */
  format?: string
  /** Prize pool (optional) */
  prizePool?: string
}

interface TournamentCardProps {
  /** Tournament data object */
  tournament: TournamentCardMetrics
  /** Click handler (typically navigates to tournament detail) */
  onClick: (tournament: TournamentCardMetrics) => void
  /** Optional CSS class */
  className?: string
}

/**
 * Get status badge styling
 */
const getStatusVariant = (status: TournamentStatus): string => {
  switch (status) {
    case 'upcoming':
      return 'bg-sky-500/20 text-sky-300 border-sky-500/30'
    case 'in-progress':
      return 'bg-green-500/20 text-green-300 border-green-500/30'
    case 'completed':
      return 'bg-slate-600/30 text-slate-300 border-slate-600/50'
    case 'cancelled':
      return 'bg-red-500/20 text-red-300 border-red-500/30'
    default:
      return 'bg-slate-800/50 text-slate-300 border-slate-700/50'
  }
}

/**
 * Get status label
 */
const getStatusLabel = (status: TournamentStatus): string => {
  switch (status) {
    case 'upcoming':
      return 'Upcoming'
    case 'in-progress':
      return 'In Progress'
    case 'completed':
      return 'Completed'
    case 'cancelled':
      return 'Cancelled'
    default:
      return status
  }
}

/**
 * Format date to readable string
 */
const formatDate = (dateString: string): string => {
  const date = new Date(dateString)
  if (Number.isNaN(date.getTime())) {
    return dateString
  }
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined,
  })
}

export default function TournamentCard({
  tournament,
  onClick,
  className = '',
}: TournamentCardProps) {
  return (
    <div
      onClick={() => onClick(tournament)}
      className={`
        bg-slate-900/60 border border-slate-800 rounded-lg p-4 sm:p-5
        hover:bg-slate-900 hover:border-sky-500/30 hover:shadow-lg hover:shadow-sky-500/10
        active:scale-95 transition-all duration-200 cursor-pointer
        flex flex-col h-full group
        ${className}
      `}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick(tournament)
        }
      }}
      aria-label={`Tournament: ${tournament.name}, Status: ${getStatusLabel(tournament.status)}`}
    >
      {/* Header with status badge */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <h3 className="text-sm sm:text-base font-semibold text-white truncate group-hover:text-sky-300 transition-colors flex-1 min-w-0">
          {tournament.name}
        </h3>
        <div className={`flex-shrink-0 rounded-lg px-2.5 py-1.5 text-xs font-semibold whitespace-nowrap border ${getStatusVariant(tournament.status)}`}>
          {getStatusLabel(tournament.status)}
        </div>
      </div>

      {/* Location if provided */}
      {tournament.location && (
        <div className="flex items-center gap-2 text-xs text-slate-400 mb-2">
          <MapPin className="w-3.5 h-3.5" />
          <span className="truncate">{tournament.location}</span>
        </div>
      )}

      {/* Date */}
      <div className="flex items-center gap-2 mb-4 text-sm text-slate-300">
        <Calendar className="w-4 h-4 flex-shrink-0 text-sky-400" />
        <span>{formatDate(tournament.date)}</span>
      </div>

      {/* Metrics */}
      <div className="flex flex-wrap gap-2 mb-4 flex-grow">
        {tournament.playerCount > 0 && (
          <MetricBadge
            label="Players"
            value={tournament.playerCount}
            variant="primary"
            icon={<Users className="w-3 h-3" />}
          />
        )}
        {tournament.trophyCount !== undefined && (
          <MetricBadge
            label="Trophies"
            value={tournament.trophyCount}
            variant="default"
            icon={<Trophy className="w-3 h-3" />}
          />
        )}
      </div>

      {/* Format if provided */}
      {tournament.format && (
        <div className="pt-3 border-t border-slate-800/50">
          <p className="text-xs text-slate-400">
            <span className="font-medium text-slate-300">{tournament.format}</span>
          </p>
        </div>
      )}
    </div>
  )
}
