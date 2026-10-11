/**
 * Messages API functions
 */

import apiClient from './client'

export interface Message {
  timestamp: string
  message: string
  category: 'trading_paused' | 'alerts' | 'info' | 'warning' | 'capital_schedule'
  details?: any
}

export interface MessagesResponse {
  messages: Message[]
  total: number
}

export const messagesApi = {
  getMessages: async (category?: string, limit?: number): Promise<MessagesResponse> => {
    try {
      const params = new URLSearchParams()
      if (category) params.append('category', category)
      if (limit) params.append('limit', limit.toString())
      
      const response = await apiClient.get<MessagesResponse>(`/messages?${params.toString()}`)
      return response.data
    } catch (error: any) {
      // Return empty messages if endpoint doesn't exist
      if (error.response?.status === 404) {
        return { messages: [], total: 0 }
      }
      throw error
    }
  },
}
