/**
 * useLiveLogStream — hook that owns the lifecycle of a long-running admin job's
 * live log: start the fetch stream, accumulate text into state, detect "Done in"
 * completion marker, and abort cleanly on unmount or close.
 *
 * Mirrors the logic that originally lived inline in SettingsAdmin.tsx for
 * `startRebuildLogStream` and `startScraperLogStream`. A single tested
 * implementation removes copy-paste drift across every admin live-log button.
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { streamLog } from '@/api/liveLogStream'
import { jobOutcomeToStreamStatus, parseLiveLogJobOutcome } from '@/utils/liveLogOutcome'

export type LiveLogStatus =
  | 'idle'
  | 'running'
  | 'complete'
  | 'complete_warning'
  | 'complete_failed'
  | 'stream_ended'
  | 'error'

export interface StartOptions {
  /**
   * Per-call override for the `onComplete` callback. When supplied, this fires
   * (in addition to / instead of the hook-level default — see `mergeOnComplete`)
   * the first time `Done in` is observed in the stream. Useful when one shared
   * modal services many buttons that each need their own cache invalidations.
   */
  onComplete?: () => void
  /**
   * If true, both the per-call `onComplete` and the hook-level default fire.
   * If false (default), the per-call `onComplete` replaces the default for
   * this run only — the next run reverts to the default.
   */
  mergeOnComplete?: boolean
}

export interface UseLiveLogStreamResult {
  /** Current modal open state. */
  open: boolean
  /** Current stream status. The UI should color-code based on this. */
  status: LiveLogStatus
  /** True while bytes are still arriving from the server. */
  loading: boolean
  /** Accumulated text content so far. */
  content: string
  /**
   * Open the modal and start streaming. Pass a relative URL (e.g. `/admin/system/backup/log`)
   * and optional per-call options (notably `onComplete`).
   */
  start: (relativeLogUrl: string, options?: StartOptions) => void
  /** Re-open the same stream from the beginning (used by the "Refresh log" button). */
  refresh: () => void
  /** Close the modal and abort any in-flight stream. */
  close: () => void
}

interface UseLiveLogStreamOptions {
  /** Optional bearer token (typically `user.token` from AuthContext). */
  authToken?: string | null
  /**
   * Called once per session as soon as `Done in` is observed in the stream.
   * Use this to invalidate react-query caches / show a success toast.
   * A per-call `start({ onComplete })` can replace or augment this default.
   */
  onComplete?: () => void
}

export function useLiveLogStream(
  options: UseLiveLogStreamOptions = {},
): UseLiveLogStreamResult {
  const { authToken, onComplete } = options
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState<LiveLogStatus>('idle')
  const [loading, setLoading] = useState(false)
  const [content, setContent] = useState('')
  const abortRef = useRef<AbortController | null>(null)
  const completeFiredRef = useRef(false)
  const lastUrlRef = useRef<string | null>(null)
  const lastOptionsRef = useRef<StartOptions | undefined>(undefined)
  const onCompleteRef = useRef(onComplete)

  useEffect(() => {
    onCompleteRef.current = onComplete
  }, [onComplete])

  const beginStream = useCallback(
    (url: string, perCall?: StartOptions) => {
      abortRef.current?.abort()
      const ac = new AbortController()
      abortRef.current = ac
      lastUrlRef.current = url
      lastOptionsRef.current = perCall
      completeFiredRef.current = false
      setContent('')
      setStatus('running')
      setLoading(true)
      streamLog(
        url,
        (chunk) => {
          setContent((prev) => {
            const next = prev + chunk
            if (next.includes('Done in')) {
              setStatus(jobOutcomeToStreamStatus(parseLiveLogJobOutcome(next)))
              if (!completeFiredRef.current) {
                completeFiredRef.current = true
                const callbacks: Array<() => void> = []
                const perCallCb = perCall?.onComplete
                if (perCallCb) callbacks.push(perCallCb)
                if (!perCallCb || perCall?.mergeOnComplete) {
                  if (onCompleteRef.current) callbacks.push(onCompleteRef.current)
                }
                for (const cb of callbacks) {
                  try {
                    cb()
                  } catch (err) {
                    // Surface but never break the stream over a callback error.
                    console.error('useLiveLogStream onComplete handler threw', err)
                  }
                }
              }
            }
            return next
          })
        },
        ac.signal,
        authToken,
      )
        .then(() => {
          setLoading(false)
          setStatus((prev) =>
            prev === 'complete' ||
            prev === 'complete_warning' ||
            prev === 'complete_failed' ||
            prev === 'error'
              ? prev
              : 'stream_ended',
          )
        })
        .catch((e: unknown) => {
          setLoading(false)
          const err = e as { name?: string; message?: string }
          if (err?.name === 'AbortError') {
            setStatus((prev) => (prev === 'running' ? 'stream_ended' : prev))
            return
          }
          setStatus('error')
          setContent((prev) => prev + `\n[Error streaming log: ${err?.message ?? 'unknown'}]`)
        })
    },
    [authToken],
  )

  const start = useCallback(
    (url: string, options?: StartOptions) => {
      setOpen(true)
      beginStream(url, options)
    },
    [beginStream],
  )

  const refresh = useCallback(() => {
    if (lastUrlRef.current) beginStream(lastUrlRef.current, lastOptionsRef.current)
  }, [beginStream])

  const close = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setOpen(false)
    setStatus('idle')
    setLoading(false)
    completeFiredRef.current = false
  }, [])

  useEffect(
    () => () => {
      abortRef.current?.abort()
    },
    [],
  )

  return { open, status, loading, content, start, refresh, close }
}
