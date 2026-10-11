/**
 * Manual rating adjustments — not implemented as HTTP API (use existing admin/tournament flows).
 */

import React from 'react'

export const AlfaRatingAdjustments: React.FC = () => {
  return (
    <div className="max-w-3xl mx-auto space-y-6 p-6">
      <h1 className="text-3xl font-bold text-slate-pool_opt_in">Rating adjustments</h1>
      <div className="bg-slate-800 border border-amber-700/50 rounded-lg p-6 text-slate-300">
        <p className="mb-2 font-semibold text-amber-200">Not available via API</p>
        <p>
          The legacy dashboard expected <span className="font-mono">/api/alfa/admin/adjustments</span> routes that do not
          exist on this server. Use director/admin tournament and ratings tooling instead.
        </p>
      </div>
    </div>
  )
}

export default AlfaRatingAdjustments
