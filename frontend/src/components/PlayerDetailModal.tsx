/**
 * PlayerDetailModal – modal for player details and ranking history
 */

import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { rankingsApi, type PlayerData } from '@/api/rankings'
import apiClient from '@/api/client'
import { useAuth } from '@/contexts/AuthContext'

interface PlayerDetailModalProps {
  isOpen: boolean
  onClose: () => void
  playerName: string | null
}

// Time period options for history display
const TIME_PERIODS = [
  { label: 'Last 30 Days', days: 30 },
  { label: 'Last 60 Days', days: 60 },
  { label: 'Last 90 Days', days: 90 },
  { label: 'All History', days: null },
]

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  const date = new Date(dateStr)
  if (Number.isNaN(date.getTime())) {
    return String(dateStr)
  }
  return date.toLocaleDateString()
}

export default function PlayerDetailModal({ isOpen, onClose, playerName }: PlayerDetailModalProps) {
  const [timePeriodDays, setTimePeriodDays] = useState<number | null>(null)
  const { user } = useAuth()
  const [isSavingPreference, setIsSavingPreference] = useState(false)
  
  // Check if user is admin or super admin
  const isAdminOrSuperAdmin = user?.role === 'admin' || user?.role === 'super_admin'
  
  // Load saved preference on mount
  useEffect(() => {
    if (isAdminOrSuperAdmin && isOpen) {
      // Try to load from localStorage first (faster)
      const savedDays = localStorage.getItem('ranking_history_days')
      if (savedDays) {
        setTimePeriodDays(savedDays === 'null' ? null : parseInt(savedDays, 10))
      } else {
        // Could load from server here: GET /api/users/preferences/ranking_history_days
        // For now, we use localStorage
      }
    }
  }, [isOpen, isAdminOrSuperAdmin])
  
  const handleTimePeriodChange = async (days: number | null) => {
    setTimePeriodDays(days)
    
    // Save to localStorage immediately
    localStorage.setItem('ranking_history_days', String(days))
    
    // Optionally save to server for persistence across devices
    if (isAdminOrSuperAdmin) {
      setIsSavingPreference(true)
      try {
        // apiClient adds the Bearer token (and API base URL); a bare fetch() was rejected with 401.
        await apiClient.post('/users/preferences/ranking_history_days', {
          key: 'ranking_history_days',
          value: days,
        })
      } catch (error) {
        console.warn('Failed to save preference to server:', error)
      } finally {
        setIsSavingPreference(false)
      }
    }
  }
  
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['player', playerName, timePeriodDays],
    queryFn: () => rankingsApi.getPlayer(playerName!),
    enabled: isOpen && !!playerName,
    retry: 1,
  })

  if (!isOpen) return null

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="player-modal-title"
    >
      <div
        className="bg-gradient-to-b from-slate-800 to-slate-900 border border-felt/30 rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Tournament-themed header */}
        <div className="p-6 border-b border-felt/20 bg-gradient-to-r from-slate-900 to-slate-800">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <h2 id="player-modal-title" className="text-3xl font-bold text-white mb-1 truncate">
                {playerName || 'Player'}
              </h2>
              <div className="flex items-center gap-2 text-felt/80 text-sm">
                <span>Professional Player Profile</span>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-white/10 text-white transition-colors flex-shrink-0"
              aria-label="Close"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          
          {/* Time period selector - admin/super-admin only */}
          {isAdminOrSuperAdmin && (
            <div className="mt-4 pt-4 border-t border-felt/20">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-semibold text-felt uppercase">History Period:</span>
                {TIME_PERIODS.map((period) => (
                  <button
                    key={period.label}
                    onClick={() => handleTimePeriodChange(period.days)}
                    disabled={isSavingPreference}
                    className={`text-xs px-3 py-1 rounded transition-colors ${
                      timePeriodDays === period.days
                        ? 'bg-felt text-slate-900 font-semibold'
                        : 'bg-slate-700/50 text-slate-300 hover:bg-slate-700'
                    } ${isSavingPreference ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    {period.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="p-6 overflow-y-auto flex-1">
          {!playerName && (
            <p className="text-muted-foreground">No player selected.</p>
          )}
          {playerName && isLoading && (
            <div className="animate-pulse space-y-4">
              <div className="h-8 bg-muted rounded w-1/3" />
              <div className="h-32 bg-muted rounded" />
              <div className="h-24 bg-muted rounded" />
            </div>
          )}
          {playerName && isError && (
            <div className="bg-destructive/10 border border-destructive/30 rounded-lg p-4 text-destructive">
              {error instanceof Error ? error.message : 'Failed to load player data.'}
            </div>
          )}
          {playerName && data && data.player_name != null && (
            <PlayerContent data={data} />
          )}
        </div>
      </div>
    </div>
  )
}

function PlayerContent({ data }: { data: PlayerData }) {
  const wpba = data?.wpba ?? { current: null, history: [] }
  const wpa = data?.wpa ?? { current: null, history: [] }

  // Determine achievement badge
  const getAchievementBadge = (current: { rank?: number } | null) => {
    if (!current || current.rank == null) return null
    const rank = current.rank
    if (rank === 1) return { emoji: '🏆', text: 'Champion', color: 'text-yellow-400' }
    if (rank <= 5) return { emoji: '⭐', text: 'Top 5', color: 'text-yellow-300' }
    if (rank <= 10) return { emoji: '🎖️', text: 'Top 10', color: 'text-orange-300' }
    if (rank <= 25) return { emoji: '📍', text: 'Top 25', color: 'text-slate-300' }
    return null
  }

  const wpbaAchievement = getAchievementBadge(wpba.current)
  const wpaAchievement = getAchievementBadge(wpa.current)

  return (
    <div className="space-y-6">
      {/* Rankings Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* WPBA Card */}
        <RankingCard
          association="WPBA"
          current={wpba.current}
          history={wpba.history}
          achievement={wpbaAchievement}
        />

        {/* WPA Card */}
        <RankingCard
          association="WPA"
          current={wpa.current}
          history={wpa.history}
          achievement={wpaAchievement}
        />
      </div>

      {/* Ranking Trends */}
      <div className="border-t border-felt/20 pt-4">
        <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <span className="text-felt">📈</span> Ranking Timeline
        </h4>
        <RankingTimeline wpba={wpba.history} wpa={wpa.history} />
      </div>
    </div>
  )
}

function RankingCard({
  association,
  current,
  history,
  achievement,
}: {
  association: string
  current: any
  history: any[]
  achievement: any
}) {
  return (
    <div className="bg-slate-700/50 border border-felt/30 rounded-lg p-4 hover:bg-slate-700/70 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <h3 className="font-bold text-white">{association}</h3>
        {achievement && (
          <div className="flex items-center gap-1 bg-felt/20 px-2 py-1 rounded">
            <span>{achievement.emoji}</span>
            <span className={`text-xs font-semibold ${achievement.color}`}>{achievement.text}</span>
          </div>
        )}
      </div>

      {current ? (
        <>
          <div className="space-y-2 mb-4">
            <div className="flex justify-between items-center">
              <span className="text-slate-300 text-sm">Current Rank</span>
              <span className="text-2xl font-bold text-felt">#{current.rank}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-300 text-sm">Points</span>
              <span className="font-mono text-lg font-semibold text-white">{Number(current.points).toFixed(2)}</span>
            </div>
            {current.date && (
              <div className="flex justify-between items-center">
                <span className="text-slate-300 text-sm">Updated</span>
                <span className="text-xs text-slate-400">{formatDate(current.date)}</span>
              </div>
            )}
          </div>

          {history && Array.isArray(history) && history.length > 1 && (
            <div className="bg-slate-800/50 rounded p-2 text-xs">
              <div className="text-slate-400 mb-1">Peak: #{Math.min(...history.map((h) => h?.rank ?? 999))}</div>
              <div className="text-slate-300">
                Trend: {(history[0]?.rank ?? 0) < (history[history.length - 1]?.rank ?? 0) ? '📉 Lower' : '📈 Higher'}
              </div>
            </div>
          )}
        </>
      ) : (
        <p className="text-slate-400 text-sm italic">No ranking data available</p>
      )}
    </div>
  )
}

function RankingTimeline({ wpba: wpbaHistory, wpa: wpaHistory }: { wpba: any[]; wpa: any[] }) {
  const wpba = Array.isArray(wpbaHistory) ? wpbaHistory : []
  const wpa = Array.isArray(wpaHistory) ? wpaHistory : []
  const allHistory = [
    ...wpba.map((h) => ({ ...h, association: 'WPBA', date: h?.date ?? '' })),
    ...wpa.map((h) => ({ ...h, association: 'WPA', date: h?.date ?? '' })),
  ].sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())

  if (allHistory.length === 0) {
    return <p className="text-slate-400 text-sm">No ranking history available</p>
  }

  return (
    <div className="max-h-48 overflow-y-auto space-y-2">
      {allHistory.slice(0, 15).map((item, i) => (
        <div key={i} className="flex items-center gap-3 p-2 rounded hover:bg-slate-700/50 transition-colors">
          <div className="text-xs font-semibold text-felt min-w-[40px]">{item.association ?? '—'}</div>
          <div className="flex-1 min-w-0">
            <div className="flex justify-between items-center">
              <span className="text-white font-mono">#{item.rank ?? '—'}</span>
              <span className="text-slate-400 text-xs">{formatDate(item.date)}</span>
            </div>
            <div className="text-xs text-slate-400">{Number(item.points ?? 0).toFixed(2)} pts</div>
          </div>
        </div>
      ))}
      {allHistory.length > 15 && (
        <div className="text-xs text-slate-500 pt-2 border-t border-felt/20">
          +{allHistory.length - 15} more records
        </div>
      )}
    </div>
  )
}
