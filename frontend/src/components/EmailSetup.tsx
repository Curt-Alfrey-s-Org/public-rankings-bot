/**
 * Email Setup component - shown when user logs in with requires_email_setup=true
 * Allows Fargo account users to provide their email address for account activation
 */

import { useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { toast } from '@/lib/toast'

export default function EmailSetup() {
  const { setupEmail, logout } = useAuth()
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    if (!email || !email.trim()) {
      setError('Email address is required')
      setLoading(false)
      return
    }

    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(email.trim())) {
      setError('Please enter a valid email address')
      setLoading(false)
      return
    }

    try {
      const result = await setupEmail(email.trim())
      if (result.success) {
        setSuccess(true)
        toast.success(result.message || 'Email set successfully. Please check your email to verify.')
      } else {
        setError(result.message || 'Failed to set email address')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set email address')
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-background">
        <div className="w-full max-w-md rounded-2xl border border-border bg-card p-8 shadow-2xl shadow-black/20">
          <h1 className="text-2xl font-bold text-foreground text-center mb-4">
            Email Set Successfully
          </h1>
          <p className="text-sm text-muted-foreground text-center mb-6">
            We've sent a verification email to <strong>{email}</strong>. Please check your inbox and click the verification link to complete your account setup.
          </p>
          <p className="text-xs text-muted-foreground text-center">
            After verifying your email, sign in again and you'll be asked to set a new password.
          </p>
          <button
            type="button"
            onClick={() => logout()}
            className="mt-6 w-full py-3 px-4 rounded-xl border border-border bg-card text-foreground font-medium hover:bg-accent transition-colors"
          >
            Back to sign in
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background">
      <div className="w-full max-w-md rounded-2xl border border-border bg-card p-8 shadow-2xl shadow-black/20">
        <h1 className="text-2xl font-bold text-foreground text-center mb-1 tracking-tight">
          Account Setup Required
        </h1>
        <p className="text-sm text-muted-foreground text-center mb-6">
          Please provide your email address to complete your account activation.
        </p>

        {error && (
          <div
            className="mb-4 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-2 text-sm text-destructive"
            role="alert"
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-foreground mb-1">
              Email Address
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              placeholder="your.email@example.com"
              className="w-full px-4 py-2.5 rounded-xl bg-background border border-input text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading || !email.trim()}
            className="w-full py-3 px-4 rounded-xl border border-border bg-card text-foreground font-medium hover:bg-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Setting up...' : 'Continue'}
          </button>
        </form>
      </div>
    </div>
  )
}
