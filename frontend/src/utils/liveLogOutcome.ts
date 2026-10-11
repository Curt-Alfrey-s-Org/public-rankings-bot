import type { LiveLogStatus } from '@/hooks/useLiveLogStream'

/** Terminal statuses once `Done in` is observed in a job log. */
export type LiveLogJobOutcome = 'complete' | 'complete_warning' | 'complete_failed'

/**
 * Infer job outcome from accumulated log text (server writes `[OK]` / `[ERROR]`
 * markers before `Done in Xs.`). Keeps admin modals honest when a job finishes
 * but data was not fully saved (e.g. WPA Men drop guard, CP timeout).
 */
export function parseLiveLogJobOutcome(logText: string): LiveLogJobOutcome {
  const tail = logText.slice(-6000)
  const hasOk = /\[OK\]/i.test(tail)
  const hasError = /\[ERROR\]/i.test(tail)
  const partial =
    /NOT saved|not saved|division\(s\) not saved|returned no data/i.test(tail)

  if (hasError && !hasOk) return 'complete_failed'
  if (partial && (hasOk || hasError)) return 'complete_warning'
  if (hasError) return 'complete_failed'
  return 'complete'
}

/** Map parsed job outcome to stream status (after `Done in`). */
export function jobOutcomeToStreamStatus(outcome: LiveLogJobOutcome): LiveLogStatus {
  switch (outcome) {
    case 'complete_warning':
      return 'complete_warning'
    case 'complete_failed':
      return 'complete_failed'
    default:
      return 'complete'
  }
}

export function liveLogStatusLabel(status: LiveLogStatus): string {
  switch (status) {
    case 'running':
      return 'In progress…'
    case 'complete':
      return 'Finished successfully'
    case 'complete_warning':
      return 'Finished with warnings — review the log'
    case 'complete_failed':
      return 'Finished with errors — no data saved'
    case 'stream_ended':
      return 'Live stream ended — job may still be running'
    case 'error':
      return 'Could not read the log stream'
    default:
      return ''
  }
}

export function liveLogStatusClass(status: LiveLogStatus): string {
  switch (status) {
    case 'complete':
      return 'text-emerald-400'
    case 'complete_warning':
      return 'text-amber-400'
    case 'complete_failed':
    case 'error':
      return 'text-red-400'
    case 'stream_ended':
      return 'text-amber-400'
    case 'running':
      return 'text-sky-400'
    default:
      return 'text-slate-400'
  }
}
