/**
 * Verify Email page — reads token from URL, auto-verifies on load via GET.
 * On error: shows message and form to request a new verification email.
 */

import { useEffect, useState, FormEvent } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import apiClient from '@/api/client'
import styles from '@/styles/VerifyEmail.module.css'

const REDIRECT_SECONDS = 3
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export default function VerifyEmailPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')
  const [countdown, setCountdown] = useState(REDIRECT_SECONDS)
  const [resendEmail, setResendEmail] = useState('')
  const [resendLoading, setResendLoading] = useState(false)
  const [resendSuccess, setResendSuccess] = useState(false)
  const [resendError, setResendError] = useState('')

  useEffect(() => {
    if (!token || token.trim() === '') {
      setStatus('error')
      setMessage('Invalid or missing verification link.')
      return
    }

    let cancelled = false
    apiClient
      .get(`/auth/verify-email?token=${encodeURIComponent(token.trim())}`)
      .then(() => {
        if (!cancelled) {
          setStatus('success')
          setMessage('Your email has been verified. Redirecting to sign in...')
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const data = err && typeof err === 'object' && 'response' in err
          ? (err as { response?: { data?: { detail?: string; message?: string } } }).response?.data
          : null
        const msg = data?.detail ?? data?.message ?? 'Verification failed. The link may be invalid or expired.'
        setStatus('error')
        setMessage(typeof msg === 'string' ? msg : 'Verification failed.')
      })

    return () => {
      cancelled = true
    }
  }, [token])

  const handleResend = async (e: FormEvent) => {
    e.preventDefault()
    setResendError('')
    setResendSuccess(false)
    const email = resendEmail.trim()
    if (!EMAIL_REGEX.test(email)) {
      setResendError('Please enter a valid email address.')
      return
    }
    setResendLoading(true)
    try {
      await apiClient.post('/auth/request-verification-email', { email })
      setResendSuccess(true)
      setResendEmail('')
    } catch (err: unknown) {
      const data = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { detail?: string; message?: string } } }).response?.data
        : null
      const msg = data?.detail ?? data?.message ?? 'Failed to send verification email.'
      setResendError(typeof msg === 'string' ? msg : 'Failed to send verification email.')
    } finally {
      setResendLoading(false)
    }
  }

  useEffect(() => {
    if (status !== 'success') return
    const t = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) {
          clearInterval(t)
          window.location.href = '/'
          return 0
        }
        return c - 1
      })
    }, 1000)
    return () => clearInterval(t)
  }, [status])

  return (
    <div className={styles.wrapper}>
      <div className={styles.card}>
        <h1 className={styles.title}>Verify your email</h1>

        {status === 'loading' && (
          <p className={styles.loading}>Verifying your email...</p>
        )}

        {status === 'success' && (
          <>
            <div className={styles.successBox} role="alert">
              {message}
            </div>
            <p className={styles.redirectNote}>
              Redirecting to sign in in {countdown} second{countdown !== 1 ? 's' : ''}...
            </p>
            <p className={styles.linkBlock}>
              <Link to="/" className={styles.link}>Go to Sign In now</Link>
            </p>
          </>
        )}

        {status === 'error' && (
          <>
            <div className={styles.errorBox} role="alert">
              {message}
            </div>
            <p className={styles.linkBlock}>
              <Link to="/" className={styles.link}>Back to Sign In</Link>
            </p>
            <div className={styles.resendSection}>
              <p className={styles.message} style={{ marginBottom: '0.75rem' }}>
                Enter your email to receive a new verification link:
              </p>
              <form onSubmit={handleResend}>
                <label htmlFor="resend-email" className={styles.resendLabel}>Email</label>
                <input
                  type="email"
                  id="resend-email"
                  value={resendEmail}
                  onChange={(e) => setResendEmail(e.target.value)}
                  placeholder="you@example.com"
                  className={styles.resendInput}
                  disabled={resendLoading}
                  autoComplete="email"
                />
                {resendError && (
                  <div className={styles.errorBox} style={{ marginBottom: '0.75rem' }}>{resendError}</div>
                )}
                {resendSuccess && (
                  <div className={styles.successBox} style={{ marginBottom: '0.75rem' }}>
                    Verification email sent! Check your inbox.
                  </div>
                )}
                <button type="submit" disabled={resendLoading} className={styles.resendBtn}>
                  {resendLoading ? 'Sending...' : 'Resend verification email'}
                </button>
              </form>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
