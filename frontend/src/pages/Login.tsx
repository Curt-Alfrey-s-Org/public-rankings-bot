/**
 * Login page: Single sign-in with role resolution.
 * Shows "Up & running" when the API is ready for users to log in.
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/contexts/AuthContext'
import { healthApi } from '@/api/health'
import { loginFeaturesApi, type FeatureItem } from '@/api/loginFeatures'

export default function Login() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const { data: health, isSuccess: healthOk, isLoading: healthLoading } = useQuery({
    queryKey: ['login-page-health'],
    queryFn: async () => {
      const { data } = await healthApi.getBasic()
      return data
    },
    retry: 2,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  })
  const isReady = healthOk && health?.status === 'healthy'

  const { data: featuresData } = useQuery({
    queryKey: ['login-features', 'short'],
    queryFn: () => loginFeaturesApi.get('short'),
    staleTime: 60_000,
    retry: 1,
  })
  const shortList: FeatureItem[] = featuresData?.short?.length ? featuresData.short : []

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const result = await login(username, password)
      if (!result.success) {
        setError(result.message || 'Invalid username or password')
      }
    } catch (e: unknown) {
      setError('Invalid username or password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-8 shadow-2xl shadow-black/20">
        <h1 className="text-2xl font-bold text-foreground text-center mb-1 tracking-tight">
          Rankings
        </h1>
        <p className="text-sm text-muted-foreground text-center mb-2">
          Sign in to view WPBA & WPA rankings
        </p>

        {/* Site in work message */}
        <div className="mb-4 rounded-lg border border-amber-200/50 bg-amber-50/10 dark:border-amber-800/50 dark:bg-amber-950/20 px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse"></div>
            <p className="text-sm font-medium text-amber-700 dark:text-amber-400">
              Site in work — New features being added regularly
            </p>
          </div>
        </div>

        <p className="text-xs font-medium text-muted-foreground mb-1.5">What you get</p>
        <ul className="text-[11px] text-muted-foreground text-left space-y-1 mb-4 list-none max-h-[32vh] overflow-y-auto pr-1" aria-label="Features">
          {shortList.map((item, i) => (
            <li key={`${item.title}-${i}`}>
              <strong className="text-foreground">{item.title}</strong> — {item.description}
            </li>
          ))}
        </ul>
        {isReady && (
          <p className="text-xs text-center mb-4 text-emerald-500 dark:text-emerald-400 font-medium" role="status">
            Up & running
          </p>
        )}
        {healthLoading && (
          <p className="text-xs text-center mb-4 text-muted-foreground" role="status">
            Checking…
          </p>
        )}

        {error && (
          <div
            className="mb-4 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-2 text-sm text-destructive"
            role="alert"
          >
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label htmlFor="username" className="block text-sm font-medium text-foreground mb-1">
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              className="w-full px-4 py-2.5 rounded-xl bg-background border border-input text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-foreground mb-1">
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              className="w-full px-4 py-2.5 rounded-xl bg-background border border-input text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="••••••••"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 px-4 rounded-xl border border-border bg-card text-foreground font-medium hover:bg-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? '…' : 'Sign in'}
          </button>
        </form>
      </div>
      <p className="text-xs text-muted-foreground text-center">
        Built by{' '}
        <a href="https://alfaqd.com" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
          Example Example
        </a>
        {' · '}
        <a href="https://alfaqd.com" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
          alfaqd.com
        </a>
        {' · '}
        <a href="https://github.com/example-owner-s-Org" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
          GitHub
        </a>
        {' · '}
        <a href="https://x.com/example" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
          X
        </a>
        {' — '}
        Self-hosted · custom cloud & web
      </p>
    </div>
  )
}
