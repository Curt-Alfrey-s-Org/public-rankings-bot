/**
 * Player Card Component
 * Card layout showing player name, rating, rank, and recent activity
 * Includes hover effects (shadow, scale) and click navigation
 * 
 * @component
 * @example
 * <PlayerCard
 *   player={{
 *     id: '123',
 *     name: 'Alice Johnson',
 *     rating: 1850,
 *     rank: 5,
 *     lastUpdated: '2026-01-15',
 *     trend: 12
 *   }}
 *   onClick={() => navigate('/player/123')}
 * />
 */

import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import MetricBadge from './MetricBadge'

interface PlayerCardMetrics {
  /** Player unique identifier */
  id: string
  /** Player display name */
  name: string
  /** Current rating (Fargo/ALFA) */
  rating: number
  /** Current rank */
  rank: number
  /** Last rating update date (ISO format) */
  lastUpdated: string
  /** Rating trend percentage */
  trend?: number
  /** Country/region (optional) */
  country?: string
  /** Number of tournaments played (optional) */
  tournamentsPlayed?: number
  /** Win rate percentage (optional) */
  winRate?: number
}

interface PlayerCardProps {
  /** Player data object */
  player: PlayerCardMetrics
  /** Click handler (typically navigates to player detail) */
  onClick: (player: PlayerCardMetrics) => void
  /** Optional CSS class */
  className?: string
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

/**
 * Get trend icon based on value
 */
const getTrendIcon = (trend?: number) => {
  if (!trend) return null
  if (trend > 0) return <TrendingUp className="w-4 h-4 text-sky-500" />
  if (trend < 0) return <TrendingDown className="w-4 h-4 text-red-500" />
  return <Minus className="w-4 h-4 text-slate-400" />
}

export default function PlayerCard({
  player,
  onClick,
  className = '',
}: PlayerCardProps) {
  return (
    <div
      onClick={() => onClick(player)}
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
          onClick(player)
        }
      }}
      aria-label={`Player: ${player.name}, Rank ${player.rank}`}
    >
      {/* Header with rank badge */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-sm sm:text-base font-semibold text-white truncate group-hover:text-sky-300 transition-colors">
            {player.name}
          </h3>
          {player.country && (
            <p className="text-xs text-slate-400 mt-0.5">{player.country}</p>
          )}
        </div>
        <div className="flex-shrink-0 bg-sky-500/20 text-sky-300 border border-sky-500/30 rounded-lg px-2.5 py-1.5">
          <div className="text-xs font-bold">#{player.rank}</div>
        </div>
      </div>

      {/* Rating display */}
      <div className="flex items-baseline gap-2 mb-4 flex-grow">
        <span className="text-2xl sm:text-3xl font-bold text-white">
          {player.rating}
        </span>
        <span className="text-xs text-slate-400">rating</span>
      </div>

      {/* Metrics row */}
      <div className="flex flex-wrap gap-2 mb-4">
        {player.winRate !== undefined && (
          <MetricBadge
            label="Win %"
            value={`${player.winRate.toFixed(1)}%`}
            variant="success"
          />
        )}
        {player.tournamentsPlayed !== undefined && (
          <MetricBadge
            label="Tournaments"
            value={player.tournamentsPlayed}
            variant="default"
          />
        )}
      </div>

      {/* Footer with trend and date */}
      <div className="pt-3 border-t border-slate-800/50 flex items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-1.5 text-slate-400">
          {getTrendIcon(player.trend)}
          {player.trend !== undefined && (
            <span className={player.trend > 0 ? 'text-sky-400' : player.trend < 0 ? 'text-red-400' : ''}>
              {player.trend > 0 ? '+' : ''}{player.trend}%
            </span>
          )}
        </div>
        <span className="text-slate-500">
          {formatDate(player.lastUpdated)}
        </span>
      </div>
    </div>
  )
}
