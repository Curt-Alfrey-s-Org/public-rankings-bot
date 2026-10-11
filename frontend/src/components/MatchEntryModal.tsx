import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { tournamentsApi, type Match } from '@/api/tournaments'
import { toast } from '@/lib/toast'

interface MatchEntryModalProps {
  match: Match | null
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
  playerAvatars?: Record<string, string>
  playerNames?: Record<string, string>
  /** Simple mode: big buttons, minimal clutter (for score keeper at table) */
  simpleMode?: boolean
  /** Override score save (e.g. Test Center API). Defaults to production tournaments API. */
  updateScoreFn?: (matchId: string, player1Games: number, player2Games: number) => Promise<unknown>
  /** When false, simpleMode + still uses local score only (Test Center). Default true for production. */
  postRacks?: boolean
}

export default function MatchEntryModal({
  match,
  isOpen,
  onClose,
  onSuccess,
  playerAvatars: _playerAvatars = {},
  playerNames = {},
  simpleMode = false,
  updateScoreFn,
  postRacks = true,
}: MatchEntryModalProps) {
  const [player1Games, setPlayer1Games] = useState('0')
  const [player2Games, setPlayer2Games] = useState('0')
  const [isBye, setIsBye] = useState(false)
  const [rackBusy, setRackBusy] = useState(false)

  // Load initial values when modal opens
  useEffect(() => {
    if (match && isOpen) {
      const m = match as Match & { operator_score?: number; player2_score?: number }
      setPlayer1Games(String(m.operator_games ?? m.operator_score ?? 0))
      setPlayer2Games(String(m.player2_games ?? m.player2_score ?? 0))
      setIsBye(match.status === 'bye')
    }
  }, [match, isOpen])

  // Update match score mutation (bulk / final save)
  const updateScoreMutation = useMutation({
    mutationFn: async () => {
      if (!match) throw new Error('No match selected')

      if (isBye) {
        const save = updateScoreFn ?? ((id: string) => tournamentsApi.updateMatchScore(id, 0, 0))
        return save(match.match_id, 0, 0)
      }

      const p1 = parseInt(player1Games, 10)
      const p2 = parseInt(player2Games, 10)

      if (isNaN(p1) || isNaN(p2)) {
        throw new Error('Invalid game count')
      }

      const save = updateScoreFn ?? ((id: string, a: number, b: number) => tournamentsApi.updateMatchScore(id, a, b))
      return save(match.match_id, p1, p2)
    },
    onSuccess: () => {
      toast.success('Match score updated successfully')
      onSuccess?.()
      onClose()
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'Failed to update match score'
      toast.error(message)
    },
  })

  const handleSave = () => {
    updateScoreMutation.mutate()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !updateScoreMutation.isPending && !rackBusy) {
      handleSave()
    } else if (e.key === 'Escape') {
      onClose()
    }
  }

  /** Scorekeeper path: each + posts a rack so EST + live odds update. */
  const postRackForWinner = async (player: 1 | 2) => {
    if (!match || !postRacks || updateScoreFn) {
      // Local-only or Test Center override
      if (player === 1) {
        setPlayer1Games((prev) => (parseInt(prev, 10) + 1).toString())
      } else {
        setPlayer2Games((prev) => (parseInt(prev, 10) + 1).toString())
      }
      return
    }
    const winnerId = player === 1 ? match.operator_id : match.player2_id
    if (!winnerId) {
      toast.error('Player not assigned')
      return
    }
    const p1 = parseInt(player1Games, 10) || 0
    const p2 = parseInt(player2Games, 10) || 0
    const gameNumber = p1 + p2 + 1
    setRackBusy(true)
    try {
      await tournamentsApi.submitGame({
        match_id: match.match_id,
        game_number: gameNumber,
        winner_id: winnerId,
      })
      if (player === 1) {
        setPlayer1Games(String(p1 + 1))
      } else {
        setPlayer2Games(String(p2 + 1))
      }
      toast.success(`Rack ${gameNumber} recorded`)
      onSuccess?.()
    } catch (error: unknown) {
      const message =
        (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        (error instanceof Error ? error.message : 'Failed to record rack')
      toast.error(String(message))
    } finally {
      setRackBusy(false)
    }
  }

  const handleIncrement = (player: 1 | 2) => {
    if (simpleMode && postRacks && !updateScoreFn) {
      void postRackForWinner(player)
      return
    }
    if (player === 1) {
      setPlayer1Games((prev) => (parseInt(prev, 10) + 1).toString())
    } else {
      setPlayer2Games((prev) => (parseInt(prev, 10) + 1).toString())
    }
  }

  const handleDecrement = (player: 1 | 2) => {
    // Decrement is local only — does not delete games (use bulk save carefully)
    if (player === 1) {
      const current = parseInt(player1Games, 10)
      if (current > 0) setPlayer1Games((current - 1).toString())
    } else {
      const current = parseInt(player2Games, 10)
      if (current > 0) setPlayer2Games((current - 1).toString())
    }
  }

  const getPlayerName = (playerId: string | undefined) => {
    if (!playerId) return 'TBD'
    return playerNames[playerId] || playerId
  }

  if (!isOpen || !match) return null

  const busy = updateScoreMutation.isPending || rackBusy
  const btnClass = simpleMode
    ? 'min-w-[64px] min-h-[64px] py-4 px-4 bg-felt text-slate-900 rounded-xl text-3xl font-bold hover:bg-felt/90 active:scale-95 transition-all touch-manipulation disabled:opacity-50'
    : 'px-3 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded font-semibold transition-colors disabled:opacity-50'
  const inputClass = simpleMode
    ? 'flex-1 bg-slate-700 text-white text-center text-4xl font-bold rounded-xl py-4 border border-slate-600 focus:border-felt focus:outline-none min-w-[80px]'
    : 'flex-1 bg-slate-700 text-white text-center text-2xl font-bold rounded py-2 border border-slate-600 focus:border-blue-500 focus:outline-none'

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-slate-800 rounded-xl max-w-md w-full border border-slate-600 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        <div className={`flex items-center justify-between ${simpleMode ? 'p-4' : 'p-6'} border-b border-slate-600`}>
          <h2 className="text-lg font-bold text-white">{simpleMode ? 'Enter score' : 'Enter Match Score'}</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-2xl font-bold" aria-label="Close">
            ✕
          </button>
        </div>

        <div className={simpleMode ? 'p-6 space-y-6' : 'p-6 space-y-6'}>
          {simpleMode && postRacks && !updateScoreFn && (
            <p className="text-xs text-slate-400 text-center">
              + posts a rack (live EST + odds). Save applies bulk score if needed.
            </p>
          )}
          {match.status === 'bye' && (
            <div className="bg-slate-700/50 rounded p-4 text-center">
              <p className="text-slate-300">BYE match — no players</p>
            </div>
          )}

          {match.status !== 'bye' && (
            <div className="space-y-6">
              <div className="space-y-2">
                <div className={`font-semibold text-white ${simpleMode ? 'text-lg' : 'text-sm'}`}>
                  {getPlayerName(match.operator_id)}
                </div>
                <div className="flex items-center justify-center gap-4">
                  <button
                    onClick={() => handleDecrement(1)}
                    className={btnClass}
                    disabled={busy}
                    type="button"
                  >
                    −
                  </button>
                  <input
                    type="number"
                    value={player1Games}
                    onChange={(e) => setPlayer1Games(e.target.value)}
                    className={inputClass}
                    min="0"
                    disabled={busy}
                  />
                  <button
                    onClick={() => handleIncrement(1)}
                    className={btnClass}
                    disabled={busy}
                    type="button"
                  >
                    +
                  </button>
                </div>
              </div>

              <div className="text-center text-slate-500 font-medium">vs</div>

              <div className="space-y-2">
                <div className={`font-semibold text-white ${simpleMode ? 'text-lg' : 'text-sm'}`}>
                  {getPlayerName(match.player2_id)}
                </div>
                <div className="flex items-center justify-center gap-4">
                  <button
                    onClick={() => handleDecrement(2)}
                    className={btnClass}
                    disabled={busy}
                    type="button"
                  >
                    −
                  </button>
                  <input
                    type="number"
                    value={player2Games}
                    onChange={(e) => setPlayer2Games(e.target.value)}
                    className={inputClass}
                    min="0"
                    disabled={busy}
                  />
                  <button
                    onClick={() => handleIncrement(2)}
                    className={btnClass}
                    disabled={busy}
                    type="button"
                  >
                    +
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className={`flex gap-3 ${simpleMode ? 'p-4' : 'p-6'} border-t border-slate-600`}>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 py-3 rounded-lg bg-slate-700 text-white hover:bg-slate-600"
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="flex-1 py-3 rounded-lg bg-sky-600 text-white hover:bg-sky-500 disabled:opacity-50"
            disabled={busy}
          >
            {updateScoreMutation.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
