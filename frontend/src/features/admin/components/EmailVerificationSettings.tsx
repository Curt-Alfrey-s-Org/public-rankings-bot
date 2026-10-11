/**
 * Email verification status and resend - shown for all authenticated users in User Settings.
 */

import { useState, useEffect } from 'react'
import { usersApi } from '@/api/users'
import { resendVerification } from '@/api/auth'
import { toast } from '@/lib/toast'

export function EmailVerificationSettings() {
  const [emailVerified, setEmailVerified] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)

  useEffect(() => {
    usersApi
      .getProfile()
      .then((p) => setEmailVerified(p.email_verified))
      .catch(() => setEmailVerified(null))
      .finally(() => setLoading(false))
  }, [])

  const handleResend = async () => {
    setSending(true)
    try {
      const res = await resendVerification()
      toast.success(res.message ?? 'Verification email sent.')
      setEmailVerified(false) // Still unverified until they click the link
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string }; status?: number }; message?: string }
      const msg = ax?.response?.data?.detail ?? ax?.message ?? 'Failed to send verification email'
      toast.error(typeof msg === 'string' ? msg : 'Failed to send verification email')
    } finally {
      setSending(false)
    }
  }

  if (loading || emailVerified === null) {
    return (
      <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <h3 className="text-lg font-semibold text-white mb-2">Email verification</h3>
        <p className="text-sm text-slate-400">Loading…</p>
      </div>
    )
  }

  return (
    <div
      className="rounded-lg border border-slate-700 bg-slate-800/50 p-4"
      title="View email verification status and resend verification email."
    >
      <h3 className="text-lg font-semibold text-white mb-2">Email verification</h3>
      {emailVerified ? (
        <p className="text-sm text-slate-400">
          <span className="text-green-500"> verified</span> — Your email address has been verified.
        </p>
      ) : (
        <>
          <p className="text-sm text-slate-400 mb-3">
            Your email is not yet verified. Verification is required for &quot;Forgot password&quot; and account
            notifications. Check your inbox (and spam folder) for the verification link.
          </p>
          <button
            type="button"
            onClick={handleResend}
            disabled={sending}
            className="px-3 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {sending ? 'Sending…' : 'Send verification email'}
          </button>
        </>
      )}
    </div>
  )
}
