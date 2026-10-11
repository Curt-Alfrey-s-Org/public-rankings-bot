/**
 * Login form for Pro Billiards Software.
 * Self-service registration is at `/register` (see SplashLogin copy).
 */

import { useState, FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { logger } from '@/lib/logger'

interface LoginFormProps {
  onSubmit: (username: string, password: string) => Promise<{ success: boolean; message?: string }>
  onSuccess: () => void
  /** No title/subtitle; tighter card; labels screen-reader only (splash overlay). */
  variant?: 'default' | 'minimal'
}

export default function LoginForm({ onSubmit, onSuccess, variant = 'default' }: LoginFormProps) {
  useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    if (!username.trim()) {
      setError('Username is required')
      return
    }
    if (!password) {
      setError('Password is required')
      return
    }
    setLoading(true)
    try {
      const res = await onSubmit(username.trim(), password)
      if (res.success) {
        onSuccess()
      } else {
        setError(res.message || 'Invalid username or password')
      }
    } catch (error) {
      logger.error('Login submission failed unexpectedly', error as Error, { username: username.trim() })
      setError('Login failed')
    } finally {
      setLoading(false)
    }
  }

  const isMinimal = variant === 'minimal'

  return (
    <form
      onSubmit={handleSubmit}
      className={`w-full max-w-sm mx-auto bg-slate-900/95 backdrop-blur border border-slate-700 rounded-2xl shadow-2xl ${
        isMinimal ? 'p-4 sm:p-5' : 'p-8'
      }`}
    >
      {!isMinimal && (
        <div className="text-center mb-6">
          <h2 className="text-xl font-bold text-white">Pro Billiards Software</h2>
          <p className="mt-2 text-[11px] sm:text-xs font-medium uppercase tracking-wide text-amber-200/90">
            Official software of the{' '}
            <a
              href="https://example.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-amber-pool_opt_in hover:text-white underline-offset-2 hover:underline focus:outline-none focus:ring-2 focus:ring-sky-500/50 rounded"
            >
              USPBF
            </a>
          </p>
        </div>
      )}

      {error && (
        <div className="mb-4 px-4 py-3 rounded-lg bg-red-500/20 text-red-400 border border-red-500/30 text-sm">
          {error}
        </div>
      )}

      <div className={isMinimal ? 'space-y-3' : 'space-y-4'}>
        <div>
          <label
            htmlFor="username"
            className={isMinimal ? 'sr-only' : 'block text-sm font-medium text-slate-300 mb-2'}
          >
            Username
          </label>
          <input
            type="text"
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoFocus
            placeholder={isMinimal ? 'Username' : undefined}
            className={`w-full rounded-lg bg-slate-800 border border-slate-600 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent ${
              isMinimal ? 'px-3 py-2.5 text-sm' : 'px-4 py-3'
            }`}
            disabled={loading}
          />
        </div>
        <div>
          <label
            htmlFor="password"
            className={isMinimal ? 'sr-only' : 'block text-sm font-medium text-slate-300 mb-2'}
          >
            Password
          </label>
          <input
            type="password"
            id="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            placeholder="••••••••"
            className={`w-full rounded-lg bg-slate-800 border border-slate-600 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent ${
              isMinimal ? 'px-3 py-2.5 text-sm' : 'px-4 py-3'
            }`}
            disabled={loading}
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className={`w-full rounded-lg font-semibold text-white bg-sky-600 hover:bg-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-900 disabled:opacity-50 disabled:cursor-not-allowed transition-colors ${
            isMinimal ? 'py-2.5 px-3 text-sm' : 'py-3 px-4'
          }`}
        >
          {loading ? 'Signing in...' : 'Sign In'}
        </button>
        <p className={`text-center flex flex-wrap items-center justify-center gap-x-3 gap-y-1 ${isMinimal ? 'mt-2' : 'mt-4'}`}>
          <Link
            to="/register"
            className={
              isMinimal
                ? 'text-[11px] text-amber-200/90 hover:text-amber-pool_opt_in hover:underline'
                : 'text-sm text-amber-200/90 hover:text-amber-pool_opt_in hover:underline'
            }
          >
            New account (coming soon)
          </Link>
          <Link
            to="/forgot-password"
            className={
              isMinimal
                ? 'text-[11px] text-sky-400/90 hover:text-sky-300 hover:underline'
                : 'text-sm text-sky-400 hover:text-sky-300 hover:underline'
            }
          >
            Forgot password?
          </Link>
        </p>
      </div>
    </form>
  )
}
