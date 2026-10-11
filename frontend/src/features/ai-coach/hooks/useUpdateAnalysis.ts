/**
 * useUpdateAnalysis - PATCH /api/ai-coach/analyses/{id}
 * @module features/ai-coach/hooks/useUpdateAnalysis
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { aiCoachApi } from '@/api/aiCoach'

export function useUpdateAnalysis() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ analysisId, summary_text }: { analysisId: string; summary_text?: string | null }) =>
      aiCoachApi.updateAnalysis(analysisId, { summary_text }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-coach-history'] })
    },
  })
}
