/**
 * Modal shown after login when email is not verified.
 * Explains that the user should check their email for the verification link
 * and that verification is needed for Forgot password.
 */

import { useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { Link } from 'react-router-dom'
import { logger } from '@/lib/logger'

const DISMISS_KEY = 'email_verification_modal_dismissed'

export default function EmailVerificationModal() {
  const { emailVerified, user } = useAuth()
  const [dismissed, setDismissed] = useState(() => {
    try {
      return sessionStorage.getItem(DISMISS_KEY) === '1'
    } catch (error) {
      logger.warn('Failed to read email verification modal dismiss state', undefined, error as Error)
      return false
    }
  })

  // Don't show if verified, dismissed, or not logged in
  if (emailVerified || dismissed || !user) return null

  const handleDismiss = () => {
    try {
      sessionStorage.setItem(DISMISS_KEY, '1')
    } catch (error) {
      logger.warn('Failed to persist email verification modal dismiss state', undefined, error as Error)
    }
    setDismissed(true)
  }

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-labelledby="email-verification-title"
      aria-modal="true"
    >
      <div className="w-full max-w-md rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-xl">
        <h2 id="email-verification-title" className="text-xl font-semibold text-white mb-2">
          Confirm your email
        </h2>
        <p className="text-sm text-slate-400 mb-4">
          Please check your inbox and click the verification link we sent when you registered. If you
          don&apos;t see it, check your spam folder.
        </p>
        <p className="text-sm text-slate-400 mb-4">
          Verification is required to use &quot;Forgot password&quot; and for account notifications.
        </p>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/settings"
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90"
          >
            User Settings (resend email)
          </Link>
          <button
            type="button"
            onClick={handleDismiss}
            className="px-4 py-2 rounded-lg border border-slate-600 text-slate-300 text-sm font-medium hover:bg-slate-800"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  )
}
