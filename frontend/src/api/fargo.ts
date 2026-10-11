/**
 * FARGO rating API client
 */

import { apiClient } from './client'

export interface FargoPlayer {
  name: string
  rating: number
  info: string
}

export interface FargoSearchResponse {
  players: FargoPlayer[]
}

export const fargoApi = {
  /**
   * Search for players by name (external FairMatch disabled).
   * Returns stored or empty results. Use CSV import for fresh Fargo data.
   */
  async searchPlayers(name: string): Promise<FargoPlayer[]> {
    try {
      const response = await apiClient.get<FargoSearchResponse>(`/fargo/search?name=${encodeURIComponent(name)}`)
      return response.data?.players ?? []
    } catch (e) {
      // External Fargo search is disabled (CSV import policy). Return empty; caller should use local data.
      return []
    }
  },
}
