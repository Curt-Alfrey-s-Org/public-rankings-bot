/** useHeadToHead - Fetches head-to-head comparison data */

import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/api/client'
import type { HeadToHeadResponse } from '@/features/head-to-head/types/comparison'

export function useHeadToHead(playerId: string | null, opponentId: string | null) {
  return useQuery({
    queryKey: ['head-to-head', playerId, opponentId],
    queryFn: async (): Promise<HeadToHeadResponse> => {
      if (!playerId || !opponentId) throw new Error('Both players required')
      const { data } = await apiClient.get(
        `/players/${encodeURIComponent(playerId)}/head-to-head/${encodeURIComponent(opponentId)}`
      )
      return data
    },
    enabled: !!playerId && !!opponentId,
    refetchInterval: 30_000,
  })
}
