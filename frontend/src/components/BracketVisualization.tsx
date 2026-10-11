/**
 * Tournament Bracket Visualization Component
 * Renders a traditional tournament bracket with connecting lines
 * Similar to the VectorStock 64-team tournament bracket style
 */

import React, { useState } from 'react'

interface BracketMatch {
  match_id: string
  tournament_id: string
  operator_id?: string
  player2_id?: string
  operator_name?: string
  player2_name?: string
  operator_score?: number
  player2_score?: number
  winner_id?: string
  status: string
  table_number?: number
  round_number: number
  bracket_type: string
}

interface BracketVisualizationProps {
  matches: BracketMatch[]
  tournamentName: string
  isDirectorMode?: boolean
  onMatchClick?: (match: BracketMatch) => void
}

interface BracketNode {
  id: string
  name: string
  score?: number
  winner: boolean
  match?: BracketMatch
  children?: [BracketNode, BracketNode]
}

export default function BracketVisualization({
  matches,
  tournamentName,
  isDirectorMode = false,
  onMatchClick
}: BracketVisualizationProps) {
  const [selectedMatch, setSelectedMatch] = useState<BracketMatch | null>(null)

  // Group matches by round
  const matchesByRound = matches.reduce((acc, match) => {
    const key = `${match.bracket_type}-${match.round_number}`
    if (!acc[key]) acc[key] = []
    acc[key].push(match)
    return acc
  }, {} as Record<string, BracketMatch[]>)

  // Get max round number
  const maxRound = Math.max(...matches.map(m => m.round_number))

  const handleMatchClick = (match: BracketMatch) => {
    setSelectedMatch(match)
    onMatchClick?.(match)
  }

  const getMatchStatus = (match: BracketMatch) => {
    if (match.status === 'completed') return 'completed'
    if (match.status === 'in_progress') return 'active'
    return 'pending'
  }

  const getWinnerName = (match: BracketMatch) => {
    if (!match.winner_id) return null
    if (match.winner_id === match.operator_id) return match.operator_name
    if (match.winner_id === match.player2_id) return match.player2_name
    return null
  }

  return (
    <div className="bracket-visualization">
      <div className="bracket-header">
        <h2 className="bracket-title">🏆 {tournamentName} - Tournament Bracket</h2>
        <p className="bracket-subtitle">Click on matches to view details</p>
      </div>

      <div className="bracket-container">
        {/* Render rounds from right to left (finals on left, early rounds on right) */}
        {Array.from({ length: maxRound }, (_, i) => maxRound - i).map(roundNum => {
          const roundMatches = matchesByRound[`winners-${roundNum}`] || []
          const isFinal = roundNum === maxRound

          return (
            <div key={`round-${roundNum}`} className={`bracket-round ${isFinal ? 'final-round' : ''}`}>
              <div className="round-header">
                <h3 className="round-title">
                  {isFinal ? '🏆 Final' : `Round ${roundNum}`}
                </h3>
                <span className="round-count">{roundMatches.length} matches</span>
              </div>

              <div className="round-matches">
                {roundMatches.map((match, index) => {
                  const status = getMatchStatus(match)
                  const winnerName = getWinnerName(match)

                  return (
                    <div key={match.match_id} className="bracket-match-container">
                      {/* Connecting line from previous round (if not round 1) */}
                      {roundNum > 1 && (
                        <div className="bracket-connector">
                          <div className="connector-line"></div>
                        </div>
                      )}

                      {/* Match box */}
                      <div
                        className={`bracket-match ${status} ${selectedMatch?.match_id === match.match_id ? 'selected' : ''}`}
                        onClick={() => handleMatchClick(match)}
                      >
                        <div className="match-players">
                          <div className={`player-slot ${match.winner_id === match.operator_id ? 'winner' : ''}`}>
                            <span className="player-name">
                              {match.operator_name || 'TBD'}
                            </span>
                            {match.operator_score !== undefined && (
                              <span className="player-score">{match.operator_score}</span>
                            )}
                          </div>

                          <div className="vs-divider">vs</div>

                          <div className={`player-slot ${match.winner_id === match.player2_id ? 'winner' : ''}`}>
                            <span className="player-name">
                              {match.player2_name || 'TBD'}
                            </span>
                            {match.player2_score !== undefined && (
                              <span className="player-score">{match.player2_score}</span>
                            )}
                          </div>
                        </div>

                        <div className="match-footer">
                          <span className="match-table">
                            {match.table_number ? `Table ${match.table_number}` : 'TBD'}
                          </span>
                          <span className={`match-status status-${status}`}>
                            {status === 'completed' ? '✓' :
                             status === 'active' ? '🔴' : '⏳'}
                          </span>
                        </div>

                        {/* Winner advancement line (if not final round) */}
                        {roundNum < maxRound && winnerName && (
                          <div className="winner-connector">
                            <div className="winner-line"></div>
                            <div className="winner-arrow">▶</div>
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>

      {/* Legend */}
      <div className="bracket-legend">
        <div className="legend-item">
          <div className="legend-color completed"></div>
          <span>Completed</span>
        </div>
        <div className="legend-item">
          <div className="legend-color active"></div>
          <span>In Progress</span>
        </div>
        <div className="legend-item">
          <div className="legend-color pending"></div>
          <span>Pending</span>
        </div>
        <div className="legend-item">
          <div className="winner-indicator">★</div>
          <span>Winner</span>
        </div>
      </div>

      <style jsx>{`
        .bracket-visualization {
          width: 100%;
          padding: 20px;
          background: #0f172a;
          border-radius: 12px;
          color: white;
        }

        .bracket-header {
          text-align: center;
          margin-bottom: 30px;
          padding-bottom: 20px;
          border-bottom: 2px solid #334155;
        }

        .bracket-title {
          font-size: 2rem;
          font-weight: bold;
          color: #f1f5f9;
          margin-bottom: 8px;
        }

        .bracket-subtitle {
          color: #94a3b8;
          font-size: 1rem;
        }

        .bracket-container {
          display: flex;
          overflow-x: auto;
          gap: 40px;
          padding: 20px;
          justify-content: center;
          min-height: 600px;
        }

        .bracket-round {
          display: flex;
          flex-direction: column;
          align-items: center;
          min-width: 280px;
        }

        .final-round {
          background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
          border-radius: 12px;
          padding: 20px;
          margin: 0 10px;
        }

        .round-header {
          margin-bottom: 20px;
          text-align: center;
        }

        .round-title {
          font-size: 1.2rem;
          font-weight: bold;
          color: #e2e8f0;
          margin-bottom: 4px;
        }

        .round-count {
          color: #64748b;
          font-size: 0.9rem;
        }

        .round-matches {
          display: flex;
          flex-direction: column;
          gap: 60px;
          align-items: center;
        }

        .bracket-match-container {
          position: relative;
          display: flex;
          align-items: center;
        }

        .bracket-connector {
          position: absolute;
          right: -40px;
          top: 50%;
          transform: translateY(-50%);
          width: 40px;
          height: 2px;
          background: #475569;
        }

        .connector-line {
          width: 100%;
          height: 100%;
          background: linear-gradient(90deg, #475569 0%, #64748b 100%);
          border-radius: 1px;
        }

        .bracket-match {
          background: #1e293b;
          border: 2px solid #334155;
          border-radius: 8px;
          padding: 16px;
          min-width: 240px;
          cursor: pointer;
          transition: all 0.3s ease;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        }

        .bracket-match:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
          border-color: #3b82f6;
        }

        .bracket-match.selected {
          border-color: #10b981;
          box-shadow: 0 0 20px rgba(16, 185, 129, 0.3);
        }

        .bracket-match.completed {
          border-color: #10b981;
          background: linear-gradient(135deg, #1e293b 0%, #065f46 20%);
        }

        .bracket-match.active {
          border-color: #f59e0b;
          background: linear-gradient(135deg, #1e293b 0%, #92400e 20%);
        }

        .match-players {
          display: flex;
          flex-direction: column;
          gap: 8px;
          margin-bottom: 12px;
        }

        .player-slot {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 12px;
          background: #334155;
          border-radius: 6px;
          transition: all 0.2s ease;
        }

        .player-slot.winner {
          background: linear-gradient(135deg, #065f46 0%, #047857 100%);
          border: 2px solid #10b981;
        }

        .player-name {
          font-weight: 500;
          color: #f1f5f9;
          flex: 1;
          text-align: left;
        }

        .player-score {
          font-family: 'Monaco', monospace;
          font-weight: bold;
          color: #10b981;
          background: #0f172a;
          padding: 2px 6px;
          border-radius: 4px;
          min-width: 24px;
          text-align: center;
        }

        .vs-divider {
          text-align: center;
          color: #64748b;
          font-size: 0.8rem;
          font-weight: bold;
          margin: 4px 0;
          text-transform: uppercase;
          letter-spacing: 1px;
        }

        .match-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 0.85rem;
          color: #94a3b8;
        }

        .match-table {
          font-weight: 500;
        }

        .match-status {
          font-size: 1.2rem;
        }

        .status-completed {
          color: #10b981;
        }

        .status-active {
          color: #f59e0b;
        }

        .status-pending {
          color: #64748b;
        }

        .winner-connector {
          position: absolute;
          left: -40px;
          top: 50%;
          transform: translateY(-50%);
          display: flex;
          align-items: center;
        }

        .winner-line {
          width: 30px;
          height: 2px;
          background: linear-gradient(-90deg, #10b981 0%, #065f46 100%);
          border-radius: 1px;
        }

        .winner-arrow {
          color: #10b981;
          font-size: 0.8rem;
          margin-left: 4px;
        }

        .bracket-legend {
          display: flex;
          justify-content: center;
          gap: 30px;
          margin-top: 30px;
          padding-top: 20px;
          border-top: 1px solid #334155;
          flex-wrap: wrap;
        }

        .legend-item {
          display: flex;
          align-items: center;
          gap: 8px;
          color: #94a3b8;
          font-size: 0.9rem;
        }

        .legend-color {
          width: 16px;
          height: 16px;
          border-radius: 4px;
        }

        .legend-color.completed {
          background: linear-gradient(135deg, #10b981 0%, #065f46 100%);
          border: 1px solid #10b981;
        }

        .legend-color.active {
          background: linear-gradient(135deg, #f59e0b 0%, #92400e 100%);
          border: 1px solid #f59e0b;
        }

        .legend-color.pending {
          background: #334155;
          border: 1px solid #475569;
        }

        .winner-indicator {
          color: #10b981;
          font-size: 1.2rem;
        }

        /* Mobile responsiveness */
        @media (max-width: 768px) {
          .bracket-container {
            flex-direction: column;
            gap: 20px;
            overflow-x: visible;
          }

          .bracket-round {
            min-width: auto;
            width: 100%;
          }

          .bracket-match {
            min-width: 200px;
          }

          .bracket-connector,
          .winner-connector {
            display: none;
          }

          .bracket-legend {
            flex-direction: column;
            gap: 10px;
            align-items: center;
          }
        }
      `}</style>
    </div>
  )
}