/**
 * Anomaly review UI removed — server endpoints retired Feb 2026 (professional context).
 */

import React from 'react'

export const AlfaAnomalyAlerts: React.FC = () => {
  return (
    <div className="max-w-3xl mx-auto space-y-6 p-6">
      <h1 className="text-3xl font-bold text-slate-pool_opt_in">Anomaly alerts</h1>
      <div className="bg-slate-800 border border-slate-600 rounded-lg p-6 text-slate-300 leading-relaxed">
        <p className="mb-3">
          Sandbagging / anomaly detection dashboards and HTTP endpoints were removed from the Rankings Bot API.
          WPA/WPBA professional events are treated as non-handicapped competition; variance in finishes is expected.
        </p>
        <p className="text-sm text-slate-500">
          See backend notes in <span className="font-mono text-slate-400">api/routes/alfa_ratings.py</span> and project docs.
        </p>
      </div>
    </div>
  )
}

export default AlfaAnomalyAlerts
