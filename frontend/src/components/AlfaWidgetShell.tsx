import type { ReactNode } from 'react'
import {
  AlfaAskAiDock,
  AlfaAskAiProvider,
  AlfaWidgetProvider,
} from '@alfa-ai/chat-widget'
import { useAuth } from '@/contexts/AuthContext'
import { getAuthHeaders } from '@/lib/authToken'
import {
  alfaAvatarSrc,
  rankingsEmptyStateHint,
  rankingsPageHint,
  rankingsPlaceholder,
} from '@/lib/alfaWidgetCopy'

export function AlfaWidgetShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()

  return (
    <AlfaWidgetProvider
      config={{
        storagePrefix: 'rankings_bot',
        avatarSrc: alfaAvatarSrc(),
        getAuthHeaders,
        onUnauthenticated: () => void logout(),
        showModelPicker: false,
        pageHint: rankingsPageHint,
        placeholder: rankingsPlaceholder,
        emptyStateHint: rankingsEmptyStateHint,
      }}
    >
      <AlfaAskAiProvider>
        {children}
        <AlfaAskAiDock enabled={!!user} accountLabel={user?.user ?? ''} />
      </AlfaAskAiProvider>
    </AlfaWidgetProvider>
  )
}
