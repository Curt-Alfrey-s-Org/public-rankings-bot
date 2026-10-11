/**
 * Renders archived tournament-tab payloads (overview, bracket, matches, etc.)
 * from the same JSON harvest used for coverage flags. Never shows internal harvester names in UI.
 */
import { useMemo, useState } from 'react'

export type TabPayloadCoverage = {
  has_overview: boolean
  has_bracket: boolean
  has_live_scores: boolean
  has_matches: boolean
  has_schedule: boolean
  has_players: boolean
  has_stats: boolean
  has_performance: boolean
  tab_overview?: Record<string, unknown> | null
  tab_players?: Array<Record<string, unknown>> | null
  tab_brackets?: Array<Record<string, unknown>> | null
  tab_matches?: Array<Record<string, unknown>> | null
  tab_schedule?: Record<string, unknown> | unknown[] | null
  tab_live_scores?: Record<string, unknown> | unknown[] | null
  tab_stats?: Array<Record<string, unknown>> | null
  tab_performance?: Record<string, unknown> | unknown[] | null
}

/** Strip internal harvester wording from user-visible strings */
export function sanitizeTournamentSourceText(value: unknown): string {
  if (value == null) return ''
  return String(value)
    .replace(/\bexternal\s*pool\b/gi, '')
    .replace(/externalpool/gi, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

function JsonKeyValue({
  data,
  depth = 0,
}: {
  data: Record<string, unknown>
  depth?: number
}) {
  const entries = Object.entries(data).filter(([k]) => k !== '__proto__')
  if (entries.length === 0) return <p className="text-sm text-slate-400">Empty</p>
  return (
    <dl
      className={`space-y-2 ${depth > 0 ? 'pl-3 border-l border-slate-700' : ''}`}
    >
      {entries.map(([key, val]) => (
        <div key={key}>
          <dt className="text-xs uppercase tracking-wide text-slate-500">{sanitizeTournamentSourceText(key)}</dt>
          <dd className="text-sm text-slate-200 mt-0.5">
            <JsonValue value={val} depth={depth + 1} />
          </dd>
        </div>
      ))}
    </dl>
  )
}

function JsonValue({ value, depth }: { value: unknown; depth: number }) {
  if (value === null || value === undefined) return <span className="text-slate-500">—</span>
  if (typeof value === 'boolean') return <span>{value ? 'Yes' : 'No'}</span>
  if (typeof value === 'number') return <span>{value}</span>
  if (typeof value === 'string') return <span>{sanitizeTournamentSourceText(value)}</span>
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-slate-500">[]</span>
    if (value.every((x) => x !== null && typeof x === 'object' && !Array.isArray(x))) {
      return <ObjectArrayTable rows={value as Record<string, unknown>[]} />
    }
    return (
      <ul className="list-disc list-inside text-sm">
        {value.map((v, i) => (
          <li key={i}>
            <JsonValue value={v} depth={depth} />
          </li>
        ))}
      </ul>
    )
  }
  if (typeof value === 'object') {
    return <JsonKeyValue data={value as Record<string, unknown>} depth={depth} />
  }
  return <span>{String(value)}</span>
}

function ObjectArrayTable({ rows }: { rows: Array<Record<string, unknown>> }) {
  const columns = useMemo(() => {
    const keys = new Set<string>()
    for (const r of rows.slice(0, 50)) {
      Object.keys(r).forEach((k) => keys.add(k))
    }
    return Array.from(keys).sort()
  }, [rows])

  if (rows.length === 0) return null

  return (
    <div className="overflow-x-auto max-h-[420px] overflow-y-auto rounded border border-slate-700/60">
      <table className="w-full text-xs text-left">
        <thead className="sticky top-0 bg-slate-900/95 border-b border-slate-700">
          <tr>
            {columns.map((c) => (
              <th key={c} className="px-2 py-1.5 font-medium text-slate-400 whitespace-nowrap">
                {sanitizeTournamentSourceText(c)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 200).map((row, ri) => (
            <tr key={ri} className="border-b border-slate-800/80">
              {columns.map((c) => (
                <td key={c} className="px-2 py-1 text-slate-200 max-w-[240px] truncate" title={sanitizeTournamentSourceText(row[c])}>
                  {row[c] == null ? '—' : typeof row[c] === 'object' ? JSON.stringify(row[c]) : sanitizeTournamentSourceText(row[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

type TabId =
  | 'overview'
  | 'bracket'
  | 'live'
  | 'matches'
  | 'schedule'
  | 'players'
  | 'stats'
  | 'performance'

export default function TournamentSourceTabs({ coverage }: { coverage: TabPayloadCoverage }) {
  const [active, setActive] = useState<TabId>('overview')

  const liveMatches = useMemo(() => {
    const tls = coverage.tab_live_scores
    if (tls && typeof tls === 'object' && !Array.isArray(tls)) {
      const o = tls as Record<string, unknown>
      const bm = o.bracket_matches
      const mm = o.matches
      const rows: Record<string, unknown>[] = []
      if (Array.isArray(bm)) rows.push(...(bm as Record<string, unknown>[]))
      if (Array.isArray(mm)) rows.push(...(mm as Record<string, unknown>[]))
      if (rows.length > 0) return rows
    }
    const m = coverage.tab_matches || []
    return m.filter((row) => {
      const st = String(row.status || '').toLowerCase()
      return st === 'in_progress' || st === 'live'
    })
  }, [coverage.tab_live_scores, coverage.tab_matches])

  const scheduledRows = useMemo(() => {
    const ts = coverage.tab_schedule
    if (ts && typeof ts === 'object' && !Array.isArray(ts)) {
      const o = ts as Record<string, unknown>
      const out: Array<{ source: string; row: Record<string, unknown> }> = []
      const br = o.bracket_rows
      const mr = o.match_rows
      if (Array.isArray(br)) {
        for (const row of br as Record<string, unknown>[]) {
          out.push({ source: 'bracket', row })
        }
      }
      if (Array.isArray(mr)) {
        for (const row of mr as Record<string, unknown>[]) {
          out.push({ source: 'match', row })
        }
      }
      if (out.length > 0) return out
    }
    const out: Array<{ source: string; row: Record<string, unknown> }> = []
    for (const row of coverage.tab_brackets || []) {
      if (row.scheduled_time) out.push({ source: 'bracket', row })
    }
    for (const row of coverage.tab_matches || []) {
      if (row.scheduled_time) out.push({ source: 'match', row })
    }
    return out
  }, [coverage.tab_schedule, coverage.tab_brackets, coverage.tab_matches])

  const statsRows = useMemo(() => {
    const ts = coverage.tab_stats
    if (ts && ts.length > 0) return ts
    return coverage.tab_players || []
  }, [coverage.tab_stats, coverage.tab_players])

  const performanceRows = useMemo(() => {
    const tp = coverage.tab_performance
    if (tp && typeof tp === 'object' && !Array.isArray(tp)) {
      const o = tp as Record<string, unknown>
      const bm = o.bracket_matches
      const mm = o.matches
      const rows: Record<string, unknown>[] = []
      if (Array.isArray(bm)) rows.push(...(bm as Record<string, unknown>[]))
      if (Array.isArray(mm)) rows.push(...(mm as Record<string, unknown>[]))
      if (rows.length > 0) return rows
    }
    const m = coverage.tab_matches || []
    const withScores = m.filter(
      (row) =>
        row.player_score != null ||
        row.opponent_score != null ||
        row.challenger1_score != null ||
        row.challenger2_score != null
    )
    if (withScores.length > 0) return withScores
    return coverage.tab_brackets || []
  }, [coverage.tab_performance, coverage.tab_matches, coverage.tab_brackets])

  const available: { id: TabId; label: string; ok: boolean }[] = [
    { id: 'overview', label: 'Overview', ok: coverage.has_overview },
    { id: 'bracket', label: 'Bracket', ok: coverage.has_bracket },
    { id: 'live', label: 'Live scores', ok: coverage.has_live_scores },
    { id: 'matches', label: 'Matches', ok: coverage.has_matches },
    { id: 'schedule', label: 'Schedule', ok: coverage.has_schedule },
    { id: 'players', label: 'Players', ok: coverage.has_players },
    { id: 'stats', label: 'Stats', ok: coverage.has_stats },
    { id: 'performance', label: 'Performance', ok: coverage.has_performance },
  ]

  const hasAnyPayload =
    (coverage.tab_overview && Object.keys(coverage.tab_overview).length > 0) ||
    (coverage.tab_players && coverage.tab_players.length > 0) ||
    (coverage.tab_brackets && coverage.tab_brackets.length > 0) ||
    (coverage.tab_matches && coverage.tab_matches.length > 0) ||
    (coverage.tab_schedule != null && coverage.tab_schedule !== '') ||
    (coverage.tab_live_scores != null && coverage.tab_live_scores !== '') ||
    (coverage.tab_stats && coverage.tab_stats.length > 0) ||
    (coverage.tab_performance != null && coverage.tab_performance !== '')

  return (
    <div className="rounded-lg border border-slate-700/60 bg-slate-900/40 p-4">
      <h4 className="text-lg font-semibold text-white mb-2">Tournament data</h4>
      <p className="text-xs text-slate-400 mb-4">
        Tabs mirror the source tournament site (overview, bracket, scores, schedule, players, etc.). Data appears when a
        snapshot has been archived for this event.
      </p>

      <div className="flex flex-wrap gap-1 mb-4 border-b border-slate-700/80 pb-2">
        {available.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setActive(t.id)}
            className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
              active === t.id
                ? 'bg-sky-600/40 text-sky-pool_opt_in border border-sky-500/50'
                : t.ok
                  ? 'text-slate-200 border border-slate-600 hover:bg-slate-800/80'
                  : 'text-slate-500 border border-slate-800 cursor-not-allowed opacity-60'
            }`}
            title={t.ok ? t.label : 'No data flagged for this tab in archive'}
          >
            {t.ok ? '✓' : '○'} {t.label}
          </button>
        ))}
      </div>

      {!hasAnyPayload && (
        <p className="text-sm text-slate-400">
          No archived tab payload for this tournament yet. Run the tournament harvest so snapshots are stored, then reopen
          this page.
        </p>
      )}

      {active === 'overview' && coverage.tab_overview && Object.keys(coverage.tab_overview).length > 0 && (
        <JsonKeyValue data={coverage.tab_overview as Record<string, unknown>} />
      )}
      {active === 'overview' && (!coverage.tab_overview || Object.keys(coverage.tab_overview).length === 0) && hasAnyPayload && (
        <p className="text-sm text-slate-400">No overview object in archive.</p>
      )}

      {active === 'bracket' && coverage.tab_brackets && coverage.tab_brackets.length > 0 && (
        <ObjectArrayTable rows={coverage.tab_brackets} />
      )}

      {active === 'live' && (
        <>
          {liveMatches.length > 0 ? (
            <ObjectArrayTable rows={liveMatches} />
          ) : (
            <p className="text-sm text-slate-400">No live / in-progress rows in the archived snapshot.</p>
          )}
        </>
      )}

      {active === 'matches' && coverage.tab_matches && coverage.tab_matches.length > 0 && (
        <ObjectArrayTable rows={coverage.tab_matches} />
      )}

      {active === 'schedule' && (
        <>
          {scheduledRows.length > 0 ? (
            <ObjectArrayTable rows={scheduledRows.map((x) => ({ ...x.row, _source: x.source }))} />
          ) : (
            <p className="text-sm text-slate-400">No scheduled times in the archived snapshot.</p>
          )}
        </>
      )}

      {active === 'players' && coverage.tab_players && coverage.tab_players.length > 0 && (
        <ObjectArrayTable rows={coverage.tab_players} />
      )}

      {active === 'stats' &&
        (statsRows.length > 0 ? (
          <ObjectArrayTable rows={statsRows} />
        ) : (
          <p className="text-sm text-slate-400">No stats rows in the archived snapshot.</p>
        ))}

      {active === 'performance' && (
        <>
          {performanceRows.length > 0 ? (
            <ObjectArrayTable rows={performanceRows} />
          ) : (
            <p className="text-sm text-slate-400">No score rows in the archived snapshot.</p>
          )}
        </>
      )}
    </div>
  )
}
