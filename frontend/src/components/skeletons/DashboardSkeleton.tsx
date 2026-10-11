/**
 * Skeleton loader for Dashboard page
 * Matches widget grid layout
 */

export default function DashboardSkeleton() {
  return (
    <div className="flex flex-col min-h-full bg-slate-950 animate-pulse">
      <div className="p-4 sm:p-6 md:p-8 space-y-6">
        <div className="space-y-2">
          <div className="h-8 bg-slate-700 rounded w-48" />
          <div className="h-4 bg-slate-700/60 rounded w-3/4 max-w-md" />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-slate-800/60 border border-slate-700/40 rounded-lg p-6">
              <div className="h-5 bg-slate-700 rounded w-1/3 mb-4" />
              <div className="space-y-3">
                <div className="h-4 bg-slate-700/60 rounded w-full" />
                <div className="h-4 bg-slate-700/60 rounded w-5/6" />
                <div className="h-4 bg-slate-700/40 rounded w-4/5" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
