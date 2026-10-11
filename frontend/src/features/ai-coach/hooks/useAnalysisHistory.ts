/**
 * useAnalysisHistory - GET /api/ai-coach/history with pagination
 * @module features/ai-coach/hooks/useAnalysisHistory
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import type { AnalysisHistory } from '@/features/ai-coach/types/api'

/** History response shape */
export interface HistoryResponse {
  analyses: AnalysisHistory[]
  total: number
  limit: number
  offset: number
}

/**
 * Hook to fetch analysis history with pagination.
 */
export function useAnalysisHistory(limit: number, offset: number) {
  return useQuery({
    queryKey: ['ai-coach-history', limit, offset],
    queryFn: async (): Promise<HistoryResponse> => {
      const { data } = await apiClient.get<HistoryResponse>('/ai-coach/history', {
        params: { limit, offset },
      })
      return data
    },
    staleTime: 30000,
  })
}
