/**
 * LiveLogModal — reusable modal that shows the live, streaming output of a
 * long-running admin job (rebuild, scrape, calibration, deploy, ...).
 *
 * The visual design is the same as the original rebuild-website + scraper-run
 * modals; the lifecycle (fetch → decode → detect "Done in") is owned by
 * `useLiveLogStream`, so this component is purely presentational.
 *
 * Usage:
 *   const log = useLiveLogStream({ authToken, onComplete: () => queryClient.invalidateQueries(...) })
 *   ...
 *   <LiveLogModal
 *     {...log}
 *     title="Website rebuild"
 *     subtitle={<>Output from <code>logs/rebuild_website.log</code> on the server.</>}
 *   />
 *   ...
 *   onClick={() => log.start('/admin/rebuild-website/log')}
 */

import { useEffect, useRef, type ReactNode } from 'react'

import type { LiveLogStatus } from '@/hooks/useLiveLogStream'
import { liveLogStatusClass, liveLogStatusLabel } from '@/utils/liveLogOutcome'

export interface LiveLogModalProps {
  /** Whether the modal is open. */
  open: boolean
  /** Stream status from `useLiveLogStream`. */
  status: LiveLogStatus
  /** True while bytes are arriving. */
  loading: boolean
  /** Accumulated log text. */
  content: string
  /** Re-open the same stream from the top (server log file is rewritten on POST). */
  refresh: () => void
  /** Close the modal and abort any in-flight stream. */
  close: () => void
  /** Modal heading (e.g. "Website rebuild"). */
  title: string
  /** Optional secondary line (e.g. "Output from logs/scraper_wpba.log on the server."). */
  subtitle?: ReactNode
  /**
   * Optional override for the wording shown when `status === 'stream_ended'`.
   * Defaults to a generic "the job may still be running on the server" notice.
   */
  endedNotice?: ReactNode
  /**
   * Optional id for the modal title element (for screen readers). A stable id
   * lets multiple LiveLogModal instances coexist without aria-labelledby clashing.
   */
  titleId?: string
}

/**
 * Self-contained modal. Renders nothing when `open` is false.
 */
export function LiveLogModal({
  open,
  status,
  loading,
  content,
  refresh,
  close,
  title,
  subtitle,
  endedNotice,
  titleId,
}: LiveLogModalProps) {
  const endRef = useRef<HTMLDivElement>(null)
  const id = titleId ?? 'live-log-modal-title'

  useEffect(() => {
    if (!open) return
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [open, content])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4"
      onClick={close}
      role="presentation"
    >
      <div
        className="w-full max-w-4xl max-h-[90vh] flex flex-col rounded-xl border border-border bg-slate-900 text-slate-pool_opt_in shadow-xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby={id}
      >
        <div className="flex items-start justify-between gap-3 border-b border-slate-700 px-4 py-3 shrink-0">
          <div>
            <h2 id={id} className="text-lg font-semibold text-white">
              {title}
            </h2>
            {subtitle && <p className="text-xs text-slate-400 mt-1">{subtitle}</p>}
          </div>
          <button
            type="button"
            onClick={close}
            className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-300 hover:bg-slate-800 hover:text-white"
          >
            Close
          </button>
        </div>

        <div className="px-4 py-2 border-b border-slate-700 shrink-0 flex flex-wrap items-center gap-2">
          {status === 'running' && (
            <span className="inline-flex items-center gap-2 text-sm text-sky-400">
              <span className="inline-block h-2 w-2 rounded-full bg-sky-400 animate-pulse" aria-hidden />
              {liveLogStatusLabel(status)}
            </span>
          )}
          {(status === 'complete' ||
            status === 'complete_warning' ||
            status === 'complete_failed') && (
            <span className={`text-sm font-medium ${liveLogStatusClass(status)}`}>
              {liveLogStatusLabel(status)}
            </span>
          )}
          {status === 'stream_ended' && (
            <span className={`text-sm font-medium ${liveLogStatusClass(status)}`}>
              {endedNotice ?? liveLogStatusLabel(status)}
            </span>
          )}
          {status === 'error' && (
            <span className={`text-sm font-medium ${liveLogStatusClass(status)}`}>
              {liveLogStatusLabel(status)}
            </span>
          )}
          {loading && <span className="text-xs text-slate-500">Receiving…</span>}
        </div>

        <div className="flex-1 min-h-[200px] overflow-auto px-4 py-3">
          <pre className="text-xs font-mono whitespace-pre-wrap break-words text-slate-200">
            {content || (loading ? 'Connecting to log…' : '[Waiting for log…]')}
            <div ref={endRef} />
          </pre>
        </div>

        <div className="border-t border-slate-700 px-4 py-2 flex justify-end gap-2 shrink-0">
          <button
            type="button"
            onClick={refresh}
            className="rounded-lg px-3 py-1.5 text-sm font-medium bg-slate-800 text-slate-200 hover:bg-slate-700"
          >
            Refresh log
          </button>
          <button
            type="button"
            onClick={close}
            className="rounded-lg px-3 py-1.5 text-sm font-medium bg-sky-600 text-white hover:bg-sky-500"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  )
}
