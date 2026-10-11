/**
 * Skeleton loader for Home page
 * Matches the layout of hero, ALFa section, app capabilities, and news cards
 */

export default function HomeSkeleton() {
  return (
    <div className="flex flex-col min-h-full bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto space-y-8 sm:space-y-10 md:space-y-12 animate-pulse">
          {/* Hero */}
          <header className="pt-2">
            <div className="h-10 bg-slate-700 rounded w-3/4 mb-2" />
            <div className="h-4 bg-slate-700/60 rounded w-1/2" />
          </header>

          {/* ALFa section */}
          <section className="rounded-2xl border border-slate-700/40 bg-slate-800/40 p-6 md:p-8">
            <div className="flex items-start gap-4 mb-6">
              <div className="w-16 h-16 md:w-20 md:h-20 rounded-full bg-slate-700" />
              <div className="flex-1 space-y-2">
                <div className="h-8 bg-slate-700 rounded w-1/3" />
                <div className="h-4 bg-slate-700/60 rounded w-full" />
                <div className="h-4 bg-slate-700/60 rounded w-4/5" />
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 md:gap-4">
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <div key={i} className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/30">
                  <div className="h-6 w-8 bg-slate-700 rounded mb-2" />
                  <div className="h-4 bg-slate-700/60 rounded w-3/4 mb-1" />
                  <div className="h-3 bg-slate-700/40 rounded w-full" />
                </div>
              ))}
            </div>
          </section>

          {/* App Capabilities */}
          <section>
            <div className="h-6 bg-slate-700 rounded w-48 mb-4" />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-4 bg-slate-700/60 rounded w-full" />
                ))}
              </div>
              <div className="space-y-2">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-4 bg-slate-700/60 rounded w-full" />
                ))}
              </div>
            </div>
          </section>

          {/* News cards */}
          <section>
            <div className="h-6 bg-slate-700 rounded w-24 mb-4" />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {[1, 2].map((i) => (
                <div key={i} className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/40">
                  <div className="flex items-start gap-3">
                    <div className="h-8 w-8 bg-slate-700 rounded" />
                    <div className="flex-1 space-y-2">
                      <div className="h-4 bg-slate-700 rounded w-2/3" />
                      <div className="h-3 bg-slate-700/60 rounded w-1/2" />
                      <div className="h-3 bg-slate-700/40 rounded w-full" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
