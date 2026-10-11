/**
 * Director clock settings: shot clock (default 40s), game clock, match clock, table time alert.
 * Shown on Data Input for Director/Admin.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { directorApi, type DirectorClockSettings } from '@/api/director'
import { toast } from '@/lib/toast'
import { useState } from 'react'

const DEFAULT_SHOT = 40
const DEFAULT_SHOT_ENABLED = false
const DEFAULT_GAME = 0
const DEFAULT_MATCH = 0
const DEFAULT_TABLE_ALERT = 0

export default function DirectorClockSettingsSection() {
  const queryClient = useQueryClient()
  const [local, setLocal] = useState<DirectorClockSettings | null>(null)

  const { data, isLoading, isError } = useQuery({
    queryKey: ['director-clock-settings'],
    queryFn: directorApi.getClockSettings,
    staleTime: 60000,
  })

  const updateMutation = useMutation({
    mutationFn: (body: Partial<DirectorClockSettings>) => directorApi.updateClockSettings(body),
    onSuccess: (updated) => {
      setLocal(null)
      queryClient.setQueryData(['director-clock-settings'], updated)
      toast.success('Clock settings saved')
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : 'Failed to save clock settings')
    },
  })

  const settings = local ?? data ?? {
    shot_clock_enabled: DEFAULT_SHOT_ENABLED,
    shot_clock_seconds: DEFAULT_SHOT,
    game_clock_minutes: DEFAULT_GAME,
    match_clock_minutes: DEFAULT_MATCH,
    table_time_alert_minutes: DEFAULT_TABLE_ALERT,
  }

  const update = (patch: Partial<DirectorClockSettings>) => {
    if (local) {
      setLocal({ ...local, ...patch })
    } else if (data) {
      setLocal({ ...data, ...patch })
    } else {
      setLocal({
        shot_clock_enabled: DEFAULT_SHOT_ENABLED,
        shot_clock_seconds: DEFAULT_SHOT,
        game_clock_minutes: DEFAULT_GAME,
        match_clock_minutes: DEFAULT_MATCH,
        table_time_alert_minutes: DEFAULT_TABLE_ALERT,
        ...patch,
      })
    }
  }

  const save = () => {
    if (!local) return
    updateMutation.mutate(local)
  }

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading clock settings…</p>
  if (isError) return <p className="text-sm text-destructive">Could not load clock settings.</p>

  const hasChanges = local != null

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <h2 className="text-lg font-semibold text-foreground mb-2">Table clocks (Director)</h2>
      <p className="text-sm text-muted-foreground mb-4">
        Shot clock applies to a player&apos;s turn. Game and match clocks are set per table. Table time alert notifies when a table runs over the limit so you can send a timekeeper.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
        <div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={settings.shot_clock_enabled ?? false}
              onChange={(e) => update({ shot_clock_enabled: e.target.checked })}
              className="rounded border-input"
            />
            <span className="text-sm font-medium text-foreground">Shot clock enabled</span>
          </label>
          <span className="text-xs text-muted-foreground block mt-1">Default off. Enable for timed matches.</span>
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1">Shot clock (seconds)</label>
          <input
            type="number"
            min={10}
            max={120}
            value={settings.shot_clock_seconds}
            onChange={(e) => update({ shot_clock_seconds: Math.max(10, Math.min(120, Number(e.target.value) || 40)) })}
            className="w-full rounded border border-input bg-background px-3 py-2 text-foreground"
            disabled={!settings.shot_clock_enabled}
          />
          <span className="text-xs text-muted-foreground">40s per shot when enabled</span>
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1">Game clock (minutes)</label>
          <input
            type="number"
            min={0}
            max={120}
            value={settings.game_clock_minutes}
            onChange={(e) => update({ game_clock_minutes: Math.max(0, Math.min(120, Number(e.target.value) || 0)) })}
            className="w-full rounded border border-input bg-background px-3 py-2 text-foreground"
          />
          <span className="text-xs text-muted-foreground">0 = off</span>
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1">Match clock (minutes)</label>
          <input
            type="number"
            min={0}
            max={300}
            value={settings.match_clock_minutes}
            onChange={(e) => update({ match_clock_minutes: Math.max(0, Math.min(300, Number(e.target.value) || 0)) })}
            className="w-full rounded border border-input bg-background px-3 py-2 text-foreground"
          />
          <span className="text-xs text-muted-foreground">0 = off</span>
        </div>
        <div>
          <label className="block text-sm font-medium text-foreground mb-1">Table time alert (minutes)</label>
          <input
            type="number"
            min={0}
            max={180}
            value={settings.table_time_alert_minutes}
            onChange={(e) => update({ table_time_alert_minutes: Math.max(0, Math.min(180, Number(e.target.value) || 0)) })}
            className="w-full rounded border border-input bg-background px-3 py-2 text-foreground"
          />
          <span className="text-xs text-muted-foreground">0 = off; alert when table exceeds this</span>
        </div>
      </div>
      {hasChanges && (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={save}
            disabled={updateMutation.isPending}
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
          >
            {updateMutation.isPending ? 'Saving…' : 'Save clock settings'}
          </button>
          <button
            type="button"
            onClick={() => setLocal(null)}
            className="px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-muted"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  )
}
