import { Outlet, NavLink } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'

const settingsNavItems = [
  { path: '/settings', pathEnd: true, label: 'User settings', icon: '👤' },
  { path: '/settings/rankings-assistant', pathEnd: true, label: 'Rankings Assistant', icon: '💬' },
  { path: '/settings/admin', pathEnd: true, label: 'Admin', icon: '🔧', adminOnly: true },
  { path: '/settings/admin/edit-splash', pathEnd: false, label: 'Edit Splash', icon: '🖼️', adminOnly: true },
  { path: '/settings/admin/appearance', pathEnd: false, label: 'Appearance', icon: '🎨', adminOnly: true },
  { path: '/settings/admin/ui-customizations', pathEnd: false, label: 'UI Customizations', icon: '🎛️', adminOnly: true },
  { path: '/settings/admin/system-messages', pathEnd: false, label: 'System & messages', icon: '🖥️', adminOnly: true },
  { path: '/settings/admin/health-logs', pathEnd: false, label: 'Health & logs', icon: '📋', adminOnly: true },
  { path: '/settings/admin/ai-monitor', pathEnd: false, label: 'AI Monitor (website)', icon: '🤖', adminOnly: true },
  {
    path: '/settings/admin/ai-monitor-internal',
    pathEnd: false,
    label: 'AI Monitor (internal)',
    icon: '🔒',
    adminOnly: true,
    superAdminOnly: true,
  },
  {
    path: '/settings/admin/ai-dev-tools',
    pathEnd: false,
    label: 'AI Dev Tools',
    icon: '🛠️',
    adminOnly: true,
    superAdminOnly: true,
  },
]

export default function SettingsLayout() {
  const { user, isAdmin, isSuperAdmin } = useAuth()
  const showAdminNav = isAdmin || isSuperAdmin

  return (
    <div className="flex flex-col h-full bg-black/90 text-foreground overflow-hidden">
      <header className="bg-card/50 backdrop-blur-sm border-b border-border px-6 py-4 flex-shrink-0">
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Your profile and app preferences.
          {showAdminNav
            ? ' Administrators can also open Admin in the list for appearance, messages, and health tools.'
            : ''}
        </p>
        {user && (
          <p className="text-xs text-muted-foreground mt-1" data-testid="settings-role">
            Logged in as <strong>{user.user}</strong> ({user.role.replace('_', ' ')})
          </p>
        )}
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-56 flex-shrink-0 border-r border-border p-4 overflow-y-auto">
          <nav className="space-y-1">
            {settingsNavItems
              .filter((item) => {
                if ('superAdminOnly' in item && item.superAdminOnly && !isSuperAdmin) return false
                return !item.adminOnly || showAdminNav
              })
              .map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.pathEnd}
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
