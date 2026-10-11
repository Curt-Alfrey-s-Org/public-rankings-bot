/**
 * Clocks for a selected match: shot clock (player turn), game clock, match clock, table time.
 * When tournamentId is provided, shows time until match start and on pace / behind pace.
 */

import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { directorApi } from '@/api/director'
import { tournamentsApi } from '@/api/tournaments'
import ShotClock from './ShotClock'

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

function formatCountdown(seconds: number): string {
  if (seconds <= 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

interface MatchClocksPanelProps {
  matchId: string
  tournamentId?: string
  onOpenTimekeeper?: (matchId: string) => void
}

export default function MatchClocksPanel({ matchId, tournamentId, onOpenTimekeeper }: MatchClocksPanelProps) {
  const { data: timerState } = useQuery({
    queryKey: ['match-timer-state', tournamentId, matchId],
    queryFn: () => (tournamentId ? tournamentsApi.getMatchStateForTimers(tournamentId, matchId) : Promise.resolve(null)),
    enabled: !!tournamentId && !!matchId,
    staleTime: 10_000,
  })

  const { data: settings } = useQuery({
    queryKey: ['director-clock-settings'],
    queryFn: directorApi.getClockSettings,
    staleTime: 60000,
  })

  const shotClockEnabled = settings?.shot_clock_enabled ?? false
  const shotSeconds = settings?.shot_clock_seconds ?? 40
  const gameLimitMinutes = settings?.game_clock_minutes ?? 0
  const matchLimitMinutes = settings?.match_clock_minutes ?? 0
  const tableAlertMinutes = settings?.table_time_alert_minutes ?? 0

  const [shotRunning, setShotRunning] = useState(false)
  const [gameRunning, setGameRunning] = useState(false)
  const [gameElapsed, setGameElapsed] = useState(0)
  const [matchRunning, setMatchRunning] = useState(false)
  const [matchElapsed, setMatchElapsed] = useState(0)
  const [tableRunning, setTableRunning] = useState(false)
  const [tableElapsed, setTableElapsed] = useState(0)

  useEffect(() => {
    if (!gameRunning) return
    const t = setInterval(() => setGameElapsed((e) => e + 1), 1000)
    return () => clearInterval(t)
  }, [gameRunning])

  useEffect(() => {
    if (!matchRunning) return
    const t = setInterval(() => setMatchElapsed((e) => e + 1), 1000)
    return () => clearInterval(t)
  }, [matchRunning])

  useEffect(() => {
    if (!tableRunning) return
    const t = setInterval(() => setTableElapsed((e) => e + 1), 1000)
    return () => clearInterval(t)
  }, [tableRunning])

  const gameLimitSeconds = gameLimitMinutes * 60
  const matchLimitSeconds = matchLimitMinutes * 60
  const tableAlertSeconds = tableAlertMinutes * 60
  const tableOverAlert = tableAlertMinutes > 0 && tableElapsed >= tableAlertSeconds

  const scheduledTime = timerState?.scheduled_time ? new Date(timerState.scheduled_time).getTime() : null
  const startedAt = timerState?.started_at ? new Date(timerState.started_at).getTime() : null
  const matchLimitMin = timerState?.match_time_limit_minutes ?? matchLimitMinutes
  const [timeUntilStart, setTimeUntilStart] = useState<number | null>(null)
  const [matchElapsedFromApi, setMatchElapsedFromApi] = useState<number | null>(null)

  useEffect(() => {
    if (!scheduledTime || startedAt) return
    const tick = () => setTimeUntilStart(Math.max(0, Math.floor((scheduledTime - Date.now()) / 1000)))
    tick()
    const t = setInterval(tick, 1000)
    return () => clearInterval(t)
  }, [scheduledTime, startedAt])

  useEffect(() => {
    if (!startedAt) return
    const tick = () => setMatchElapsedFromApi(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)))
    tick()
    const t = setInterval(tick, 1000)
    return () => clearInterval(t)
  }, [startedAt])

  const matchLimitSec = matchLimitMin * 60
  const behindPace = matchElapsedFromApi != null && matchLimitSec > 0
    ? matchElapsedFromApi > matchLimitSec
    : false

  return (
    <div className="border-t border-slate-700 pt-4 mt-4 space-y-4">
      <h3 className="text-sm font-semibold text-slate-200">Table clocks</h3>

      {/* Time until match start (player-facing) */}
      {tournamentId && timeUntilStart !== null && scheduledTime && !startedAt && (
        <div>
          <p className="text-xs text-slate-400 mb-1">Time until match starts</p>
          <p className="font-mono font-bold tabular-nums text-lg text-white">
            {formatCountdown(timeUntilStart)}
          </p>
        </div>
      )}

      {/* On pace / Behind pace (player-facing) */}
      {tournamentId && matchLimitMin > 0 && matchElapsedFromApi != null && (
        <div>
          <p className="text-xs text-slate-400 mb-1">Match time limit {matchLimitMin} min</p>
          <p className={`font-semibold ${behindPace ? 'text-amber-400' : 'text-green-400'}`}>
            {behindPace ? 'Behind pace' : 'On pace'}
          </p>
          <p className="text-xs text-slate-500 font-mono">{formatElapsed(matchElapsedFromApi)} elapsed</p>
        </div>
      )}

      {/* Shot clock (only when enabled; default off) */}
      {shotClockEnabled && (
        <div className="flex items-center gap-3 flex-wrap">
          <ShotClock
            seconds={shotSeconds}
            running={shotRunning}
            onExpire={() => setShotRunning(false)}
            size="sm"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setShotRunning((r) => !r)}
              className="px-2 py-1 rounded bg-slate-600 text-slate-200 text-xs font-medium hover:bg-slate-500"
            >
              {shotRunning ? 'Pause' : 'Start'}
            </button>
            <button
              type="button"
              onClick={() => setShotRunning(false)}
              className="px-2 py-1 rounded border border-slate-600 text-slate-300 text-xs font-medium hover:bg-slate-700"
            >
              Reset
            </button>
          </div>
        </div>
      )}

      {/* Game clock */}
      {gameLimitMinutes > 0 && (
        <div>
          <p className="text-xs text-slate-400 mb-1">Game clock (limit {gameLimitMinutes} min)</p>
          <div className="flex items-center gap-2">
            <span
              className={`font-mono font-bold tabular-nums text-lg ${
                gameElapsed >= gameLimitSeconds ? 'text-red-500' : 'text-white'
              }`}
            >
              {formatElapsed(gameElapsed)}
            </span>
            <button
              type="button"
              onClick={() => setGameRunning((r) => !r)}
              className="px-2 py-1 rounded bg-slate-600 text-slate-200 text-xs font-medium hover:bg-slate-500"
            >
              {gameRunning ? 'Pause' : 'Start'}
            </button>
            <button
              type="button"
              onClick={() => { setGameRunning(false); setGameElapsed(0) }}
              className="px-2 py-1 rounded border border-slate-600 text-slate-300 text-xs"
            >
              Reset
            </button>
          </div>
        </div>
      )}

      {/* Match clock */}
      {matchLimitMinutes > 0 && (
        <div>
          <p className="text-xs text-slate-400 mb-1">Match clock (limit {matchLimitMinutes} min)</p>
          <div className="flex items-center gap-2">
            <span
              className={`font-mono font-bold tabular-nums text-lg ${
                matchElapsed >= matchLimitSeconds ? 'text-red-500' : 'text-white'
              }`}
            >
              {formatElapsed(matchElapsed)}
            </span>
            <button
              type="button"
              onClick={() => setMatchRunning((r) => !r)}
              className="px-2 py-1 rounded bg-slate-600 text-slate-200 text-xs font-medium hover:bg-slate-500"
            >
              {matchRunning ? 'Pause' : 'Start'}
            </button>
            <button
              type="button"
              onClick={() => { setMatchRunning(false); setMatchElapsed(0) }}
              className="px-2 py-1 rounded border border-slate-600 text-slate-300 text-xs"
            >
              Reset
            </button>
          </div>
        </div>
      )}

      {/* Table time (elapsed); alert when over limit */}
      {tableAlertMinutes > 0 && (
        <div>
          <p className="text-xs text-slate-400 mb-1">Table time (alert at {tableAlertMinutes} min)</p>
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`font-mono font-bold tabular-nums text-lg ${
                tableOverAlert ? 'text-red-500' : 'text-white'
              }`}
            >
              {formatElapsed(tableElapsed)}
            </span>
            <button
              type="button"
              onClick={() => setTableRunning((r) => !r)}
              className="px-2 py-1 rounded bg-slate-600 text-slate-200 text-xs font-medium hover:bg-slate-500"
            >
              {tableRunning ? 'Pause' : 'Start'}
            </button>
            <button
              type="button"
              onClick={() => { setTableRunning(false); setTableElapsed(0) }}
              className="px-2 py-1 rounded border border-slate-600 text-slate-300 text-xs"
            >
              Reset
            </button>
            {tableOverAlert && onOpenTimekeeper && (
              <button
                type="button"
                onClick={() => onOpenTimekeeper(matchId)}
                className="px-3 py-1.5 rounded bg-amber-600 text-white text-xs font-semibold hover:bg-amber-700"
              >
                Send timekeeper →
              </button>
            )}
          </div>
          {tableOverAlert && (
            <p className="text-xs text-amber-400 mt-1">Table over time. Send a timekeeper to monitor shot clock.</p>
          )}
        </div>
      )}

      {gameLimitMinutes === 0 && matchLimitMinutes === 0 && tableAlertMinutes === 0 && (
        <p className="text-xs text-slate-500">Set game clock, match clock, or table time alert in Data Input → Table clocks.</p>
      )}
    </div>
  )
}
