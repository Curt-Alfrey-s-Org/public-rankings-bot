/**
 * Movement page: who is moving up (rank up, new players, points gains only).
 * Declines are not shown. Test/sim players excluded. Includes chart and climbers (past year).
 * WPBA, WPA Women, WPA Men; top 20 climbers; export admin-only.
 */

import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { rankingsApi, type MovementEntry, type MovementClimber } from '@/api/rankings'
import { useAuth } from '@/contexts/AuthContext'

interface MovementProps {
  sidebarOpen?: boolean
  onSidebarToggle?: () => void
}

type MovementSystem = 'WPBA' | 'WPA_Women' | 'WPA_Men'

const CHANGE_LABELS: Record<string, string> = {
  rank_up: '↑ Rank up',
  rank_down: '↓ Rank down',
  points_change: 'Points gain',
  new_player: 'New',
}

function exportMovementToCsv(entries: MovementEntry[], system: string) {
  const headers = ['Player', 'Change', 'Old Rank', 'New Rank', 'Old Points', 'New Points', 'Date']
  const rows = entries.map((e) => [
    e.player_name,
    CHANGE_LABELS[e.change_type] ?? e.change_type,
    e.old_rank ?? '',
    e.new_rank ?? '',
    e.old_points ?? '',
    e.new_points ?? '',
    e.change_date,
  ])
  const csv = [headers.join(','), ...rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(','))].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `movement-${system.toLowerCase()}-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

type ChartType = 'bar' | 'line'

function MovementChart({
  entries,
  chartType,
}: {
  entries: MovementEntry[]
  chartType: ChartType
}) {
  const chartData = useMemo(() => {
    const c: Record<string, number> = {}
    entries.forEach((e) => {
      const t = e.change_type || 'other'
      c[t] = (c[t] || 0) + 1
    })
    const types = ['rank_up', 'new_player', 'points_change'] as const
    return types
      .filter((t) => (c[t] ?? 0) > 0)
      .map((type) => ({
        name: CHANGE_LABELS[type] ?? type,
        value: c[type] ?? 0,
        fill: type === 'rank_up' || type === 'new_player' ? '#16a34a' : '#0284c7',
      }))
  }, [entries])

  if (chartData.length === 0) return null

  if (chartType === 'line') {
    const maxVal = Math.max(...chartData.map((x) => x.value))
    const pts = chartData
      .map((d, i) => {
        const x = chartData.length <= 1 ? 200 : (i / (chartData.length - 1)) * 380 + 10
        const y = 100 - (d.value / Math.max(1, maxVal)) * 80 + 10
        return `${x},${y}`
      })
      .join(' ')
    return (
      <div className="h-48">
        <svg viewBox="0 0 400 120" preserveAspectRatio="none" className="w-full h-full">
          <polyline
            fill="none"
            stroke="#16a34a"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={pts}
          />
        </svg>
        <div className="flex flex-wrap gap-4 mt-2 text-sm text-muted-foreground">
          {chartData.map((d) => (
            <span key={d.name}>
              {d.name}: <strong className="text-foreground">{d.value}</strong>
            </span>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="h-48 flex items-end gap-2">
      {chartData.map((d) => (
        <div key={d.name} className="flex-1 flex flex-col items-center gap-1">
          <div
            className="w-full rounded-t min-h-[4px] transition-all"
            style={{
              height: `${(d.value / Math.max(...chartData.map((x) => x.value))) * 100}%`,
              backgroundColor: d.fill,
            }}
          />
          <span className="text-xs text-muted-foreground truncate max-w-full" title={d.name}>
            {d.name}
          </span>
          <span className="text-sm font-medium tabular-nums">{d.value}</span>
        </div>
      ))}
    </div>
  )
}

export default function Movement({ sidebarOpen: _sidebarOpen, onSidebarToggle: _onSidebarToggle }: MovementProps) {
  const [system, setSystem] = useState<MovementSystem>('WPBA')
  const [chartType, setChartType] = useState<ChartType>('bar')
  const { isAdmin, isSuperAdmin } = useAuth()
  const canExport = isAdmin || isSuperAdmin

  const apiSystem = system === 'WPA_Women' || system === 'WPA_Men' ? 'WPA' : system
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['movement', system],
    queryFn: () => rankingsApi.getMovement(apiSystem, 20),
    staleTime: 60000,
    retry: 1,
  })

  const { data: climbersData, isLoading: climbersLoading } = useQuery({
    queryKey: ['movement-climbers', system],
    queryFn: () => rankingsApi.getMovementClimbers(apiSystem, 20, 365),
    staleTime: 60000,
    retry: 1,
  })

  const climbers = climbersData?.climbers ?? []
  const maxGain = useMemo(() => Math.max(1, ...climbers.map((c: MovementClimber) => c.net_rank_gain)), [climbers])

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-50">
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-2xl font-bold text-slate-50 mb-2">Movement</h1>
          <p className="text-slate-400 mb-4">
            Who is moving up this week/month. Only rank gains, new entries, and points increases are shown; declines are not listed. Recorded when new snapshots are saved.
          </p>

      <div className="flex flex-wrap items-center gap-2 mb-4">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setSystem('WPBA')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              system === 'WPBA'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted/50 text-muted-foreground hover:bg-muted'
            }`}
          >
            WPBA
          </button>
          <button
            type="button"
            onClick={() => setSystem('WPA_Women')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              system === 'WPA_Women'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted/50 text-muted-foreground hover:bg-muted'
            }`}
          >
            WPA Women
          </button>
          <button
            type="button"
            onClick={() => setSystem('WPA_Men')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              system === 'WPA_Men'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted/50 text-muted-foreground hover:bg-muted'
            }`}
          >
            WPA Men
          </button>
        </div>
        {canExport && data && data.movement.length > 0 && (
          <button
            type="button"
            onClick={() => exportMovementToCsv(data.movement, system)}
            className="px-4 py-2 rounded-lg border border-border bg-background text-foreground text-sm font-medium hover:bg-muted transition-colors"
          >
            Export to CSV
          </button>
        )}
      </div>

      {data && data.movement.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-4 mb-6">
          <div className="flex items-center justify-between gap-2 mb-3">
            <h2 className="text-sm font-semibold text-foreground">Moving up by type</h2>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setChartType('bar')}
                className={`px-2 py-1 rounded text-xs font-medium ${
                  chartType === 'bar' ? 'bg-primary text-primary-foreground' : 'bg-muted/50 text-muted-foreground hover:bg-muted'
                }`}
              >
                Bar
              </button>
              <button
                type="button"
                onClick={() => setChartType('line')}
                className={`px-2 py-1 rounded text-xs font-medium ${
                  chartType === 'line' ? 'bg-primary text-primary-foreground' : 'bg-muted/50 text-muted-foreground hover:bg-muted'
                }`}
              >
                Line
              </button>
            </div>
          </div>
          <MovementChart entries={data.movement} chartType={chartType} />
        </div>
      )}

      {isLoading && <p className="text-muted-foreground">Loading movement…</p>}
      {isError && (
        <div className="rounded-lg border border-amber-800 bg-amber-950/30 p-4 flex items-center justify-between gap-2 mb-4">
          <span className="text-amber-200 text-sm">{error instanceof Error ? error.message : 'Could not load movement.'}</span>
          <button type="button" onClick={() => refetch()} className="px-3 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:opacity-90">Retry</button>
        </div>
      )}
      {data && (
        <div className="rounded-lg border border-border bg-card overflow-hidden">
          {data.movement.length === 0 ? (
            <p className="p-6 text-muted-foreground text-center">
              No one moving up this period yet. Run a refresh to save a new snapshot; rank gains and new entries will appear here.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/30">
                    <th className="text-left p-3 font-medium text-foreground">Player</th>
                    <th className="text-left p-3 font-medium text-foreground">Change</th>
                    <th className="text-left p-3 font-medium text-foreground">Old → New</th>
                    <th className="text-left p-3 font-medium text-foreground">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {data.movement.map((entry: MovementEntry, i: number) => (
                    <tr key={`${String(entry.player_name)}-${entry.change_date}-${i}`} className="border-b border-border/50">
                      <td className="p-3 font-medium text-foreground">{entry.player_name ?? '—'}</td>
                      <td className="p-3">
                        <span
                          className={
                            entry.change_type === 'rank_up' || entry.change_type === 'new_player'
                              ? 'text-green-600 dark:text-green-400'
                              : entry.change_type === 'rank_down'
                                ? 'text-amber-600 dark:text-amber-400'
                                : 'text-muted-foreground'
                          }
                        >
                          {CHANGE_LABELS[entry.change_type] ?? entry.change_type}
                        </span>
                      </td>
                      <td className="p-3 text-muted-foreground">
                        {entry.old_rank != null ? `#${entry.old_rank}` : '—'} →{' '}
                        {entry.new_rank != null ? `#${entry.new_rank}` : '—'}
                        {(entry.old_points != null || entry.new_points != null) && (
                          <span className="ml-2">
                            ({entry.old_points ?? '—'} → {entry.new_points ?? '—'} pts)
                          </span>
                        )}
                      </td>
                      <td className="p-3 text-muted-foreground">{entry.change_date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <div className="mt-8 rounded-lg border border-border bg-card overflow-hidden">
        <h2 className="text-lg font-semibold text-foreground p-4 border-b border-border">Climbers (past year)</h2>
        <p className="text-sm text-slate-400 px-4 pb-2">
          Who is moving up over the last 12 months—net rank gain (test/sim players excluded).
        </p>
        {climbersLoading && <p className="p-4 text-muted-foreground">Loading climbers…</p>}
        {!climbersLoading && climbers.length === 0 && (
          <p className="p-6 text-muted-foreground text-center">No climber data yet. Run a refresh and record snapshots over time.</p>
        )}
        {!climbersLoading && climbers.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="text-left p-3 font-medium text-foreground">Player</th>
                  <th className="text-left p-3 font-medium text-foreground">Net rank gain</th>
                  <th className="text-left p-3 font-medium text-foreground">Changes</th>
                </tr>
              </thead>
              <tbody>
                {climbers.map((c: MovementClimber, i: number) => (
                  <tr key={`${c.player_name}-${i}`} className="border-b border-border/50">
                    <td className="p-3 font-medium text-foreground">{c.player_name}</td>
                    <td className="p-3">
                      <div className="flex items-center gap-2">
                        <div className="w-24 h-5 bg-slate-800 rounded overflow-hidden">
                          <div
                            className="h-full bg-green-600/80 rounded"
                            style={{ width: `${(c.net_rank_gain / maxGain) * 100}%`, minWidth: 4 }}
                          />
                        </div>
                        <span className="text-green-400">+{c.net_rank_gain}</span>
                      </div>
                    </td>
                    <td className="p-3 text-muted-foreground">{c.change_count ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
        </div>
      </div>
    </div>
  )
}
