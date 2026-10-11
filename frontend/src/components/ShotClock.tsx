/**
 * Shot clock: countdown for a player's turn (e.g. 40 seconds, configurable by director).
 * Used on table view and in timekeeper view.
 */

import { useState, useEffect } from 'react'

export interface ShotClockProps {
  /** Duration in seconds (e.g. 40). */
  seconds: number
  /** When true, countdown runs. */
  running: boolean
  /** Callback when time hits 0. */
  onExpire?: () => void
  /** Optional label (e.g. player name). */
  label?: string
  /** Compact vs large display. */
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export default function ShotClock({
  seconds,
  running,
  onExpire,
  label,
  size = 'md',
  className = '',
}: ShotClockProps) {
  const [remaining, setRemaining] = useState(seconds)

  useEffect(() => {
    setRemaining(seconds)
  }, [seconds])

  useEffect(() => {
    if (!running) return
    const startFrom = remaining > 0 ? remaining : seconds
    setRemaining(startFrom)
    const end = Date.now() + startFrom * 1000
    const t = setInterval(() => {
      const left = Math.max(0, Math.ceil((end - Date.now()) / 1000))
      setRemaining(left)
      if (left === 0) {
        clearInterval(t)
        onExpire?.()
      }
    }, 200)
    return () => clearInterval(t)
  }, [running, onExpire])

  const sizeClass = size === 'sm' ? 'text-lg' : size === 'lg' ? 'text-5xl' : 'text-3xl'
  const low = remaining <= 10 && running

  return (
    <div className={`flex flex-col items-center justify-center ${className}`}>
      {label && (
        <span className="text-sm text-muted-foreground mb-1">{label}</span>
      )}
      <div
        className={`font-mono font-bold tabular-nums ${sizeClass} ${
          low ? 'text-red-500 animate-pulse' : 'text-foreground'
        }`}
      >
        {running ? remaining : seconds}
      </div>
      <span className="text-xs text-muted-foreground mt-1">sec</span>
    </div>
  )
}
