/**
 * usePaymentIntent - POST /api/payments/intent
 * @module features/ai-coach/hooks/usePaymentIntent
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import type {
  PaymentIntentRequest,
  PaymentIntentResponse,
} from '@/features/ai-coach/types/api'

/** Options for usePaymentIntent */
export interface UsePaymentIntentOptions {
  onSuccess?: (data: PaymentIntentResponse) => void
  onError?: (error: Error) => void
}

/**
 * Hook to create a Stripe PaymentIntent for AI Coach hour pass.
 * Returns client_secret for Stripe Elements.
 */
export function usePaymentIntent(options?: UsePaymentIntentOptions) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (
      request?: PaymentIntentRequest
    ): Promise<PaymentIntentResponse> => {
      const { data } = await apiClient.post<PaymentIntentResponse>(
        '/payments/intent',
        request ?? { hours: 1, amount_cents: 999 }
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
