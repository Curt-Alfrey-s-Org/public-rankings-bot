import { useQuery } from '@tanstack/react-query'
import { messagesApi, Message } from '@/api/messages'

const LIMIT = 10

export default function DashboardActivity() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['messages', 'dashboard-activity'],
    queryFn: () => messagesApi.getMessages(undefined, LIMIT),
    refetchInterval: 5000,
    staleTime: 2000,
    refetchOnWindowFocus: false,
  })

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }

  return (
    <div className="w-full flex flex-col h-full">
      <h3 className="text-base sm:text-lg font-semibold mb-3 sm:mb-4">Recent activity</h3>
      <div className="flex-grow overflow-y-auto space-y-1 sm:space-y-2 text-xs sm:text-sm min-h-[200px]">
        {isLoading && (
          <div className="text-center py-6 text-muted-foreground">Loading…</div>
        )}
        {error && !data && (
          <div className="text-center py-6 text-muted-foreground">No messages yet</div>
        )}
        {data && data.messages.length === 0 && (
          <div className="text-center py-6 text-muted-foreground">No messages yet</div>
        )}
        {(data?.messages ?? []).map((msg: Message, i: number) => (
          <div
            key={`${msg.timestamp}-${i}`}
            className="flex gap-2 py-2 px-2 rounded hover:bg-muted/20 transition-colors border-b border-border/30 last:border-0"
          >
            <span className="text-muted-foreground shrink-0 font-mono text-xs">{formatTime(msg.timestamp)}</span>
            <span className="truncate flex-1 break-words" title={msg.message}>{msg.message}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
