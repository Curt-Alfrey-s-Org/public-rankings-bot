/**
 * ComparisonStats - Head-to-head record and common opponents
 */

import type { HeadToHeadRecord, PlayerComparison } from '@/features/head-to-head/types/comparison'

interface ComparisonStatsProps {
  headToHead: HeadToHeadRecord
  operator: PlayerComparison
  player2: PlayerComparison
  player1Name: string
  player2Name: string
  showAlfa?: boolean
}

export function ComparisonStats({ headToHead, operator, player2, player1Name, player2Name, showAlfa = false }: ComparisonStatsProps) {
  const { 
    direct_wins_p1, 
    direct_losses_p1, 
    fargo_win_probability_p1,
    fargo_win_probability_p2,
    common_opponents, 
    matches 
  } = headToHead

  // Helper to format match result for display
  const formatMatchResult = (match: typeof matches[0]) => {
    const isPlayer1First = match.operator_name === player1Name
    const p1Score = isPlayer1First ? match.operator_score : match.player2_score
    const p2Score = isPlayer1First ? match.player2_score : match.operator_score
    
    return {
      score: `${p1Score ?? '?'}–${p2Score ?? '?'}`,
      winner: match.winner === player1Name ? player1Name : 
              match.winner === player2Name ? player2Name : 
              'Unknown'
    }
  }

  // Calculate win probability percentages
  const hasWinProbability = fargo_win_probability_p1 !== null && 
                            fargo_win_probability_p1 !== undefined &&
                            fargo_win_probability_p2 !== null && 
                            fargo_win_probability_p2 !== undefined
  
  const winProbP1Pct = hasWinProbability ? Math.round((fargo_win_probability_p1 ?? 0) * 100) : null
  const winProbP2Pct = hasWinProbability ? Math.round((fargo_win_probability_p2 ?? 0) * 100) : null

  return (
    <div className="space-y-4">
      {/* Fargo Ratings (and ALFa when admin) & Win Probability */}
      <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <h3 className="text-lg font-semibold text-sky-400 mb-3">{showAlfa ? 'Fargo & ALFa Ratings' : 'Fargo Ratings'}</h3>
        {showAlfa && <p className="text-xs text-slate-500 mb-3">ALFa = fargo on steroids</p>}
        
        {/* Fargo Display */}
        <div className="grid grid-cols-2 gap-4 mb-2">
          <div className="text-center">
            <p className="text-sm text-slate-400 mb-1">{player1Name}</p>
            <p className="text-xs text-slate-500">Fargo</p>
            {operator.fargo_rating !== null && operator.fargo_rating !== undefined ? (
              <p className="text-2xl font-bold text-sky-400">{operator.fargo_rating}</p>
            ) : (
              <p className="text-sm text-slate-500 italic">Not rated</p>
            )}
            {showAlfa && (
              <>
                <p className="text-xs text-slate-500 mt-2">ALFa Rating</p>
                {operator.alfa_rating != null ? (
                  <p className="text-2xl font-bold text-sky-400">{Math.round(operator.alfa_rating)}</p>
                ) : (
                  <p className="text-sm text-slate-500 italic">—</p>
                )}
              </>
            )}
          </div>
          <div className="text-center">
            <p className="text-sm text-slate-400 mb-1">{player2Name}</p>
            <p className="text-xs text-slate-500">Fargo</p>
            {player2.fargo_rating !== null && player2.fargo_rating !== undefined ? (
              <p className="text-2xl font-bold text-slate-400">{player2.fargo_rating}</p>
            ) : (
              <p className="text-sm text-slate-500 italic">Not rated</p>
            )}
            {showAlfa && (
              <>
                <p className="text-xs text-slate-500 mt-2">ALFa Rating</p>
                {player2.alfa_rating != null ? (
                  <p className="text-2xl font-bold text-slate-400">{Math.round(player2.alfa_rating)}</p>
                ) : (
                  <p className="text-sm text-slate-500 italic">—</p>
                )}
              </>
            )}
          </div>
        </div>

        {/* Win Probability Bar */}
        {hasWinProbability && winProbP1Pct !== null && winProbP2Pct !== null && (
          <div className="mt-4">
            <p className="text-xs text-slate-400 mb-2 text-center">Win Probability (Fargo-based)</p>
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-sky-400 w-12 text-right">{winProbP1Pct}%</span>
              <div className="flex-1 h-6 rounded-full overflow-hidden bg-slate-700 flex">
                <div 
                  className="bg-sky-500 transition-all duration-300"
                  style={{ width: `${winProbP1Pct}%` }}
                />
                <div 
                  className="bg-slate-500 transition-all duration-300"
                  style={{ width: `${winProbP2Pct}%` }}
                />
              </div>
              <span className="text-sm font-semibold text-slate-400 w-12">{winProbP2Pct}%</span>
            </div>
          </div>
        )}

        {!hasWinProbability && (
          <p className="text-sm text-slate-500 text-center mt-2 italic">
            Win probability unavailable (requires Fargo ratings for both players)
          </p>
        )}
      </div>

      {/* Summary Stats */}
      <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
        <h3 className="text-lg font-semibold text-sky-400">Head-to-Head Summary</h3>
        <div className="mt-2 text-sm text-slate-300">
          <p>
            {player1Name} vs {player2Name}: {direct_wins_p1}–{direct_losses_p1}
          </p>
          {common_opponents.length > 0 && (
            <p className="mt-2">
              Common opponents: {common_opponents.length}
            </p>
          )}
          {matches.length > 0 && (
            <p className="mt-2 text-slate-400">
              Total matches: {matches.length}
            </p>
          )}
        </div>
      </div>

      {/* Match History */}
      {matches.length > 0 && (
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
          <h3 className="text-lg font-semibold text-sky-400 mb-3">Match History</h3>
          <div className="space-y-3">
            {matches.map((match) => {
              const result = formatMatchResult(match)
              const winnerIsP1 = result.winner === player1Name
              
              return (
                <div 
                  key={match.id} 
                  className="border-l-4 pl-3 py-2 rounded-r border-slate-600 bg-slate-900/30"
                  style={{ 
                    borderLeftColor: winnerIsP1 ? '#38bdf8' : '#94a3b8' 
                  }}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <p className="font-medium text-white">
                        {match.tournament_name}
                      </p>
                      <p className="text-sm text-slate-400 mt-1">
                        {match.date || match.year || 'Date unknown'} • {match.location}
                      </p>
                      {match.round && (
                        <p className="text-xs text-slate-500 mt-0.5">
                          Round {match.round}
                        </p>
                      )}
                    </div>
                    <div className="text-right ml-4">
                      <p className={`font-bold ${winnerIsP1 ? 'text-sky-400' : 'text-slate-400'}`}>
                        {result.score}
                      </p>
                      <p className="text-xs text-slate-500 mt-1">
                        Winner: {result.winner}
                      </p>
                    </div>
                  </div>
                  {match.notes && (
                    <p className="text-xs text-slate-500 mt-2 italic">
                      {match.notes}
                    </p>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* No matches message */}
      {matches.length === 0 && (
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
          <p className="text-sm text-slate-400 text-center">
            No direct match history found between these players.
          </p>
        </div>
      )}
    </div>
  )
}
