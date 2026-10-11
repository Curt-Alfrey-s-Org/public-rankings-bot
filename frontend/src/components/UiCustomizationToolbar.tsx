import { useUiCustomization } from '@/contexts/UiCustomizationContext'

export default function UiCustomizationToolbar() {
  const { canEdit, isEditing, isSaving, startEdit, cancelEdit, resetDraft, saveDraft } = useUiCustomization()

  if (!canEdit) return null

  return (
    <div className="fixed bottom-4 right-4 z-50">
      {!isEditing ? (
        <button
          type="button"
          onClick={startEdit}
          title="Edit text and widgets on this page. For all labels and options, go to Settings → Admin → UI Customizations."
          className="px-4 py-2 rounded-lg bg-sky-600 text-white text-sm font-semibold shadow-lg hover:bg-sky-500"
        >
          Edit UI
        </button>
      ) : (
        <div className="flex flex-col gap-2 rounded-xl bg-slate-900/90 border border-slate-700 px-3 py-2 shadow-xl">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-300">Edit mode</span>
          <button
            type="button"
            onClick={saveDraft}
            disabled={isSaving}
            className="px-3 py-1.5 rounded bg-sky-600 text-white text-xs font-semibold hover:bg-sky-500 disabled:opacity-50"
          >
            {isSaving ? 'Saving...' : 'Save'}
          </button>
          <button
            type="button"
            onClick={cancelEdit}
            disabled={isSaving}
            className="px-3 py-1.5 rounded border border-slate-600 text-slate-200 text-xs hover:bg-slate-800 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={resetDraft}
            disabled={isSaving}
            className="px-3 py-1.5 rounded border border-slate-700 text-slate-400 text-xs hover:text-slate-200 disabled:opacity-50"
          >
            Reset
          </button>
          </div>
          <p className="text-[10px] text-slate-400">Editing this page only. Full control: Settings → Admin → UI Customizations.</p>
        </div>
      )}
    </div>
  )
}
