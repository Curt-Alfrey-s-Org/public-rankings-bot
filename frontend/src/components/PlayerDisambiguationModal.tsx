/**
 * Modal for disambiguating multiple Fargo players with same name.
 * Shows list of matching players with their rating and location/org info.
 * User selects the correct player; selection is saved to user_player_links.
 */

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FargoPlayer } from '@/api/fargo'
import { usersApi } from '@/api/users'
import { toast } from '@/lib/toast'

interface PlayerDisambiguationModalProps {
  isOpen: boolean
  onClose: () => void
  players: FargoPlayer[]
  searchName: string
  username: string
  onSelection?: (player: FargoPlayer) => void
}

export default function PlayerDisambiguationModal({
  isOpen,
  onClose,
  players,
  searchName,
  username,
  onSelection,
}: PlayerDisambiguationModalProps) {
  const queryClient = useQueryClient()
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)

  const extractLicense = (info: string | undefined): string | null => {
    if (!info) return null
    const m = info.match(/\b([A-Z]{2,5}\s*-\s*\d{2,5})\b/i)
    return m ? m[1].trim() : null
  }

  const saveMappingMutation = useMutation({
    mutationFn: async (player: FargoPlayer) => {
      await usersApi.upsertPlayerLink({
        username,
        player_name: player.name,
        player_id: null,
        license_number: extractLicense(player.info) ?? undefined,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['player-links'] })
      queryClient.invalidateQueries({ queryKey: ['my-player-info'] })
      toast.success('Player mapping saved')
    },
    onError: (e) => {
      toast.error(e instanceof Error ? e.message : 'Failed to save mapping')
    },
  })

  const handleSelect = () => {
    if (selectedIndex === null) {
      toast.error('Please select a player')
      return
    }
    const player = players[selectedIndex]
    if (!player) return

    // Save mapping first
    saveMappingMutation.mutate(player, {
      onSuccess: () => {
        onSelection?.(player)
        onClose()
      },
    })
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 rounded-xl border border-slate-600 shadow-2xl max-w-2xl w-full max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-slate-600 flex-shrink-0">
          <h2 className="text-xl font-bold text-white">Multiple Players Found</h2>
          <p className="text-slate-400 text-sm mt-1">
            Found {players.length} player{players.length !== 1 ? 's' : ''} matching "{searchName}". Select the correct one:
          </p>
        </div>

        {/* Player List */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="space-y-3">
            {players.map((player, index) => (
              <label
                key={index}
                className={`flex items-start gap-3 p-4 rounded-lg border-2 cursor-pointer transition-all ${
                  selectedIndex === index
                    ? 'border-sky-500 bg-sky-500/10'
                    : 'border-slate-600 bg-slate-700/30 hover:border-slate-500 hover:bg-slate-700/50'
                }`}
              >
                <input
                  type="radio"
                  name="player-select"
                  checked={selectedIndex === index}
                  onChange={() => setSelectedIndex(index)}
                  className="mt-1 flex-shrink-0"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-3 flex-wrap">
                    <span className="text-white font-semibold text-lg">{player.name}</span>
                    <span className="text-sky-400 font-mono font-bold text-xl">{player.rating.toFixed(0)}</span>
                  </div>
                  {player.info && player.info !== 'N/A' && (
                    <p className="text-slate-400 text-sm mt-1">{player.info}</p>
                  )}
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-slate-600 flex gap-3 justify-end flex-shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-white font-medium transition-colors"
            disabled={saveMappingMutation.isPending}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSelect}
            disabled={selectedIndex === null || saveMappingMutation.isPending}
            className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saveMappingMutation.isPending ? 'Saving...' : 'Select & Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
