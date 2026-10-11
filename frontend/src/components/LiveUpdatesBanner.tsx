import { useState, useEffect } from 'react'
import { LiveUpdateEvent, useLiveUpdates } from '@/hooks/useLiveUpdates'

interface LiveUpdatesBannerProps {
  /** Currently active page (e.g., 'rankings', 'tournament-history') */
  currentPage?: string
}

/**
 * Banner component that shows live update notifications.
 * Displays status, timing, and relevant metadata for scraper events.
 */
export function LiveUpdatesBanner({ currentPage: _currentPage }: LiveUpdatesBannerProps) {
  const [lastEvent, setLastEvent] = useState<LiveUpdateEvent | null>(null)
  const [isVisible, setIsVisible] = useState(false)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)

  useLiveUpdates({
    onUpdate: (event) => {
      setLastEvent(event)
      setIsVisible(true)
      setElapsedSeconds(0)

      // Auto-hide after 4 seconds (unless another event comes in)
      const hideTimer = setTimeout(() => {
        setIsVisible(false)
      }, 4000)

      return () => clearTimeout(hideTimer)
    },
    invalidateAllOnUpdate: true,
    showNotifications: false,
  })

  useEffect(() => {
    if (!isVisible || !lastEvent) return

    const interval = setInterval(() => {
      setElapsedSeconds((s) => s + 1)
    }, 1000)

    return () => clearInterval(interval)
  }, [isVisible, lastEvent])

  if (!isVisible || !lastEvent) {
    return null
  }

  const isSuccess = lastEvent.status === 'success'
  const scraperLabel = lastEvent.scraper_type.toUpperCase().replace(/_/g, ' ')

  return (
    <div
      className={`fixed bottom-4 right-4 px-4 py-3 rounded-lg shadow-lg border-l-4 animate-fadeInOut ${
        isSuccess
          ? 'bg-slate-800 border-sky-500 text-sky-200'
          : 'bg-slate-800 border-red-500 text-red-200'
      }`}
    >
      <div className="flex items-center gap-3">
        {/* Icon */}
        <div>
          {isSuccess ? (
            <svg
              className="w-5 h-5 animate-spin"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
          ) : (
            <svg
              className="w-5 h-5"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
          )}
        </div>

        {/* Content */}
        <div className="flex-1">
          <div className="text-sm font-semibold">
            {isSuccess ? '✓' : '✗'} {scraperLabel}
          </div>
          <div className="text-xs opacity-75">
            {isSuccess ? (
              <>
                Updated {lastEvent.rows_updated} records in {lastEvent.duration_s.toFixed(1)}s
              </>
            ) : (
              <>
                {lastEvent.error}
              </>
            )}
          </div>
        </div>

        {/* Elapsed time */}
        <div className="text-xs opacity-50">
          {elapsedSeconds}s ago
        </div>
      </div>
    </div>
  )
}

/**
 * Minimal version showing only update indicator dot
 */
export function LiveUpdatesDot() {
  const [isUpdating, setIsUpdating] = useState(false)

  useLiveUpdates({
    onUpdate: () => {
      setIsUpdating(true)
      const timer = setTimeout(() => setIsUpdating(false), 2000)
      return () => clearTimeout(timer)
    },
  })

  if (!isUpdating) {
    return null
  }

  return (
    <div className="fixed top-4 right-4 flex items-center gap-2">
      <span className="text-xs text-slate-400">Updating...</span>
      <div className="w-2 h-2 rounded-full bg-sky-500 animate-pulse" />
    </div>
  )
}
