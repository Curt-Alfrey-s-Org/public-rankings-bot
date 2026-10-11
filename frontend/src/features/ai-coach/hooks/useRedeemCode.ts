/**
 * useRedeemCode - POST /api/ai-coach/coupon/redeem
 * @module features/ai-coach/hooks/useRedeemCode
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import type { RedeemCodeRequest, RedeemCodeResponse } from '@/features/ai-coach/types/api'

/** Redeem code mutation options */
export interface UseRedeemCodeOptions {
  onSuccess?: (data: RedeemCodeResponse) => void
  onError?: (error: Error) => void
}

/**
 * Hook to redeem a promo/coupon code.
 * Invalidates usage query on success.
 */
export function useRedeemCode(options?: UseRedeemCodeOptions) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (request: RedeemCodeRequest): Promise<RedeemCodeResponse> => {
      const { data } = await apiClient.post<RedeemCodeResponse>(
        '/ai-coach/coupon/redeem',
        request
      )
      return data
    },
    onSuccess: (data, _variables, _context) => {
      queryClient.invalidateQueries({ queryKey: ['ai-coach-usage'] })
      options?.onSuccess?.(data)
    },
    onError: (error: Error) => {
      options?.onError?.(error)
    },
  })
}
