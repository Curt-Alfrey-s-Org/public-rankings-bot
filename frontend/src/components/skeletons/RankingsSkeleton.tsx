/**
 * Skeleton loader for Rankings page
 * Matches the layout of hero, stats cards, search bar, and table
 */

export default function RankingsSkeleton() {
  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-50">
      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="max-w-7xl mx-auto space-y-4 sm:space-y-6">
          {/* Hero section skeleton */}
          <section className="rounded-2xl border-2 border-slate-700/40 bg-slate-800/40 p-4 sm:p-6 md:p-8 animate-pulse">
            <div className="text-center mb-6">
              <div className="h-8 bg-slate-700 rounded w-3/4 mx-auto mb-2" />
              <div className="h-4 bg-slate-700/60 rounded w-1/2 mx-auto" />
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-2 sm:gap-3 max-w-5xl mx-auto">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="h-14 bg-slate-700/60 rounded-xl" />
              ))}
            </div>
          </section>

          {/* Stats cards skeleton */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-slate-800/60 border border-slate-700/40 rounded-xl p-4 animate-pulse">
                <div className="h-3 bg-slate-700 rounded w-1/3 mb-2" />
                <div className="h-8 bg-slate-700 rounded w-1/2 mb-1" />
                <div className="h-3 bg-slate-700/60 rounded w-2/3" />
              </div>
            ))}
          </div>

          {/* Header + refresh button skeleton */}
          <div className="bg-slate-800/60 border border-slate-700/40 rounded-xl p-4 sm:p-6 animate-pulse">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div className="space-y-2">
                <div className="h-10 bg-slate-700 rounded w-2/3" />
                <div className="h-4 bg-slate-700/60 rounded w-1/2" />
                <div className="h-3 bg-slate-700/40 rounded w-1/3" />
              </div>
              <div className="h-12 bg-slate-700 rounded-lg w-40" />
            </div>
          </div>

          {/* Search + export skeleton */}
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1 h-11 bg-slate-800 rounded-lg animate-pulse" />
            <div className="h-11 bg-slate-800 rounded-lg w-32 animate-pulse" />
          </div>

          {/* Table skeleton */}
          <div className="bg-slate-800/40 border border-slate-700/40 rounded-xl overflow-hidden animate-pulse">
            <div className="border-b-2 border-slate-700 p-4">
              <div className="flex gap-4">
                {[1, 2, 3, 4, 5, 6].map((i) => (
                  <div key={i} className="h-4 bg-slate-700 rounded w-16" />
                ))}
              </div>
            </div>
            <div className="divide-y divide-slate-700/40">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((i) => (
                <div key={i} className="flex items-center gap-4 p-4">
                  <div className="h-5 w-8 bg-slate-700 rounded" />
                  <div className="h-4 flex-1 max-w-[200px] bg-slate-700/60 rounded" />
                  <div className="h-4 w-16 bg-slate-700/60 rounded" />
                  <div className="h-4 w-12 bg-slate-700/60 rounded" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
