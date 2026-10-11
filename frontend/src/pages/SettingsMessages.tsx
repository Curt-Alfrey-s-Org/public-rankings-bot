import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { messagesApi, Message } from '@/api/messages'

export default function SettingsMessagesPage() {
  const [filterCategory, setFilterCategory] = useState<string>('all')

  const { data, isLoading, error } = useQuery({
    queryKey: ['messages', filterCategory],
    queryFn: () => messagesApi.getMessages(filterCategory === 'all' ? undefined : filterCategory, 100),
    refetchInterval: 5000,
    retry: 1,
    retryDelay: 1000,
    staleTime: 3000,
  })

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'trading_paused':
      case 'alerts':
      case 'fargo_failed':
      case 'scrape_failed':
        return 'text-red-600 bg-red-500/20'
      case 'warning':
        return 'text-yellow-600 bg-yellow-500/20'
      case 'capital_schedule':
        return 'text-blue-600 bg-blue-500/20'
      case 'info':
        return 'text-blue-600 bg-blue-500/20'
      default:
        return 'text-muted-foreground bg-muted'
    }
  }

  const getCategoryLabel = (category: string) => {
    switch (category) {
      case 'fargo_failed': return 'Fargo failed'
      case 'scrape_failed': return 'Scrape failed'
      case 'trading_paused': return 'Paused'
      case 'capital_schedule': return 'Capital'
      default: return category.toUpperCase()
    }
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Messages & Alerts</h2>
        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          className="px-3 py-2 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="all">All</option>
          <option value="fargo_failed">Fargo failed</option>
          <option value="scrape_failed">Scrape failed</option>
          <option value="trading_paused">Paused</option>
          <option value="alerts">Alerts</option>
          <option value="info">Info</option>
          <option value="warning">Warnings</option>
          <option value="capital_schedule">Capital</option>
        </select>
      </div>

      <div className="bg-card border border-border rounded-lg p-4 min-h-[400px]">
        {isLoading && (
          <div className="text-center py-8 text-muted-foreground">Loading...</div>
        )}

        {error && !isLoading && !data && (
          <div className="text-center py-8 text-muted-foreground">
            No messages yet
          </div>
        )}

        {!error && data && data.messages.length === 0 && (
          <div className="text-center py-8 text-muted-foreground">
            No messages yet
          </div>
        )}

        {data && data.messages.length > 0 && (
          <div className="space-y-3">
            {data.messages.map((message: Message, index: number) => (
              <div
                key={index}
                className="p-3 bg-muted/50 rounded-lg border-l-4"
                style={{
                  borderLeftColor:
                    message.category === 'trading_paused' || message.category === 'alerts' ||
                    message.category === 'fargo_failed' || message.category === 'scrape_failed'
                      ? '#dc3545'
                      : message.category === 'warning'
                        ? '#ffcmonitor'
                        : '#667eea',
                }}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-muted-foreground">
                    {formatTime(message.timestamp)}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-semibold uppercase ${getCategoryColor(
                      message.category
                    )}`}
                  >
                    {getCategoryLabel(message.category)}
                  </span>
                </div>
                <p className="text-sm leading-snug">{message.message}</p>
                {message.details && message.details.failed_players && (
                  <p className="text-xs text-muted-foreground mt-2">
                    Players: {(message.details.failed_players as string[]).slice(0, 15).join(', ')}
                    {(message.details.failed_players as string[]).length > 15 && ' …'}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
