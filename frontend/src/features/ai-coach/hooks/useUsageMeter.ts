/**
 * useUsageMeter - GET /api/ai-coach/usage with caching
 * @module features/ai-coach/hooks/useUsageMeter
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import type { UsageResponse } from '@/features/ai-coach/types/api'

/**
 * Hook to fetch tier usage meter. Cached for 60s.
 */
export function useUsageMeter() {
  return useQuery({
    queryKey: ['ai-coach-usage'],
    queryFn: async (): Promise<UsageResponse> => {
      const { data } = await apiClient.get<UsageResponse>('/ai-coach/usage')
      return data
    },
    staleTime: 60000,
  })
}
