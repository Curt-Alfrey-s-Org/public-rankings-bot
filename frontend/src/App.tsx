import { Suspense, lazy, useState, type ReactNode } from 'react'
import { createBrowserRouter, RouterProvider, Navigate, Outlet, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Sidebar from '@/components/Sidebar'
import ErrorBoundary from '@/components/ErrorBoundary'
import RouteErrorBoundary from '@/components/RouteErrorBoundary'
import RouteSuspenseFallback from '@/components/RouteSuspenseFallback'
import PageErrorFallback from '@/components/PageErrorFallback'
import VideoBackground from '@/components/VideoBackground'
import SplashLogin from '@/pages/SplashLogin'
import { useAuth, AuthProvider } from '@/contexts/AuthContext'
import { UiCustomizationProvider } from '@/contexts/UiCustomizationContext'
import { AlfaWidgetShell } from '@/components/AlfaWidgetShell'
import UiCustomizationToolbar from '@/components/UiCustomizationToolbar'
import EditableText from '@/components/EditableText'
import LiveUpdatesProvider from '@/components/LiveUpdatesProvider'
import ConnectionStatus from '@/components/ConnectionStatus'
import UpdateRequiredGate from '@/components/UpdateRequiredGate'
import EmailSetup from '@/components/EmailSetup'
import ChangePasswordGate from '@/components/ChangePasswordGate'
import PageLoader from '@/components/PageLoader'
import { Toaster } from 'sonner'
import Home from '@/pages/Home'
import './App.css'

// Lazy load page components (Home is eager so /home works even if lazy chunks 404 after a bad deploy)
const Rankings = lazy(() => import('@/pages/Rankings'))
const TournamentHistory = lazy(() => import('@/pages/TournamentHistory'))
const FutureTournaments = lazy(() => import('@/pages/FutureTournaments'))
const SettingsLayout = lazy(() => import('@/pages/SettingsLayout'))
const UserSettings = lazy(() => import('@/features/admin').then((m) => ({ default: m.UserSettings })))
const SettingsAdmin = lazy(() => import('@/pages/SettingsAdmin'))
const SettingsAdminAppearance = lazy(() => import('@/pages/SettingsAdminAppearance'))
const SettingsAdminUICustomizations = lazy(() => import('@/pages/SettingsAdminUICustomizations'))
const SettingsEditSplash = lazy(() => import('@/pages/SettingsEditSplash'))
const SettingsSystemAndMessages = lazy(() => import('@/pages/SettingsSystemAndMessages'))
const SettingsHealthAndLogs = lazy(() => import('@/pages/SettingsHealthAndLogs'))
const SettingsAIMonitor = lazy(() => import('@/pages/SettingsAIMonitor'))
const SettingsInternalAIMonitor = lazy(() => import('@/pages/SettingsInternalAIMonitor'))
const SettingsRankingsAssistant = lazy(() => import('@/pages/SettingsRankingsAssistant'))
const SettingsAIDevTools = lazy(() => import('@/pages/SettingsAIDevTools'))
const Logs = lazy(() => import('@/pages/Logs'))
const DataInput = lazy(() => import('@/pages/DataInput'))
const TournamentWizard = lazy(() => import('@/pages/TournamentWizard'))
const TournamentWizardLayout = lazy(() => import('@/pages/TournamentWizardLayout'))
const TournamentRegistration = lazy(() => import('@/pages/TournamentRegistration'))
const PlayerManagement = lazy(() => import('@/pages/PlayerManagement'))
const PlayerPerformance = lazy(() => import('@/pages/PlayerPerformance'))
const Bracket = lazy(() => import('@/pages/Bracket'))
const Leaderboard = lazy(() => import('@/pages/Leaderboard'))
const HotStreak = lazy(() => import('@/pages/HotStreak'))
const Leagues = lazy(() => import('@/pages/Leagues'))
const Tours = lazy(() => import('@/pages/Tours'))
const TestCenter = lazy(() => import('@/pages/TestCenter'))
const AICoach = lazy(() => import('@/features/ai-coach').then((m) => ({ default: m.AICoachPage })))
const HeadToHead = lazy(() => import('@/features/head-to-head').then((m) => ({ default: m.HeadToHeadPage })))
const Rules = lazy(() => import('@/pages/Rules'))
const Register = lazy(() => import('@/pages/Register'))
const VerifyEmailPage = lazy(() => import('@/pages/VerifyEmailPage'))
const AlfaChatPopupPage = lazy(() => import('@/pages/AlfaChatPopupPage'))

// Create QueryClient instance — live-update defaults (app is not I/O/CPU heavy)
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 0, // Data is stale immediately so refetches can run
      gcTime: 1000 * 60 * 2, // 2 minutes (formerly cacheTime)
      refetchOnWindowFocus: true, // Refetch when user returns to tab
      retry: 3,
      retryDelay: (attempt) => Math.min(1000 * (2 ** attempt), 30000),
    },
  },
})

