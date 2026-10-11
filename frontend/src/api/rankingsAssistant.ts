import { apiClient } from '@/api/client'

export interface RankingsAssistantAskResponse {
  answer: string
  assistant_tier: string
  context_keys: string[]
  disclaimer: string
}

export async function askRankingsAssistant(question: string): Promise<RankingsAssistantAskResponse> {
  const { data } = await apiClient.post<RankingsAssistantAskResponse>(
    '/rankings-assistant/ask',
    { question },
    { timeout: 120_000 }
  )
  return data
}
