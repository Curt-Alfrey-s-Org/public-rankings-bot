/**
 * Hook for notification preferences
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { notificationsApi, type NotificationPreferences } from '@/api/notifications'

export function useNotificationPrefs() {
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: ['notification-preferences'],
    queryFn: async () => {
      const { data } = await notificationsApi.getPreferences()
      return data
    },
  })

  const mutation = useMutation({
    mutationFn: async (prefs: NotificationPreferences) => {
      const { data } = await notificationsApi.updatePreferences(prefs)
      return data
    },
    onSuccess: (data) => {
      queryClient.setQueryData(['notification-preferences'], data)
    },
  })

  return {
    prefs: query.data,
    isLoading: query.isLoading,
    error: query.error,
    update: mutation.mutate,
    isUpdating: mutation.isPending,
  }
}