// RequireAdmin component for route protection
function RequireAdmin({ children }: { children: ReactNode }) {
  const { isAdmin, isSuperAdmin } = useAuth()
  if (isAdmin || isSuperAdmin) return <>{children}</>
  return <Navigate to="/settings" replace />
}

// RequireSuperAdmin: only super_admin can access (e.g. Leagues, Tours — hidden from others)
function RequireSuperAdmin({ children }: { children: ReactNode }) {
  const { isSuperAdmin } = useAuth()
  if (isSuperAdmin) return <>{children}</>
  return <Navigate to="/rankings" replace />
}

// RequireDirectorOrAdmin: director, admin, or super_admin can access (e.g. New Tournament)
function RequireDirectorOrAdmin({ children }: { children: ReactNode }) {
  const { isDirector, isAdmin, isSuperAdmin } = useAuth()
  if (isDirector || isAdmin || isSuperAdmin) return <>{children}</>
  return <Navigate to="/rankings" replace />
}

/** Routes shown without forcing SplashLogin (unauthenticated). */
function isPublicAuthPath(pathname: string): boolean {
  const seg = pathname.replace(/\/+$/, '').split('/').filter(Boolean)
  const last = seg[seg.length - 1] || ''
  return last === 'register' || last === 'verify-email'
}

// Layout component that provides the main app structure
function AppLayout() {
  const location = useLocation()
  const { user, isLoading: authLoading, logout, requires_email_setup, must_change_password, force_password_reset, isAdmin } = useAuth()
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    // Start closed on mobile/tablet (< lg), open on desktop (>= 1024px)
    if (typeof window !== 'undefined') {
      return window.innerWidth >= 1024
    }
    return true
  })
  const [appearance] = useState({
    theme: localStorage.getItem('theme') || 'dark',
    videoBackground: localStorage.getItem('videoBackground') === 'true',
  })

  if (authLoading) {
    return <PageLoader />
  }

  if (!user) {
    if (isPublicAuthPath(location.pathname)) {
      return (
        <div className="min-h-[100dvh] bg-slate-950 text-white">
          <Suspense fallback={<RouteSuspenseFallback />}>
            <Outlet />
          </Suspense>
        </div>
      )
    }
    return <SplashLogin />
  }

  // Show email setup if required (Fargo first-login: set email before anything else)
  if (requires_email_setup) {
    return <EmailSetup />
  }

  // Force a password change when required (bootstrap users, or pro accounts after
  // email verification sets force_password_reset). Backend returns these flags on login.
  if (must_change_password || force_password_reset) {
    return <ChangePasswordGate />
  }

  const handleSidebarToggle = () => {
    setSidebarOpen(!sidebarOpen)
  }

  return (
    <AlfaWidgetShell>
    <div className="flex flex-col h-screen h-[100dvh] bg-slate-950 text-white overflow-hidden dark">
      {appearance.videoBackground && <VideoBackground />}

      {/* Mobile/Tablet Header - Visible on small and tablet (up to lg), with sidebar toggle */}
      <header className="w-screen lg:hidden fixed top-0 left-0 right-0 bg-slate-950 border-b border-slate-800 flex items-center px-4 z-40 shadow-lg mobile-header-safe">
        <button
          onClick={handleSidebarToggle}
          className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center hover:bg-slate-800 text-slate-50 rounded-lg transition-colors flex-shrink-0"
          aria-label="Toggle menu"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
            {sidebarOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
        <div className="flex-1 text-center">
          <h1 className="font-semibold text-sm text-slate-50">
            <EditableText
              textKey="app.mobile.title"
              defaultText="Rankings Bot"
              className="block"
              inputClassName="bg-transparent border border-sky-500/40 rounded px-1 py-0.5 text-inherit w-full"
            />
          </h1>
        </div>
        <button
          onClick={() => {
            logout()
          }}
          className="p-2 min-h-[44px] min-w-[44px] flex items-center justify-center hover:bg-slate-800 text-slate-50 rounded-lg transition-colors flex-shrink-0"
          aria-label="Sign out"
          title="Sign out"
        >
          <span className="text-lg">🚪</span>
        </button>
      </header>

      {/* Main Layout */}
      <div className="flex flex-1 main-content-offset lg:pt-0 overflow-hidden min-h-0">
        <Sidebar isOpen={sidebarOpen} onToggle={handleSidebarToggle} />

        {/* Floating menu button when sidebar closed on desktop */}
        {!sidebarOpen && (
          <button
            onClick={handleSidebarToggle}
            className="hidden lg:flex fixed left-4 top-4 z-40 p-2.5 rounded-lg bg-slate-800/90 hover:bg-slate-700 border border-slate-600 shadow-lg transition-colors"
            aria-label="Open menu"
            title="Open menu"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        )}

        {/* Sidebar overlay - click to close on mobile/tablet */}
        {sidebarOpen && (
          <div
            className="lg:hidden fixed inset-0 bg-black/50 z-30 sidebar-overlay-top"
            onClick={handleSidebarToggle}
            aria-hidden="true"
          />
        )}

        <main className="flex-1 overflow-auto transition-all duration-300 w-full min-h-0 app-main-scroll main-with-alfa-dock">
        <ErrorBoundary fallback={<PageErrorFallback />} showDetails={isAdmin}>
          <Suspense fallback={<RouteSuspenseFallback />}>
            <Outlet />
          </Suspense>
        </ErrorBoundary>
      </main>
      </div>
      <div className="fixed z-50 connection-status-position">
        <ConnectionStatus />
      </div>
      <UiCustomizationToolbar />
    </div>
    </AlfaWidgetShell>
  )
}

