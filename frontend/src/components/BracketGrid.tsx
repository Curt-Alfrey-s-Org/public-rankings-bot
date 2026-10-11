import { useState } from 'react'
import MatchEntryModal from './MatchEntryModal'

interface Match {
  match_id: string
  bracket_type: string
  round_number: number
  status?: 'bye' | 'completed' | 'in_progress' | 'pending' | string
  table_number?: number | null
  scheduled_time?: string | null
  winner_id?: string | null
  operator_id?: string | null
  player2_id?: string | null
  operator_name?: string | null
  player2_name?: string | null
  operator_score?: number | null
  player2_score?: number | null
}

interface BracketGridProps {
  tournamentId: string
  matches: Match[]
  isLoading?: boolean
  isDirectorMode?: boolean
  onTimeKeeperOpen?: (matchId: string) => void
  updateScoreFn?: (matchId: string, player1Games: number, player2Games: number) => Promise<unknown>
  onScoreSuccess?: () => void
}

export default function BracketGrid({
  tournamentId,
  matches,
  isLoading = false,
  isDirectorMode = false,
  onTimeKeeperOpen,
  updateScoreFn,
  onScoreSuccess,
}: BracketGridProps) {
  const [selectedMatch, setSelectedMatch] = useState<Match | null>(null)
  const [showScoreModal, setShowScoreModal] = useState(false)

  // Group matches by round and bracket type
  const matchesByRound: Record<string, Match[]> = {}
  matches.forEach((match) => {
    const key = `${match.bracket_type}-${match.round_number}`
    if (!matchesByRound[key]) {
      matchesByRound[key] = []
    }
    matchesByRound[key].push(match)
  })

  const getRoundsFor = (bracketType: string) =>
    [...new Set(matches.filter((m) => m.bracket_type === bracketType).map((m) => m.round_number))].sort((a, b) => a - b)

  // Get unique round numbers for each bracket type
  const winnerRounds = getRoundsFor('winners')
  const loserRounds = getRoundsFor('losers')
  const stage2Rounds = getRoundsFor('stage2')
  const grandFinalRounds = getRoundsFor('grand_final')

  const handleMatchClick = (match: Match) => {
    if (!match.status || match.status === 'bye') return
    setSelectedMatch(match)
    setShowScoreModal(true)
  }

  const formatTime = (dateString?: string) => {
    if (!dateString) return null
    const date = new Date(dateString)
    if (Number.isNaN(date.getTime())) {
      return null
    }
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true })
  }

  const renderRound = (bracketType: string, roundNum: number) => {
    const key = `${bracketType}-${roundNum}`
    const roundMatches = matchesByRound[key] || []
    const label =
      bracketType === 'winners'
        ? 'Winners'
        : bracketType === 'losers'
          ? 'Losers'
          : bracketType === 'stage2'
            ? 'Stage 2'
          : bracketType === 'grand_final'
            ? 'Grand Final'
            : bracketType
    const icon =
      bracketType === 'winners'
        ? '🏆'
        : bracketType === 'losers'
          ? '📉'
          : bracketType === 'stage2'
            ? '🎯'
          : bracketType === 'grand_final'
            ? '🎖️'
            : '🎯'

    return (
      <div key={key} className="flex-shrink-0 w-96">
        <div className="mb-4 sticky top-0 bg-slate-900/80 backdrop-blur z-10 py-2">
          <h3 className="text-sm font-bold text-slate-300 uppercase tracking-wide">
            {icon} {label} R{roundNum}
          </h3>
          <div className="h-0.5 bg-gradient-to-r from-sky-500/50 to-transparent mt-1" />
        </div>

        <div className="space-y-3">
          {roundMatches.map((match) => (
            <MatchCard
              key={match.match_id}
              match={match}
              selected={selectedMatch?.match_id === match.match_id}
              onClick={() => handleMatchClick(match)}
              isDirectorMode={isDirectorMode}
              onTimeKeeperOpen={onTimeKeeperOpen}
              formatTime={formatTime}
            />
          ))}
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-slate-400">Loading bracket...</p>
      </div>
    )
  }

  if (matches.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 bg-slate-800/50 rounded-lg border border-slate-700">
        <p className="text-slate-400">No bracket generated yet. Create tournament and generate bracket to view matches.</p>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Winners Bracket */}
      {winnerRounds.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <span>🏆</span> Winners Bracket
          </h2>
          <div className="overflow-x-auto bg-slate-800/30 backdrop-blur rounded-lg border border-slate-700 p-4 pb-6">
            <div className="flex gap-4">
              {winnerRounds.map((roundNum) => renderRound('winners', roundNum))}
            </div>
          </div>
        </div>
      )}

      {/* Losers Bracket */}
      {loserRounds.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <span>📉</span> Losers Bracket
          </h2>
          <div className="overflow-x-auto bg-slate-800/30 backdrop-blur rounded-lg border border-slate-700 p-4 pb-6">
            <div className="flex gap-4">
              {loserRounds.map((roundNum) => renderRound('losers', roundNum))}
            </div>
          </div>
        </div>
      )}

      {/* Stage 2 */}
      {stage2Rounds.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <span>🎯</span> Stage 2
          </h2>
          <div className="overflow-x-auto bg-slate-800/30 backdrop-blur rounded-lg border border-slate-700 p-4 pb-6">
            <div className="flex gap-4">
              {stage2Rounds.map((roundNum) => renderRound('stage2', roundNum))}
            </div>
          </div>
        </div>
      )}

      {/* Grand Final */}
      {grandFinalRounds.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <span>🎖️</span> Grand Final
          </h2>
          <div className="overflow-x-auto bg-slate-800/30 backdrop-blur rounded-lg border border-slate-700 p-4 pb-6">
            <div className="flex gap-4">
              {grandFinalRounds.map((roundNum) => renderRound('grand_final', roundNum))}
            </div>
          </div>
        </div>
      )}

      {/* Score Modal */}
      <MatchEntryModal
        match={selectedMatch}
        isOpen={showScoreModal}
        onClose={() => {
          setShowScoreModal(false)
          setSelectedMatch(null)
        }}
        onSuccess={() => {
          setShowScoreModal(false)
          setSelectedMatch(null)
          onScoreSuccess?.()
        }}
        updateScoreFn={updateScoreFn}
      />
    </div>
  )
}

