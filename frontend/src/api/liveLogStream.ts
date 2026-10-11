/**
 * Generic live-log streaming client for long-running admin actions.
 *
 * Mirrors the pattern already used by `admin.ts:streamRebuildWebsiteLog` and
 * `rankings.ts:streamScraperLog`, but parameterized so any new admin button can
 * follow its own per-job log file by passing a relative URL.
 *
 * Backend pairing: `api/services/live_log.py` writes to `logs/<job_id>.log` and
 * exposes a `text/plain; charset=utf-8` `StreamingResponse` (chunked transfer +
 * `X-Accel-Buffering: no`) that ends on the first `Done in Xs.` marker.
 */

import { API_BASE_URL } from './client'

/**
 * Standard response shape returned by every endpoint that uses the backend
 * `start_background_action(...)` helper from `api/services/live_log.py`. Use this
 * when typing axios calls into a long-running admin POST so the call site can
 * reliably tell "started" vs "already_running" and pluck `message` for a toast.
 */
export interface LiveLogStarted {
  status: 'started' | 'already_running'
  /** Human-readable summary intended for a toast / inline banner. */
  message?: string
  /** Server-side log file path the matching GET stream is reading from. */
  log_file?: string
  /** The internal job_id (matches the URL suffix used for streaming). */
  job?: string
  /** Some endpoints add their own extra context (e.g. `scraper`, `rating_type`). */
  [key: string]: unknown
}

/**
 * Build the same Authorization headers axios uses, but for `fetch()` (which
 * does not run our axios interceptors). Prefers the explicit token from
 * `AuthContext` because localStorage can lag/desync after login.
 */
function buildAuthHeaders(explicitToken?: string | null): Record<string, string> {
  const headers: Record<string, string> = {}
  const apiKey =
    typeof import.meta.env.VITE_API_KEY === 'string' && import.meta.env.VITE_API_KEY
      ? import.meta.env.VITE_API_KEY
      : ''
  if (apiKey) headers['X-API-Key'] = apiKey

  let token = (explicitToken && explicitToken.trim()) || null
  if (!token) token = localStorage.getItem('access_token')
  if (!token) token = localStorage.getItem('auth_token')
  if (!token) {
    try {
      const authData = localStorage.getItem('rankings_bot_auth')
      if (authData) {
        const parsed = JSON.parse(authData) as { token?: string; access_token?: string }
        token = parsed?.token ?? parsed?.access_token ?? null
      }
    } catch {
      /* ignore malformed legacy blob */
    }
  }
  if (!token) {
    token = sessionStorage.getItem('access_token') || sessionStorage.getItem('auth_token')
  }
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

/**
 * Open a streaming connection and invoke `onChunk` with each decoded text chunk
 * until the server closes the stream or the AbortSignal fires.
 *
 * @param relativeUrl  Path relative to the API base, e.g. `/admin/system/backup/log`.
 * @param onChunk      Called for each text chunk (already decoded as UTF-8).
 * @param signal       Optional AbortSignal to cancel the stream from the UI.
 * @param authToken    Optional token override (typically `user.token` from AuthContext).
 */
export async function streamLog(
  relativeUrl: string,
  onChunk: (text: string) => void,
  signal?: AbortSignal,
  authToken?: string | null,
): Promise<void> {
  const url = `${API_BASE_URL}${relativeUrl}`
  const res = await fetch(url, { headers: buildAuthHeaders(authToken), signal })
  if (!res.ok) {
    throw new Error(res.statusText || `Failed to stream log (HTTP ${res.status})`)
  }
  const reader = res.body?.getReader()
  if (!reader) throw new Error('No response body')
  const dec = new TextDecoder()
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      if (value) onChunk(dec.decode(value, { stream: true }))
    }
    const tail = dec.decode()
    if (tail) onChunk(tail)
  } finally {
    reader.releaseLock()
  }
}
