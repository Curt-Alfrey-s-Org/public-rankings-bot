/**
 * Force-update gate (Guns of Boom / Boom Beach style).
 * If the server requires a newer app version, show a blocking "Update" prompt
 * so all users must refresh before continuing.
 * If the UI bundle was built for a different API image (VITE_API_BUILD_HASH), prompt refresh.
 */

import { useState, useEffect } from 'react'
import { systemApi } from '@/api/system'

const APP_VERSION = (import.meta.env.VITE_APP_VERSION as string) || '1.0.0'
const EXPECTED_API_BUILD_HASH = (import.meta.env.VITE_API_BUILD_HASH as string)?.trim() || ''

/** Compare semver-like strings (e.g. "1.0.0" vs "1.0.1"). Returns true if a < b. */
function isVersionLess(a: string, b: string): boolean {
  const parse = (s: string) =>
    s.split('.').map((n) => parseInt(n, 10) || 0)
  const pa = parse(a)
  const pb = parse(b)
  const len = Math.max(pa.length, pb.length)
  for (let i = 0; i < len; i++) {
    const va = pa[i] ?? 0
    const vb = pb[i] ?? 0
    if (va < vb) return true
    if (va > vb) return false
  }
  return false
}

type GateState = 'loading' | 'ok' | 'version' | 'hash'

interface UpdateRequiredGateProps {
  children: React.ReactNode
}

export default function UpdateRequiredGate({ children }: UpdateRequiredGateProps) {
  const [gate, setGate] = useState<GateState>('loading')

  useEffect(() => {
    systemApi
      .getAppVersion()
      .then(({ min_app_version, build_hash }) => {
        const min = (min_app_version || '1.0.0').trim() || '1.0.0'
        if (isVersionLess(APP_VERSION, min)) {
          setGate('version')
          return
        }
        if (
          EXPECTED_API_BUILD_HASH &&
          build_hash &&
          build_hash !== 'unknown' &&
          EXPECTED_API_BUILD_HASH !== build_hash
        ) {
          setGate('hash')
          return
        }
        setGate('ok')
      })
      .catch(() => {
        // If we can't reach the API (e.g. offline), allow the app to load
        setGate('ok')
      })
  }, [])

  if (gate === 'loading') {
    return (
      <div className="flex flex-col h-screen bg-slate-950 text-slate-50 items-center justify-center">
        <div className="inline-block w-8 h-8 border-2 border-sky-500 border-t-transparent rounded-full animate-spin" role="status" aria-label="Loading" />
      </div>
    )
  }

  if (gate === 'version') {
    return (
      <div className="flex flex-col h-screen bg-slate-950 text-slate-50 items-center justify-center p-6" role="alert">
        <div className="max-w-md w-full rounded-xl border-2 border-amber-600/50 bg-slate-900/90 backdrop-blur p-6 text-center space-y-4">
          <h1 className="text-xl font-bold text-amber-400">Update required</h1>
          <p className="text-slate-300">
            A new version of the app is available. Please refresh the page to update and continue.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="w-full min-h-[48px] px-4 py-3 bg-amber-600 text-white font-semibold rounded-lg hover:bg-amber-500 transition-colors"
          >
            Update now
          </button>
        </div>
      </div>
    )
  }

  if (gate === 'hash') {
    return (
      <div className="flex flex-col h-screen bg-slate-950 text-slate-50 items-center justify-center p-6" role="alert">
        <div className="max-w-md w-full rounded-xl border-2 border-sky-600/50 bg-slate-900/90 backdrop-blur p-6 text-center space-y-4">
          <h1 className="text-xl font-bold text-sky-400">Refresh required</h1>
          <p className="text-slate-300">
            This page does not match the running API (stale or split deploy). Hard refresh to load the correct bundle, or run a full deploy so the site and API are built together.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="w-full min-h-[48px] px-4 py-3 bg-sky-600 text-white font-semibold rounded-lg hover:bg-sky-500 transition-colors"
          >
            Refresh now
          </button>
        </div>
      </div>
    )
  }

  return <>{children}</>
}
