import { useState, useEffect } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import FailDetailsPopup from './FailDetailsPopup'
import ModuleLights from './ModuleLights'
import { systemApi, type RunTestsResponse, type SystemHealthResponse } from '@/api/system'
import { useAuth } from '@/contexts/AuthContext'
import { useUiCustomization } from '@/contexts/UiCustomizationContext'
import EditableText from '@/components/EditableText'

/** Shape health self_test for Fail Details popup (built-in API checks). */
function healthToLastTestResult(health: SystemHealthResponse): RunTestsResponse | null {
  const st = health?.self_test
  if (!st || !Array.isArray(st.results)) return null
  const failed_tests = st.results
    .filter((r: { passed?: boolean }) => !r.passed)
    .map((r: { name: string; error?: string }) => ({ name: r.name, passed: false, error: r.error }))
  const total = st.total ?? 0
  const passed = st.passed_count ?? 0
  const failed = st.failed_count ?? failed_tests.length
  const durationMs = st.timings?.total_duration_ms ?? 0
  return {
    success: st.passed ?? false,
    total,
    passed,
    failed,
    warnings: 0,
    duration_s: durationMs / 1000,
    failed_tests: failed_tests.length > 0 ? failed_tests : undefined,
    timestamp: new Date().toISOString(),
    source: 'health',
  }
}

interface SidebarProps {
  isOpen: boolean
  onToggle: () => void
  avatarUrl?: string
  /** When true, hide avatar (none for pics). */
  avatarNone?: boolean
}

const DEFAULT_AVATAR = '/assets/avatar-default.png'

