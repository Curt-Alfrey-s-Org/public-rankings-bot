/**
 * useSubmitAnalysis - POST /api/ai-coach/analyze
 * @module features/ai-coach/hooks/useSubmitAnalysis
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import type { SubmitAnalysisRequest, AnalysisResponse } from '@/features/ai-coach/types/api'

/** Submit analysis mutation options */
export interface UseSubmitAnalysisOptions {
  onSuccess?: (data: AnalysisResponse) => void
  onError?: (error: Error) => void
}

/**
 * Hook to submit video frames for AI coaching analysis.
 * Invalidates usage and history queries on success.
 */
export function useSubmitAnalysis(options?: UseSubmitAnalysisOptions) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (request: SubmitAnalysisRequest): Promise<AnalysisResponse> => {
      const { data } = await apiClient.post<AnalysisResponse>('/ai-coach/analyze', request, {
        timeout: 60000,
      })
      return data
    },
    onSuccess: (data, _variables, _context) => {
      queryClient.invalidateQueries({ queryKey: ['ai-coach-usage'] })
      queryClient.invalidateQueries({ queryKey: ['ai-coach-history'] })
      options?.onSuccess?.(data)
    },
    onError: (error: Error) => {
      options?.onError?.(error)
    },
  })
}
