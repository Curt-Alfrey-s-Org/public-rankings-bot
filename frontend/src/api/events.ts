/**
 * Future tournament events from WPA and WPBA (scraped).
 */

import { apiClient } from './client'

export interface FutureEvent {
  name: string
  start_date: string
  end_date: string
  location: string | null
  url: string
  source: 'WPBA' | 'WPA Men' | 'WPA Women'
}

export interface FutureEventsResponse {
  events: FutureEvent[]
}

export interface GetFutureEventsParams {
  limit?: number
  location?: string
  days?: number
}

export const eventsApi = {
  getFutureEvents: (limit = 50, params?: { location?: string; days?: number; skip_cache?: boolean }) =>
    apiClient
      .get<FutureEventsResponse>('/events/future', {
        params: {
          limit,
          location: params?.location || undefined,
          days: params?.days ?? undefined,
          skip_cache: params?.skip_cache ?? undefined,
        },
      })
      .then((r) => r.data),
}