export default function Sidebar({ isOpen, onToggle, avatarUrl = DEFAULT_AVATAR, avatarNone = false }: SidebarProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user, logout, isAdmin, isSuperAdmin, isDirector } = useAuth()
  const { isEditing, getButton, setDraftButton } = useUiCustomization()
  const [showFailDetails, setShowFailDetails] = useState(false)

  // Fetch system health for status indicators (admin+ only)
  const { data: health } = useQuery({
    queryKey: ['system-health'],
    queryFn: systemApi.getHealth,
    enabled: !!user && isAdmin,
    refetchInterval: 120000, // Refresh every 2 minutes for health status
    retry: 1,
    retryDelay: 1000,
    staleTime: 10000,
  })

  // Sync health self-check results into query cache for Fail Details popup.
  useEffect(() => {
    if (!health) return
    const lastResult = healthToLastTestResult(health)
    if (lastResult) {
      queryClient.setQueryData(['last-test-result'], lastResult)
    }
  }, [health, queryClient])

  const selfTestPassed =
    health?.self_test?.passed === true ? true : health?.self_test?.passed === false ? false : null
  const passedCount = health?.self_test?.passed_count
  const totalCount = health?.self_test?.total

  // Rankings App: primary menu (rankings-first). Data Input, Bracket, Players under New Tournament; Register under Future Tournaments.
  const menuItems = [
    { key: 'nav.home', path: '/home', label: 'Home', icon: '🏠', title: 'Start here — news links and shortcuts' },
    { key: 'nav.rankings', path: '/rankings', label: 'Rankings', icon: '🏆', title: 'WPBA, WPA, Heyball, and Artistic standings' },
    { key: 'nav.tournament_history', path: '/tournament-history', label: 'Tournament History', icon: '📜', title: 'Past events, finishes, and filters' },
    { key: 'nav.future_tournaments', path: '/future-tournaments', label: 'Future Tournaments', icon: '📅', title: 'Upcoming events and registration' },
    { key: 'nav.test_center', path: '/test-center', label: 'Test Center', icon: '🔧', title: 'Practice tournaments and bracket testing', directorOrAdminOnly: true },
    { key: 'nav.tournament_wizard', path: '/tournament-wizard', label: 'New Tournament', icon: '🎯', title: 'Set up a tournament, enter results, run a bracket', directorOrAdminOnly: true },
    { key: 'nav.player_performance', path: '/player-performance', label: 'Player Performance', icon: '📊', title: 'Stats, charts, and history for you or a player you follow' },
    { key: 'nav.head_to_head', path: '/head-to-head', label: 'Head-to-Head', icon: '⚔️', title: 'Side-by-side comparison of two players' },
    { key: 'nav.leaderboard', path: '/leaderboard', label: 'Leaderboard', icon: '🏅', title: 'Points leaders and recent tour results' },
    { key: 'nav.hot_streak', path: '/hot-streak', label: 'Hot Streak', icon: '🔥', title: 'Who is climbing the fastest lately' },
    { key: 'nav.leagues', path: '/leagues', label: 'Leagues', icon: '🏟️', title: 'Leagues and team standings' },
    { key: 'nav.tours', path: '/tours', label: 'Tours', icon: '🗓️', title: 'Multi-stop tours and series points' },
    { key: 'nav.ai_coach', path: '/ai-coach', label: 'AI Coach', icon: '🎱', title: 'Video feedback on your game' },
    { key: 'nav.rules_license_points', path: '/rules', label: 'Rules, License, & Points', icon: '📋', title: 'Official rules, licenses, and how points work' },
    { key: 'nav.settings', path: '/settings', label: 'Settings', icon: '⚙️', title: 'Your account and preferences' },
  ]

  return (
    <aside
      className={`fixed lg:static left-0 lg:top-auto top-16 lg:top-0 h-[calc(100vh-64px)] lg:h-full bg-card/95 backdrop-blur-md border-r border-border shadow-xl transition-all duration-300 z-30 lg:z-50 ${
        isOpen ? 'w-64 max-w-[85vw]' : 'w-0 overflow-hidden'
      }`}
      aria-label="Main navigation"
    >
      <div className="h-full flex flex-col">
        {/* Sidebar Header - Hidden on mobile/tablet (header is in top bar) */}
        <div className="hidden lg:flex p-4 border-b border-border items-center justify-between gap-2">
          <button
            type="button"
            onClick={onToggle}
            className="p-2 -ml-2 hover:bg-accent rounded-lg transition-colors flex-shrink-0"
            title="Collapse menu"
            aria-label="Collapse menu"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          <div className="flex items-center gap-3 min-w-0 flex-1">
            {!avatarNone && user && (
              <Link 
                to="/settings"
                className="flex flex-col items-center gap-1 group cursor-pointer hover:opacity-80 transition-opacity"
                title="View Profile"
              >
                <span className="text-[10px] text-muted-foreground group-hover:text-foreground transition-colors font-medium truncate max-w-[60px]">
                  {user.user}
                </span>
                <img
                  src={avatarUrl}
                  alt={`${user.user}'s avatar`}
                  className="w-9 h-9 rounded-full object-cover flex-shrink-0 border-2 border-border shadow-inner group-hover:border-primary group-hover:shadow-lg transition-all"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = DEFAULT_AVATAR
                  }}
                />
              </Link>
            )}
            {!avatarNone && !user && (
              <img
                src={avatarUrl}
                alt="Avatar"
                className="w-9 h-9 rounded-full object-cover flex-shrink-0 border-2 border-border shadow-inner"
                onError={(e) => {
                  (e.target as HTMLImageElement).src = DEFAULT_AVATAR
                }}
              />
            )}
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-foreground truncate tracking-tight">
                <EditableText
                  textKey="sidebar.title"
                  defaultText="Rankings"
                  className="block"
                  inputClassName="bg-transparent border border-sky-500/40 rounded px-1 py-0.5 text-inherit w-full"
                />
              </h2>
              <p className="text-[11px] text-muted-foreground truncate">
                <EditableText
                  textKey="sidebar.subtitle"
                  defaultText="WPBA & WPA"
                  className="block"
                  inputClassName="bg-transparent border border-sky-500/40 rounded px-1 py-0.5 text-inherit w-full"
                />
              </p>
            </div>
          </div>
          {user && (
            <button
              type="button"
              onClick={() => {
                logout()
                navigate('/rankings')
              }}
              className="p-2 hover:bg-accent rounded-lg transition-colors flex-shrink-0"
              title="Sign out"
              aria-label="Sign out"
            >
              <span className="text-lg">🚪</span>
            </button>
          )}
        </div>

        {/* Navigation - visible when sidebar is open */}
        {true && (
          <nav className={`flex-1 p-4 space-y-2 overflow-y-auto touch-scroll ${!isOpen ? 'hidden' : ''}`}>
            {menuItems.map((item) => {
              // Leagues and Tours: only show for super_admin (focus on WPBA, WPA m/w, Heyball m/w rankings for now)
              if ((item.key === 'nav.leagues' || item.key === 'nav.tours') && !isSuperAdmin) return null
              // New Tournament: only show for director, admin, or super_admin
              if (item.directorOrAdminOnly && !isDirector && !isAdmin && !isSuperAdmin) return null
              // Test tournament: only show for super_admin
              if (item.adminOnly && !isAdmin && !isSuperAdmin) return null
              if (item.superAdminOnly && !isSuperAdmin) return null
              const isTournamentWizard = item.key === 'nav.tournament_wizard' && (location.pathname === '/tournament-wizard' || location.pathname.startsWith('/tournament-wizard/'))
              const isFutureTournaments = item.key === 'nav.future_tournaments' && (location.pathname === '/future-tournaments' || location.pathname.startsWith('/future-tournaments/'))
              const isHeadToHead = item.key === 'nav.head_to_head' && (location.pathname === '/head-to-head' || location.pathname.startsWith('/head-to-head'))
              const isActive = isTournamentWizard || isFutureTournaments || isHeadToHead || location.pathname === item.path
              const navItem = getButton(item.key, item.label)
              if (!navItem.visible && !isEditing) return null
              if (!navItem.visible && isEditing) {
                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => setDraftButton(item.key, { visible: true })}
                    className="w-full text-left px-4 py-2.5 rounded-lg border border-dashed border-slate-700 text-xs text-slate-400 hover:text-white"
                  >
                    Add {item.label}
                  </button>
                )
              }
              const content = (
                <div
                  className={`flex items-center gap-3 px-4 py-3 md:py-2.5 min-h-[48px] md:min-h-[40px] rounded-lg transition-all duration-200 text-sm md:text-base ${
                    isActive
                      ? 'bg-primary text-primary-foreground shadow-sm'
                      : 'hover:bg-accent/80 text-foreground'
                  }`}
                >
                  <span className="text-lg opacity-90 flex-shrink-0">{item.icon}</span>
                  {isEditing ? (
                    <input
                      type="text"
                      value={navItem.label}
                      onChange={(e) => setDraftButton(item.key, { label: e.target.value })}
                      className="bg-transparent border border-sky-500/40 rounded px-1 py-0.5 text-sm font-medium text-foreground"
                    />
                  ) : (
                    <span className="font-medium text-sm">{navItem.label}</span>
                  )}
                </div>
              )

              return (
                <div key={item.key} className="relative">
                  {isEditing ? (
                    content
                  ) : (
                    <Link
                      to={item.path}
                      title={item.title}
                      onClick={() => window.innerWidth < 1024 && isOpen && onToggle()}
                    >
                      {content}
                    </Link>
                  )}
                  {isEditing && (
                    <button
                      type="button"
                      onClick={() => setDraftButton(item.key, { visible: false })}
                      className="absolute -top-2 -right-2 bg-slate-900 border border-slate-700 rounded-full w-5 h-5 text-[10px] text-slate-300 hover:text-white"
                      aria-label={`Hide ${item.label}`}
                    >
                      x
                    </button>
                  )}
                </div>
              )
            })}
          </nav>
        )}

        {/* Footer with Status Indicators - visible when sidebar is open */}
        {true && (
          <div className={`p-4 border-t border-border ${!isOpen ? 'hidden' : ''}`}>
            {/* Self-Test Status (admin+ only) */}
            {isAdmin && (
              <div className="mb-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-muted-foreground">Self-Test:</span>
                  <div className="flex items-center gap-2">
                    {selfTestPassed === true && (
                      <div className="flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" title="All tests passed"></div>
                        <span className="text-xs text-green-500">PASS</span>
                      </div>
                    )}
                    {selfTestPassed === false && (
                      <div className="flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-red-500" title="Some tests failed"></div>
                        <span className="text-xs text-red-500">FAIL</span>
                      </div>
                    )}
                    {selfTestPassed === null && (
                      <div className="flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-yellow-500 animate-pulse" title="Testing..."></div>
                        <span className="text-xs text-yellow-500">...</span>
                      </div>
                    )}
                  </div>
                </div>
                {(passedCount != null && totalCount != null) && (
                  <div className="text-[10px] text-muted-foreground/70 mb-1">
                    {passedCount}/{totalCount} passed
                    {health?.self_test?.timings != null && ` • ${Number(health.self_test.timings.total_duration_ms).toFixed(0)}ms`}
                  </div>
                )}
                <button
                  onClick={() => setShowFailDetails(true)}
                  className="w-full mt-1 px-2 py-1 text-[10px] bg-muted/50 hover:bg-muted text-muted-foreground rounded transition-colors"
                  title="Show popup of test fail details for analysis (view-only)"
                >
                  View Fail Details
                </button>
              </div>
            )}

            {/* Module Lights (super_admin only) */}
            {isSuperAdmin && (
              <div className="mb-3">
                <ModuleLights />
              </div>
            )}
            
            {/* System Info */}
            <div className="text-sm text-muted-foreground">
              <p>Rankings</p>
              <p className="text-xs mt-1">v1.0.0</p>
            </div>
          </div>
        )}
      </div>

      {/* Fail Details Popup */}
      <FailDetailsPopup isOpen={showFailDetails} onClose={() => setShowFailDetails(false)} />
    </aside>
  )
}
