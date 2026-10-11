/**
 * Public appearance API: default avatar/background for users without custom.
 */

import { apiClient } from './client'

export interface DefaultAppearanceResponse {
  default_avatar_url: string
  default_background_url: string
}

export const appearanceApi = {
  getDefault: () =>
    apiClient.get<DefaultAppearanceResponse>('/appearance/default').then((r) => r.data),
}
