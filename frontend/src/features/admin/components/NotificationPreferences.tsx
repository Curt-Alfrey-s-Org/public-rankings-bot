/**
 * Notification preferences component
 */

import { useNotificationPrefs } from '../hooks/useNotificationPrefs'

export function NotificationPreferences() {
  const { prefs, isLoading, update, isUpdating } = useNotificationPrefs()

  if (isLoading || !prefs) {
    return (
      <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4 animate-pulse">
        <div className="h-4 bg-slate-700 rounded w-1/3 mb-4" />
        <div className="h-10 bg-slate-700 rounded w-full" />
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
      <h3 className="text-lg font-semibold text-white mb-2">Notification Preferences</h3>
      <label className="flex items-center gap-3 cursor-pointer">
        <input
          type="checkbox"
          checked={prefs.notify_rank_changes}
          onChange={(e) => update({ notify_rank_changes: e.target.checked })}
          disabled={isUpdating}
          className="rounded border-slate-600 bg-slate-900 text-sky-500 focus:ring-sky-500"
        />
        <span className="text-slate-300">Email me when my ranking changes</span>
      </label>
      {isUpdating && (
        <p className="mt-2 text-xs text-slate-500">Saving...</p>
      )}
    </div>
  )
}
