/**
 * Format an ISO date-only string (YYYY-MM-DD) for display without UTC shift.
 * `new Date('2026-06-08')` parses as UTC midnight → shows prior day in US TZ.
 */
export function formatLocalDate(
  isoDate: string | null | undefined,
  options: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric', year: 'numeric' },
): string {
  if (!isoDate) return '—'
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(isoDate).trim())
  if (!m) {
    try {
      return new Date(isoDate).toLocaleDateString('en-US', options)
    } catch {
      return String(isoDate)
    }
  }
  const [, y, mo, d] = m
  const local = new Date(Number(y), Number(mo) - 1, Number(d))
  return local.toLocaleDateString('en-US', options)
}
