/**
 * Hook for user settings aggregation
 */

import { useNotificationPrefs } from './useNotificationPrefs'
import { useAuth } from '@/contexts/AuthContext'

export function useUserSettings() {
  const { user, isAdmin } = useAuth()
  const notificationPrefs = useNotificationPrefs()

  return {
    user,
    isAdmin,
    notificationPrefs,
  }
}
