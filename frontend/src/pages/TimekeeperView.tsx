/**
 * Full-screen shot clock for a timekeeper at a table.
 * Opened when director sends a timekeeper (e.g. after table time alert).
 * Query param: matchId (optional, for label).
 */

import { useState } from 'react'
import { useSearchParams, useLocation, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { directorApi } from '@/api/director'
import ShotClock from '@/components/ShotClock'

export default function TimekeeperView() {
  const [searchParams] = useSearchParams()
  const location = useLocation()
  const matchId = searchParams.get('matchId') ?? ''
  const [running, setRunning] = useState(false)
  const bracketPath = location.pathname.startsWith('/director') ? '/director/bracket' : '/tournaments/bracket'

  const { data: settings } = useQuery({
    queryKey: ['director-clock-settings'],
    queryFn: directorApi.getClockSettings,
    staleTime: 60000,
  })

  const shotClockEnabled = settings?.shot_clock_enabled ?? false
  const seconds = settings?.shot_clock_seconds ?? 40

  if (!shotClockEnabled) {
    return (
      <div className="fixed inset-0 z-[200] flex flex-col items-center justify-center bg-slate-950 text-white">
        <div className="absolute top-4 left-4">
          <Link
            to={bracketPath}
            className="text-slate-400 hover:text-white text-sm font-medium"
          >
            ← Back to bracket
          </Link>
        </div>
        <div className="text-center p-8">
          <p className="text-xl text-slate-300 mb-2">Shot clock is off</p>
          <p className="text-sm text-slate-500">Enable shot clock in Data Input → Table clocks.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-[200] flex flex-col items-center justify-center bg-slate-950 text-white">
      <div className="absolute top-4 left-4">
        <Link
          to={bracketPath}
          className="text-slate-400 hover:text-white text-sm font-medium"
        >
          ← Back to bracket
        </Link>
      </div>
      {matchId && (
        <p className="absolute top-4 right-4 text-slate-400 text-sm font-mono truncate max-w-[200px]" title={matchId}>
          Table: {matchId.slice(0, 12)}…
        </p>
      )}
      <div className="text-center">
        <p className="text-slate-400 text-sm mb-2">Shot clock — timekeeper view</p>
        <ShotClock
          seconds={seconds}
          running={running}
          onExpire={() => setRunning(false)}
          size="lg"
          className="my-6"
        />
        <div className="flex justify-center gap-3 mt-4">
          <button
            type="button"
            onClick={() => setRunning((r) => !r)}
            className="px-6 py-3 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700"
          >
            {running ? 'Pause' : 'Start'}
          </button>
          <button
            type="button"
            onClick={() => setRunning(false)}
            className="px-6 py-3 rounded-lg border border-slate-600 text-slate-300 font-medium hover:bg-slate-800"
          >
            Reset
          </button>
        </div>
      </div>
    </div>
  )
}
