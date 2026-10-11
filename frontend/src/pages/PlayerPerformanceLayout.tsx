import { Outlet, NavLink } from 'react-router-dom'

const playerPerformanceNavItems = [
  { path: '/player-performance', pathEnd: true, label: 'Overview', icon: '📊', title: 'Player statistics, ranking history, and tournament results' },
]

export default function PlayerPerformanceLayout() {
  return (
    <div className="flex flex-col h-full bg-black/90 text-foreground overflow-hidden">
      <header className="bg-card/50 backdrop-blur-sm border-b border-border px-6 py-4 flex-shrink-0">
        <h1 className="text-2xl font-bold">Player Performance</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Player statistics, ranking history, and tournament results (Movement is in the main menu)
        </p>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-56 flex-shrink-0 border-r border-border p-4 overflow-y-auto">
          <nav className="space-y-1">
            {playerPerformanceNavItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.pathEnd}
                title={item.title}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-primary text-primary-foreground'
                      : 'text-foreground hover:bg-accent'
                  }`
                }
              >
                <span className="text-lg opacity-90">{item.icon}</span>
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </aside>

        <main className="flex-1 overflow-y-auto min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