// Create routes configuration
const createRoutes = () => [
  {
    path: '/alfa-chat',
    element: (
      <RouteErrorBoundary>
        <Suspense fallback={<RouteSuspenseFallback />}>
          <AlfaChatPopupPage />
        </Suspense>
      </RouteErrorBoundary>
    ),
  },
  {
    path: "/",
    element: <AppLayout />,
    children: [
      {
        index: true,
        element: <Navigate to="/home" replace />,
      },
      {
        path: "register",
        element: (
          <RouteErrorBoundary>
            <Register />
          </RouteErrorBoundary>
        ),
      },
      {
        path: "verify-email",
        element: (
          <RouteErrorBoundary>
            <VerifyEmailPage />
          </RouteErrorBoundary>
        ),
      },
      {
        path: "home",
        element: <RouteErrorBoundary><Home /></RouteErrorBoundary>,
      },
      {
        path: "dashboard",
        element: <Navigate to="/home" replace />,
      },
      {
        path: "my-stats",
        element: <Navigate to="/player-performance" replace />,
      },
      {
        path: "rankings",
        element: <RouteErrorBoundary><Rankings /></RouteErrorBoundary>,
      },
      {
        path: "tournament-history",
        element: <RouteErrorBoundary><TournamentHistory /></RouteErrorBoundary>,
      },
      {
        path: "future-tournaments",
        element: <RouteErrorBoundary><FutureTournaments /></RouteErrorBoundary>,
      },
      {
        path: "test-center",
        element: <RouteErrorBoundary><RequireDirectorOrAdmin><TestCenter /></RequireDirectorOrAdmin></RouteErrorBoundary>,
      },
      {
        path: "tournament-wizard",
        element: <RouteErrorBoundary><RequireDirectorOrAdmin><TournamentWizardLayout /></RequireDirectorOrAdmin></RouteErrorBoundary>,
        children: [
          {
            index: true,
            element: <RouteErrorBoundary><TournamentWizard /></RouteErrorBoundary>,
          },
          {
            path: "data-input",
            element: <RouteErrorBoundary><DataInput /></RouteErrorBoundary>,
          },
          {
            path: "bracket",
            element: <RouteErrorBoundary><Bracket /></RouteErrorBoundary>,
          },
          {
            path: "players",
            element: <RouteErrorBoundary><PlayerManagement /></RouteErrorBoundary>,
          },
        ],
      },
      {
        path: "tournaments/register",
        element: <RouteErrorBoundary><TournamentRegistration /></RouteErrorBoundary>,
      },
      {
        path: "player-performance",
        element: <RouteErrorBoundary><PlayerPerformance /></RouteErrorBoundary>,
      },
      {
        path: "head-to-head",
        element: <RouteErrorBoundary><HeadToHead /></RouteErrorBoundary>,
      },
      {
        path: "per-tournament-rankings",
        element: <Navigate to="/tournament-history" replace />,
      },
      {
        path: "leaderboard",
        element: <RouteErrorBoundary><Leaderboard /></RouteErrorBoundary>,
      },
      {
        path: "hot-streak",
        element: <RouteErrorBoundary><HotStreak /></RouteErrorBoundary>,
      },
      {
        path: "leagues",
        element: <RouteErrorBoundary><RequireSuperAdmin><Leagues /></RequireSuperAdmin></RouteErrorBoundary>,
      },
      {
        path: "tours",
        element: <RouteErrorBoundary><RequireSuperAdmin><Tours /></RequireSuperAdmin></RouteErrorBoundary>,
      },
      {
        path: "ai-coach",
        element: <RouteErrorBoundary><AICoach /></RouteErrorBoundary>,
      },
      {
        path: "rules",
        element: <RouteErrorBoundary><Rules /></RouteErrorBoundary>,
      },
      {
        path: "settings",
        element: <RouteErrorBoundary><SettingsLayout /></RouteErrorBoundary>,
        children: [
          {
            index: true,
            element: <RouteErrorBoundary><UserSettings /></RouteErrorBoundary>,
          },
          {
            path: "rankings-assistant",
            element: (
              <RouteErrorBoundary>
                <SettingsRankingsAssistant />
              </RouteErrorBoundary>
            ),
          },
          {
            path: "admin",
            element: <RouteErrorBoundary><RequireAdmin><SettingsAdmin /></RequireAdmin></RouteErrorBoundary>,
          },
          {
            path: "admin/edit-splash",
            element: <RouteErrorBoundary><RequireAdmin><SettingsEditSplash /></RequireAdmin></RouteErrorBoundary>,
          },
          {
            path: "admin/appearance",
            element: <RouteErrorBoundary><RequireAdmin><SettingsAdminAppearance /></RequireAdmin></RouteErrorBoundary>,
          },
          {
            path: "admin/ui-customizations",
            element: <RouteErrorBoundary><RequireAdmin><SettingsAdminUICustomizations /></RequireAdmin></RouteErrorBoundary>,
          },
          {
            path: "admin/system-messages",
            element: <RouteErrorBoundary><RequireAdmin><SettingsSystemAndMessages /></RequireAdmin></RouteErrorBoundary>,
          },
          {
            path: "admin/health-logs",
            element: <RouteErrorBoundary><RequireAdmin><SettingsHealthAndLogs /></RequireAdmin></RouteErrorBoundary>,
          },
          {
            path: "admin/ai-monitor",
            element: <RouteErrorBoundary><RequireAdmin><SettingsAIMonitor /></RequireAdmin></RouteErrorBoundary>,
          },
          {
            path: "admin/ai-monitor-internal",
            element: (
              <RouteErrorBoundary>
                <RequireSuperAdmin>
                  <SettingsInternalAIMonitor />
                </RequireSuperAdmin>
              </RouteErrorBoundary>
            ),
          },
          {
            path: "admin/ai-dev-tools",
            element: (
              <RouteErrorBoundary>
                <RequireSuperAdmin>
                  <SettingsAIDevTools />
                </RequireSuperAdmin>
              </RouteErrorBoundary>
            ),
          },
        ],
      },
      {
        path: "system",
        element: <Navigate to="/settings/admin/system-messages" replace />,
      },
      {
        path: "logs",
        element: <RouteErrorBoundary><Logs /></RouteErrorBoundary>,
      },
      {
        path: "data-input",
        element: <Navigate to="/tournament-wizard/data-input" replace />,
      },
      {
        path: "bracket",
        element: <Navigate to="/tournament-wizard/bracket" replace />,
      },
      {
        path: "players",
        element: <Navigate to="/tournament-wizard/players" replace />,
      },
      {
        path: "movement",
        element: <Navigate to="/rankings" replace />,
      },
      {
        path: "*",
        element: <Navigate to="/rankings" replace />,
      },
    ],
  },
]

