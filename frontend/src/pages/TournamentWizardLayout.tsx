/**
 * New Tournament layout: Create, Data Input, Bracket, Player Management.
 * Tabs navigate between sub-views. IAW navigation restructure.
 */

import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'

const tabs: Array<{ path: string; label: string; icon: string; directorOnly?: boolean }> = [
  { path: '', label: 'Create', icon: '🎯' },
  { path: 'data-input', label: 'Data Input', icon: '📥', directorOnly: true },
  { path: 'bracket', label: 'Bracket', icon: '🌳' },
  { path: 'players', label: 'Players', icon: '👥' },
]

export default function TournamentWizardLayout() {
  const { isDirector, isAdmin } = useAuth()
  const canSeeDataInput = isDirector || isAdmin

  return (
    <div className="flex-1 overflow-auto bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      <div className="sticky top-0 z-10 bg-slate-900/95 backdrop-blur border-b border-slate-700">
        <div className="max-w-7xl mx-auto px-4 md:px-6 py-3">
          <h1 className="text-2xl md:text-3xl font-bold text-white mb-3">New Tournament</h1>
          <nav className="flex flex-wrap gap-2" role="tablist" aria-label="New Tournament sections">
            {tabs.map(({ path, label, icon, directorOnly }) => {
              if (directorOnly && !canSeeDataInput) return null
              const to = path ? `/tournament-wizard/${path}` : '/tournament-wizard'
              return (
                <NavLink
                  key={path || 'create'}
                  to={to}
                  end={!path}
                  className={({ isActive }) =>
                    `px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700 hover:text-white'
                    }`
                  }
                >
                  <span className="mr-1.5">{icon}</span>
                  {label}
                </NavLink>
              )
            })}
          </nav>
        </div>
      </div>
      <div className="max-w-7xl mx-auto p-4 md:p-6">
        <Outlet />
      </div>
    </div>
  )
}
