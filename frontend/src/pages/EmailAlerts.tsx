/**
 * Email Alerts — Subscribe to email when a player's ranking changes.
 * Accessible from the menu.
 */

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { rankingsApi } from '@/api/rankings'
import { API_BASE_URL } from '@/api/client'
import { toast } from '@/lib/toast'

interface EmailAlertsProps {
  sidebarOpen?: boolean
  onSidebarToggle?: () => void
}

const SYSTEMS = [
  { value: 'WPBA', label: 'WPBA' },
  { value: 'WPA', label: 'WPA' },
] as const

export default function EmailAlerts({ sidebarOpen: _sidebarOpen, onSidebarToggle }: EmailAlertsProps) {
  const [notifyEmail, setNotifyEmail] = useState('')
  const [notifyPlayerName, setNotifyPlayerName] = useState('')
  const [notifySystem, setNotifySystem] = useState<string>('WPBA')
  const [notifySuccess, setNotifySuccess] = useState<string | null>(null)
  const [notifyError, setNotifyError] = useState<string | null>(null)

  const notifySubscribeMutation = useMutation({
    mutationFn: ({ email, playerName, system }: { email: string; playerName: string; system: string }) =>
      rankingsApi.notifySubscribe(email, playerName, system as 'WPBA' | 'WPA'),
    onSuccess: (data) => {
      const msg = data.message || "You're subscribed. We'll email you when this player's ranking changes."
      setNotifySuccess(msg)
      setNotifyError(null)
      setNotifyEmail('')
      setNotifyPlayerName('')
      toast.success(msg)
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : 'Subscription failed.'
      setNotifyError(msg)
      setNotifySuccess(null)
      toast.error(msg)
    },
  })

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-50">
      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="max-w-2xl mx-auto space-y-6">
          {/* Top bar: menu toggle (mobile/tablet) */}
          <div className="flex items-center justify-between gap-2 md:hidden">
            {onSidebarToggle && (
              <button
                type="button"
                onClick={onSidebarToggle}
                className="p-2.5 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-xl hover:bg-accent transition-colors"
                aria-label="Toggle menu"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
            )}
            <span className="text-sm font-medium text-muted-foreground">Email Alerts</span>
          </div>

          <h1 className="text-2xl font-bold text-white">Email Alerts</h1>
          <p className="text-sm text-muted-foreground">
            Get an email when a player&apos;s rank or points change. Enter your email and the player name (as shown on the Rankings page).
          </p>

          <div className="rounded-xl border border-border bg-card p-4 shadow-sm" role="region" aria-label="Subscribe to email alerts">
            <div className="flex items-center justify-between gap-2 mb-2">
              <p className="font-medium text-foreground">Subscribe to ranking changes</p>
              <a
                href={`${API_BASE_URL}/docs/notifications-email`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline shrink-0"
              >
                Learn more
              </a>
            </div>
            {notifySuccess && (
              <p className="text-sm text-green-600 dark:text-green-400 mb-3" role="alert">{notifySuccess}</p>
            )}
            {notifyError && (
              <p className="text-sm text-destructive mb-3" role="alert">{notifyError}</p>
            )}
            <div className="flex flex-col sm:flex-row flex-wrap gap-3">
              <div className="min-w-0 flex-1 sm:min-w-[12rem]">
                <label htmlFor="notify-email" className="block text-xs font-medium text-muted-foreground mb-1">Email</label>
                <input
                  id="notify-email"
                  type="email"
                  value={notifyEmail}
                  onChange={(e) => { setNotifyEmail(e.target.value); setNotifyError(null); setNotifySuccess(null); }}
                  placeholder="you@example.com"
                  className="w-full min-w-0 px-3 py-2.5 rounded-lg bg-background border border-input text-foreground text-sm"
                />
              </div>
              <div className="min-w-0 flex-1 sm:min-w-[12rem]">
                <label htmlFor="notify-player" className="block text-xs font-medium text-muted-foreground mb-1">Player name</label>
                <input
                  id="notify-player"
                  type="text"
                  value={notifyPlayerName}
                  onChange={(e) => { setNotifyPlayerName(e.target.value); setNotifyError(null); setNotifySuccess(null); }}
                  placeholder="Player name (e.g. from Rankings)"
                  className="w-full min-w-0 px-3 py-2.5 rounded-lg bg-background border border-input text-foreground text-sm"
                />
              </div>
              <div className="min-w-0 w-full sm:w-auto sm:min-w-[8rem]">
                <label htmlFor="notify-system" className="block text-xs font-medium text-muted-foreground mb-1">System</label>
                <select
                  id="notify-system"
                  value={notifySystem}
                  onChange={(e) => setNotifySystem(e.target.value)}
                  className="w-full min-w-0 px-3 py-2.5 rounded-lg bg-background border border-input text-foreground text-sm"
                >
                  {SYSTEMS.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </div>
              <div className="flex items-end">
                <button
                  type="button"
                  onClick={() => {
                    if (!notifyEmail.trim() || !notifyPlayerName.trim()) {
                      setNotifyError('Email and player name are required.')
                      return
                    }
                    notifySubscribeMutation.mutate({
                      email: notifyEmail.trim(),
                      playerName: notifyPlayerName.trim(),
                      system: notifySystem,
                    })
                  }}
                  disabled={notifySubscribeMutation.isPending}
                  className="min-h-[44px] shrink-0 px-4 py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  {notifySubscribeMutation.isPending ? 'Subscribing...' : 'Notify me'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
