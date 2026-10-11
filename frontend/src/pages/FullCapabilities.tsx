/**
 * Full Software Capabilities — long feature list (editable by super_admin).
 * Linked from Home as "Full Software Capabilities".
 */

import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { loginFeaturesApi, type FeatureItem } from '@/api/loginFeatures'

export default function FullCapabilities() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['login-features', 'full'],
    queryFn: () => loginFeaturesApi.get('full'),
    staleTime: 60_000,
  })
  const fullList: FeatureItem[] = data?.full?.length ? data.full : []

  return (
    <div className="flex flex-col min-h-full bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-50">
      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="max-w-3xl mx-auto">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-primary mb-4"
          >
            ← Back to Home
          </Link>
          <h1 className="text-2xl sm:text-3xl font-bold text-white mb-2">
            Full Software Capabilities
          </h1>
          <p className="text-slate-400 text-sm mb-6">
            Everything the app can do. This list is editable by super admin in Settings → Admin.
          </p>
          {isLoading && (
            <p className="text-slate-400">Loading…</p>
          )}
          {error && (
            <p className="text-amber-400">Could not load list. Try again later.</p>
          )}
          {!isLoading && !error && fullList.length === 0 && (
            <p className="text-slate-400">No capabilities listed yet.</p>
          )}
          {!isLoading && fullList.length > 0 && (
            <ul className="space-y-3 sm:space-y-4" aria-label="Full capabilities">
              {fullList.map((item, i) => (
                <li
                  key={`${item.title}-${i}`}
                  className="p-4 rounded-xl bg-slate-800/60 border border-slate-700"
                >
                  <strong className="text-white block mb-1">{item.title}</strong>
                  <span className="text-sm text-slate-400">{item.description}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
