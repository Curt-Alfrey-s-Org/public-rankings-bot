/**
 * Generic page skeleton for routes without a custom skeleton
 * Used as Suspense fallback for lazy-loaded pages
 */

export default function PageSkeleton() {
  return (
    <div
      className="flex flex-col items-center justify-center min-h-[40vh] gap-4 px-4"
      role="status"
      aria-label="Loading page"
    >
      <div className="w-full max-w-md space-y-4 animate-pulse">
        <div className="h-8 bg-slate-700 rounded w-3/4" />
        <div className="h-4 bg-slate-700/60 rounded w-full" />
        <div className="h-4 bg-slate-700/60 rounded w-5/6" />
        <div className="h-4 bg-slate-700/40 rounded w-4/5" />
        <div className="flex gap-3 pt-4">
          <div className="h-10 bg-slate-700 rounded-lg w-24" />
          <div className="h-10 bg-slate-700/60 rounded-lg w-32" />
        </div>
      </div>
    </div>
  )
}
