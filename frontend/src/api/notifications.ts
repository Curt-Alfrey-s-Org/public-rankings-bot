/**
 * Notification preferences API
 */

import apiClient from './client'

export interface NotificationPreferences {
  notify_rank_changes: boolean
}

export const notificationsApi = {
  getPreferences: () =>
    apiClient.get<NotificationPreferences>('/notifications/preferences'),
  updatePreferences: (prefs: NotificationPreferences) =>
    apiClient.put<NotificationPreferences>('/notifications/preferences', prefs),
}
