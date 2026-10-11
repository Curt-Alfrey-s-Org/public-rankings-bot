/**
 * Connection Status Indicator
 * Shows API connection status (checks HTTP health endpoint)
 */

import { useQuery } from '@tanstack/react-query'
import apiClient from '@/api/client'

export default function ConnectionStatus() {
  // Check API health instead of WebSocket
  const { data, isLoading, isError, error, failureCount, refetch, isFetching } = useQuery({
    queryKey: ['api-health'],
    queryFn: async () => {
      const response = await apiClient.get('/health', {
        timeout: 10000, // 10s to tolerate slow API under load (e.g. when switching associations)
      })
      return response.data
    },
    refetchInterval: (query) => (query.state.status === 'error' ? 15000 : 5000), // Back off when API is down to reduce timeout spam
    retry: 3,
    retryDelay: (attempt) => Math.min(1000 * (2 ** attempt), 10000),
    staleTime: 4000,
    refetchOnWindowFocus: false,
    retryOnMount: true,
    throwOnError: false,
  })

  const isConnected = !isError && !!data
  const isReconnecting = isFetching && !isConnected

  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${
      isConnected ? 'bg-green-900/20 border-green-700/40' : 'bg-red-900/20 border-red-700/40'
    }`}>
      <div
        className={`w-2 h-2 rounded-full transition-colors ${
          isConnected ? 'bg-green-500 animate-pulse' : isReconnecting || isLoading ? 'bg-yellow-500' : 'bg-red-500'
        }`}
        title={isConnected ? 'API connected' : isReconnecting || isLoading ? 'Reconnecting...' : 'API offline'}
      />
      <span className="text-xs font-medium text-slate-200">
        {isConnected
          ? 'Online'
          : isReconnecting || isLoading
            ? `Reconnecting (attempt ${failureCount + 1})...`
            : 'Offline'}
      </span>
      {!isConnected && !isLoading && (
        <button
          onClick={() => refetch()}
          className="text-xs px-2 py-1 rounded bg-slate-700 hover:bg-slate-600 text-white"
        >
          Retry
        </button>
      )}
      {isError && error instanceof Error && (
        <span className="hidden md:inline text-[11px] text-slate-400 max-w-[220px] truncate">
          {error.message}
        </span>
      )}
    </div>
  )
}
