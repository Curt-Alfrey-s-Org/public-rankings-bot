/**
 * Login features API — capabilities list (splash + Full Capabilities page).
 * Editable by super_admin in Settings > Admin.
 */

import apiClient from './client'

export interface FeatureItem {
  title: string
  description: string
}

export interface LoginFeaturesResponse {
  short: FeatureItem[]
  full: FeatureItem[]
}

export const loginFeaturesApi = {
  /** Get full list (splash, capabilities page), or both short/full. No auth. */
  get(variant?: 'short' | 'full'): Promise<LoginFeaturesResponse> {
    const params = variant ? { variant } : {}
    return apiClient
      .get<LoginFeaturesResponse>('/login-features', { params })
      .then((r) => r.data)
  },

  /** Update short and/or full lists. Super_admin only. */
  update(body: { short?: FeatureItem[]; full?: FeatureItem[] }): Promise<LoginFeaturesResponse> {
    return apiClient.put<LoginFeaturesResponse>('/login-features', body).then((r) => r.data)
  },
}