// Create the router with future flags enabled
const router = createBrowserRouter(createRoutes(), {
  future: {
    v7_startTransition: true,
    v7_relativeSplatPath: true,
    v7_fetcherPersist: true,
    v7_normalizeFormMethod: true,
    v7_partialHydration: true,
    v7_skipActionErrorRevalidation: true,
  },
})

export default function App() {
  return (
    <ErrorBoundary fallback={
      <div style={{ color: 'white', padding: '20px', maxWidth: '480px' }}>
        <h2 style={{ marginBottom: '0.5rem' }}>Something went wrong</h2>
        <p style={{ color: '#94a3b8', marginBottom: '1rem' }}>An error occurred. Try refreshing the page (Ctrl+Shift+R) or clearing site data.</p>
        <button onClick={() => window.location.reload()} style={{ padding: '0.5rem 1rem', cursor: 'pointer', background: '#0ea5e9', border: 'none', borderRadius: '6px', color: 'white' }}>Refresh page</button>
      </div>
    }>
      <QueryClientProvider client={queryClient}>
        <UpdateRequiredGate>
          <AuthProvider>
            <UiCustomizationProvider>
              <LiveUpdatesProvider>
                <RouterProvider router={router} />
                <Toaster richColors position="top-right" />
              </LiveUpdatesProvider>
            </UiCustomizationProvider>
          </AuthProvider>
        </UpdateRequiredGate>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}

