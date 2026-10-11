/**
 * API path prefixes for production vs Test Center embedded views.
 * Default matches production; Test Center wraps children with test-center prefixes.
 */
import React, { createContext, useContext, useMemo } from 'react'
import { createRankingsApi } from '@/api/rankings'
import { createTournamentsApi } from '@/api/tournaments'
import { createTournamentHistoryApi } from '@/api/tournamentHistory'

export interface ApiPathPrefixes {
  rankings: string
  tournaments: string
  tournamentHistory: string
  /** Distinguishes React Query cache keys when embedding production pages in Test Center. */
  scope: 'production' | 'test-center'
}

const defaultPrefixes: ApiPathPrefixes = {
  rankings: '/rankings',
  tournaments: '/tournaments',
  tournamentHistory: '/tournament-history',
  scope: 'production',
}

const ApiPathContext = createContext<ApiPathPrefixes>(defaultPrefixes)

export function ApiPathProvider({
  children,
  value,
}: {
  children: React.ReactNode
  value: Partial<ApiPathPrefixes>
}) {
  const merged = { ...defaultPrefixes, ...value }
  return <ApiPathContext.Provider value={merged}>{children}</ApiPathContext.Provider>
}

export function useApiPathPrefixes(): ApiPathPrefixes {
  return useContext(ApiPathContext)
}

export function useRankingsApi() {
  const { rankings } = useApiPathPrefixes()
  return useMemo(() => createRankingsApi(rankings), [rankings])
}

export function useTournamentsApi() {
  const { tournaments } = useApiPathPrefixes()
  return useMemo(() => createTournamentsApi(tournaments), [tournaments])
}

export function useTournamentHistoryApi() {
  const { tournamentHistory } = useApiPathPrefixes()
  return useMemo(() => createTournamentHistoryApi(tournamentHistory), [tournamentHistory])
}

/** Test Center: all mirror routes under /api/test-center/... */
export const testCenterApiPrefixes: ApiPathPrefixes = {
  rankings: '/test-center/rankings',
  tournaments: '/test-center/tournaments',
  tournamentHistory: '/test-center/tournament-history',
  scope: 'test-center',
}
