/**
 * Main Alfa Dashboard Overview Page
 */

import React from 'react'
import { AlertTriangle, Users, Activity } from 'lucide-react'
import { useAlfaDashboardStats, useAlfaSystemHealth } from '@/hooks/useAlfaRatings'
import AlfaMetricCard from '@/components/AlfaMetricCard'
import EditableText from '@/components/EditableText'
import { useUiCustomization } from '@/contexts/UiCustomizationContext'

export const AlfaDashboard: React.FC = () => {
  const { data: stats, isLoading: statsLoading } = useAlfaDashboardStats()
  const { data: health } = useAlfaSystemHealth()

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-4xl font-bold text-slate-pool_opt_in">
          <EditableText
            textKey="alfa.dashboard.title"
            defaultText="Alfa Dashboard"
            className="block"
            inputClassName="bg-transparent border border-sky-500/40 rounded px-1 py-0.5 text-inherit w-full"
          />
        </h1>
        <p className="text-slate-400 mt-2">
          <EditableText
            textKey="alfa.dashboard.subtitle"
            defaultText="Premium rating system overview and monitoring"
            className="block"
            inputClassName="bg-transparent border border-sky-500/40 rounded px-1 py-0.5 text-inherit w-full"
          />
        </p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <AlfaMetricCard
          title="Total Players"
          value={stats?.total_players || 0}
          change={{ value: stats?.total_players || 0, percentage: false }}
          icon={<Users className="w-5 h-5" />}
          color="default"
          loading={statsLoading}
        />
        <AlfaMetricCard
          title="New Players Today"
          value={stats?.new_players || 0}
          icon={<Users className="w-5 h-5" />}
          color="success"
          loading={statsLoading}
        />
        <AlfaMetricCard
          title="Legacy anomaly flags (DB)"
          value={stats?.anomalies_detected || 0}
          icon={<AlertTriangle className="w-5 h-5" />}
          color="default"
          loading={statsLoading}
        />
        <AlfaMetricCard
          title="System Health"
          value={`${(stats?.system_health_score ?? 0).toFixed(0)}%`}
          icon={<Activity className="w-5 h-5" />}
          color={stats != null && (stats.system_health_score ?? 0) >= 90 ? 'success' : 'warning'}
          loading={statsLoading}
        />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Activity (sandbagging/anomaly UI removed Feb 2026) */}
        <div className="lg:col-span-2 bg-slate-800 rounded-lg border border-slate-700 p-6">
          <h2 className="text-xl font-semibold text-slate-pool_opt_in mb-4">
            <EditableText
              textKey="alfa.dashboard.activity.title"
              defaultText="Activity"
              className="block"
              inputClassName="bg-transparent border border-sky-500/40 rounded px-1 py-0.5 text-inherit w-full"
            />
          </h2>
          <div className="space-y-3 text-slate-300 text-sm leading-relaxed">
            <p>
              Sandbagging / anomaly review endpoints were removed from the API (professional WPA/WPBA context).
              Use <span className="text-sky-400 font-mono">predictions_today</span> from dashboard stats for model activity.
            </p>
            <p className="text-slate-400">
              Predictions logged today:{' '}
              <span className="text-slate-pool_opt_in font-semibold">{stats?.predictions_today ?? 0}</span>
            </p>
          </div>
        </div>

        {/* System Status */}
        <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
          <h2 className="text-xl font-semibold text-slate-pool_opt_in mb-4">
            <EditableText
              textKey="alfa.dashboard.status.title"
              defaultText="System Status"
              className="block"
              inputClassName="bg-transparent border border-sky-500/40 rounded px-1 py-0.5 text-inherit w-full"
            />
          </h2>
          <div className="space-y-4">
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-slate-400">Model Status</span>
                <span className={`text-sm font-semibold ${health?.checks?.model_loaded ? 'text-emerald-400' : 'text-red-400'}`}>
                  {health?.checks?.model_loaded ? '✓ Online' : '✗ Offline'}
                </span>
              </div>
            </div>
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-slate-400">Database</span>
                <span className={`text-sm font-semibold ${health?.checks?.database_connected ? 'text-emerald-400' : 'text-red-400'}`}>
                  {health?.checks?.database_connected ? '✓ Online' : '✗ Offline'}
                </span>
              </div>
            </div>
            <div className="pt-4 border-t border-slate-700">
              <p className="text-xs text-slate-500 mb-2">Health Score</p>
              <div className="w-full bg-slate-700 rounded-full h-2 overflow-hidden">
                <div
                  className={`h-full transition-all ${
                    (health?.health_score || 0) >= 90 ? 'bg-emerald-500' :
                    (health?.health_score || 0) >= 70 ? 'bg-yellow-500' :
                    'bg-red-500'
                  }`}
                  style={{ width: `${health?.health_score ?? 0}%` }}
                />
              </div>
              <p className="text-xs text-sky-400 mt-2 font-mono">{(health?.health_score ?? 0).toFixed(0)}%</p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <ActionButton buttonKey="alfa.quick.players" label="View All Players" href="/alfa/players" icon="👥" />
        <ActionButton buttonKey="alfa.quick.system" label="System status" href="/alfa/system" icon="📡" />
        <ActionButton buttonKey="alfa.quick.predictions" label="Predictions & explain" href="/alfa/predictions" icon="🎯" />
        <ActionButton buttonKey="alfa.quick.health" label="System Health" href="/alfa/health" icon="❤️" />
      </div>
    </div>
  )
}

interface ActionButtonProps {
  buttonKey: string
  label: string
  href: string
  icon: string
}

const ActionButton: React.FC<ActionButtonProps> = ({ buttonKey, label, href, icon }) => {
  const { getButton, isEditing, setDraftButton } = useUiCustomization()
  const { label: currentLabel, visible } = getButton(buttonKey, label)

  if (!visible && !isEditing) return null
  if (!visible && isEditing) {
    return (
      <button
        type="button"
        onClick={() => setDraftButton(buttonKey, { visible: true })}
        className="p-4 rounded-lg border border-dashed border-slate-600 text-xs text-slate-300 hover:text-white"
      >
        Add {label}
      </button>
    )
  }

  return (
    <div className="relative">
      {isEditing ? (
        <div className="flex items-center justify-center gap-3 p-4 rounded-lg bg-slate-800 border border-slate-700">
          <span className="text-xl">{icon}</span>
          <input
            type="text"
            value={currentLabel}
            onChange={(e) => setDraftButton(buttonKey, { label: e.target.value })}
            className="bg-transparent border border-sky-500/40 rounded px-1 py-0.5 text-sm font-medium text-slate-200"
          />
        </div>
      ) : (
        <a
          href={href}
          className="flex items-center justify-center gap-3 p-4 rounded-lg bg-slate-800 border border-slate-700 hover:border-sky-500 hover:bg-slate-700 transition-colors"
        >
          <span className="text-xl">{icon}</span>
          <span className="text-sm font-medium text-slate-200">{currentLabel}</span>
        </a>
      )}
      {isEditing && (
        <button
          type="button"
          onClick={() => setDraftButton(buttonKey, { visible: false })}
          className="absolute -top-2 -right-2 bg-slate-900 border border-slate-700 rounded-full w-5 h-5 text-[10px] text-slate-300 hover:text-white"
          aria-label={`Hide ${label}`}
        >
          x
        </button>
      )}
    </div>
  )
}

export default AlfaDashboard
