/**
 * Health Dashboard - API status, DB latency, Redis, uptime, error logs.
 * Manual Fargo scrape moved to Settings > Admin.
 */

import { useQuery } from '@tanstack/react-query'
import { healthApi, type HealthDetailedResponse } from '@/api/health'

function formatUptime(seconds: number) {
  if (seconds < 60) return `${Math.round(seconds)}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  return `${d}d ${h}h`
}

function StatusBadge({ status, label }: { status: string; label?: string }) {
  const colors: Record<string, string> = {
    healthy: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50',
    degraded: 'bg-amber-500/20 text-amber-400 border-amber-500/50',
    unhealthy: 'bg-red-500/20 text-red-400 border-red-500/50',
    not_configured: 'bg-slate-600/20 text-slate-400 border-slate-600/50',
    not_available: 'bg-slate-600/20 text-slate-400 border-slate-600/50',
    skipped: 'bg-slate-600/20 text-slate-400 border-slate-600/50',
  }
  const c = colors[status] ?? 'bg-slate-600/20 text-slate-400'
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium border ${c}`}>
      {label ?? status}
    </span>
  )
}

export function HealthDashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['health-detailed'],
    queryFn: async () => {
      const { data: res } = await healthApi.getDetailed()
      return res
    },
    refetchInterval: 30_000,
  })

  if (isLoading) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-slate-700 rounded w-1/3" />
          <div className="h-48 bg-slate-800 rounded" />
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <div className="rounded-lg border border-red-800 bg-red-900/20 p-6 text-red-200">
          <h2 className="text-lg font-semibold">Failed to load health status</h2>
          <p className="mt-2 text-sm">{error instanceof Error ? error.message : 'Unknown error'}</p>
        </div>
      </div>
    )
  }

  const h = data as HealthDetailedResponse
  const grafanaBaseUrl = import.meta.env.VITE_GRAFANA_BASE_URL as string | undefined
  const prometheusBaseUrl = import.meta.env.VITE_PROMETHEUS_BASE_URL as string | undefined

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <header>
        <h1 className="text-2xl font-bold text-white">Health & Monitoring</h1>
        <p className="mt-1 text-slate-400">
          API status, database latency, Redis connection, and uptime
        </p>
      </header>

      {/* Summary row */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">API Status</p>
          <p className="mt-2">
            <StatusBadge status={h.status} />
          </p>
        </div>
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Uptime</p>
          <p className="mt-2 text-lg font-semibold text-white">
            {h.uptime_seconds != null ? formatUptime(h.uptime_seconds) : '—'}
          </p>
        </div>
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Auth DB</p>
          <p className="mt-2 flex items-center gap-2">
            <StatusBadge status={h.database?.status ?? 'unknown'} />
            {h.database?.latency_ms != null && (
              <span className="text-sm text-slate-400">{h.database.latency_ms} ms</span>
            )}
          </p>
        </div>
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Rankings DB</p>
          <p className="mt-2 flex items-center gap-2">
            <StatusBadge status={h.rankings_db?.status ?? 'unknown'} />
            {h.rankings_db?.latency_ms != null && (
              <span className="text-sm text-slate-400">{h.rankings_db.latency_ms} ms</span>
            )}
          </p>
        </div>
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Redis</p>
          <p className="mt-2 flex items-center gap-2">
            <StatusBadge
              status={h.redis?.status ?? 'unknown'}
              label={h.redis?.status === 'not_configured' ? 'Optional' : undefined}
            />
            {h.redis?.latency_ms != null && (
              <span className="text-sm text-slate-400">{h.redis.latency_ms} ms</span>
            )}
          </p>
          {h.redis?.status === 'not_configured' && (
            <p className="mt-1 text-xs text-slate-500">Only needed for Celery task queue</p>
          )}
        </div>
      </div>

      {/* Auth database details */}
      {h.database?.error && (
        <div className="rounded-lg border border-amber-800 bg-amber-900/20 p-4">
          <h3 className="font-medium text-amber-200">Auth Database Error</h3>
          <p className="mt-1 font-mono text-sm text-slate-300">{h.database.error}</p>
        </div>
      )}

      {/* Rankings DB details */}
      {h.rankings_db?.error && h.rankings_db.status !== 'skipped' && (
        <div className="rounded-lg border border-amber-800 bg-amber-900/20 p-4">
          <h3 className="font-medium text-amber-200">Rankings DB Error</h3>
          <p className="mt-1 font-mono text-sm text-slate-300">{h.rankings_db.error}</p>
        </div>
      )}

      {/* Redis details */}
      {h.redis?.error && h.redis.status !== 'not_configured' && (
        <div className="rounded-lg border border-amber-800 bg-amber-900/20 p-4">
          <h3 className="font-medium text-amber-200">Redis Error</h3>
          <p className="mt-1 font-mono text-sm text-slate-300">{h.redis.error}</p>
        </div>
      )}

      {/* Advanced monitoring links */}
      {(grafanaBaseUrl || prometheusBaseUrl) && (
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-6">
          <h2 className="mb-4 text-lg font-semibold text-white">Advanced Monitoring</h2>
          <p className="mb-4 text-sm text-slate-400">
            Detailed metrics, dashboards, and historical data for API performance, containers, database, and system resources.
          </p>
          <div className="flex flex-wrap gap-3">
            {grafanaBaseUrl && (
              <>
                <a
                  href={`${grafanaBaseUrl}/d/rankings_bot_overview`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-700/50 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 hover:border-slate-500"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  System Overview
                </a>
                <a
                  href={`${grafanaBaseUrl}/d/rankings_bot_api`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-700/50 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 hover:border-slate-500"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  API Performance
                </a>
                <a
                  href={grafanaBaseUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-700/50 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 hover:border-slate-500"
                >
                  <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                  </svg>
                  Grafana Home
                </a>
              </>
            )}
            {prometheusBaseUrl && (
              <a
                href={prometheusBaseUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-700/50 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 hover:border-slate-500"
              >
                <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 17a1 1 0 102 0V9a1 1 0 10-2 0v8zm-4 0a1 1 0 102 0v-4a1 1 0 10-2 0v4zm8 0a1 1 0 102 0v-6a1 1 0 10-2 0v6zM5 21h14a2 2 0 002-2V5a2 2 0 00-2-2h-4m-6 0H5a2 2 0 00-2 2v14a2 2 0 002 2h4m0-18h6" />
                </svg>
                Prometheus
              </a>
            )}
          </div>
        </div>
      )}

      <p className="text-xs text-slate-500">
        Last updated: {h.timestamp} · Service: {h.service} v{h.version}
      </p>
    </div>
  )
}
