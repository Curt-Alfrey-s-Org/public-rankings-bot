/**
 * Module status lights for super_admin.
 * Shows backend, api, frontend, database, http, network.
 * Colors: green (ok), yellow (loading), red (down).
 */

import { useQuery } from '@tanstack/react-query'
import { systemApi } from '@/api/system'

const MODULE_ORDER = ['backend', 'api', 'frontend', 'database', 'http', 'network'] as const

function LightDot({ status, label, message }: { status: 'ok' | 'loading' | 'down'; label: string; message: string }) {
  const colorClass =
    status === 'ok'
      ? 'bg-green-500'
      : status === 'loading'
        ? 'bg-yellow-500 animate-pulse'
        : 'bg-red-500'
  const title = `${label}: ${message}`
  return (
    <div
      className="flex flex-col items-center gap-0.5"
      title={title}
    >
      <div
        className={`w-2.5 h-2.5 rounded-full ${colorClass}`}
        aria-label={title}
      />
      <span className="text-[9px] text-muted-foreground uppercase tracking-wider">{label}</span>
    </div>
  )
}

export default function ModuleLights() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['module-lights'],
    queryFn: () => systemApi.getModuleLights(),
    refetchInterval: 10000, // 10s
    staleTime: 5000,
    retry: 0, // Don't retry on failure
    throwOnError: false, // Gracefully handle errors
  })

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-muted/30">
        <div className="w-2.5 h-2.5 rounded-full bg-yellow-500 animate-pulse" />
        <span className="text-[10px] text-muted-foreground">Loading...</span>
      </div>
    )
  }

  if (isError || !data?.modules) {
    return (
      <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-muted/30">
        <div className="w-2.5 h-2.5 rounded-full bg-red-500" title="Lights unavailable" />
        <span className="text-[10px] text-muted-foreground">Lights</span>
      </div>
    )
  }

  const modules = data.modules
  return (
    <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 px-2 py-1.5 rounded-lg bg-muted/30">
      {MODULE_ORDER.map((key) => {
        const m = modules[key]
        if (!m) return null
        return (
          <LightDot
            key={key}
            status={m.status}
            label={key}
            message={m.message || ''}
          />
        )
      })}
    </div>
  )
}
