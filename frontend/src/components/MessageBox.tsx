import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { messagesApi, Message } from '@/api/messages'

export default function MessageBox() {
  const [filterCategory, setFilterCategory] = useState<string>('all')

  const { data, isLoading, error } = useQuery({
    queryKey: ['messages', filterCategory],
    queryFn: () => messagesApi.getMessages(filterCategory === 'all' ? undefined : filterCategory, 50),
    refetchInterval: 5000, // Update every 5 seconds (reduced from 1s to prevent excessive polling)
    retry: 1,
    retryDelay: 1000,
    staleTime: 3000, // Increased from 500ms to 3s to reduce unnecessary refetches
    retryOnMount: false,
    refetchOnWindowFocus: false, // Don't refetch when window regains focus
  })

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'trading_paused':
      case 'alerts':
        return 'text-red-600 bg-red-500/20'
      case 'warning':
        return 'text-yellow-600 bg-yellow-500/20'
      case 'capital_schedule':
        return 'text-blue-600 bg-blue-500/20'
      default:
        return 'text-muted-foreground bg-muted'
    }
  }

  return (
    <div className="bg-card border border-border rounded-lg p-3">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold">Messages & Alerts</h3>
        <select
          value={filterCategory}
          onChange={(e) => setFilterCategory(e.target.value)}
          className="px-2 py-1 bg-background border border-input rounded text-xs focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="all">All</option>
          <option value="trading_paused">Paused</option>
          <option value="alerts">Alerts</option>
          <option value="info">Info</option>
          <option value="warning">Warnings</option>
          <option value="capital_schedule">Capital</option>
        </select>
      </div>

      <div className="h-[300px] overflow-y-auto space-y-2">
        {isLoading && (
          <div className="text-center py-4 text-muted-foreground text-xs">Loading...</div>
        )}

        {/* Show empty state instead of error messages */}
        {error && !isLoading && !data && (
          <div className="text-center py-4 text-muted-foreground text-xs">
            No messages yet
          </div>
        )}

        {!error && data && data.messages.length === 0 && (
          <div className="text-center py-4 text-muted-foreground text-xs">
            No messages yet
          </div>
        )}

        {data &&
          data.messages.map((message: Message, index: number) => (
            <div
              key={index}
              className="p-2 bg-muted/50 rounded border-l-2"
              style={{
                borderLeftColor:
                  message.category === 'trading_paused' || message.category === 'alerts'
                    ? '#dc3545'
                    : message.category === 'warning'
                    ? '#ffcmonitor'
                    : '#667eea',
              }}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-muted-foreground">
                    {formatTime(message.timestamp)}
                  </span>
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase ${getCategoryColor(
                      message.category
                    )}`}
                  >
                    {message.category === 'trading_paused' ? 'PAUSED' : 
                     message.category === 'capital_schedule' ? 'CAPITAL' :
                     message.category.toUpperCase()}
                  </span>
                </div>
              </div>
              <p className="text-xs leading-tight">{message.message}</p>
            </div>
          ))}
      </div>
    </div>
  )
}
