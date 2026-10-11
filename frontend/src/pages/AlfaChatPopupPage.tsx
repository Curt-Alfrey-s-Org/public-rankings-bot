import { AlfaWidgetProvider, AlfaChatPopup } from '@alfa-ai/chat-widget'
import { getAuthHeaders } from '@/lib/authToken'
import {
  alfaAvatarSrc,
  rankingsEmptyStateHint,
  rankingsPageHint,
  rankingsPlaceholder,
} from '@/lib/alfaWidgetCopy'

/** Popup window route (/alfa-chat) — same geometry as contracts-bot. */
export default function AlfaChatPopupPage() {
  return (
    <AlfaWidgetProvider
      config={{
        storagePrefix: 'rankings_bot',
        avatarSrc: alfaAvatarSrc(),
        getAuthHeaders,
        showModelPicker: false,
        pageHint: rankingsPageHint,
        placeholder: rankingsPlaceholder,
        emptyStateHint: rankingsEmptyStateHint,
      }}
    >
      <AlfaChatPopup />
    </AlfaWidgetProvider>
  )
}
