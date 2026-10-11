import { useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import BracketGrid from '@/components/BracketGrid'
import { testTournamentsApi, type TestMatch } from '@/api/testTournaments'

interface TestCenterBracketPanelProps {
  tournamentId: string
  matches: TestMatch[]
  isDirectorMode?: boolean
  title?: string
  isLoading?: boolean
  tournamentStatus?: string
}

export default function TestCenterBracketPanel({
  tournamentId,
  matches,
  isDirectorMode = false,
  title = 'Bracket',
  isLoading = false,
  tournamentStatus,
}: TestCenterBracketPanelProps) {
  const queryClient = useQueryClient()

  const refreshBracketData = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['test-matches'] })
    queryClient.invalidateQueries({ queryKey: ['test-bracket-tree'] })
    queryClient.invalidateQueries({ queryKey: ['test-tournament'] })
    queryClient.invalidateQueries({ queryKey: ['test-leaderboard'] })
  }, [queryClient])

  const updateScoreFn = useCallback(
    (matchId: string, player1Games: number, player2Games: number) =>
      testTournamentsApi.updateMatchScore(matchId, player1Games, player2Games),
    [],
  )

  return (
    <div className="mb-6 border border-slate-700 rounded-lg p-4 bg-slate-900/40">
      <h3 className="text-xl font-semibold text-white mb-1">{title}</h3>
      {tournamentStatus === 'completed' && (
        <p className="text-sm text-emerald-400 mb-2">Tournament finished — bracket is read-only for review.</p>
      )}
      {isDirectorMode && tournamentStatus !== 'completed' && (
        <p className="text-sm text-slate-400 mb-4">
          Click a match and use Score to enter results. Winners advance automatically.
        </p>
      )}
      <BracketGrid
        tournamentId={tournamentId}
        matches={matches}
        isLoading={isLoading}
        isDirectorMode={isDirectorMode && tournamentStatus !== 'completed'}
        updateScoreFn={updateScoreFn}
        onScoreSuccess={refreshBracketData}
      />
    </div>
  )
}
