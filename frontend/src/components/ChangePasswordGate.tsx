/**
 * Full-screen gate shown when super admin must set a new password on first login.
 * Do not advertise.
 */

import { useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'

export default function ChangePasswordGate() {
  const { changePassword, must_change_password } = useAuth()
  const [newPassword, setNewPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    if (newPassword !== confirm) {
      setError('Passwords do not match')
      return
    }
    if (!/[A-Z]/.test(newPassword) || !/[a-z]/.test(newPassword) || !/[0-9]/.test(newPassword) || !/[!@#$%^&*()\-_=+[\]{};':"|,.<>?]/.test(newPassword)) {
      setError('Password must include uppercase, lowercase, number, and special character')
      return
    }
    setLoading(true)
    try {
      const result = await changePassword(newPassword)
      if (result.success) {
        // Password changed successfully, gate will auto-hide when context updates
      } else {
        setError(result.message || 'Failed to change password')
      }
    } catch (err: unknown) {
      const ax = err as { response?: { status?: number; data?: { detail?: string | string[]; message?: string } }; code?: string; message?: string }
      let msg: string
      if (ax?.code === 'ECONNABORTED') {
        msg = 'Request timed out. Your password may have been updated—try refreshing the page.'
      } else if (ax?.response?.data) {
        const d = ax.response.data
        const detail = d.detail != null
          ? (Array.isArray(d.detail)
              ? d.detail.map((x: string | { msg?: string }) => (typeof x === 'string' ? x : (x?.msg ?? ''))).join(', ')
              : String(d.detail))
          : d.message
        msg = detail || `Request failed (${ax.response?.status ?? 'unknown'})`
      } else {
        msg = ax?.message && typeof ax.message === 'string' ? ax.message : 'Failed to update password'
      }
      setError(msg)
      // Debug: log full error so it appears in browser DevTools Console
      console.error('[ChangePassword] full error:', err)
      const summary = {
        code: (err as { code?: string })?.code,
        message: (err as { message?: string })?.message,
        status: (err as { response?: { status?: number } })?.response?.status,
        detail: (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail,
      }
      console.error('[ChangePassword] summary:', JSON.stringify(summary, null, 2))
      ;(window as unknown as { __changePasswordLastErr?: unknown }).__changePasswordLastErr = summary
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/95 p-4">
      <div className="w-full max-w-md rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-xl">
        <h2 className="text-xl font-semibold text-white mb-2">Set new password</h2>
        <p className="text-sm text-slate-400 mb-4">You must set a new password before continuing.</p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">New password</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
              className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-white placeholder-slate-500 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="8+ chars, upper, lower, number, special"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Confirm password</label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              autoComplete="new-password"
              className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-white placeholder-slate-500 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              placeholder="Confirm"
            />
          </div>
          {error && (
            <div className="space-y-2">
              <p className="text-sm text-red-400">{error}</p>
              <button
                type="button"
                onClick={() => {
                  const ax = (window as unknown as { __changePasswordLastErr?: unknown }).__changePasswordLastErr
                  const text = ax != null ? JSON.stringify(ax, null, 2) : error
                  navigator.clipboard.writeText(text).then(() => alert('Copied to clipboard'))
                }}
                className="text-xs text-slate-400 hover:text-slate-300 underline"
              >
                Copy error details
              </button>
            </div>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-primary px-4 py-2.5 font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
          >
            {loading ? 'Updating…' : 'Set password'}
          </button>
        </form>
      </div>
    </div>
  )
}
