import { Outlet, NavLink } from 'react-router-dom'

const tournamentsNavItems = [
  { path: '/tournaments/history', label: 'Tournament History', icon: '📜', title: 'Browse tournament history and player records' },
  { path: '/tournaments/upcoming', label: 'Future Tournaments', icon: '🌐', title: 'Future WPA and WPBA events with full details' },
  { path: '/tournaments/current', label: 'Current Tournaments', icon: '📋', title: 'View, edit, and delete current tournaments' },
  { path: '/tournaments/bracket', label: 'Bracket', icon: '🌳', title: 'View bracket and enter match scores' },
  { path: '/tournaments/leaderboard', label: 'Leaderboard', icon: '🏅', title: 'Tournament leaderboard and player statistics' },
]

export default function TournamentsLayout() {
  return (
    <div className="flex flex-col h-full bg-black/90 text-foreground overflow-hidden">
      <header className="bg-card/50 backdrop-blur-sm border-b border-border px-6 py-4 flex-shrink-0">
        <h1 className="text-2xl font-bold">Tournaments</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          History, upcoming events, bracket, and leaderboard
        </p>
        {/* Shown only on narrow viewports (phone). Directors: use tablet or browser for wizard and director tools. */}
        <div className="md:hidden mt-3 p-3 rounded-lg bg-amber-500/15 border border-amber-500/40 text-amber-200 text-sm">
          <strong>Small screen:</strong> For director tools (Wizard, Director mode, Score keeper), use the <strong>Tournament Director</strong> menu or a tablet or desktop.
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-56 flex-shrink-0 border-r border-border p-4 overflow-y-auto">
          <nav className="space-y-1">
            {tournamentsNavItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
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
