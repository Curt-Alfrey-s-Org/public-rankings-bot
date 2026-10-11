/**
 * Data input page: placeholder for Director/Admin rankings or tournament data input.
 * Visible and accessible only to users with director or admin role.
 * Includes data quality status (duplicate players, missing fields, point consistency).
 */

import { useState, useEffect, useMemo } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  rankingsApi,
  type DataQualityIssue,
  type TournamentDefinition,
  type TournamentImport,
  type PlayersWithoutFargoResponse,
  type ImportEligibilityResponse,
} from '@/api/rankings'
import { API_BASE_URL } from '@/api/client'
import { toast } from '@/lib/toast'
import DirectorClockSettingsSection from '@/components/DirectorClockSettings'

interface DataInputProps {
  sidebarOpen?: boolean
  onSidebarToggle?: () => void
}

function DataQualitySection() {
  const { data: quality, isLoading, isError } = useQuery({
    queryKey: ['data-quality'],
    queryFn: rankingsApi.getDataQuality,
    staleTime: 60000,
  })

  if (isLoading) return <p className="text-sm text-muted-foreground">Checking data quality…</p>
  if (isError) return <p className="text-sm text-destructive">Could not run data quality checks.</p>
  if (!quality) return null

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h2 className="text-lg font-semibold text-foreground mb-2">Data quality</h2>
      <div className="flex items-center gap-3 mb-3">
        {quality.passed ? (
          <span className="text-sm text-green-600 dark:text-green-400 font-medium">Passed</span>
        ) : (
          <span className="text-sm text-destructive font-medium">{quality.issues_count} error(s)</span>
        )}
        {quality.warnings_count > 0 && (
          <span className="text-sm text-amber-600 dark:text-amber-400">{quality.warnings_count} warning(s)</span>
        )}
      </div>
      {quality.issues.length > 0 && (
        <ul className="space-y-2 text-sm">
          {quality.issues.map((issue: DataQualityIssue, i: number) => (
            <li
              key={i}
              className={
                issue.severity === 'error'
                  ? 'text-destructive'
                  : 'text-amber-600 dark:text-amber-400'
              }
            >
              {issue.message}
              {issue.count != null && ` (${issue.count})`}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function RecentActivitySection() {
  const { data: audit, isLoading, isError } = useQuery({
    queryKey: ['audit-log'],
    queryFn: () => rankingsApi.getAuditLog(20),
    staleTime: 30000,
  })

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading recent activity…</p>
  if (isError) return <p className="text-sm text-muted-foreground">Could not load audit log.</p>
  if (!audit?.entries?.length) return null

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h2 className="text-lg font-semibold text-foreground mb-2">Recent activity</h2>
      <ul className="space-y-1.5 text-sm text-muted-foreground">
        {audit.entries.slice(0, 10).map((entry) => (
          <li key={entry.id} className="flex flex-wrap gap-x-2 gap-y-0">
            <span className="text-foreground/80 font-medium">{entry.actor_subject}</span>
            <span>({entry.actor_role})</span>
            <span>{entry.action}</span>
            <span className="text-xs">{new Date(entry.created_at).toLocaleString()}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

const ACCEPT_IMPORT = '.pdf,.docx,.xlsx,.xml,.csv,.txt'

const CURATED_IMPORT_SYSTEMS = [
  { value: 'WPBA', label: 'WPBA Women' },
  { value: 'WPA', label: 'WPA Women' },
  { value: 'WPA_Men', label: 'WPA Men' },
  { value: 'WPA_Artistic', label: 'Artistic Pool' },
  { value: 'WPA_Heyball_Men', label: 'Heyball Men' },
  { value: 'WPA_Heyball_Women', label: 'Heyball Women' },
  { value: 'Competitors_Pool_9Ball', label: '9-Ball' },
  { value: 'Competitors_Pool_10Ball', label: '10-Ball' },
  { value: 'Competitors_Pool_8Ball', label: '8-Ball' },
  { value: 'Competitors_Pool_Women_9Ball', label: '9-Ball Women' },
  { value: 'Competitors_Pool_Men_9Ball', label: '9-Ball Men' },
] as const

const POPULATE_REQUIRED_SYSTEMS = [
  'WPA_Women',
  'WPA_Men',
  'Competitors_Pool_9Ball',
  'Competitors_Pool_10Ball',
  'Competitors_Pool_8Ball',
  'WPA_Artistic',
  'WPA_Heyball_Women',
  'WPA_Heyball_Men',
] as const

function buildImportSystemOptions(el: ImportEligibilityResponse): { value: string; label: string }[] {
  const allowed = new Set(el.allowed_systems)
  const curated = CURATED_IMPORT_SYSTEMS.filter((c) => allowed.has(c.value))
  const curatedVals = new Set(curated.map((c) => c.value))
  const extra = el.allowed_systems.filter((s) => !curatedVals.has(s)).sort().map((s) => ({ value: s, label: s }))
  return [...curated, ...extra]
}

function canRunPopulateFromImport(el: ImportEligibilityResponse): boolean {
  return POPULATE_REQUIRED_SYSTEMS.every((s) => el.allowed_systems.includes(s))
}

function tournamentImportBuckets(el: ImportEligibilityResponse): ('WPBA' | 'WPA')[] {
  if (el.full_access) return ['WPBA', 'WPA']
  const out: ('WPBA' | 'WPA')[] = []
  if (el.scopes.includes('WPBA')) out.push('WPBA')
  if (el.scopes.includes('WPA')) out.push('WPA')
  return out
}

function PlayersWithoutFargoSection() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['players-without-fargo'],
    queryFn: rankingsApi.getPlayersWithoutFargo,
    staleTime: 60000,
  })

  const exportMutation = useMutation({
    mutationFn: rankingsApi.exportPlayersWithoutFargo,
    onSuccess: (blob) => {
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'players_without_fargo.txt'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    },
  })

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading players without Fargo…</p>
  if (isError) return <p className="text-sm text-destructive">Could not load players without Fargo.</p>

  const resp = data as PlayersWithoutFargoResponse | undefined
  const players = resp?.players ?? []
  const fromPlayers = resp?.from_players_table ?? 0
  const fromRankings = resp?.from_rankings ?? 0

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h2 className="text-lg font-semibold text-foreground mb-2">Players without Fargo rating</h2>
      <p className="text-sm text-muted-foreground mb-3">
        Players in our system without a Fargo score. Use this list for manual web search (e.g. FargoRate.com) to verify they are not in the Fargo rating system.
      </p>
      <div className="flex flex-wrap gap-3 mb-3">
        <span className="text-sm text-muted-foreground">
          {players.length} total ({fromPlayers} from players table, {fromRankings} from rankings)
        </span>
        <button
          type="button"
          onClick={() => refetch()}
          className="px-3 py-1.5 text-sm rounded-lg bg-muted hover:bg-muted/80 text-foreground"
        >
          Refresh list
        </button>
        <button
          type="button"
          onClick={() => exportMutation.mutate()}
          disabled={exportMutation.isPending || players.length === 0}
          className="px-3 py-1.5 text-sm rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {exportMutation.isPending ? '…' : 'Export to file'}
        </button>
      </div>
      {players.length > 0 && (
        <div className="max-h-48 overflow-y-auto border border-border rounded p-2 text-sm">
          <ul className="space-y-1">
            {players.slice(0, 50).map((p, i) => (
              <li key={i} className="flex gap-2">
                <span className="font-medium">{p.name}</span>
                {p.source && <span className="text-muted-foreground">({p.source})</span>}
              </li>
            ))}
          </ul>
          {players.length > 50 && (
            <p className="text-muted-foreground mt-2">… and {players.length - 50} more. Export to see all.</p>
          )}
        </div>
      )}
    </div>
  )
}

function ManualEntrySection({
  importOptions,
  blockImports,
  blockMessage,
  elLoading,
}: {
  importOptions: { value: string; label: string }[]
  blockImports: boolean
  blockMessage?: string
  elLoading: boolean
}) {
  const queryClient = useQueryClient()
  const [system, setSystem] = useState('')
  const [rows, setRows] = useState<{ rank: number; name: string; points: number; country: string }[]>([
    { rank: 1, name: '', points: 0, country: '' },
  ])
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!importOptions.length) return
    setSystem((prev) => (importOptions.some((o) => o.value === prev) ? prev : importOptions[0].value))
  }, [importOptions])

  const importMutation = useMutation({
    mutationFn: () =>
      rankingsApi.importManual(
        system,
        rows.filter((r) => r.name.trim()).map((r) => ({ rank: r.rank, name: r.name.trim(), points: r.points, country: r.country.trim() || undefined })),
      ),
    onSuccess: (data) => {
      setMessage(data.message)
      setError(null)
      toast.success(data.message ?? 'Import completed')
      queryClient.invalidateQueries({ queryKey: ['rankings'] })
      queryClient.invalidateQueries({ queryKey: ['data-quality'] })
      queryClient.invalidateQueries({ queryKey: ['audit-log'] })
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Import failed'
      setError(msg)
      setMessage(null)
      toast.error(msg)
    },
  })

  const addRow = () => setRows((prev) => [...prev, { rank: prev.length + 1, name: '', points: 0, country: '' }])
  const removeRow = (i: number) => setRows((prev) => prev.filter((_, idx) => idx !== i).map((r, idx) => ({ ...r, rank: idx + 1 })))
  const updateRow = (i: number, field: 'name' | 'points' | 'country', value: string | number) =>
    setRows((prev) => {
      const next = [...prev]
      next[i] = { ...next[i], [field]: value }
      if (field === 'points') next[i].points = Number(value) || 0
      return next
    })

  const validRows = rows.filter((r) => r.name.trim()).length

  if (elLoading) {
    return (
      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="text-lg font-semibold text-foreground mb-2">Manual entry</h2>
        <p className="text-sm text-muted-foreground">Loading which ranking systems you may update…</p>
      </div>
    )
  }

  if (blockImports) {
    return (
      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="text-lg font-semibold text-foreground mb-2">Manual entry</h2>
        <p className="text-sm text-muted-foreground">{blockMessage ?? 'You cannot import rankings until an administrator assigns your association.'}</p>
      </div>
    )
  }
  if (!importOptions.length) {
    return (
      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="text-lg font-semibold text-foreground mb-2">Manual entry</h2>
        <p className="text-sm text-muted-foreground">No ranking systems are available for your account. Ask an admin to assign the correct association(s).</p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h2 className="text-lg font-semibold text-foreground mb-2">Manual entry</h2>
      <p className="text-sm text-muted-foreground mb-3">Choose the game type column to load data into, then enter rows (rank, name, points, country). Submit adds them as a new snapshot.</p>
      <div className="mb-4">
        <GameTypeButtons selected={system} options={importOptions} onSelect={(v) => setSystem(v)} label="Load data into" />
      </div>
      <div className="overflow-x-auto max-h-48 overflow-y-auto border border-border rounded mb-3">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 sticky top-0">
            <tr>
              <th className="text-left p-2 font-medium">Rank</th>
              <th className="text-left p-2 font-medium">Name</th>
              <th className="text-left p-2 font-medium">Points</th>
              <th className="text-left p-2 font-medium">Country</th>
              <th className="w-8" />
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-border/50">
                <td className="p-1">
                  <input
                    type="number"
                    min={1}
                    value={r.rank}
                    onChange={(e) => setRows((prev) => prev.map((p, j) => (j === i ? { ...p, rank: Math.max(1, parseInt(e.target.value, 10) || 1) } : p)))}
                    className="w-14 rounded border border-input bg-background px-1 py-0.5 text-foreground"
                  />
                </td>
                <td className="p-1">
                  <input
                    type="text"
                    value={r.name}
                    onChange={(e) => updateRow(i, 'name', e.target.value)}
                    placeholder="Player name"
                    className="w-40 rounded border border-input bg-background px-2 py-0.5 text-foreground"
                  />
                </td>
                <td className="p-1">
                  <input
                    type="number"
                    min={0}
                    step={0.01}
                    value={r.points || ''}
                    onChange={(e) => updateRow(i, 'points', e.target.value)}
                    className="w-20 rounded border border-input bg-background px-1 py-0.5 text-foreground"
                  />
                </td>
                <td className="p-1">
                  <input
                    type="text"
                    value={r.country}
                    onChange={(e) => updateRow(i, 'country', e.target.value)}
                    placeholder="USA"
                    className="w-16 rounded border border-input bg-background px-1 py-0.5 text-foreground"
                  />
                </td>
                <td className="p-1">
                  <button type="button" onClick={() => removeRow(i)} className="text-muted-foreground hover:text-destructive text-sm" title="Remove row">−</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={addRow} className="px-3 py-1.5 rounded border border-border bg-background text-sm font-medium hover:bg-muted">
          Add row
        </button>
        <button
          type="button"
          onClick={() => importMutation.mutate()}
          disabled={validRows === 0 || !system || importMutation.isPending}
          className="px-4 py-1.5 rounded bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
        >
          {importMutation.isPending ? 'Importing...' : `Submit ${validRows} row(s)`}
        </button>
        {message && <span className="text-sm text-green-600 dark:text-green-400" role="alert">{message}</span>}
        {error && <span className="text-sm text-destructive" role="alert">{error}</span>}
      </div>
    </div>
  )
}

/** Shared game-type button grid: select which column (ranking system) to import into. */
function GameTypeButtons({
  selected,
  onSelect,
  label = 'Import into',
  options,
}: {
  selected: string
  onSelect: (value: string) => void
  label?: string
  options: { value: string; label: string }[]
}) {
  return (
    <div className="space-y-2">
      <span className="text-sm font-medium text-foreground">{label}:</span>
      <div className="flex flex-wrap gap-2">
        {options.map((s) => (
          <button
            key={s.value}
            type="button"
            onClick={() => onSelect(s.value)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium border-2 transition-colors ${
              selected === s.value
                ? 'border-primary bg-primary/15 text-primary'
                : 'border-border bg-background hover:bg-muted text-foreground'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>
    </div>
  )
}

function FileImportSection({
  importOptions,
  blockImports,
  blockMessage,
  elLoading,
}: {
  importOptions: { value: string; label: string }[]
  blockImports: boolean
  blockMessage?: string
  elLoading: boolean
}) {
  const queryClient = useQueryClient()
  const [system, setSystem] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const importMutation = useMutation({
    mutationFn: () => (file ? rankingsApi.importFile(file, system) : Promise.reject(new Error('Select a file'))),
    onSuccess: (data) => {
      setMessage(data.message)
      setError(null)
      setFile(null)
      toast.success(data.message ?? 'File import completed')
      queryClient.invalidateQueries({ queryKey: ['rankings'] })
      queryClient.invalidateQueries({ queryKey: ['data-quality'] })
      queryClient.invalidateQueries({ queryKey: ['audit-log'] })
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Import failed'
      setError(msg)
      setMessage(null)
      toast.error(msg)
    },
  })

  const [showFormatGuide, setShowFormatGuide] = useState(false)

  useEffect(() => {
    if (!importOptions.length) return
    setSystem((prev) => (importOptions.some((o) => o.value === prev) ? prev : importOptions[0].value))
  }, [importOptions])

  if (elLoading) {
    return (
      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="text-lg font-semibold text-foreground mb-2">Import from file</h2>
        <p className="text-sm text-muted-foreground">Loading which ranking systems you may update…</p>
      </div>
    )
  }

  if (blockImports) {
    return (
      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="text-lg font-semibold text-foreground mb-2">Import from file</h2>
        <p className="text-sm text-muted-foreground">{blockMessage ?? 'You cannot import rankings until an administrator assigns your association.'}</p>
      </div>
    )
  }
  if (!importOptions.length) {
    return (
      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="text-lg font-semibold text-foreground mb-2">Import from file</h2>
        <p className="text-sm text-muted-foreground">No ranking systems are available for your account. Ask an admin to assign the correct association(s).</p>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h2 className="text-lg font-semibold text-foreground mb-2">Import from file</h2>
      <p className="text-sm text-muted-foreground mb-3">
        Choose the game type column to load data into, then upload a file. PDF, DOCX, XLSX, XML, CSV, or TXT with Rank/Position, Name, Points, and optionally Country.
      </p>
      <button
        type="button"
        onClick={() => setShowFormatGuide((v) => !v)}
        className="text-sm text-primary hover:underline mb-3"
      >
        {showFormatGuide ? '▼ Hide' : '▶'} Upload format guide (CSV, spreadsheet, PDF)
      </button>
      {showFormatGuide && (
        <div className="rounded-lg border border-border bg-muted/30 p-4 mb-4 text-sm text-foreground space-y-3">
          <p className="font-medium">Required columns (any file type):</p>
          <ul className="list-disc list-inside space-y-1 text-muted-foreground">
            <li><strong className="text-foreground">Rank / Position</strong> — finishing position (1, 2, 3…)</li>
            <li><strong className="text-foreground">Name</strong> — player full name</li>
            <li><strong className="text-foreground">Points</strong> — ranking points (numeric)</li>
          </ul>
          <p className="font-medium">Optional: Country, License number, Stops played.</p>
          <p className="font-medium mt-2">By file type:</p>
          <ul className="list-disc list-inside space-y-1 text-muted-foreground">
            <li><strong className="text-foreground">CSV / TXT</strong> — Header row with Rank (or Position), Name, Points; comma or tab separated. Optional: Country, License, Stops.</li>
            <li><strong className="text-foreground">Spreadsheet (XLSX)</strong> — Same columns in the first sheet. For WPA Men/Women, multiple point columns (e.g. 8-ball, 9-ball, 10-ball) are split into the matching ranking buttons automatically.</li>
            <li><strong className="text-foreground">PDF / DOCX</strong> — Tables are extracted; ensure columns are clearly separated (Rank, Name, Points, Country).</li>
            <li><strong className="text-foreground">XML</strong> — Table or list with rank, name, points (and optional country) elements.</li>
          </ul>
          <p className="text-muted-foreground mt-2">
            The app keeps the same column structure everywhere: rankings tables and tournaments created from upload or the wizard use Rank, Name, Points, Country (and optional fields) consistently.
          </p>
        </div>
      )}
      <div className="mb-4">
        <GameTypeButtons selected={system} options={importOptions} onSelect={(v) => setSystem(v)} label="Load data into" />
      </div>
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <span className="px-3 py-1.5 rounded border border-border bg-background hover:bg-muted text-foreground">Choose file</span>
          <input
            type="file"
            accept={ACCEPT_IMPORT}
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              setFile(f || null)
              setMessage(null)
              setError(null)
            }}
          />
          {file && <span className="text-muted-foreground text-sm truncate max-w-48">{file.name}</span>}
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => importMutation.mutate()}
          disabled={!file || !system || importMutation.isPending}
          className="px-4 py-1.5 rounded bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
        >
          {importMutation.isPending ? 'Uploading & importing...' : 'Upload and import'}
        </button>
        {message && <span className="text-sm text-green-600 dark:text-green-400" role="alert">{message}</span>}
        {error && <span className="text-sm text-destructive" role="alert">{error}</span>}
      </div>
    </div>
  )
}

function PopulateFromImportSection({ show }: { show: boolean }) {
  const queryClient = useQueryClient()
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const populateMutation = useMutation({
    mutationFn: async () => {
      const cpTargets = ['Competitors_Pool_9Ball', 'Competitors_Pool_10Ball', 'Competitors_Pool_8Ball']
      const fromWomen = await rankingsApi.copyFromImport('WPA_Women', [
        ...cpTargets,
        'WPA_Artistic',
        'WPA_Heyball_Women',
      ])
      const fromMen = await rankingsApi.copyFromImport('WPA_Men', ['WPA_Heyball_Men'])
      return { fromWomen, fromMen }
    },
    onSuccess: (data) => {
      const total = data.fromWomen.total + data.fromMen.total
      setMessage(`Copied ${total} rankings to 9-Ball, 10-Ball, 8-Ball, Artistic Pool, and Heyball from WPA Women and WPA Men.`)
      setError(null)
      toast.success('Ranking buttons populated from import')
      queryClient.invalidateQueries({ queryKey: ['rankings'] })
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Copy failed'
      setError(msg)
      setMessage(null)
      toast.error(msg)
    },
  })

  if (!show) return null

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h2 className="text-lg font-semibold text-foreground mb-2">Populate ranking buttons from import</h2>
      <p className="text-sm text-muted-foreground mb-3">
        Copy the latest WPA Women and WPA Men snapshots into 9-Ball, 10-Ball, 8-Ball, Artistic Pool, and Heyball Women/Men so each Rankings button shows data.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => populateMutation.mutate()}
          disabled={populateMutation.isPending}
          className="px-4 py-1.5 rounded bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
        >
          {populateMutation.isPending ? 'Copying...' : 'Populate from WPA Women & Men'}
        </button>
        {message && <span className="text-sm text-green-600 dark:text-green-400" role="alert">{message}</span>}
        {error && <span className="text-sm text-destructive" role="alert">{error}</span>}
      </div>
    </div>
  )
}

function TournamentImportsSection({ buckets, elLoading }: { buckets: ('WPBA' | 'WPA')[]; elLoading: boolean }) {
  const queryClient = useQueryClient()
  const [activeBucket, setActiveBucket] = useState<'WPBA' | 'WPA'>('WPBA')

  useEffect(() => {
    if (buckets.length && !buckets.includes(activeBucket)) {
      setActiveBucket(buckets[0])
    }
  }, [buckets, activeBucket])

  const bucket = buckets.length ? (buckets.includes(activeBucket) ? activeBucket : buckets[0]) : 'WPBA'

  const { data, isLoading, isError } = useQuery({
    queryKey: ['tournament-imports', bucket],
    queryFn: () => rankingsApi.getTournamentImports(bucket),
    staleTime: 30000,
    enabled: buckets.length > 0,
  })
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [editPoints, setEditPoints] = useState<number[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const updateMutation = useMutation({
    mutationFn: ({ id, name, points_by_place }: { id: number; name?: string; points_by_place?: number[] }) =>
      rankingsApi.updateTournamentImport(id, { name, points_by_place }),
    onSuccess: (_, vars) => {
      setMessage('Saved.')
      setError(null)
      toast.success('Import saved')
      queryClient.invalidateQueries({ queryKey: ['tournament-imports'] })
      setExpandedId(vars.id)
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Save failed'
      setError(msg)
      setMessage(null)
      toast.error(msg)
    },
  })

  const confirmMutation = useMutation({
    mutationFn: (id: number) => rankingsApi.confirmTournamentImport(id),
    onSuccess: () => {
      setMessage('Tournament confirmed.')
      setError(null)
      toast.success('Tournament confirmed')
      queryClient.invalidateQueries({ queryKey: ['tournament-imports'] })
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Confirm failed'
      setError(msg)
      setMessage(null)
      toast.error(msg)
    },
  })

  const updateRankingsMutation = useMutation({
    mutationFn: () => rankingsApi.updateRankingsFromTournamentImports(bucket),
    onSuccess: (data) => {
      setMessage(data.message)
      setError(null)
      toast.success(data.message ?? 'Rankings updated')
      queryClient.invalidateQueries({ queryKey: ['tournament-imports'] })
      queryClient.invalidateQueries({ queryKey: ['rankings'] })
      queryClient.invalidateQueries({ queryKey: ['rankings-last-update'] })
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Update rankings failed'
      setError(msg)
      setMessage(null)
      toast.error(msg)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => rankingsApi.deleteTournamentImport(id),
    onSuccess: () => {
      setExpandedId(null)
      toast.success('Import removed')
      queryClient.invalidateQueries({ queryKey: ['tournament-imports'] })
    },
    onError: (err: unknown) => toast.error(err instanceof Error ? err.message : 'Delete failed'),
  })

  const imports: TournamentImport[] = data?.imports ?? []
  const confirmedCount = imports.filter((i) => i.status === 'confirmed').length

  const openEdit = (imp: TournamentImport) => {
    setExpandedId(imp.id)
    setEditName(imp.name)
    const pts = imp.points_by_place?.length
      ? [...imp.points_by_place]
      : (imp.raw_results?.length ? Array(imp.raw_results.length).fill(0) : [0])
    setEditPoints(pts)
  }
  const setEditPointAt = (index: number, value: number) => {
    setEditPoints((prev) => {
      const next = [...prev]
      next[index] = value
      return next
    })
  }
  const addPlace = () => setEditPoints((prev) => [...prev, 0])
  const removePlace = () => setEditPoints((prev) => (prev.length > 1 ? prev.slice(0, -1) : prev))

  if (elLoading) {
    return (
      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="text-lg font-semibold text-foreground mb-2">Tournament imports</h2>
        <p className="text-sm text-muted-foreground">Loading tournament permissions…</p>
      </div>
    )
  }

  if (buckets.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-4">
        <h2 className="text-lg font-semibold text-foreground mb-2">Tournament imports</h2>
        <p className="text-sm text-muted-foreground">
          Tournament merge and WPBA/WPA import queues are limited to accounts with a WPBA or WPA association. Your assigned scopes do not include those buckets (for example, CP-only directors use file import above instead).
        </p>
      </div>
    )
  }

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading tournament imports…</p>
  if (isError) return <p className="text-sm text-destructive">Could not load tournament imports.</p>

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h2 className="text-lg font-semibold text-foreground mb-2">Tournament imports</h2>
      {buckets.length > 1 && (
        <div className="flex gap-2 mb-3">
          {buckets.map((b) => (
            <button
              key={b}
              type="button"
              onClick={() => setActiveBucket(b)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium border ${
                bucket === b ? 'border-primary bg-primary/15 text-primary' : 'border-border bg-background text-foreground hover:bg-muted'
              }`}
            >
              {b}
            </button>
          ))}
        </div>
      )}
      <p className="text-sm text-muted-foreground mb-3">
        <strong>How it works:</strong> When you add <code className="bg-muted px-1 rounded text-xs">final_results.txt</code> and click Refresh on Rankings,
        each tournament appears here as <strong>Incomplete</strong>. Fill in the tournament name and point values for 1st, 2nd, 3rd place, etc. Click <strong>Save</strong>, then <strong>Confirm</strong>.
        When all tournaments you want are confirmed, click <strong>Update rankings</strong> to apply them to the rankings. Tournaments without weights do not affect rankings until you enter them and confirm.
      </p>
      {imports.length === 0 ? (
        <p className="text-sm text-muted-foreground">No tournament imports yet. Add <code className="bg-muted px-1 rounded text-xs">final_results.txt</code> to <code className="bg-muted px-1 rounded text-xs">tournament_tools/</code> and click Refresh on the Rankings page.</p>
      ) : (
        <>
          <ul className="space-y-3 mb-4">
            {imports.map((imp) => (
              <li key={imp.id} className="rounded border border-border bg-muted/20 overflow-hidden">
                <div
                  className="flex flex-wrap items-center gap-2 p-3 cursor-pointer hover:bg-muted/30"
                  onClick={() => (expandedId === imp.id ? setExpandedId(null) : openEdit(imp))}
                  onKeyDown={(e) => e.key === 'Enter' && (expandedId === imp.id ? setExpandedId(null) : openEdit(imp))}
                  role="button"
                  tabIndex={0}
                >
                  <span className="font-medium text-foreground">{imp.name}</span>
                  <span
                    className={
                      imp.status === 'incomplete'
                        ? 'text-xs px-2 py-0.5 rounded bg-amber-pool_opt_in dark:bg-amber-900/40 text-amber-800 dark:text-amber-200 font-medium'
                        : imp.status === 'complete'
                          ? 'text-xs px-2 py-0.5 rounded bg-blue-pool_opt_in dark:bg-blue-900/40 text-blue-800 dark:text-blue-200 font-medium'
                          : 'text-xs px-2 py-0.5 rounded bg-green-pool_opt_in dark:bg-green-900/40 text-green-800 dark:text-green-200 font-medium'
                    }
                  >
                    {imp.status === 'incomplete'
                      ? 'Incomplete — enter weights'
                      : imp.status === 'complete'
                        ? 'Complete — confirm to include'
                        : 'Confirmed'}
                  </span>
                  {imp.raw_results?.length != null && (
                    <span className="text-xs text-muted-foreground">{imp.raw_results.length} placings</span>
                  )}
                  <span className="ml-auto text-muted-foreground text-sm">{expandedId === imp.id ? '▼' : '▶'}</span>
                </div>
                {expandedId === imp.id && (
                  <div className="p-3 pt-0 border-t border-border space-y-3" onClick={(e) => e.stopPropagation()}>
                    <div className="flex flex-wrap items-center gap-2">
                      <label className="text-sm text-muted-foreground">Tournament name</label>
                      <input
                        type="text"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        placeholder="e.g. Iron City VI"
                        className="rounded border border-input bg-background px-2 py-1 text-foreground w-48"
                      />
                    </div>
                    <div>
                      <span className="text-sm text-muted-foreground block mb-1">Point weights (1st, 2nd, 3rd…)</span>
                      <div className="flex flex-wrap items-center gap-1">
                        {editPoints.map((p, i) => (
                          <input
                            key={i}
                            type="number"
                            min={0}
                            step={0.5}
                            value={p}
                            onChange={(e) => setEditPointAt(i, Number(e.target.value) || 0)}
                            className="w-14 rounded border border-input bg-background px-1 py-0.5 text-foreground text-sm"
                            title={`Place ${i + 1}`}
                          />
                        ))}
                        <button type="button" onClick={addPlace} className="text-muted-foreground hover:text-foreground text-sm px-1" title="Add place">+</button>
                        <button type="button" onClick={removePlace} className="text-muted-foreground hover:text-foreground text-sm px-1" title="Remove last">−</button>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => updateMutation.mutate({ id: imp.id, name: editName.trim(), points_by_place: editPoints })}
                        disabled={updateMutation.isPending}
                        className="px-3 py-1.5 rounded bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
                      >
                        {updateMutation.isPending ? 'Saving...' : 'Save'}
                      </button>
                      <button
                        type="button"
                        onClick={() => confirmMutation.mutate(imp.id)}
                        disabled={imp.status === 'confirmed' || !editPoints.length || confirmMutation.isPending}
                        className="px-3 py-1.5 rounded border border-border bg-background text-sm font-medium hover:bg-muted disabled:opacity-50"
                      >
                        {confirmMutation.isPending ? 'Confirming...' : 'Confirm'}
                      </button>
                      <button
                        type="button"
                        onClick={() => deleteMutation.mutate(imp.id)}
                        disabled={deleteMutation.isPending}
                        className="text-sm text-destructive hover:underline"
                      >
                        {deleteMutation.isPending ? 'Removing...' : 'Remove'}
                      </button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-border">
            <button
              type="button"
              onClick={() => updateRankingsMutation.mutate()}
              disabled={confirmedCount === 0 || updateRankingsMutation.isPending}
              className="px-4 py-2 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 disabled:opacity-50"
            >
              {updateRankingsMutation.isPending ? 'Updating rankings...' : 'Update rankings'}
            </button>
            <span className="text-sm text-muted-foreground">
              {confirmedCount === 0
                ? 'Confirm at least one tournament above first.'
                : `Uses ${confirmedCount} confirmed tournament(s).`}
            </span>
          </div>
        </>
      )}
      {message && <p className="text-sm text-green-600 dark:text-green-400 mt-2" role="alert">{message}</p>}
      {error && <p className="text-sm text-destructive mt-2" role="alert">{error}</p>}
    </div>
  )
}

function TournamentDefinitionsSection() {
  const queryClient = useQueryClient()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['tournament-definitions'],
    queryFn: () => rankingsApi.getTournamentDefinitions(),
    staleTime: 30000,
  })
  const [name, setName] = useState('')
  const [pointsList, setPointsList] = useState<number[]>([100, 80, 60])
  const [defaultForImport, setDefaultForImport] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editName, setEditName] = useState('')
  const [editPointsList, setEditPointsList] = useState<number[]>([])

  const createMutation = useMutation({
    mutationFn: () =>
      rankingsApi.createTournamentDefinition({
        name: name.trim(),
        points_by_place: pointsList,
        is_default_for_import: defaultForImport,
      }),
    onSuccess: () => {
      setMessage('Tournament definition created.')
      setError(null)
      setName('')
      setPointsList([100, 80, 60])
      setDefaultForImport(false)
      toast.success('Tournament definition created')
      queryClient.invalidateQueries({ queryKey: ['tournament-definitions'] })
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Create failed'
      setError(msg)
      setMessage(null)
      toast.error(msg)
    },
  })

  const setDefaultMutation = useMutation({
    mutationFn: (id: number) => rankingsApi.setDefaultTournamentDefinition(id),
    onSuccess: () => {
      toast.success('Default definition updated')
      queryClient.invalidateQueries({ queryKey: ['tournament-definitions'] })
    },
    onError: (err: unknown) => toast.error(err instanceof Error ? err.message : 'Failed to set default'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => rankingsApi.deleteTournamentDefinition(id),
    onSuccess: () => {
      toast.success('Definition removed')
      queryClient.invalidateQueries({ queryKey: ['tournament-definitions'] })
      if (editingId !== null) setEditingId(null)
    },
    onError: (err: unknown) => toast.error(err instanceof Error ? err.message : 'Delete failed'),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, name: n, points_by_place }: { id: number; name?: string; points_by_place?: number[] }) =>
      rankingsApi.updateTournamentDefinition(id, { name: n, points_by_place }),
    onSuccess: () => {
      setEditingId(null)
      toast.success('Definition saved')
      queryClient.invalidateQueries({ queryKey: ['tournament-definitions'] })
    },
    onError: (err: unknown) => toast.error(err instanceof Error ? err.message : 'Save failed'),
  })

  const definitions: TournamentDefinition[] = data?.definitions ?? []
  const addPlace = () => setPointsList((prev) => [...prev, 0])
  const removePlace = () => setPointsList((prev) => (prev.length > 1 ? prev.slice(0, -1) : prev))
  const setPoint = (index: number, value: number) =>
    setPointsList((prev) => {
      const next = [...prev]
      next[index] = value
      return next
    })
  const startEdit = (d: TournamentDefinition) => {
    setEditingId(d.id)
    setEditName(d.name)
    setEditPointsList([...d.points_by_place])
  }
  const setEditPoint = (index: number, value: number) => {
    setEditPointsList((prev) => {
      const next = [...prev]
      next[index] = value
      return next
    })
  }

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading tournament definitions…</p>
  if (isError) return <p className="text-sm text-destructive">Could not load tournament definitions.</p>

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h2 className="text-lg font-semibold text-foreground mb-2">Tournament definitions</h2>
      <p className="text-sm text-muted-foreground mb-3">
        Enter tournament name and point values for 1st place, 2nd place, 3rd place, etc. When you import from{' '}
        <code className="bg-muted px-1 rounded text-xs">final_results.txt</code> (via Refresh), the default definition&apos;s points are applied to rankings.
      </p>
      <ul className="space-y-2 mb-4">
        {definitions.map((d) => (
          <li key={d.id} className="flex flex-wrap items-center gap-2 rounded border border-border/50 p-2 bg-muted/30">
            {editingId === d.id ? (
              <>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="rounded border border-input bg-background px-2 py-0.5 text-foreground w-40"
                  placeholder="Tournament name"
                />
                <span className="text-xs text-muted-foreground">Points:</span>
                {editPointsList.map((p, i) => (
                  <input
                    key={i}
                    type="number"
                    min={0}
                    step={0.5}
                    value={p}
                    onChange={(e) => setEditPoint(i, Number(e.target.value) || 0)}
                    className="w-14 rounded border border-input bg-background px-1 py-0.5 text-foreground text-sm"
                  />
                ))}
                <button
                  type="button"
                  onClick={() => updateMutation.mutate({ id: d.id, name: editName.trim(), points_by_place: editPointsList })}
                  disabled={updateMutation.isPending || !editName.trim()}
                  className="px-2 py-0.5 rounded bg-primary text-primary-foreground text-xs disabled:opacity-50"
                >
                  {updateMutation.isPending ? 'Saving...' : 'Save'}
                </button>
                <button type="button" onClick={() => setEditingId(null)} className="text-xs text-muted-foreground hover:underline">
                  Cancel
                </button>
              </>
            ) : (
              <>
                <span className="font-medium text-foreground">{d.name}</span>
                {d.is_default_for_import && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-primary/20 text-primary font-medium">Default for import</span>
                )}
                <span className="text-xs text-muted-foreground">
                  {d.points_by_place.map((p, i) => `${i + 1}: ${p}`).join(', ')}
                </span>
                <button
                  type="button"
                  onClick={() => setDefaultMutation.mutate(d.id)}
                  disabled={d.is_default_for_import || setDefaultMutation.isPending}
                  className="text-xs px-2 py-0.5 rounded border border-border hover:bg-muted"
                >
                  {setDefaultMutation.isPending ? 'Setting...' : 'Set default'}
                </button>
                <button type="button" onClick={() => startEdit(d)} className="text-xs text-primary hover:underline">
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => deleteMutation.mutate(d.id)}
                  disabled={deleteMutation.isPending}
                  className="text-xs text-destructive hover:underline"
                >
                  {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
                </button>
              </>
            )}
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-end gap-3 p-3 rounded border border-border bg-muted/20">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">Tournament name</span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Iron City VI"
            className="rounded border border-input bg-background px-2 py-1 text-foreground w-48"
          />
        </label>
        <div className="flex flex-col gap-1">
          <span className="text-sm text-muted-foreground">Points (1st, 2nd, 3rd…)</span>
          <div className="flex flex-wrap items-center gap-1">
            {pointsList.map((p, i) => (
              <input
                key={i}
                type="number"
                min={0}
                step={0.5}
                value={p}
                onChange={(e) => setPoint(i, Number(e.target.value) || 0)}
                className="w-14 rounded border border-input bg-background px-1 py-0.5 text-foreground text-sm"
                title={`Place ${i + 1}`}
              />
            ))}
            <button type="button" onClick={addPlace} className="text-muted-foreground hover:text-foreground text-sm px-1" title="Add place">
              +
            </button>
            <button type="button" onClick={removePlace} className="text-muted-foreground hover:text-foreground text-sm px-1" title="Remove last place">
              −
            </button>
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={defaultForImport}
            onChange={(e) => setDefaultForImport(e.target.checked)}
            className="rounded border-input"
          />
          <span className="text-muted-foreground">Use as default for import</span>
        </label>
        <button
          type="button"
          onClick={() => createMutation.mutate()}
          disabled={!name.trim() || createMutation.isPending}
          className="px-4 py-1.5 rounded bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
        >
          {createMutation.isPending ? 'Adding...' : 'Add definition'}
        </button>
      </div>
      {message && <p className="text-sm text-green-600 dark:text-green-400 mt-2" role="alert">{message}</p>}
      {error && <p className="text-sm text-destructive mt-2" role="alert">{error}</p>}
    </div>
  )
}

function BackupSection() {
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleBackup = async () => {
    setError(null)
    setDownloading(true)
    try {
      const blob = await rankingsApi.getBackup()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `rankings-${new Date().toISOString().split('T')[0]}.dump`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Download failed')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h2 className="text-lg font-semibold text-foreground mb-2">Backup database</h2>
      <p className="text-sm text-muted-foreground mb-3">Download a copy of the rankings database (Admin only).</p>
      {error && <p className="text-sm text-destructive mb-2" role="alert">{error}</p>}
      <button
        type="button"
        onClick={handleBackup}
        disabled={downloading}
        className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
      >
        {downloading ? '…' : 'Download backup'}
      </button>
    </div>
  )
}

const IMPORT_BLOCK_MSG =
  'No association is assigned to your account. An administrator must assign your association (for example WPBA_Women or WPA_Women under Settings → Users) before you can import or update rankings.'

export default function DataInput({ sidebarOpen: _sidebarOpen, onSidebarToggle: _onSidebarToggle }: DataInputProps) {
  const { isDirector, isAdmin, isSuperAdmin } = useAuth()

  const { data: eligibility, isLoading: elLoading, isError: elError } = useQuery({
    queryKey: ['rankings-import-eligibility'],
    queryFn: rankingsApi.getImportEligibility,
    staleTime: 60_000,
    enabled: Boolean(isDirector || isAdmin || isSuperAdmin),
  })

  const importOptions = useMemo(() => (eligibility ? buildImportSystemOptions(eligibility) : []), [eligibility])
  const blockDirectorImports = Boolean(eligibility?.role === 'director' && eligibility?.needs_association_assignment)
  const showPopulate = Boolean(eligibility && !elError && canRunPopulateFromImport(eligibility))
  const tourBuckets = useMemo(() => {
    if (elLoading || !eligibility) return []
    return tournamentImportBuckets(eligibility)
  }, [eligibility, elLoading])

  if (!isDirector && !isAdmin && !isSuperAdmin) {
    return (
      <div className="p-6 max-w-2xl">
        <h1 className="text-2xl font-bold text-foreground mb-2">Data input</h1>
        <p className="text-muted-foreground mb-4">Only tournament directors and administrators can use this page.</p>
        <Link to="/rankings" className="text-primary hover:underline">Go to Rankings</Link>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-50">
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto">
          <h1 className="text-2xl font-bold text-slate-50 mb-2">Data input</h1>
          <p className="text-slate-400 mb-6">
            Add or update standings by hand, or upload a file (spreadsheet, PDF, and other common formats). Your changes are saved for the ranking list you pick (for example WPBA Women or WPA Men).{' '}
            <a
              href={`${API_BASE_URL}/docs/director-import`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline text-sm"
            >
              Director guide (detailed steps)
            </a>
          </p>
        {elError && (
          <p className="text-sm text-destructive mb-4" role="alert">
            We couldn&apos;t load your import permissions. Refresh the page or try again shortly.
          </p>
        )}
        <div className="space-y-6">
        <DataQualitySection />
        <DirectorClockSettingsSection />
        <TournamentImportsSection buckets={tourBuckets} elLoading={elLoading} />
        <TournamentDefinitionsSection />
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="text-lg font-semibold text-foreground mb-2">Tournament results import</h2>
          <p className="text-sm text-muted-foreground mb-2">
            After your results file is in the usual folder for your site, run <strong>Refresh</strong> on the Rankings page so new events appear here as <strong>Incomplete</strong>.
            Name the event, set points for each place, save, confirm, then use <strong>Update rankings</strong> so standings reflect the new data.
          </p>
          <p className="text-xs text-muted-foreground">
            Files should follow the WPA-style layout your director was given (finish order, names, country, points). Full column rules are in the director documentation linked above.
          </p>
        </div>
        <ManualEntrySection
          importOptions={importOptions}
          blockImports={blockDirectorImports}
          blockMessage={IMPORT_BLOCK_MSG}
          elLoading={elLoading}
        />
        <FileImportSection
          importOptions={importOptions}
          blockImports={blockDirectorImports}
          blockMessage={IMPORT_BLOCK_MSG}
          elLoading={elLoading}
        />
        <PopulateFromImportSection show={showPopulate} />
        {isAdmin && <PlayersWithoutFargoSection />}
        <RecentActivitySection />
          {isAdmin && <BackupSection />}
        </div>
        </div>
      </div>
    </div>
  )
}
