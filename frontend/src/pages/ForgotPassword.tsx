/**
 * Forgot password — Request a password reset link by email or username.
 * No auth required. Matches login/splash styling.
 */

import { useState, FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { requestPasswordReset } from '@/api/auth'

export default function ForgotPassword() {
  const [emailOrUsername, setEmailOrUsername] = useState('')
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setStatus('idle')
    setMessage('')
    const value = emailOrUsername.trim()
    if (!value) {
      setStatus('error')
      setMessage('Enter your email or username')
      return
    }
    setLoading(true)
    try {
      const res = await requestPasswordReset(value)
      setStatus('success')
      setMessage(res.message || 'If an account exists, a reset link has been sent to your email.')
    } catch (err: unknown) {
      setStatus('error')
      const detail = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
        : null
      setMessage(detail || 'Something went wrong. Please try again later.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black">
      <div className="absolute inset-0 bg-black/40" />
      <div className="relative z-10 w-full max-w-sm mx-auto px-6">
        <div className="bg-slate-900/95 backdrop-blur border border-slate-700 rounded-2xl shadow-2xl p-8">
          <h1 className="text-xl font-bold text-white text-center mb-2">Forgot password?</h1>
          <p className="text-sm text-slate-400 text-center mb-6">
            Enter your email or username. If an account exists, we will send a reset link.
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

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email-or-username" className="block text-sm font-medium text-slate-300 mb-2">
                Email or username
              </label>
              <input
                type="text"
                id="email-or-username"
                value={emailOrUsername}
                onChange={(e) => setEmailOrUsername(e.target.value)}
                autoComplete="username"
                autoFocus
                placeholder="you@example.com or yourusername"
                className="w-full px-4 py-3 rounded-lg bg-slate-800 border border-slate-600 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent"
                disabled={loading}
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 rounded-lg font-semibold text-white bg-sky-600 hover:bg-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:ring-offset-2 focus:ring-offset-slate-900 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? 'Sending...' : 'Send reset link'}
            </button>
          </form>

          <p className="text-center mt-6">
            <Link to="/" className="text-sm text-sky-400 hover:text-sky-300 hover:underline">
              Back to sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
