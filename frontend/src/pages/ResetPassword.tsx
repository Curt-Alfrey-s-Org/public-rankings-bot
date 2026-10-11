/**
 * Reset password — Set new password using token from email link.
 * No auth required. Route: /reset-password?token=...
 */

import { useState, FormEvent, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { resetPassword } from '@/api/auth'

const PASSWORD_RULES = '8+ characters with uppercase, lowercase, number, and special character'

export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') ?? ''

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!token.trim()) {
      setStatus('error')
      setMessage('Invalid reset link. Please use the link from your email or request a new one.')
    }
  }, [token])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setStatus('idle')
    setMessage('')
    if (!token.trim()) {
      setStatus('error')
      setMessage('Invalid reset link. Please request a new one.')
      return
    }
    if (password !== confirm) {
      setStatus('error')
      setMessage('Passwords do not match.')
      return
    }
    if (password.length < 8) {
      setStatus('error')
      setMessage(`Password must be ${PASSWORD_RULES}.`)
      return
    }
    setLoading(true)
    try {
      const res = await resetPassword(token, password)
      setStatus('success')
      setMessage(res.message || 'Password updated. You can now sign in.')
    } catch (err: unknown) {
      setStatus('error')
      const detail = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : null
      setMessage(detail || 'Something went wrong. Please request a new reset link.')
    } finally {
      setLoading(false)
    }
  }

  if (!token.trim()) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black">
        <div className="absolute inset-0 bg-black/40" />
        <div className="relative z-10 w-full max-w-sm mx-auto px-6">
          <div className="bg-slate-900/95 backdrop-blur border border-slate-700 rounded-2xl shadow-2xl p-8">
            <h1 className="text-xl font-bold text-white text-center mb-4">Reset password</h1>
            <div className="mb-4 px-4 py-3 rounded-lg bg-red-500/20 text-red-400 border border-red-500/30 text-sm">
              {message}
            </div>
            <p className="text-center">
              <Link to="/forgot-password" className="text-sm text-sky-400 hover:text-sky-300 hover:underline">
                Request a new reset link
              </Link>
            </p>
            <p className="text-center mt-4">
              <Link to="/" className="text-sm text-sky-400 hover:text-sky-300 hover:underline">
                Back to sign in
              </Link>
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black">
      <div className="absolute inset-0 bg-black/40" />
      <div className="relative z-10 w-full max-w-sm mx-auto px-6">
        <div className="bg-slate-900/95 backdrop-blur border border-slate-700 rounded-2xl shadow-2xl p-8">
          <h1 className="text-xl font-bold text-white text-center mb-2">Set new password</h1>
          <p className="text-sm text-slate-400 text-center mb-6">
            Password must be {PASSWORD_RULES}.
          </p>

          {status === 'success' && (
            <div className="mb-4 px-4 py-3 rounded-lg bg-green-500/20 text-green-400 border border-green-500/30 text-sm">
              {message}
            </div>
          )}
          {status === 'error' && (
            <div className="mb-4 px-4 py-3 rounded-lg bg-red-500/20 text-red-400 border border-red-500/30 text-sm">
              {message}
            </div>
          )}

          {status !== 'success' && (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="password" className="block text-sm font-medium text-slate-300 mb-2">
                  New password
                </label>
                <input
                  type="password"
                  id="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                  autoFocus
                  placeholder="••••••••"
                  className="w-full px-4 py-3 rounded-lg bg-slate-800 border border-slate-600 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent"
                  disabled={loading}
                />
              </div>
              <div>
                <label htmlFor="confirm" className="block text-sm font-medium text-slate-300 mb-2">
                  Confirm password
                </label>
                <input
                  type="password"
                  id="confirm"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  autoComplete="new-password"
                  placeholder="••••••••"
                  className="w-full px-4 py-3 rounded-lg bg-slate-800 border border-slate-600 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent"
                  disabled={loading}
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 px-4 rounded-lg font-semibold text-white bg-sky-600 hover:bg-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-900 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? 'Updating...' : 'Reset password'}
              </button>
            </form>
          )}

          {status === 'success' && (
            <p className="text-center mt-4">
              <Link
                to="/"
                className="inline-block py-2 px-4 rounded-lg font-medium text-white bg-sky-600 hover:bg-sky-500"
              >
                Sign in
              </Link>
            </p>
          )}

          {status !== 'success' && (
            <p className="text-center mt-6">
              <Link to="/" className="text-sm text-sky-400 hover:text-sky-300 hover:underline">
                Back to sign in
              </Link>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
