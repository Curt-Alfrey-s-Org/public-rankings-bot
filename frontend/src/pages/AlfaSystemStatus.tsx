/**
 * Alfa system status — uses /api/alfa/health and dashboard stats aggregate (no legacy latency API).
 */

import React from 'react'
import { Activity, CheckCircle, XCircle } from 'lucide-react'
import { useAlfaSystemHealth, useAlfaDashboardStats } from '@/hooks/useAlfaRatings'
import AlfaMetricCard from '@/components/AlfaMetricCard'

export const AlfaSystemStatus: React.FC = () => {
  const { data: stats, isLoading: statsLoading } = useAlfaDashboardStats()
  const { data: health, isLoading: healthLoading } = useAlfaSystemHealth()
  const loading = statsLoading || healthLoading

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-slate-pool_opt_in">System health</h1>
        <p className="text-slate-400 mt-1">
          Alfa prediction model probe (<span className="font-mono">GET /api/alfa/health</span>) and dashboard aggregates (
          <span className="font-mono">GET /api/alfa/dashboard/stats</span>).
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <AlfaMetricCard
          title="Model"
          value={health?.checks?.model_loaded ? 'Online' : 'Offline'}
          icon={
            health?.checks?.model_loaded ? (
              <CheckCircle className="w-5 h-5 text-emerald-400" />
            ) : (
              <XCircle className="w-5 h-5 text-red-400" />
            )
          }
          color={health?.checks?.model_loaded ? 'success' : 'danger'}
          loading={loading}
        />
        <AlfaMetricCard
          title="DB probe"
          value={health?.checks?.database_connected ? 'OK' : 'Unknown'}
          icon={
            health?.checks?.database_connected ? (
              <CheckCircle className="w-5 h-5 text-emerald-400" />
            ) : (
              <XCircle className="w-5 h-5 text-red-400" />
            )
          }
          color={health?.checks?.database_connected ? 'success' : 'danger'}
          loading={loading}
        />
        <AlfaMetricCard
          title="Predictions today"
          value={stats?.predictions_today ?? 0}
          icon={<Activity className="w-5 h-5" />}
          color="default"
          loading={loading}
        />
        <AlfaMetricCard
          title="Health score"
          value={`${health?.health_score?.toFixed(0) ?? 0}%`}
          icon={<Activity className="w-5 h-5" />}
          color={
            health && health.health_score >= 90 ? 'success' : health && health.health_score >= 70 ? 'warning' : 'danger'
          }
          loading={loading}
        />
      </div>

      <div className="bg-slate-800 rounded-lg border border-slate-700 p-6 text-slate-300 text-sm leading-relaxed">
        <p className="mb-2">
          Detailed API latency histograms, cache byte counters, and per-hour prediction charts are not exposed by the
          current Rankings Bot Alfa routes. Use application logs and Prometheus (if configured for this stack) for deep
          monitoring.
        </p>
      </div>
    </div>
  )
}

export default AlfaSystemStatus
