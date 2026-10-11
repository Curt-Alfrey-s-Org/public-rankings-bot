/**
 * Compact banner at top of page showing recent system messages for admins.
 * Links to Settings → Admin → System & messages for full list.
 */

import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { messagesApi } from '@/api/messages'
import { useAuth } from '@/contexts/AuthContext'

export default function MessagesBanner() {
  const { isAdmin, isSuperAdmin } = useAuth()
  if (!isAdmin && !isSuperAdmin) return null

  const { data } = useQuery({
    queryKey: ['messages', 'banner'],
    queryFn: () => messagesApi.getMessages(undefined, 5),
    refetchInterval: 30_000,
    staleTime: 15_000,
  })

  const messages = data?.messages ?? []
  const hasMessages = messages.length > 0
  const hasAlerts = messages.some(
    (m) =>
      m.category === 'fargo_failed' ||
      m.category === 'scrape_failed' ||
      m.category === 'alerts' ||
      m.category === 'warning'
  )

  if (!hasMessages) return null

  return (
    <div
      className={`px-4 py-2 shadow-md ${
        hasAlerts ? 'bg-amber-900/90 text-amber-pool_opt_in' : 'bg-slate-800/95 text-slate-200'
      }`}
    >
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
        <div className="flex-1 min-w-0">
          <span className="font-medium">
            {messages.length} system message{messages.length !== 1 ? 's' : ''}
          </span>
          {messages[0] && (
            <span className="text-sm opacity-90 truncate ml-2">— {messages[0].message}</span>
          )}
        </div>
        <Link
          to="/settings/admin/system-messages"
          className="flex-shrink-0 px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-sm font-medium transition-colors"
        >
          View all
        </Link>
      </div>
    </div>
  )
}
