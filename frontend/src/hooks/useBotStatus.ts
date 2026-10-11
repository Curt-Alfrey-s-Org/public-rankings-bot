import { useQuery } from '@tanstack/react-query'
import { systemApi } from '@/api/system'

/**
 * Hook to query the current bot/system status.
 * Used to determine if tests can be run (bot must not be running).
 */
export function useBotStatus() {
  return useQuery({
    queryKey: ['bot-status'],
    queryFn: async () => {
      // Try to fetch system health as a proxy for bot status
      // If API is unavailable, return null (treats bot as available)
      try {
        const health = await systemApi.getHealth()
        return {
          isRunning: false, // For now, assume bot is not running
          lastUpdated: new Date(),
          ...health,
        }
      } catch (_error) {
        return null
      }
    },
    refetchInterval: 30000, // Check every 30 seconds
    retry: 1,
    retryDelay: 1000,
    staleTime: 10000,
  })
}
