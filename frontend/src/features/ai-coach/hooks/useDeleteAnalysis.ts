/**
 * useDeleteAnalysis - DELETE /api/ai-coach/analyses/{id}
 * @module features/ai-coach/hooks/useDeleteAnalysis
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { aiCoachApi } from '@/api/aiCoach'

export function useDeleteAnalysis() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (analysisId: string) => aiCoachApi.deleteAnalysis(analysisId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-coach-history'] })
    },
  })
}
