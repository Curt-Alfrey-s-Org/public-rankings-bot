/**
 * useConfirmPayment - POST /api/payments/confirm
 * @module features/ai-coach/hooks/useConfirmPayment
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import type {
  ConfirmPaymentRequest,
  ConfirmPaymentResponse,
} from '@/features/ai-coach/types/api'

/** Options for useConfirmPayment */
export interface UseConfirmPaymentOptions {
  onSuccess?: (data: ConfirmPaymentResponse) => void
  onError?: (error: Error) => void
}

/**
 * Hook to confirm a payment and update user subscription.
 */
export function useConfirmPayment(options?: UseConfirmPaymentOptions) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (
      request: ConfirmPaymentRequest
    ): Promise<ConfirmPaymentResponse> => {
      const { data } = await apiClient.post<ConfirmPaymentResponse>(
        '/payments/confirm',
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
