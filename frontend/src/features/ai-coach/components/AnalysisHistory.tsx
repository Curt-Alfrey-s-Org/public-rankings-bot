/**
 * AnalysisHistory - List of past analyses with edit/delete
 * @module features/ai-coach/components/AnalysisHistory
 */

import { useState } from 'react'
import type { AnalysisHistoryProps, AnalysisHistory as HistoryItem } from '@/features/ai-coach/types'

/** Displays list of past analyses with pagination and edit/delete */
export function AnalysisHistoryList({
  analyses,
  total,
  limit,
  offset,
  onPageChange,
  onEdit,
  onDelete,
  onProgression,
  isLoading = false,
}: AnalysisHistoryProps) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editSummary, setEditSummary] = useState('')

  if (isLoading) {
    return (
      <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <p className="text-slate-400">Loading history...</p>
      </div>
    )
  }

  if (analyses.length === 0) {
    return (
      <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <p className="text-slate-400">No analyses yet.</p>
      </div>
    )
  }

  const formatDate = (iso: string) => {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return d.toLocaleDateString(undefined, { dateStyle: 'medium' })
  }

  const handleEditClick = (a: HistoryItem) => {
    setEditingId(a.analysis_id)
    setEditSummary(a.summary ?? '')
  }

  const handleEditSave = async () => {
    if (!editingId || !onEdit) return
    await onEdit(editingId, editSummary.trim() || null)
    setEditingId(null)
  }

  const handleDeleteClick = (analysisId: string) => {
    if (!onDelete) return
    if (window.confirm('Delete this assessment? This cannot be undone.')) {
      onDelete(analysisId)
    }
  }

  return (
    <div className="space-y-4 rounded-lg border border-slate-700 bg-slate-800/50 p-4">
      <h3 className="text-lg font-semibold text-sky-400">Your Coaching History</h3>
      <ul className="space-y-2">
        {analyses.map((a: HistoryItem) => (
          <li
            key={a.analysis_id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-600/50 bg-slate-900/50 px-3 py-2"
          >
            <div className="flex flex-1 items-center gap-2 min-w-0">
              <span className="text-slate-200 truncate">{a.title}</span>
              <span className="text-sm text-slate-500 shrink-0">{formatDate(a.created_at)}</span>
              {a.overall_score != null && (
                <span className="rounded bg-sky-600/30 px-2 py-0.5 text-sm text-sky-400 shrink-0">
                  {a.overall_score.toFixed(1)}
                </span>
              )}
            </div>
            {(onEdit || onDelete || onProgression) && (
              <div className="flex gap-2 shrink-0 flex-wrap">
                {onProgression && a.status === 'completed' && (
                  <button
                    type="button"
                    onClick={() => onProgression(a.analysis_id)}
                    className="rounded border border-sky-600 px-2 py-1 text-xs text-sky-300 hover:bg-sky-900/30"
                  >
                    Progression
                  </button>
                )}
                {onEdit && (
                  <button
                    type="button"
                    onClick={() => handleEditClick(a)}
                    className="rounded border border-slate-500 px-2 py-1 text-xs text-slate-300 hover:bg-slate-700"
                  >
                    Edit
                  </button>
                )}
                {onDelete && (
                  <button
                    type="button"
                    onClick={() => handleDeleteClick(a.analysis_id)}
                    className="rounded border border-red-800 px-2 py-1 text-xs text-red-300 hover:bg-red-900/30"
                  >
                    Delete
                  </button>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
      {editingId && onEdit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-lg border border-slate-600 bg-slate-800 p-4 shadow-xl">
            <h4 className="text-lg font-semibold text-white mb-2">Edit assessment</h4>
            <textarea
              value={editSummary}
              onChange={(e) => setEditSummary(e.target.value)}
              rows={4}
              className="w-full rounded border border-slate-600 bg-slate-900 px-3 py-2 text-white placeholder-slate-500"
              placeholder="Summary or notes"
            />
            <div className="mt-3 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setEditingId(null)}
                className="rounded border border-slate-500 px-3 py-1 text-slate-300 hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleEditSave}
                className="rounded bg-sky-600 px-3 py-1 text-white hover:bg-sky-500"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
      {total > limit && onPageChange && (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => onPageChange(Math.max(0, offset - limit))}
            disabled={offset === 0}
            className="rounded border border-slate-600 px-3 py-1 text-sm text-slate-300 disabled:opacity-50"
          >
            Previous
          </button>
          <button
            type="button"
            onClick={() => onPageChange(offset + limit)}
            disabled={offset + limit >= total}
            className="rounded border border-slate-600 px-3 py-1 text-sm text-slate-300 disabled:opacity-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
