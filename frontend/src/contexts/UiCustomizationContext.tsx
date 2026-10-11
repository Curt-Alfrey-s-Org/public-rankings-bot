import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { uiCustomizationsApi, type UiCustomizationPayload, type ButtonOverride } from '@/api/uiCustomizations'
import { useAuth } from '@/contexts/AuthContext'
import { logger } from '@/lib/logger'
import { toast } from '@/lib/toast'

interface UiCustomizationContextValue {
  data: UiCustomizationPayload
  draft: UiCustomizationPayload
  isLoading: boolean
  isEditing: boolean
  isSaving: boolean
  canEdit: boolean
  startEdit: () => void
  cancelEdit: () => void
  resetDraft: () => void
  saveDraft: () => void
  setDraftText: (key: string, value: string) => void
  setDraftButton: (key: string, update: ButtonOverride) => void
  setDraftLayout: (pageKey: string, layout: string[]) => void
  getText: (key: string, fallback: string) => string
  getButton: (key: string, fallback: string) => { label: string; visible: boolean }
  getLayout: (key: string, fallback: any) => any
}

const UiCustomizationContext = createContext<UiCustomizationContextValue | null>(null)

const EMPTY = uiCustomizationsApi.defaults()

export function UiCustomizationProvider({ children }: { children: React.ReactNode }) {
  const { user, isSuperAdmin } = useAuth()
  const queryClient = useQueryClient()
  const [isEditing, setIsEditing] = useState(false)
  const [draft, setDraft] = useState<UiCustomizationPayload>(EMPTY)

  const { data, isLoading } = useQuery({
    queryKey: ['ui-customizations'],
    queryFn: () => uiCustomizationsApi.get(),
    enabled: !!user,
    staleTime: 60_000,
    gcTime: Infinity, // Keep in cache indefinitely to prevent refetch issues
    retry: 3, // Increase retries for better reliability
    refetchOnMount: 'always', // Always refetch on mount to get latest changes
  })

  useEffect(() => {
    if (!data) return
    if (!isEditing) {
      setDraft(data)
      logger.debug('UI customizations loaded from server', { data })
    }
  }, [data, isEditing])

  const updateMutation = useMutation({
    mutationFn: (payload: UiCustomizationPayload) => uiCustomizationsApi.update(payload),
    onSuccess: (saved) => {
      queryClient.setQueryData(['ui-customizations'], saved)
      setDraft(saved)
      setIsEditing(false)
      logger.debug('UI customizations saved to server', { saved })
      toast.success('UI customizations saved.')
    },
    onError: (e: Error) => {
      console.error('[UiCustomization] Save failed:', e)
      toast.error(e?.message ?? 'Failed to save UI customizations')
    },
  })

  const startEdit = useCallback(() => {
    if (!isSuperAdmin) return
    setIsEditing(true)
  }, [isSuperAdmin])

  const cancelEdit = useCallback(() => {
    setDraft(data ?? EMPTY)
    setIsEditing(false)
  }, [data])

  const resetDraft = useCallback(() => {
    setDraft(EMPTY)
  }, [])

  const saveDraft = useCallback(() => {
    if (!isSuperAdmin) return
    updateMutation.mutate(draft)
  }, [draft, isSuperAdmin, updateMutation])

  const setDraftText = useCallback((key: string, value: string) => {
    setDraft((prev) => ({
      ...prev,
      text: {
        ...prev.text,
        [key]: value,
      },
    }))
  }, [])

  const setDraftButton = useCallback((key: string, update: ButtonOverride) => {
    setDraft((prev) => ({
      ...prev,
      buttons: {
        ...prev.buttons,
        [key]: {
          ...prev.buttons[key],
          ...update,
        },
      },
    }))
  }, [])

  const setDraftLayout = useCallback((pageKey: string, layout: string[]) => {
    setDraft((prev) => ({
      ...prev,
      layouts: {
        ...prev.layouts,
        [pageKey]: layout,
      },
    }))
  }, [])

  const getText = useCallback(
    (key: string, fallback: string) => {
      const override = (isEditing ? draft : data ?? EMPTY).text?.[key]
      return override ?? fallback
    },
    [data, draft, isEditing]
  )

  const getButton = useCallback(
    (key: string, fallback: string) => {
      const source = isEditing ? draft : data ?? EMPTY
      const override = source.buttons?.[key]
      return {
        label: override?.label ?? fallback,
        visible: override?.visible ?? true,
      }
    },
    [data, draft, isEditing]
  )

  const getLayout = useCallback(
    (key: string, fallback: any) => {
      const source = isEditing ? draft : data ?? EMPTY
      return source.layouts?.[key] ?? fallback
    },
    [data, draft, isEditing]
  )

  const value = useMemo(
    () => ({
      data: data ?? EMPTY,
      draft,
      isLoading,
      isEditing,
      isSaving: updateMutation.isPending,
      canEdit: !!isSuperAdmin,
      startEdit,
      cancelEdit,
      resetDraft,
      saveDraft,
      setDraftText,
      setDraftButton,
      setDraftLayout,
      getText,
      getButton,
      getLayout,
    }),
    [
      data,
      draft,
      isLoading,
      isEditing,
      updateMutation.isPending,
      isSuperAdmin,
      startEdit,
      cancelEdit,
      resetDraft,
      saveDraft,
      setDraftText,
      setDraftButton,
      setDraftLayout,
      getText,
      getButton,
      getLayout,
    ]
  )

  return (
    <UiCustomizationContext.Provider value={value}>
      {children}
    </UiCustomizationContext.Provider>
  )
}

export function useUiCustomization(): UiCustomizationContextValue {
  const ctx = useContext(UiCustomizationContext)
  if (!ctx) throw new Error('useUiCustomization must be used within UiCustomizationProvider')
  return ctx
}
