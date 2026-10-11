/**
 * Modal to mark a match as forfeit/DQ. Director/admin only.
 * Select winner and reason (no-show, conduct, other); calls forfeit API.
 */

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { tournamentsApi, type Match, type ForfeitRequest } from '@/api/tournaments'
import { toast } from '@/lib/toast'

const FORFEIT_REASONS = [
  { value: 'no-show', label: 'No-show' },
  { value: 'conduct', label: 'Conduct' },
  { value: 'injury', label: 'Injury' },
  { value: 'withdrawal', label: 'Withdrawal' },
  { value: 'other', label: 'Other' },
]

interface ForfeitModalProps {
  match: Match | null
  tournamentId: string
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
  playerNames?: Record<string, string>
}

function getPlayerName(m: Match, which: 'operator' | 'player2', playerNames: Record<string, string>): string {
  const id = which === 'operator' ? m.operator_id : m.player2_id
  const fromMatch = which === 'operator' ? m.operator_name : m.player2_name
  return (id && playerNames[id]) ?? fromMatch ?? (id ? `Player ${id}` : 'TBD')
}

export default function ForfeitModal({
  match,
  tournamentId,
  isOpen,
  onClose,
  onSuccess,
  playerNames = {},
}: ForfeitModalProps) {
  const queryClient = useQueryClient()
  const [winnerId, setWinnerId] = useState<string>('')
  const [reason, setReason] = useState('no-show')
  const [reasonOther, setReasonOther] = useState('')

  const forfeitMutation = useMutation({
    mutationFn: (data: ForfeitRequest) =>
      match ? tournamentsApi.forfeitMatch(match.match_id, data) : Promise.reject(new Error('No match')),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tournament-matches', tournamentId] })
      toast.success('Match recorded as forfeit/DQ')
      onSuccess?.()
      onClose()
    },
    onError: (e) => {
      toast.error(e instanceof Error ? e.message : 'Forfeit failed')
    },
  })

  const handleSubmit = () => {
    if (!match || !winnerId) {
      toast.error('Select the winner')
      return
    }
    const reasonText = reason === 'other' ? reasonOther.trim() || 'Other' : FORFEIT_REASONS.find((r) => r.value === reason)?.label ?? reason
    forfeitMutation.mutate({ winner_player_id: winnerId, reason: reasonText })
  }

  if (!isOpen || !match) return null
  const p1Id = match.operator_id
  const p2Id = match.player2_id
  const hasTwoPlayers = !!(p1Id && p2Id)

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 rounded-xl border border-slate-600 shadow-2xl max-w-md w-full">
        <div className="p-6 border-b border-slate-600">
          <h2 className="text-xl font-bold text-white">Mark Forfeit / DQ</h2>
          <p className="text-slate-400 text-sm mt-1">Record winner and reason. The winner will advance.</p>
        </div>
        <div className="p-6 space-y-4">
          {!hasTwoPlayers ? (
            <p className="text-amber-200 text-sm">This match does not have two players. Use table assignment or bracket edit instead.</p>
          ) : (
            <>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Winner (advances)</label>
                <div className="flex flex-col gap-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="winner"
                      checked={winnerId === p1Id}
                      onChange={() => setWinnerId(p1Id!)}
                      className="rounded border-slate-500"
                    />
                    <span className="text-white">{getPlayerName(match, 'operator', playerNames)}</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="winner"
                      checked={winnerId === p2Id}
                      onChange={() => setWinnerId(p2Id!)}
                      className="rounded border-slate-500"
                    />
                    <span className="text-white">{getPlayerName(match, 'player2', playerNames)}</span>
                  </label>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Reason</label>
                <select
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white"
                >
                  {FORFEIT_REASONS.map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
                {reason === 'other' && (
                  <input
                    type="text"
                    placeholder="Specify reason"
                    value={reasonOther}
                    onChange={(e) => setReasonOther(e.target.value)}
                    className="mt-2 w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-500"
                  />
                )}
              </div>
            </>
          )}
        </div>
        <div className="p-6 border-t border-slate-600 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-slate-600 text-slate-300 hover:bg-slate-700"
          >
            Cancel
          </button>
          {hasTwoPlayers && (
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!winnerId || forfeitMutation.isPending}
              className="px-4 py-2 rounded-lg bg-amber-600 text-white font-medium hover:bg-amber-700 disabled:opacity-50"
            >
              {forfeitMutation.isPending ? 'Saving…' : 'Record Forfeit'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
