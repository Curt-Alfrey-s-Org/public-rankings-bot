/**
 * Modal showing QR codes for each tournament player.
 * Scan to check in. Director/admin only.
 */

import { useQueryClient } from '@tanstack/react-query'
import { QRCodeSVG } from 'qrcode.react'
import { tournamentsApi } from '@/api/tournaments'

interface CheckInQRModalProps {
  tournamentId: string
  players: { player_id: string; first_name: string; last_name: string; check_in_at?: string }[]
  isOpen: boolean
  onClose: () => void
}

export default function CheckInQRModal({
  tournamentId,
  players,
  isOpen,
  onClose,
}: CheckInQRModalProps) {
  const queryClient = useQueryClient()
  if (!isOpen) return null

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['tournament-players', tournamentId] })
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="bg-slate-800 rounded-xl border border-slate-600 shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 bg-slate-800 border-b border-slate-600 p-4 flex items-center justify-between">
          <h2 className="text-xl font-bold text-white">QR Check-in</h2>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={refresh}
              className="px-3 py-1.5 rounded bg-slate-600 text-slate-200 text-sm hover:bg-slate-500"
            >
              Refresh
            </button>
            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-700"
              aria-label="Close"
            >
              ✕
            </button>
          </div>
        </div>
        <div className="p-4 grid grid-cols-2 sm:grid-cols-3 gap-4">
          {players.map((p) => {
            const url = tournamentsApi.getCheckInUrl(tournamentId, p.player_id)
            const name = `${p.first_name} ${p.last_name}`.trim()
            return (
              <div
                key={p.player_id}
                className="flex flex-col items-center p-3 rounded-lg bg-slate-700/50 border border-slate-600"
              >
                <QRCodeSVG value={url} size={120} level="M" />
                <p className="mt-2 text-sm font-medium text-white text-center truncate w-full">
                  {name}
                </p>
                {p.check_in_at ? (
                  <span className="text-xs text-green-400 mt-1">✓ Checked in</span>
                ) : (
                  <span className="text-xs text-slate-500 mt-1">Pending</span>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
