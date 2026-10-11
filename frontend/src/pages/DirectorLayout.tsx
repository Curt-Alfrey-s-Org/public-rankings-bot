import { Outlet, NavLink, Navigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'

const directorNavItems = [
  { path: '/director/instructions', label: 'How it works', icon: '📖', title: 'Director instructions and key rules (WPBA/WPA)' },
  { path: '/director/data-input', label: 'Data input', icon: '📥', title: 'Enter or upload rankings and tournament data (Director/Admin)' },
  { path: '/director/bracket', label: 'Director mode', icon: '🎬', title: 'Bracket, tables, call table, DQ, assign, enter scores' },
  { path: '/director/timekeeper', label: 'Time keeper', icon: '⏱️', title: 'All tables — tap for full details' },
  { path: '/director/scorekeeper', label: 'Score keeper mode', icon: '📟', title: 'My table — enter scores and run timers' },
  { path: '/director/new', label: 'New Tournament', icon: '🎯', title: 'Create a new tournament (Tournament Wizard)' },
  { path: '/director/players', label: 'Tournament Player Management', icon: '👥', title: 'Manage tournament players' },
]

export default function DirectorLayout() {
  const { isDirector, isAdmin, isSuperAdmin, isScoreKeeper } = useAuth()
  const canAccess = isDirector || isAdmin || isSuperAdmin || isScoreKeeper

  if (!canAccess) {
    return <Navigate to="/tournaments" replace />
  }

  return (
    <div className="flex flex-col h-full bg-black/90 text-foreground overflow-hidden">
      <header className="bg-card/50 backdrop-blur-sm border-b border-border px-6 py-4 flex-shrink-0">
        <h1 className="text-2xl font-bold">Tournament Director</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Data input, director mode, score keeper, new tournament, and player management
        </p>
        <div className="md:hidden mt-3 p-3 rounded-lg bg-amber-500/15 border border-amber-500/40 text-amber-200 text-sm">
          <strong>Small screen:</strong> Tournament Director tools work best on a tablet or desktop. Use a larger screen or browser for full features.
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-56 flex-shrink-0 border-r border-border p-4 overflow-y-auto">
          <nav className="space-y-1">
            {directorNavItems.map((item) => (
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
