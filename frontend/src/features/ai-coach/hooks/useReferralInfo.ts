/**
 * useReferralInfo - GET /api/ai-coach/referral
 * @module features/ai-coach/hooks/useReferralInfo
 */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import type { ReferralResponse } from '@/features/ai-coach/types/api'

/**
 * Hook to fetch referral info (influencer tier only).
 * Returns 404 for non-influencers - query is disabled on error.
 */
export function useReferralInfo(enabled = true) {
  return useQuery({
    queryKey: ['ai-coach-referral'],
    queryFn: async (): Promise<ReferralResponse> => {
      const { data } = await apiClient.get<ReferralResponse>('/ai-coach/referral')
      return data
    },
    enabled,
    retry: false,
    staleTime: 60000,
  })
}
