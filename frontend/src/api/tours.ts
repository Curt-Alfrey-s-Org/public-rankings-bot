/**
 * API Client for Tour/Series Management
 */

import { apiClient } from './client'

export interface Tour {
  tour_id: string
  name: string
  year: number
  description?: string | null
}

export interface TourStop {
  id: number
  tournament_id?: string | null
  stop_number: number
  points_multiplier: number
}

const BASE = '/tours'

export const toursApi = {
  list: async (): Promise<Tour[]> => {
    const { data } = await apiClient.get<Tour[]>(BASE)
    return data
  },

  create: async (payload: { name: string; year: number; description?: string }) => {
    const { data } = await apiClient.post<{ tour_id: string; message: string }>(BASE, payload)
    return data
  },

  listStops: async (tourId: string): Promise<TourStop[]> => {
    const { data } = await apiClient.get<TourStop[]>(`${BASE}/${tourId}/stops`)
    return data
  },

  addStop: async (
    tourId: string,
    payload: { tournament_id?: string; stop_number: number; points_multiplier?: number }
  ) => {
    const { data } = await apiClient.post<{ message: string }>(`${BASE}/${tourId}/stops`, payload)
    return data
  },
}
