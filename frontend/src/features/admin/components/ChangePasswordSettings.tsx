/**
 * Change password (own account) - shown for all authenticated users in User Settings.
 */

import { useState } from 'react'
import { authApi } from '@/api/auth'
import { toast } from '@/lib/toast'

const PASSWORD_RULES = '8+ characters, uppercase, lowercase, number, and special character (!@#$%^&* etc.)'

function validatePassword(pw: string): string | null {
  if (pw.length < 8) return 'Password must be at least 8 characters'
  if (!/[A-Z]/.test(pw)) return 'Password must include an uppercase letter'
  if (!/[a-z]/.test(pw)) return 'Password must include a lowercase letter'
  if (!/[0-9]/.test(pw)) return 'Password must include a number'
  if (!/[!@#$%^&*()\-_=+[\]{};':"|,.<>?]/.test(pw)) return 'Password must include a special character'
  return null
}

export function ChangePasswordSettings() {
  const [newPassword, setNewPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setSuccess(false)
    const err = validatePassword(newPassword)
    if (err) {
      setError(err)
      return
    }
    if (newPassword !== confirm) {
      setError('Passwords do not match')
      return
    }
    setLoading(true)
    try {
      await authApi.changePassword(newPassword)
      setNewPassword('')
      setConfirm('')
      setSuccess(true)
      toast.success('Password updated. Use it on your next login.')
    } catch (err: unknown) {
      const ax = err as { response?: { data?: { detail?: string } }; message?: string }
      const msg = ax?.response?.data?.detail ?? ax?.message ?? 'Failed to update password'
      setError(typeof msg === 'string' ? msg : 'Failed to update password')
      toast.error('Password update failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4" title="Change your login password.">
      <h3 className="text-lg font-semibold text-white mb-2">Change password</h3>
      <p className="text-sm text-slate-400 mb-4">
        Set a new password for your account. Use it the next time you log in. {PASSWORD_RULES}.
      </p>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label htmlFor="change-pw-new" className="block text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">New password</label>
          <input
            id="change-pw-new"
            type="password"
            value={newPassword}
            onChange={(e) => { setNewPassword(e.target.value); setError('') }}
            autoComplete="new-password"
            className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            placeholder="New password"
          />
        </div>
        <div>
          <label htmlFor="change-pw-confirm" className="block text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Confirm new password</label>
          <input
            id="change-pw-confirm"
            type="password"
            value={confirm}
            onChange={(e) => { setConfirm(e.target.value); setError('') }}
            autoComplete="new-password"
            className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            placeholder="Confirm new password"
          />
        </div>
        {error && <p className="text-sm text-amber-500">{error}</p>}
        {success && <p className="text-sm text-green-500">Password updated. Use it on your next login.</p>}
        <button
          type="submit"
          disabled={loading || !newPassword || !confirm}
          className="px-3 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Updating…' : 'Update password'}
        </button>
      </form>
    </div>
  )
}
