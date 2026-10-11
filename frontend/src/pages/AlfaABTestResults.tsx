/**
 * A/B testing dashboard — no public API in this deployment.
 */

import React from 'react'

export const AlfaABTestResults: React.FC = () => {
  return (
    <div className="max-w-3xl mx-auto space-y-6 p-6">
      <h1 className="text-3xl font-bold text-slate-pool_opt_in">A/B testing results</h1>
      <div className="bg-slate-800 border border-slate-600 rounded-lg p-6 text-slate-300">
        <p>
          Model A/B comparison metrics are not exposed via <span className="font-mono text-sky-400">/api/alfa</span>{' '}
          in this deployment. Use offline evaluation notebooks or add a dedicated admin endpoint if needed.
        </p>
      </div>
    </div>
  )
}

export default AlfaABTestResults