interface MatchCardProps {
  match: Match
  selected: boolean
  onClick: () => void
  isDirectorMode: boolean
  onTimeKeeperOpen?: (matchId: string) => void
  formatTime: (dateString?: string) => string | null
}

function MatchCard({
  match,
  selected,
  onClick,
  isDirectorMode,
  onTimeKeeperOpen,
  formatTime,
}: MatchCardProps) {
  const isBye = match.status === 'bye'
  const isCompleted = match.status === 'completed'
  const isInProgress = match.status === 'in_progress'
  const isPending = match.status === 'pending'

  const statusColor = isBye
    ? 'bg-slate-700/30 border-slate-600'
    : isCompleted
      ? 'bg-green-900/20 border-green-700'
      : isInProgress
        ? 'bg-amber-900/20 border-amber-700'
        : isPending
          ? 'bg-slate-700/50 border-slate-600'
          : 'bg-slate-700/50 border-slate-600'

  const statusTextColor = isBye
    ? 'text-slate-500'
    : isCompleted
      ? 'text-green-300'
      : isInProgress
        ? 'text-amber-300'
        : 'text-slate-300'

  return (
    <div
      className={`border rounded-lg p-3 transition-all cursor-pointer ${statusColor} ${
        selected ? 'ring-2 ring-sky-500 ring-opacity-75' : ''
      }`}
      onClick={onClick}
    >
      {isBye ? (
        <div className="text-center py-2">
          <p className="text-xs font-semibold text-slate-500 uppercase">BYE</p>
        </div>
      ) : (
        <>
          {/* Match Header */}
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              {match.table_number && (
                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-sky-500/20 text-sky-400 text-xs font-bold">
                  T{match.table_number}
                </span>
              )}
              <span className={`text-xs font-semibold uppercase tracking-wide ${statusTextColor}`}>
                {isCompleted ? '✓ Done' : isInProgress ? '⏱ Live' : 'Pending'}
              </span>
            </div>
            {match.scheduled_time && (
              <span className="text-xs text-slate-400">🕐 {formatTime(match.scheduled_time)}</span>
            )}
          </div>

          {/* Players */}
          <div className="space-y-2">
            {/* Player 1 */}
            <div className={`p-2 rounded border ${isCompleted && match.winner_id === match.operator_id ? 'bg-green-900/30 border-green-700' : 'bg-slate-700/30 border-slate-600'}`}>
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-white truncate flex-1">
                  {match.operator_name || 'TBD'}
                </p>
                {isCompleted && (
                  <span className="ml-2 text-sm font-bold text-white flex-shrink-0">
                    {match.operator_score}
                  </span>
                )}
              </div>
            </div>

            {/* Player 2 */}
            <div className={`p-2 rounded border ${isCompleted && match.winner_id === match.player2_id ? 'bg-green-900/30 border-green-700' : 'bg-slate-700/30 border-slate-600'}`}>
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-white truncate flex-1">
                  {match.player2_name || 'TBD'}
                </p>
                {isCompleted && (
                  <span className="ml-2 text-sm font-bold text-white flex-shrink-0">
                    {match.player2_score}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Director Actions */}
          {isDirectorMode && !isCompleted && (
            <div className="mt-3 pt-3 border-t border-slate-600 flex gap-2">
              <button
                className="flex-1 px-2 py-1.5 text-xs font-semibold rounded bg-sky-600 hover:bg-sky-500 text-white transition-colors"
                onClick={(e) => {
                  e.stopPropagation()
                  onClick()
                }}
              >
                📊 Score
              </button>
              {onTimeKeeperOpen && (
                <button
                  className="flex-1 px-2 py-1.5 text-xs font-semibold rounded bg-amber-600 hover:bg-amber-500 text-white transition-colors"
                  onClick={(e) => {
                    e.stopPropagation()
                    onTimeKeeperOpen(match.match_id)
                  }}
                >
                  ⏱️ Timer
                </button>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
