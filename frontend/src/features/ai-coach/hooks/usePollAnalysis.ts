/**
 * usePollAnalysis - GET /api/ai-coach/analyses/{id}/poll with 5s polling
 * @module features/ai-coach/hooks/usePollAnalysis
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import type { PollResponse } from '@/features/ai-coach/types/api'

const POLL_INTERVAL_MS = 5000

/**
 * Hook to poll analysis status. Polls every 5s when analysisId is set
 * and status is pending or processing.
 */
export function usePollAnalysis(analysisId: string | null) {
  const query = useQuery({
    queryKey: ['ai-coach-poll', analysisId],
    queryFn: async (): Promise<PollResponse> => {
      if (!analysisId) throw new Error('No analysis ID')
      const { data } = await apiClient.get<PollResponse>(
        `/ai-coach/analyses/${analysisId}/poll`
      )
      return data
    },
    enabled: !!analysisId,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'completed' || status === 'failed') return false
      return POLL_INTERVAL_MS
    },
    retry: 2,
    staleTime: 2000,
  })

  return query
}
