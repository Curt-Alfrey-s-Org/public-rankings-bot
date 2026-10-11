/**
 * Media API: slideshow (weighted WPBA/WPA pics) and scrape trigger.
 */

import apiClient from './client'

export const mediaApi = {
  getSlideshow: (limit = 24) =>
    apiClient.get<{ urls: string[] }>('/media/slideshow', { params: { limit } }),
  getCount: () => apiClient.get<{ count: number }>('/media/count'),
  scrape: () =>
    apiClient.post<{ wpba: number; wpa: number; total: number }>('/media/scrape'),
}
