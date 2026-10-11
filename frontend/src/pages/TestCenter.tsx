/**
 * Test Center - Comprehensive Testing Suite
 * ========================================
 *
 * Admin+ only testing interface for tournament and system features.
 * Isolated from live data - safe for testing and development.
 *
 * Features:
 * - Test Tournament Management
 * - API Endpoint Testing
 * - Database Operations Testing
 * - Live System Monitoring
 * - Development Utilities
 */

import { useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { testTournamentsApi } from '@/api/testTournaments'
import { tournamentsApi, type BracketTemplate } from '@/api/tournaments'
import { tournamentHistoryApi, type UpcomingEvent } from '@/api/tournamentHistory'
import Rankings from '@/pages/Rankings'
import Leaderboard from '@/pages/Leaderboard'
import HotStreak from '@/pages/HotStreak'
import TournamentHistory from '@/pages/TournamentHistory'
import { ApiPathProvider, testCenterApiPrefixes } from '@/contexts/ApiPathContext'
import { usersApi } from '@/api/users'
import { useAuth } from '@/contexts/AuthContext'
import PageLoader from '@/components/PageLoader'
import { toast } from '@/lib/toast'
import { testCenterLogger, testCenterLog } from '@/lib/testCenterLogger'
import { testCenterErrorHandler, errorHandler, TestCenterError } from '@/lib/testCenterErrorHandler'
import TestCenterErrorDisplay from '@/components/TestCenterErrorDisplay'
import TestCenterMonitoring from '@/components/TestCenterMonitoring'
import TournamentPersistenceManager from '@/components/TournamentPersistenceManager'
import EnhancedApiTestingTab from '@/components/EnhancedApiTestingTab'
import TestCenterResetManager from '@/components/TestCenterResetManager'
import TestCenterBracketPanel from '@/components/TestCenterBracketPanel'
import ExportImportManager from '@/components/ExportImportManager'
import {
  useTournamentPersistenceInit,
  useSaveTournament,
  useLoadTournament,
  useTournamentStateWithPersistence
} from '@/hooks/useTournamentPersistence'
import { TournamentWorkflowState, SavedTournament } from '@/lib/tournamentPersistence'
import { buildTestSetupFromUpcomingEvent } from '@/lib/testCenterUpcomingPrefill'
import { upcomingEventKey } from '@/lib/upcomingEventPrefill'
import './TestCenter.css'

type TestSetupEntryMode = 'choose' | 'pick-scheduled' | 'form'

type WorkflowStep = TournamentWorkflowState['currentStep']

const WORKFLOW_STEPS: { id: WorkflowStep; number: number; label: string }[] = [
  { id: 'setup', number: 1, label: 'Setup' },
  { id: 'registration', number: 2, label: 'Registration' },
  { id: 'brackets', number: 3, label: 'Brackets' },
  { id: 'matches', number: 4, label: 'Matches' },
  { id: 'results', number: 5, label: 'Results' },
]

function canNavigateToWorkflowStep(
  step: WorkflowStep,
  tournament: { tournament_id?: string; status?: string } | null | undefined,
  matchCount: number,
): boolean {
  switch (step) {
    case 'setup':
      return true
    case 'registration':
    case 'brackets':
      return Boolean(tournament?.tournament_id)
    case 'matches':
    case 'results':
      return matchCount > 0
    default:
      return false
  }
}

function resolveWorkflowStep(
  currentStep: WorkflowStep,
  tournament: { tournament_id?: string; status?: string } | null | undefined,
  matchCount: number,
): WorkflowStep | null {
  if (!tournament?.tournament_id) return null
  if (matchCount > 0) {
    if (tournament.status === 'completed' && currentStep !== 'results') {
      return 'results'
    }
    if (currentStep === 'setup') {
      return tournament.status === 'completed' ? 'results' : 'matches'
    }
    return null
  }
  if (['matches', 'results'].includes(currentStep)) {
    return 'brackets'
  }
  if (currentStep === 'setup') {
    return 'registration'
  }
  return null
}

function upcomingMatchesDirectorAssociation(
  event: { association?: string; name?: string },
  directorAssoc: string,
): boolean {
  if (!directorAssoc) return true
  const d = directorAssoc.toUpperCase()
  const evAssoc = (event.association || '').toUpperCase()
  const title = (event.name || '').toUpperCase()
  if (d.includes('WPBA')) {
    return evAssoc.includes('WPBA') || title.includes('WPBA') || evAssoc === 'WPBA'
  }
  if (d.includes('WPA') && !d.includes('WPBA')) {
    if (evAssoc.includes('WPBA') || title.includes('WPBA')) return false
    return evAssoc.includes('WPA') || title.includes('WPA') || !evAssoc
  }
  return !evAssoc || evAssoc === d || d.startsWith(evAssoc) || evAssoc.startsWith(d)
}

function formatEventDateLabel(evt: {
  date?: string | null
  start_date?: string | null
  end_date?: string | null
}) {
  const start = evt.start_date ?? evt.date
  const end = evt.end_date ?? start
  if (!start) return ''
  if (end && end !== start) return `${start} – ${end}`
  return start
}

interface TestResult {
  test: string
  status: 'pending' | 'running' | 'passed' | 'failed'
  message: string
  duration?: number
}

export default function TestCenter() {
  const { isDirector, isSuperAdmin, isAdmin } = useAuth()
  const canAccessTestCenter = isDirector || isAdmin || isSuperAdmin
  const canUseAdminTools = isAdmin || isSuperAdmin
  const isDirectorMode = canAccessTestCenter
  const queryClient = useQueryClient()
  type TestCenterTab =
    | 'tournament-workflow'
    | 'api'
    | 'database'
    | 'system'
    | 'reset'
    | 'test-rankings'
    | 'test-leaderboard'
    | 'test-hot-streak'
    | 'test-tournament-history'
  const [activeTab, setActiveTab] = useState<TestCenterTab>('tournament-workflow')
  const [testResults, setTestResults] = useState<TestResult[]>([])
  const [isRunningTests, setIsRunningTests] = useState(false)
  const [currentErrors, setCurrentErrors] = useState<TestCenterError[]>([])
  const [errorRecoveryAttempts, setErrorRecoveryAttempts] = useState<Map<string, number>>(new Map())

  // Persistence state
  const [showPersistenceManager, setShowPersistenceManager] = useState(false)
  const [saveName, setSaveName] = useState('')
  const [saveDescription, setSaveDescription] = useState('')

  // Export/Import state
  const [showExportImportManager, setShowExportImportManager] = useState(false)

  // Initialize persistence service
  const { isLoading: persistenceLoading } = useTournamentPersistenceInit()

  // Persistence hooks
  const saveTournamentMutation = useSaveTournament()
  const loadTournamentMutation = useLoadTournament()

  // Tournament state with persistence
  const {
    tournamentState,
    updateTournamentState,
    resetTournamentState,
    saveTournament,
    lastAutoSaved,
    isAutoSaving
  } = useTournamentStateWithPersistence()

  // Error management functions
  const addError = (error: TestCenterError) => {
    setCurrentErrors(prev => {
      // Check if similar error already exists
      const existingIndex = prev.findIndex(e =>
        e.type === error.type && e.message === error.message
      )
      if (existingIndex >= 0) {
        // Update existing error
        const updated = [...prev]
        updated[existingIndex] = error
        return updated
      }
      return [...prev, error]
    })

    testCenterLog.userInteraction('error_displayed', {
      errorType: error.type,
      errorCount: currentErrors.length + 1
    })
  }

  const removeError = (errorIndex: number) => {
    setCurrentErrors(prev => prev.filter((_, index) => index !== errorIndex))
  }

  const clearErrors = () => {
    testCenterLog.userInteraction('errors_cleared', {
      errorCount: currentErrors.length
    })
    setCurrentErrors([])
  }

  const handleErrorRecovery = async (error: TestCenterError, action: string) => {
    const errorId = `${error.type}_${Date.now()}`
    const attemptCount = errorRecoveryAttempts.get(errorId) || 0

    if (attemptCount >= 3) {
      toast.error('Maximum recovery attempts reached. Please contact support.')
      return
    }

    setErrorRecoveryAttempts(prev => new Map(prev.set(errorId, attemptCount + 1)))

    try {
      const success = await errorHandler.attemptRecovery(error, action, {
        tab: activeTab as TestCenterTab
      })

      if (success) {
        testCenterLogger.errorRecovery(error.type, action, true, {
          tab: activeTab as TestCenterTab
        } as any)

        // Remove the error from display
        setCurrentErrors(prev => prev.filter(e => e !== error))
        toast.success(`Recovery action "${action}" completed successfully`)
      } else {
        testCenterLogger.errorRecovery(error.type, action, false, {
          tab: activeTab as TestCenterTab
        } as any)
        toast.error(`Recovery action "${action}" failed. Please try again.`)
      }
    } catch (recoveryError) {
      testCenterLogger.errorRecovery(error.type, action, false, {
        tab: activeTab as TestCenterTab,
        recoveryError: recoveryError.message
      } as any)
      toast.error('Recovery action failed unexpectedly')
    }
  }

  // Cleanup old errors periodically
  useEffect(() => {
    const cleanup = setInterval(() => {
      setCurrentErrors(prev => prev.filter(error => {
        // Keep network and auth errors, remove others after 30 seconds
        if (error.type === 'network' || error.type === 'auth') {
          return true
        }
        return false // Remove other errors after timeout
      }))

      // Cleanup old recovery attempts
      setErrorRecoveryAttempts(prev => {
        const now = Date.now()
        const newMap = new Map()
        for (const [key, attempts] of prev.entries()) {
          const errorTime = parseInt(key.split('_').pop() || '0')
          if (now - errorTime < 300000) { // Keep for 5 minutes
            newMap.set(key, attempts)
          }
        }
        return newMap
      })
    }, 30000) // Every 30 seconds

    return () => clearInterval(cleanup)
  }, [])

  // Directors and admins may use Test Center tournament workflow; admin-only tabs stay restricted.
  if (!canAccessTestCenter) {
    return (
      <div className="test-center-denied">
        <div className="denied-content">
          <h1>🔒 Access Denied</h1>
          <p>This page requires tournament director or administrator privileges.</p>
          <p>Please contact a system administrator for access.</p>
        </div>
      </div>
    )
  }

  // Test Tournament Data
  const { data: tournament, isLoading: tournamentLoading } = useQuery({
    queryKey: ['test-tournament'],
    queryFn: () => testTournamentsApi.getCurrentTournament(),
    enabled: activeTab === 'tournament-workflow' || activeTab === 'reset',
    staleTime: 0,
    refetchOnMount: true
  })

  const { data: myAssociationsData } = useQuery({
    queryKey: ['test-center', 'my-associations'],
    queryFn: () => usersApi.getMyAssociations(),
    enabled: (activeTab === 'tournament-workflow' || activeTab === 'reset') && canAccessTestCenter,
    staleTime: 60_000
  })
  const associationOptions = myAssociationsData?.associations ?? []

  const setupAssociation = tournamentState.tournamentSetup.association ?? ''
  const { data: bracketTemplates = [], isLoading: bracketTemplatesLoading } = useQuery({
    queryKey: ['test-center', 'bracket-templates', setupAssociation],
    queryFn: () => tournamentsApi.getBracketTemplates(setupAssociation || undefined),
    enabled: (activeTab === 'tournament-workflow' || activeTab === 'reset') && canAccessTestCenter,
    staleTime: 60_000
  })

  const { data: players = [], isLoading: playersLoading } = useQuery({
    queryKey: ['test-players'],
    queryFn: () => testTournamentsApi.getPlayers(),
    enabled: activeTab === 'tournament-workflow' || activeTab === 'reset'
  })

  const { data: matches = [], isLoading: matchesLoading } = useQuery({
    queryKey: ['test-matches'],
    queryFn: () => testTournamentsApi.getMatches(),
    enabled: activeTab === 'tournament-workflow' || activeTab === 'reset'
  })

  const { data: bracketTree } = useQuery({
    queryKey: ['test-bracket-tree'],
    queryFn: () => testTournamentsApi.getBracketTree(),
    enabled: activeTab === 'tournament-workflow' && matches.length > 0,
    staleTime: 0
  })

  const { data: leaderboard = [], isLoading: leaderboardLoading } = useQuery({
    queryKey: ['test-leaderboard'],
    queryFn: () => testTournamentsApi.getLeaderboard(),
    enabled: activeTab === 'tournament-workflow' || activeTab === 'reset'
  })

  const { data: upcomingEventsData } = useQuery({
    queryKey: ['test-center-upcoming-events'],
    queryFn: () => tournamentHistoryApi.getUpcomingEvents(undefined, 500),
    enabled: activeTab === 'tournament-workflow' && (isAdmin || isSuperAdmin),
    staleTime: 300_000,
  })
  const upcomingEvents = upcomingEventsData?.events ?? []
  const directorUpcoming = useMemo(() => {
    if (!associationOptions.length) return upcomingEvents
    return upcomingEvents.filter((e) =>
      associationOptions.some((a) => upcomingMatchesDirectorAssociation(e, a)),
    )
  }, [upcomingEvents, associationOptions])

  // Mutations with enhanced error handling
  const createTournamentMutation = useMutation({
    mutationFn: async (data: any) => {
      const operationId = `create_tournament_${Date.now()}`
      testCenterLog.startOperation(operationId, {
        tab: 'tournament-workflow',
        operation: 'create_tournament',
        step: 'setup'
      })

      try {
        const result = await errorHandler.withRetry(
          () => testTournamentsApi.setupTournament(data),
          operationId,
          { maxRetries: 2 },
          { tab: 'tournament-workflow' }
        )

        testCenterLog.endOperation(operationId, true, {
          tab: 'tournament-workflow',
          operation: 'create_tournament',
          tournamentId: result?.tournament_id
        })

        return result
      } catch (error) {
        testCenterLog.endOperation(operationId, false, {
          tab: 'tournament-workflow',
          operation: 'create_tournament'
        })

        await errorHandler.handleApiError(error, operationId, {
          tab: 'tournament-workflow',
          operation: 'create_tournament'
        })
        throw error
      }
    },
    onSuccess: async (tournamentData) => {
      // Update persistent state
      updateTournamentState({
        currentStep: 'registration',
        tournament: tournamentData
      })

      testCenterLog.stepTransition('setup', 'registration', {
        tab: 'tournament-workflow',
        tournamentId: tournamentData?.tournament_id
      })

      // Manually refetch tournament data with error handling
      try {
        testCenterLog.startOperation('refetch_after_create', {
          tab: 'tournament-workflow',
          operation: 'refetch_tournament'
        })

        const refetchedData = await errorHandler.withRetry(
          () => testTournamentsApi.getCurrentTournament(),
          'refetch_after_create',
          { maxRetries: 1 },
          { tab: 'tournament-workflow' }
        )

        testCenterLog.dataFlow('tournament_refetch', 1, {
          tab: 'tournament-workflow',
          tournamentId: refetchedData?.tournament_id
        })

        // Update persistent state with full tournament data
        updateTournamentState({ tournament: refetchedData })

        queryClient.setQueryData(['test-tournament'], refetchedData)
        testCenterLog.endOperation('refetch_after_create', true)
      } catch (error) {
        testCenterLog.endOperation('refetch_after_create', false)
        await errorHandler.handleApiError(error, 'refetch_after_create', {
          tab: 'tournament-workflow'
        })
        // Don't throw here - tournament was created successfully
      }

      queryClient.invalidateQueries({ queryKey: ['test-players'] })
      testCenterLog.userInteraction('tournament_created', {
        tournamentId: tournamentData?.tournament_id,
        tournamentName: tournamentData?.name
      })
      toast.success('Test tournament created successfully!')

      // For WPBA tournaments, immediately copy real player names from the
      // production DB (prefixed with "test ") so Step 2 opens with a pre-filled
      // roster. Writes go only to the Test Center DB.
      const rs = String(tournamentData?.ranking_system || '').toUpperCase()
      if (rs.startsWith('WPBA')) {
        const cap = Number(tournamentData?.max_players) > 0
          ? Number(tournamentData?.max_players)
          : undefined
        try {
          importWpbaMutation.mutate(cap)
        } catch (err) {
          testCenterLog.criticalError(err as Error, {
            tab: 'tournament-workflow',
            operation: 'auto_import_wpba_after_create'
          })
        }
      }
    },
    onError: (error: any) => {
      // Error already handled in mutationFn, just log the final failure
      testCenterLog.criticalError(error, {
        tab: 'tournament-workflow',
        operation: 'create_tournament_final_failure'
      })
    }
  })

  const generateBracketMutation = useMutation({
    mutationFn: async (options: any) => {
      const operationId = `generate_bracket_${Date.now()}`
      testCenterLog.startOperation(operationId, {
        tab: 'tournament-workflow',
        operation: 'generate_bracket',
        step: 'brackets'
      })

      try {
        const result = await errorHandler.withRetry(
          () => testTournamentsApi.generateBracket(options),
          operationId,
          { maxRetries: 2 },
          { tab: 'tournament-workflow' }
        )

        testCenterLog.endOperation(operationId, true, {
          tab: 'tournament-workflow',
          operation: 'generate_bracket',
          dataSize: result?.matches_created || 0
        })

        return result
      } catch (error) {
        testCenterLog.endOperation(operationId, false, {
          tab: 'tournament-workflow',
          operation: 'generate_bracket'
        })

        await errorHandler.handleApiError(error, operationId, {
          tab: 'tournament-workflow',
          operation: 'generate_bracket'
        })
        throw error
      }
    },
    onSuccess: (result) => {
      // Update persistent state
      updateTournamentState({ currentStep: 'matches' })

      testCenterLog.stepTransition('brackets', 'matches', {
        tab: 'tournament-workflow',
        matchesCreated: result?.matches_created
      })

      queryClient.invalidateQueries({ queryKey: ['test-matches'] })
      queryClient.invalidateQueries({ queryKey: ['test-bracket-tree'] })
      queryClient.invalidateQueries({ queryKey: ['test-tournament'] })
      testCenterLog.userInteraction('bracket_generated', {
        matchesCreated: result?.matches_created
      })
      toast.success(`Bracket generated successfully! Created ${result?.matches_created || 0} matches.`)
    },
    onError: (error: any) => {
      // Error already handled in mutationFn
      testCenterLog.criticalError(error, {
        tab: 'tournament-workflow',
        operation: 'generate_bracket_final_failure'
      })
    }
  })

  const simulateMatchMutation = useMutation({
    mutationFn: async ({ matchId, winnerBias }: { matchId: string; winnerBias: string }) => {
      const operationId = `simulate_match_${matchId}_${Date.now()}`
      testCenterLog.startOperation(operationId, {
        tab: 'tournament-workflow',
        operation: 'simulate_match',
        step: 'matches',
        matchId
      })

      try {
        const result = await errorHandler.withRetry(
          () => testTournamentsApi.simulateMatch(matchId, winnerBias),
          operationId,
          { maxRetries: 1 }, // Only retry once for match simulation
          { tab: 'tournament-workflow', matchId }
        )

        testCenterLog.endOperation(operationId, true, {
          tab: 'tournament-workflow',
          operation: 'simulate_match',
          matchId,
          winnerBias
        })

        return result
      } catch (error) {
        testCenterLog.endOperation(operationId, false, {
          tab: 'tournament-workflow',
          operation: 'simulate_match',
          matchId,
          winnerBias
        })

        await errorHandler.handleApiError(error, operationId, {
          tab: 'tournament-workflow',
          matchId
        })
        throw error
      }
    },
    onSuccess: (result, { matchId, winnerBias }) => {
      queryClient.invalidateQueries({ queryKey: ['test-matches'] })
      queryClient.invalidateQueries({ queryKey: ['test-leaderboard'] })
      queryClient.invalidateQueries({ queryKey: ['test-bracket-tree'] })
      queryClient.invalidateQueries({ queryKey: ['test-tournament'] })

      testCenterLog.userInteraction('match_simulated', {
        matchId,
        winnerBias,
        winnerId: result?.winner_id
      })

      toast.success(`Match simulated successfully! Winner: ${result?.operator_name || 'Unknown'} vs ${result?.player2_name || 'Unknown'}`)
    },
    onError: (error: any, { matchId }) => {
      // Error already handled in mutationFn
      testCenterLog.criticalError(error, {
        tab: 'tournament-workflow',
        operation: 'simulate_match_final_failure',
        matchId
      })
    }
  })

  const updatePlayerNameMutation = useMutation({
    mutationFn: ({ playerId, name }: { playerId: string; name: string }) =>
      testTournamentsApi.updatePlayerName(playerId, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['test-players'] })
      toast.success('Player name updated')
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Failed to update player name')
    }
  })

  const autoFillMutation = useMutation({
    mutationFn: () => testTournamentsApi.autoFill(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['test-players'] })
      toast.success(data.added > 0 ? `Added ${data.added} player(s)` : 'Tournament already full')
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Failed to auto-fill')
    }
  })

  const seedClassicsDemoMutation = useMutation({
    mutationFn: () => testTournamentsApi.seedClassicsDemoPlayers(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['test-players'] })
      toast.success(`Registered ${data.added} demo players (64, seeds 1–32)`)
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Failed to seed demo players')
    }
  })

  const randomizeSeedingMutation = useMutation({
    mutationFn: () => testTournamentsApi.randomizeSeeding(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['test-players'] })
      toast.success(`Seeding randomized (${data.randomization_count} of 3)`)
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Failed to randomize seeding')
    }
  })

  const importWpbaMutation = useMutation({
    mutationFn: (limit?: number) => testTournamentsApi.importWpbaFromProduction(limit),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['test-players'] })
      toast.success(
        data.message ||
          `Copied ${data.copied} WPBA players from production (prefixed "test ")`
      )
    },
    onError: (error: any) => {
      toast.error(
        error?.response?.data?.detail ||
          'Failed to import WPBA players from production'
      )
    }
  })

  const cloneProductionMutation = useMutation({
    mutationFn: () => testTournamentsApi.cloneProductionToTestCenter({}),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['test-players'] })
      queryClient.invalidateQueries({ queryKey: ['test-tournament'] })
      queryClient.invalidateQueries({ queryKey: ['test-matches'] })
      queryClient.invalidateQueries({ queryKey: ['test-bracket-tree'] })
      queryClient.invalidateQueries({ queryKey: ['test-leaderboard'] })
      queryClient.invalidateQueries({ queryKey: ['test-center'] })
      toast.success(
        data.message ||
          `Cloned ${data.players_copied} players, ${data.rankings_copied} rankings, ${data.tournaments_copied} tournaments`
      )
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Failed to clone production data to Test Center')
    }
  })

  const clearRegistrationMutation = useMutation({
    mutationFn: () => testTournamentsApi.clearRegistration(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['test-players'] })
      toast.success(data.removed > 0 ? `Cleared ${data.removed} player(s). You can Auto Fill now.` : 'No players to clear')
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Failed to clear registration')
    }
  })

  const addTestPlayerMutation = useMutation({
    mutationFn: (body: { first_name: string; last_name: string; country?: string }) =>
      testTournamentsApi.addPlayer(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['test-players'] })
      toast.success('Player added to test tournament')
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Failed to add player')
    }
  })

  const simulateAllMutation = useMutation({
    mutationFn: () => testTournamentsApi.simulateAllRemaining({ winner_bias: 'fair' }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['test-matches'] })
      queryClient.invalidateQueries({ queryKey: ['test-leaderboard'] })
      queryClient.invalidateQueries({ queryKey: ['test-bracket-tree'] })
      queryClient.invalidateQueries({ queryKey: ['test-tournament'] })
      toast.success(`Simulated ${data.count} match(es).`)
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || 'Simulate-all failed')
    }
  })

  // Test runners with enhanced error handling and logging
  const runApiTests = async () => {
    const testSuiteId = `api_tests_${Date.now()}`
    testCenterLog.startOperation(testSuiteId, {
      tab: 'api',
      operation: 'run_api_tests'
    })

    setIsRunningTests(true)
    const results: TestResult[] = []
    let passedTests = 0
    let failedTests = 0

    const addResult = (test: string, status: TestResult['status'], message: string, duration?: number) => {
      results.push({ test, status, message, duration })
      setTestResults([...results])

      if (status === 'passed') passedTests++
      else if (status === 'failed') failedTests++

      testCenterLog.dataFlow('test_result_added', results.length, {
        tab: 'api',
        operation: 'api_test_result',
        testName: test,
        testStatus: status
      })
    }

    try {
      // Test 1: Get current tournament
      const test1Id = 'get_current_tournament'
      testCenterLog.startOperation(test1Id, {
        tab: 'api',
        operation: 'test_api_endpoint',
        endpoint: 'getCurrentTournament'
      })

      addResult('Get Current Tournament', 'running', 'Testing API endpoint...')
      const start1 = Date.now()

      try {
        const tournament = await errorHandler.withRetry(
          () => testTournamentsApi.getCurrentTournament(),
          test1Id,
          { maxRetries: 1 },
          { tab: 'api' }
        )
        const duration1 = Date.now() - start1
        addResult('Get Current Tournament', 'passed', `Found tournament: ${tournament?.name || 'N/A'}`, duration1)

        testCenterLog.endOperation(test1Id, true, {
          tab: 'api',
          duration: duration1,
          tournamentId: tournament?.tournament_id
        })
      } catch (error) {
        const duration1 = Date.now() - start1
        const categorizedError = await errorHandler.handleApiError(error, test1Id, { tab: 'api' }, false)
        addResult('Get Current Tournament', 'failed', `Failed: ${error.message}`, duration1)
        testCenterLog.endOperation(test1Id, false, { tab: 'api', duration: duration1 })

        // Add to error display
        addError({
          ...categorizedError,
          userMessage: `API Test Failed: ${categorizedError.userMessage}`,
          suggestions: [
            ...categorizedError.suggestions,
            'Check the API endpoint status',
            'Verify test data is available'
          ]
        })
      }

      // Test 2: Get players
      const test2Id = 'get_tournament_players'
      testCenterLog.startOperation(test2Id, {
        tab: 'api',
        operation: 'test_api_endpoint',
        endpoint: 'getPlayers'
      })

      addResult('Get Tournament Players', 'running', 'Testing players endpoint...')
      const start2 = Date.now()

      try {
        const players = await errorHandler.withRetry(
          () => testTournamentsApi.getPlayers(),
          test2Id,
          { maxRetries: 1 },
          { tab: 'api' }
        )
        const duration2 = Date.now() - start2
        addResult('Get Tournament Players', 'passed', `Loaded ${players.length} players`, duration2)

        testCenterLog.dataFlow('players_loaded', players.length, {
          tab: 'api',
          operation: 'test_result'
        })

        testCenterLog.endOperation(test2Id, true, {
          tab: 'api',
          duration: duration2,
          dataSize: players.length
        })
      } catch (error) {
        const duration2 = Date.now() - start2
        const categorizedError = await errorHandler.handleApiError(error, test2Id, { tab: 'api' }, false)
        addResult('Get Tournament Players', 'failed', `Failed: ${error.message}`, duration2)
        testCenterLog.endOperation(test2Id, false, { tab: 'api', duration: duration2 })

        addError({
          ...categorizedError,
          userMessage: `Player API Test Failed: ${categorizedError.userMessage}`,
          suggestions: [
            ...categorizedError.suggestions,
            'Ensure tournament has been created with players',
            'Check player registration process'
          ]
        })
      }

      // Test 3: Get matches
      const test3Id = 'get_tournament_matches'
      testCenterLog.startOperation(test3Id, {
        tab: 'api',
        operation: 'test_api_endpoint',
        endpoint: 'getMatches'
      })

      addResult('Get Tournament Matches', 'running', 'Testing matches endpoint...')
      const start3 = Date.now()

      try {
        const matches = await errorHandler.withRetry(
          () => testTournamentsApi.getMatches(),
          test3Id,
          { maxRetries: 1 },
          { tab: 'api' }
        )
        const duration3 = Date.now() - start3
        addResult('Get Tournament Matches', 'passed', `Loaded ${matches.length} matches`, duration3)

        testCenterLog.dataFlow('matches_loaded', matches.length, {
          tab: 'api',
          operation: 'test_result'
        })

        testCenterLog.endOperation(test3Id, true, {
          tab: 'api',
          duration: duration3,
          dataSize: matches.length
        })
      } catch (error) {
        const duration3 = Date.now() - start3
        const categorizedError = await errorHandler.handleApiError(error, test3Id, { tab: 'api' }, false)
        addResult('Get Tournament Matches', 'failed', `Failed: ${error.message}`, duration3)
        testCenterLog.endOperation(test3Id, false, { tab: 'api', duration: duration3 })

        addError({
          ...categorizedError,
          userMessage: `Match API Test Failed: ${categorizedError.userMessage}`,
          suggestions: [
            ...categorizedError.suggestions,
            'Ensure bracket has been generated',
            'Check tournament status'
          ]
        })
      }

      // Test 4: Get leaderboard
      const test4Id = 'get_tournament_leaderboard'
      testCenterLog.startOperation(test4Id, {
        tab: 'api',
        operation: 'test_api_endpoint',
        endpoint: 'getLeaderboard'
      })

      addResult('Get Tournament Leaderboard', 'running', 'Testing leaderboard endpoint...')
      const start4 = Date.now()

      try {
        const leaderboard = await errorHandler.withRetry(
          () => testTournamentsApi.getLeaderboard(),
          test4Id,
          { maxRetries: 1 },
          { tab: 'api' }
        )
        const duration4 = Date.now() - start4
        addResult('Get Tournament Leaderboard', 'passed', `Generated leaderboard with ${leaderboard.length} entries`, duration4)

        testCenterLog.dataFlow('leaderboard_loaded', leaderboard.length, {
          tab: 'api',
          operation: 'test_result'
        })

        testCenterLog.endOperation(test4Id, true, {
          tab: 'api',
          duration: duration4,
          dataSize: leaderboard.length
        })
      } catch (error) {
        const duration4 = Date.now() - start4
        const categorizedError = await errorHandler.handleApiError(error, test4Id, { tab: 'api' }, false)
        addResult('Get Tournament Leaderboard', 'failed', `Failed: ${error.message}`, duration4)
        testCenterLog.endOperation(test4Id, false, { tab: 'api', duration: duration4 })

        addError({
          ...categorizedError,
          userMessage: `Leaderboard API Test Failed: ${categorizedError.userMessage}`,
          suggestions: [
            ...categorizedError.suggestions,
            'Ensure matches have been played',
            'Check leaderboard calculation logic'
          ]
        })
      }

      // Test 5: Simulate match (if available)
      const test5Id = 'simulate_match_test'
      const matches = results.find(r => r.test === 'Get Tournament Matches')?.message?.includes('Loaded')
        ? parseInt(results.find(r => r.test === 'Get Tournament Matches')!.message.match(/Loaded (\d+) matches/)?.[1] || '0')
        : 0

      if (matches > 0) {
        try {
          // Get matches again to check for pending ones
          const currentMatches = await testTournamentsApi.getMatches()
          const pendingMatches = currentMatches.filter(m => m.status === 'pending')

          if (pendingMatches.length > 0) {
            testCenterLog.startOperation(test5Id, {
              tab: 'api',
              operation: 'test_api_endpoint',
              endpoint: 'simulateMatch',
              matchId: pendingMatches[0].match_id
            })

            addResult('Simulate Match', 'running', 'Testing match simulation...')
            const start5 = Date.now()

            await errorHandler.withRetry(
              () => testTournamentsApi.simulateMatch(pendingMatches[0].match_id, 'fair'),
              test5Id,
              { maxRetries: 1 },
              { tab: 'api', matchId: pendingMatches[0].match_id }
            )
            const duration5 = Date.now() - start5
            addResult('Simulate Match', 'passed', `Simulated match: ${pendingMatches[0].match_id}`, duration5)

            testCenterLog.endOperation(test5Id, true, {
              tab: 'api',
              duration: duration5,
              matchId: pendingMatches[0].match_id
            })
          } else {
            addResult('Simulate Match', 'passed', 'No pending matches to simulate (all matches completed)', 0)
            testCenterLog.dataFlow('no_pending_matches', 0, {
              tab: 'api',
              operation: 'test_skip'
            })
          }
          } catch (error) {
          const duration5 = Date.now() - Date.now() // Fallback duration
          const categorizedError = await errorHandler.handleApiError(error, test5Id, { tab: 'api' }, false)
          addResult('Simulate Match', 'failed', `Failed: ${error.message}`, duration5)
          testCenterLog.endOperation(test5Id, false, { tab: 'api' })

          addError({
            ...categorizedError,
            userMessage: `Match Simulation Test Failed: ${categorizedError.userMessage}`,
            suggestions: [
              ...categorizedError.suggestions,
              'Ensure there are pending matches available',
              'Check match simulation permissions'
            ]
          })
        }
      } else {
        addResult('Simulate Match', 'passed', 'Skipped - no matches available', 0)
      }

      // Overall test summary
      const totalTests = results.length
      const successRate = totalTests > 0 ? (passedTests / totalTests) * 100 : 0

      testCenterLog.performance('api_tests_completion_rate', successRate, {
        tab: 'api',
        passedTests,
        failedTests,
        totalTests
      })

      testCenterLog.endOperation(testSuiteId, true, {
        tab: 'api',
        passedTests,
        failedTests,
        totalTests,
        successRate
      })

    } catch (error: any) {
      testCenterLog.endOperation(testSuiteId, false, {
        tab: 'api',
        error: error.message
      })
      await errorHandler.handleApiError(error, testSuiteId, { tab: 'api' }, false)
      addResult('API Tests Suite', 'failed', `Test suite failed: ${error.message}`)
    }

    setIsRunningTests(false)
  }

  const runDatabaseTests = async () => {
    const testSuiteId = `database_tests_${Date.now()}`
    testCenterLog.startOperation(testSuiteId, {
      tab: 'database',
      operation: 'run_database_tests'
    })

    setIsRunningTests(true)
    const results: TestResult[] = []
    let passedTests = 0
    let failedTests = 0

    const addResult = (test: string, status: TestResult['status'], message: string, duration?: number) => {
      results.push({ test, status, message, duration })
      setTestResults([...results])

      if (status === 'passed') passedTests++
      else if (status === 'failed') failedTests++

      testCenterLog.dataFlow('test_result_added', results.length, {
        tab: 'database',
        operation: 'database_test_result',
        testName: test,
        testStatus: status
      })
    }

    try {
      // Test 1: Database connectivity via tournament creation
      const test1Id = 'database_connection'
      testCenterLog.startOperation(test1Id, {
        tab: 'database',
        operation: 'test_database_connectivity'
      })

      addResult('Database Connection', 'running', 'Testing database connectivity...')

      const testTournamentData = {
        name: `TestTournament_${Date.now()}`,
        format: 'single_elimination' as const,
        max_players: 8,
        entry_fee: 50,
        tables: 2,
        race_to: 5,
        ranking_system: 'WPBA_Women',
        game_type: '9-ball',
        association: 'WPBA',
        bracket_draw_size: 8,
        bye_strategy: 'top_seed'
      }

      const start1 = Date.now()
      try {
        await errorHandler.withRetry(
          () => testTournamentsApi.setupTournament(testTournamentData),
          test1Id,
          { maxRetries: 2 },
          { tab: 'database' }
        )
        const duration1 = Date.now() - start1
        addResult('Database Connection', 'passed', 'Successfully created test tournament', duration1)

        testCenterLog.endOperation(test1Id, true, {
          tab: 'database',
          duration: duration1,
          tournamentName: testTournamentData.name
        })
      } catch (error) {
        const duration1 = Date.now() - start1
        const categorizedError = await errorHandler.handleApiError(error, test1Id, { tab: 'database' }, false)
        addResult('Database Connection', 'failed', `Failed to create tournament: ${error.message}`, duration1)
        testCenterLog.endOperation(test1Id, false, { tab: 'database', duration: duration1 })

        addError({
          ...categorizedError,
          userMessage: `Database Connection Test Failed: ${categorizedError.userMessage}`,
          suggestions: [
            ...categorizedError.suggestions,
            'Check database server status',
            'Verify database connection settings',
            'Ensure sufficient permissions for tournament creation'
          ]
        })
      }

      // Test 2: Data persistence
      const test2Id = 'data_persistence'
      testCenterLog.startOperation(test2Id, {
        tab: 'database',
        operation: 'test_data_persistence'
      })

      addResult('Data Persistence', 'running', 'Testing data persistence...')
      const start2 = Date.now()

      try {
        const currentTournament = await errorHandler.withRetry(
          () => testTournamentsApi.getCurrentTournament(),
          test2Id,
          { maxRetries: 1 },
          { tab: 'database' }
        )
        const duration2 = Date.now() - start2

        if (currentTournament?.name === testTournamentData.name) {
          addResult('Data Persistence', 'passed', 'Tournament data persisted correctly', duration2)
          testCenterLog.endOperation(test2Id, true, {
            tab: 'database',
            duration: duration2,
            tournamentId: currentTournament.tournament_id
          })
        } else {
          addResult('Data Persistence', 'failed', `Expected ${testTournamentData.name}, got ${currentTournament?.name || 'null'}`, duration2)
          testCenterLog.endOperation(test2Id, false, {
            tab: 'database',
            duration: duration2,
            expectedName: testTournamentData.name,
            actualName: currentTournament?.name
          })
        }
      } catch (error) {
        const duration2 = Date.now() - start2
        const categorizedError = await errorHandler.handleApiError(error, test2Id, { tab: 'database' }, false)
        addResult('Data Persistence', 'failed', `Failed to verify persistence: ${error.message}`, duration2)
        testCenterLog.endOperation(test2Id, false, { tab: 'database', duration: duration2 })

        addError({
          ...categorizedError,
          userMessage: `Data Persistence Test Failed: ${categorizedError.userMessage}`,
          suggestions: [
            ...categorizedError.suggestions,
            'Check database write permissions',
            'Verify transaction handling',
            'Ensure data consistency constraints'
          ]
        })
      }

      // Test 3: Player data integrity
      const test3Id = 'player_data_integrity'
      testCenterLog.startOperation(test3Id, {
        tab: 'database',
        operation: 'test_player_data_integrity'
      })

      addResult('Player Data', 'running', 'Testing player data integrity...')
      const start3 = Date.now()

      try {
        const players = await errorHandler.withRetry(
          () => testTournamentsApi.getPlayers(),
          test3Id,
          { maxRetries: 1 },
          { tab: 'database' }
        )
        const duration3 = Date.now() - start3

        if (players.length >= 8) {
          addResult('Player Data', 'passed', `Found ${players.length} players in database`, duration3)
          testCenterLog.dataFlow('players_verified', players.length, {
            tab: 'database',
            operation: 'test_result'
          })
          testCenterLog.endOperation(test3Id, true, {
            tab: 'database',
            duration: duration3,
            dataSize: players.length
          })
        } else {
          addResult('Player Data', 'failed', `Only found ${players.length} players, expected at least 8`, duration3)
          testCenterLog.endOperation(test3Id, false, {
            tab: 'database',
            duration: duration3,
            expectedMinPlayers: 8,
            actualPlayers: players.length
          })
        }
      } catch (error) {
        const duration3 = Date.now() - start3
        const categorizedError = await errorHandler.handleApiError(error, test3Id, { tab: 'database' }, false)
        addResult('Player Data', 'failed', `Failed to verify players: ${error.message}`, duration3)
        testCenterLog.endOperation(test3Id, false, { tab: 'database', duration: duration3 })

        addError({
          ...categorizedError,
          userMessage: `Player Data Test Failed: ${categorizedError.userMessage}`,
          suggestions: [
            ...categorizedError.suggestions,
            'Check player registration process',
            'Verify player data integrity',
            'Ensure proper seeding of test data'
          ]
        })
      }

      // Test 4: Match data integrity (if bracket was generated)
      const test4Id = 'match_data_integrity'
      testCenterLog.startOperation(test4Id, {
        tab: 'database',
        operation: 'test_match_data_integrity'
      })

      addResult('Match Data', 'running', 'Testing match data integrity...')
      const start4 = Date.now()

      try {
        const matches = await errorHandler.withRetry(
          () => testTournamentsApi.getMatches(),
          test4Id,
          { maxRetries: 1 },
          { tab: 'database' }
        )
        const duration4 = Date.now() - start4

        if (matches.length > 0) {
          addResult('Match Data', 'passed', `Found ${matches.length} matches in database`, duration4)
          testCenterLog.dataFlow('matches_verified', matches.length, {
            tab: 'database',
            operation: 'test_result'
          })
          testCenterLog.endOperation(test4Id, true, {
            tab: 'database',
            duration: duration4,
            dataSize: matches.length
          })
        } else {
          addResult('Match Data', 'passed', 'No matches found (bracket not generated yet)', duration4)
          testCenterLog.endOperation(test4Id, true, {
            tab: 'database',
            duration: duration4,
            note: 'no_matches_expected'
          })
        }
      } catch (error) {
        const duration4 = Date.now() - start4
        const categorizedError = await errorHandler.handleApiError(error, test4Id, { tab: 'database' }, false)
        addResult('Match Data', 'failed', `Failed to verify matches: ${error.message}`, duration4)
        testCenterLog.endOperation(test4Id, false, { tab: 'database', duration: duration4 })

        addError({
          ...categorizedError,
          userMessage: `Match Data Test Failed: ${categorizedError.userMessage}`,
          suggestions: [
            ...categorizedError.suggestions,
            'Ensure bracket generation completed',
            'Check match data relationships',
            'Verify tournament state consistency'
          ]
        })
      }

      // Overall test summary
      const totalTests = results.length
      const successRate = totalTests > 0 ? (passedTests / totalTests) * 100 : 0

      testCenterLog.performance('database_tests_completion_rate', successRate, {
        tab: 'database',
        passedTests,
        failedTests,
        totalTests
      })

      testCenterLog.endOperation(testSuiteId, true, {
        tab: 'database',
        passedTests,
        failedTests,
        totalTests,
        successRate
      })

    } catch (error: any) {
      testCenterLog.endOperation(testSuiteId, false, {
        tab: 'database',
        error: error.message
      })
      await errorHandler.handleApiError(error, testSuiteId, { tab: 'database' }, false)
      addResult('Database Tests Suite', 'failed', `Test suite failed: ${error.message}`)
    }

    setIsRunningTests(false)
  }

  const renderTabContent = () => {
    switch (activeTab) {
      case 'tournament-workflow':
        return (
          <TournamentWorkflowTab
            tournamentState={tournamentState}
            onUpdateTournamentState={updateTournamentState}
            onSaveTournament={(name, description) => saveTournament(name, description)}
            onResetTournament={resetTournamentState}
            onOpenPersistenceManager={() => setShowPersistenceManager(true)}
            onOpenExportImportManager={() => setShowExportImportManager(true)}
            associationOptions={associationOptions}
            bracketTemplates={bracketTemplates}
            bracketTemplatesLoading={bracketTemplatesLoading}
            isAdmin={!!isAdmin}
            isSuperAdmin={!!isSuperAdmin}
            isDirectorMode={isDirectorMode}
            canUseAdminTools={canUseAdminTools}
            directorUpcoming={directorUpcoming}
            tournament={tournament}
            players={players}
            matches={matches}
            leaderboard={leaderboard}
            bracketTree={bracketTree}
            isLoading={tournamentLoading || playersLoading || matchesLoading || leaderboardLoading || persistenceLoading}
            onCreateTournament={(data) => createTournamentMutation.mutate(data)}
            onGenerateBracket={(options) => generateBracketMutation.mutate(options)}
            onSimulateMatch={(matchId, winnerBias) => simulateMatchMutation.mutate({ matchId, winnerBias })}
            onSimulateAll={() => simulateAllMutation.mutate()}
            onUpdatePlayerName={(playerId, name) => updatePlayerNameMutation.mutate({ playerId, name })}
            onAutoFill={() => autoFillMutation.mutate()}
            onSeedClassicsDemo={() => seedClassicsDemoMutation.mutate()}
            onRandomizeSeeding={() => randomizeSeedingMutation.mutate()}
            onClearRegistration={() => clearRegistrationMutation.mutate()}
            onAddPlayer={(body) => addTestPlayerMutation.mutate(body)}
            onImportWpbaFromProduction={() => importWpbaMutation.mutate(undefined)}
            onCloneProduction={() => {
              if (
                !window.confirm(
                  'This replaces all Test Center mirror data (players, rankings, tournament history, Fargo history) with read-only copies from production; names get a "test " prefix. Continue?'
                )
              ) {
                return
              }
              cloneProductionMutation.mutate()
            }}
            isAutoFilling={autoFillMutation.isPending}
            isSeedingClassics={seedClassicsDemoMutation.isPending}
            isRandomizingSeeding={randomizeSeedingMutation.isPending}
            randomizationCount={randomizeSeedingMutation.data?.randomization_count ?? 0}
            isClearingRegistration={clearRegistrationMutation.isPending}
            isUpdatingPlayerName={updatePlayerNameMutation.isPending}
            isCreating={createTournamentMutation.isPending}
            isGenerating={generateBracketMutation.isPending}
            isSimulating={simulateMatchMutation.isPending}
            isSimulatingAll={simulateAllMutation.isPending}
            isAddingPlayer={addTestPlayerMutation.isPending}
            isImportingWpba={importWpbaMutation.isPending}
            isCloningProduction={cloneProductionMutation.isPending}
            lastAutoSaved={lastAutoSaved}
            isAutoSaving={isAutoSaving}
          />
        )

      case 'api':
        return (
          <EnhancedApiTestingTab
            testResults={testResults}
            isRunningTests={isRunningTests}
            onRunTests={runApiTests}
          />
        )

      case 'database':
        return (
          <DatabaseTestingTab
            testResults={testResults}
            isRunningTests={isRunningTests}
            onRunTests={runDatabaseTests}
          />
        )

      case 'system':
        return <SystemTestingTab />

      case 'reset':
        return (
          <TestCenterResetManager
            onResetComplete={() => {
              // Refresh all data after reset
              queryClient.invalidateQueries()
              testCenterLog.userInteraction('reset_complete_refresh', {
                tab: 'reset'
              })
            }}
          />
        )

      case 'test-rankings':
        return (
          <ApiPathProvider value={testCenterApiPrefixes}>
            <div className="test-center-embedded-shell" data-testid="test-center-rankings">
              <Rankings />
            </div>
          </ApiPathProvider>
        )

      case 'test-leaderboard':
        return (
          <ApiPathProvider value={testCenterApiPrefixes}>
            <div className="test-center-embedded-shell" data-testid="test-center-leaderboard">
              <Leaderboard />
            </div>
          </ApiPathProvider>
        )

      case 'test-hot-streak':
        return (
          <ApiPathProvider value={testCenterApiPrefixes}>
            <div className="test-center-embedded-shell" data-testid="test-center-hot-streak">
              <HotStreak />
            </div>
          </ApiPathProvider>
        )

      case 'test-tournament-history':
        return (
          <ApiPathProvider value={testCenterApiPrefixes}>
            <div className="test-center-embedded-shell" data-testid="test-center-tournament-history">
              <TournamentHistory />
            </div>
          </ApiPathProvider>
        )

      default:
        return null
    }
  }

  return (
    <div className="test-center">
      <div className="test-center-header">
        <h1>🧪 Test Center</h1>
        <p className="test-center-subtitle">
          {canUseAdminTools
            ? 'For administrators: try tournament flows, API checks, and tools without touching live player data.'
            : 'Practice tournament setup and brackets here — nothing you do affects live player data.'}
        </p>
        <div className="test-center-warning">
          <span className="warning-icon">⚠️</span>
          <span className="warning-text">
            Practice area only — anything you do here does not change real tournaments or rankings.
          </span>
        </div>

        <TestCenterMonitoring />
      </div>

      <div className="test-center-tabs">
        <button
          className={`tab-button ${activeTab === 'tournament-workflow' ? 'active' : ''}`}
          onClick={() => {
            testCenterLog.userInteraction('tab_switch', {
              fromTab: activeTab,
              toTab: 'tournament-workflow'
            })
            setActiveTab('tournament-workflow')
          }}
        >
          🏆 Tournament Workflow
        </button>
        {canUseAdminTools && (
          <>
        <button
          className={`tab-button ${activeTab === 'api' ? 'active' : ''}`}
          onClick={() => {
            testCenterLog.userInteraction('tab_switch', {
              fromTab: activeTab,
              toTab: 'api'
            })
            setActiveTab('api')
          }}
        >
          🔌 API Tests
        </button>
        <button
          className={`tab-button ${activeTab === 'database' ? 'active' : ''}`}
          onClick={() => {
            testCenterLog.userInteraction('tab_switch', {
              fromTab: activeTab,
              toTab: 'database'
            })
            setActiveTab('database')
          }}
        >
          🗄️ Database Tests
        </button>
        <button
          className={`tab-button ${activeTab === 'system' ? 'active' : ''}`}
          onClick={() => {
            testCenterLog.userInteraction('tab_switch', {
              fromTab: activeTab,
              toTab: 'system'
            })
            setActiveTab('system')
          }}
        >
          ⚙️ System Tests
        </button>
        <button
          className={`tab-button ${activeTab === 'reset' ? 'active' : ''}`}
          onClick={() => {
            testCenterLog.userInteraction('tab_switch', {
              fromTab: activeTab,
              toTab: 'reset'
            })
            setActiveTab('reset')
          }}
        >
          🛠️ Reset & Cleanup
        </button>
          </>
        )}
        <span className="test-center-tab-separator" aria-hidden="true" />
        <button
          className={`tab-button ${activeTab === 'test-rankings' ? 'active' : ''}`}
          onClick={() => {
            testCenterLog.userInteraction('tab_switch', { fromTab: activeTab, toTab: 'test-rankings' })
            setActiveTab('test-rankings')
          }}
          title="Same Rankings UI; data from Test Center database only"
        >
          📊 Test Rankings
        </button>
        <button
          className={`tab-button ${activeTab === 'test-leaderboard' ? 'active' : ''}`}
          onClick={() => {
            testCenterLog.userInteraction('tab_switch', { fromTab: activeTab, toTab: 'test-leaderboard' })
            setActiveTab('test-leaderboard')
          }}
        >
          🏅 Test Leaderboard
        </button>
        <button
          className={`tab-button ${activeTab === 'test-hot-streak' ? 'active' : ''}`}
          onClick={() => {
            testCenterLog.userInteraction('tab_switch', { fromTab: activeTab, toTab: 'test-hot-streak' })
            setActiveTab('test-hot-streak')
          }}
        >
          🔥 Test Hot Streak
        </button>
        <button
          className={`tab-button ${activeTab === 'test-tournament-history' ? 'active' : ''}`}
          onClick={() => {
            testCenterLog.userInteraction('tab_switch', { fromTab: activeTab, toTab: 'test-tournament-history' })
            setActiveTab('test-tournament-history')
          }}
        >
          📜 Test Tournament History
        </button>
      </div>

      {/* Error Display */}
      {currentErrors.length > 0 && (
        <div className="test-center-errors">
          <div className="error-header">
            <h3>⚠️ Active Issues ({currentErrors.length})</h3>
            <button
              onClick={clearErrors}
              className="clear-errors-btn"
            >
              Clear All
            </button>
          </div>
          {currentErrors.map((error, index) => (
            <TestCenterErrorDisplay
              key={`${error.type}_${index}`}
              error={error}
              onRetry={() => {
                // Retry logic depends on the operation that failed
                // This would need to be implemented per operation
                testCenterLog.userInteraction('error_retry_requested', {
                  errorType: error.type,
                  errorIndex: index
                })
              }}
              onRecoveryAction={(action) => handleErrorRecovery(error, action)}
              onDismiss={() => removeError(index)}
            />
          ))}
        </div>
      )}

      <div className="test-center-content">
        {renderTabContent()}
      </div>

      {/* Tournament Persistence Manager */}
      <TournamentPersistenceManager
        isOpen={showPersistenceManager}
        onClose={() => setShowPersistenceManager(false)}
        onLoadTournament={(savedTournament) => {
          loadTournamentMutation.mutate(savedTournament.id, {
            onSuccess: (loadedTournament) => {
              if (loadedTournament) {
                updateTournamentState(loadedTournament.state)
                // Clear current API data and refetch
                queryClient.invalidateQueries({ queryKey: ['test-tournament'] })
                queryClient.invalidateQueries({ queryKey: ['test-players'] })
                queryClient.invalidateQueries({ queryKey: ['test-matches'] })
                queryClient.invalidateQueries({ queryKey: ['test-leaderboard'] })
                setShowPersistenceManager(false)
              }
            }
          })
        }}
        currentTournamentState={tournamentState}
      />

      {/* Export/Import Manager */}
      <ExportImportManager
        isOpen={showExportImportManager}
        onClose={() => setShowExportImportManager(false)}
        currentTournamentState={tournamentState}
        onImportTournament={(importedTournament) => {
          // Handle imported tournament
          updateTournamentState(importedTournament)
          // Refresh all data
          queryClient.invalidateQueries({ queryKey: ['test-tournament'] })
          queryClient.invalidateQueries({ queryKey: ['test-players'] })
          queryClient.invalidateQueries({ queryKey: ['test-matches'] })
          queryClient.invalidateQueries({ queryKey: ['test-leaderboard'] })
          setShowExportImportManager(false)
        }}
        onLoadTemplate={(template) => {
          // Handle template loading
          updateTournamentState(template.baseWorkflowState)
          // Refresh all data
          queryClient.invalidateQueries({ queryKey: ['test-tournament'] })
          queryClient.invalidateQueries({ queryKey: ['test-players'] })
          queryClient.invalidateQueries({ queryKey: ['test-matches'] })
          queryClient.invalidateQueries({ queryKey: ['test-leaderboard'] })
          setShowExportImportManager(false)
        }}
      />
    </div>
  )
}

// Tournament Workflow Tab Component - Full Step-by-Step Tournament Testing with Persistence
interface TournamentWorkflowTabProps {
  tournamentState: TournamentWorkflowState
  onUpdateTournamentState: (updates: Partial<TournamentWorkflowState>) => void
  onSaveTournament: (name?: string, description?: string) => void
  onResetTournament: () => void
  onOpenPersistenceManager: () => void
  onOpenExportImportManager: () => void
  associationOptions: string[]
  bracketTemplates: BracketTemplate[]
  bracketTemplatesLoading: boolean
  isAdmin: boolean
  isSuperAdmin: boolean
  isDirectorMode: boolean
  canUseAdminTools: boolean
  directorUpcoming: UpcomingEvent[]
  tournament?: any
  players: any[]
  matches: any[]
  leaderboard: any[]
  bracketTree?: import('@/api/testTournaments').TestBracketTree
  isLoading: boolean
  onCreateTournament: (data: any) => void
  onGenerateBracket: (options: any) => void
  onSimulateMatch: (matchId: string, winnerBias: string) => void
  onSimulateAll: () => void
  onUpdatePlayerName?: (playerId: string, name: string) => void
  onAutoFill?: () => void
  onSeedClassicsDemo?: () => void
  onRandomizeSeeding?: () => void
  onClearRegistration?: () => void
  onAddPlayer?: (body: { first_name: string; last_name: string; country?: string }) => void
  onImportWpbaFromProduction?: () => void
  onCloneProduction?: () => void
  isAutoFilling?: boolean
  isSeedingClassics?: boolean
  isRandomizingSeeding?: boolean
  randomizationCount?: number
  isClearingRegistration?: boolean
  isUpdatingPlayerName?: boolean
  isCreating: boolean
  isGenerating: boolean
  isSimulating: boolean
  isSimulatingAll?: boolean
  isAddingPlayer?: boolean
  isImportingWpba?: boolean
  isCloningProduction?: boolean
  lastAutoSaved?: Date | null
  isAutoSaving?: boolean
}

function TournamentWorkflowTab({
  tournamentState,
  onUpdateTournamentState,
  onSaveTournament,
  onResetTournament,
  onOpenPersistenceManager,
  onOpenExportImportManager,
  associationOptions,
  bracketTemplates,
  bracketTemplatesLoading,
  isAdmin,
  isSuperAdmin,
  isDirectorMode,
  canUseAdminTools,
  directorUpcoming,
  tournament,
  players,
  matches,
  leaderboard,
  bracketTree,
  isLoading,
  onCreateTournament,
  onGenerateBracket,
  onSimulateMatch,
  onSimulateAll,
  onUpdatePlayerName,
  onAutoFill,
  onSeedClassicsDemo,
  onRandomizeSeeding,
  onClearRegistration,
  onAddPlayer,
  onImportWpbaFromProduction,
  onCloneProduction,
  isAutoFilling,
  isSeedingClassics,
  isRandomizingSeeding,
  randomizationCount,
  isClearingRegistration,
  isUpdatingPlayerName,
  isCreating,
  isGenerating,
  isSimulating,
  isSimulatingAll,
  isAddingPlayer,
  isImportingWpba,
  isCloningProduction,
  lastAutoSaved,
  isAutoSaving
}: TournamentWorkflowTabProps) {
  const currentStep = tournamentState.currentStep as TournamentWorkflowState['currentStep']
  const tournamentSetup = tournamentState.tournamentSetup
  const bracketSetup = tournamentState.bracketSetup
  const [setupEntryMode, setSetupEntryMode] = useState<TestSetupEntryMode>(
    tournament ? 'form' : 'choose',
  )
  const [wizardSource, setWizardSource] = useState<'new' | 'scheduled' | null>(null)

  const activeMatches = matches.filter(m => m.status === 'in_progress')
  const completedMatches = matches.filter(m => m.status === 'completed')
  const pendingMatches = matches.filter(m => m.status === 'pending')
  const hasBracket = Boolean(tournament?.tournament_id && matches.length > 0)
  const stepSyncRef = useRef<string | null>(null)

  useEffect(() => {
    if (isLoading || !tournament?.tournament_id) return
    const syncKey = `${tournament.tournament_id}:${tournament.status}:${matches.length}:${currentStep}`
    if (stepSyncRef.current === syncKey) return
    const nextStep = resolveWorkflowStep(currentStep, tournament, matches.length)
    if (nextStep && nextStep !== currentStep) {
      stepSyncRef.current = `${tournament.tournament_id}:${tournament.status}:${matches.length}:${nextStep}`
      onUpdateTournamentState({ currentStep: nextStep })
    } else {
      stepSyncRef.current = syncKey
    }
  }, [isLoading, tournament?.tournament_id, tournament?.status, matches.length, currentStep, onUpdateTournamentState])

  // Handler functions
  const handleSetupComplete = () => {
    if (!(tournamentSetup.association || '').trim()) {
      toast.error('Please select an association')
      return
    }
    if (!(tournamentSetup.rankingSystem || '').trim()) {
      toast.error('Please select who the tournament is for (Tournament for)')
      return
    }
    if (!(tournamentSetup.gameType || '').trim()) {
      toast.error('Please select Game type')
      return
    }
    if (!(tournamentSetup.format || '').trim()) {
      toast.error('Please select Format')
      return
    }
    if (!tournamentSetup.maxPlayers || tournamentSetup.maxPlayers < 4) {
      toast.error('Please enter Max Players (at least 4)')
      return
    }
    const draw =
      tournamentSetup.bracketDrawSize != null && tournamentSetup.bracketDrawSize > 0
        ? tournamentSetup.bracketDrawSize
        : undefined
    const wpbaCtx =
      /wpba/i.test(tournamentSetup.association || '') ||
      /wpba/i.test(tournamentSetup.rankingSystem || '')
    const gameTypeResolved =
      wpbaCtx && !tournamentSetup.adminUnlockGameType
        ? '9-ball'
        : (tournamentSetup.gameType || '').trim()
    onCreateTournament({
      name: tournamentSetup.name,
      format: tournamentSetup.format || 'single_elimination',
      max_players: tournamentSetup.maxPlayers,
      entry_fee: tournamentSetup.entryFee || 0,
      tables: tournamentSetup.tables || 1,
      race_to: tournamentSetup.raceTo || 9,
      race_to_final: tournamentSetup.raceToFinal ?? 10,
      ranking_system: (tournamentSetup.rankingSystem || '').trim(),
      game_type: gameTypeResolved,
      association: (tournamentSetup.association || '').trim(),
      bracket_template_id: tournamentSetup.bracketTemplateId ?? undefined,
      bracket_draw_size: draw,
      bye_strategy: 'top_seed',
      location: (tournamentSetup.location || '').trim() || undefined,
      start_date: (tournamentSetup.startDate || '').trim() || undefined,
      end_date: (tournamentSetup.endDate || '').trim() || undefined,
      prize_pool:
        tournamentSetup.prizePool != null && tournamentSetup.prizePool > 0
          ? tournamentSetup.prizePool
          : undefined
    })
  }

  const handleGenerateBracket = () => {
    onGenerateBracket({
      shuffle_seeds: bracketSetup.shuffleSeeds,
      race_to: bracketSetup.raceTo,
      bye_player_ids: bracketSetup.byePlayerIds,
      bye_seed_positions: bracketSetup.byeSeedPositions
    })
  }

  const handleStepTransition = (fromStep: string, toStep: string) => {
    onUpdateTournamentState({ currentStep: toStep as WorkflowStep })
    testCenterLog.stepTransition(fromStep, toStep, {
      tab: 'tournament-workflow',
      tournamentId: tournament?.tournament_id
    })
  }

  const handleWorkflowStepClick = useCallback(
    (step: WorkflowStep) => {
      if (step === currentStep) return
      if (!canNavigateToWorkflowStep(step, tournament, matches.length)) {
        toast.info('Complete earlier workflow steps before opening this section.')
        return
      }
      handleStepTransition(currentStep, step)
    },
    [currentStep, tournament, matches.length, onUpdateTournamentState],
  )

  const beginNewTestSetup = () => {
    onUpdateTournamentState({
      tournamentSetup: {
        name: '',
        format: '',
        maxPlayers: 32,
        entryFee: 0,
        prizePool: 0,
        tables: 1,
        raceTo: 9,
        rankingSystem: '',
        gameType: '9-ball',
        association: associationOptions[0] ?? '',
        bracketTemplateId: null,
        bracketDrawSize: null,
        adminUnlockGameType: false,
        location: '',
        startDate: '',
        endDate: '',
        raceToFinal: 10,
        createdAt: tournamentSetup.createdAt,
        updatedAt: new Date().toISOString(),
      },
    })
    setWizardSource('new')
    setSetupEntryMode('form')
  }

  const loadClassicsUsaPreset = () => {
    onUpdateTournamentState({
      tournamentSetup: {
        name: 'The Classics USA',
        format: 'double_elimination',
        maxPlayers: 64,
        entryFee: 1000,
        prizePool: 20000,
        tables: 14,
        raceTo: 9,
        rankingSystem: 'WPBA Women',
        gameType: '9-ball',
        association: 'WPBA',
        bracketTemplateId: null,
        bracketDrawSize: 64,
        adminUnlockGameType: false,
        location: 'Sparta, TN',
        startDate: '2026-04-15',
        endDate: '2026-04-17',
        raceToFinal: 10,
        createdAt: tournamentSetup.createdAt,
        updatedAt: new Date().toISOString(),
      },
    })
    setWizardSource('new')
    setSetupEntryMode('form')
    toast.success('Classics USA E2E preset loaded — review and click Activate Tournament.')
  }

  const beginScheduledFromEvent = (event: UpcomingEvent) => {
    const updates = buildTestSetupFromUpcomingEvent(event, tournamentSetup)
    onUpdateTournamentState({ tournamentSetup: { ...tournamentSetup, ...updates } })
    setWizardSource('scheduled')
    setSetupEntryMode('form')
    toast.success(`Prefilled from ${event.association || 'upcoming'} — edit any field, then Activate Tournament.`)
  }

  const renderSetupEntryChooser = () => (
    <div className="setup-step">
      <div className="step-header">
        <h2>How do you want to start?</h2>
        <p>Matches production New Tournament: custom event or scheduled calendar prefill (Test Center DB only).</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 mb-6">
        <button
          type="button"
          className="text-left rounded-xl border-2 border-slate-600 bg-slate-800/60 p-6 hover:border-sky-500/60"
          onClick={beginNewTestSetup}
        >
          <span className="text-2xl block mb-2" aria-hidden>✨</span>
          <h3 className="text-lg font-bold text-white mb-2">Start new test tournament</h3>
          <p className="text-sm text-slate-400">Blank setup — e.g. The Classics USA scenario from the E2E checklist.</p>
          <button
            type="button"
            className="text-xs text-sky-400 hover:underline mt-3"
            onClick={(e) => {
              e.stopPropagation()
              loadClassicsUsaPreset()
            }}
          >
            Load Classics USA preset (64 DE) →
          </button>
        </button>
        <button
          type="button"
          className="text-left rounded-xl border-2 border-emerald-700/40 bg-emerald-950/20 p-6 hover:border-emerald-500/60"
          onClick={() => setSetupEntryMode('pick-scheduled')}
        >
          <span className="text-2xl block mb-2" aria-hidden>📅</span>
          <h3 className="text-lg font-bold text-white mb-2">Set up scheduled test tournament</h3>
          <p className="text-sm text-slate-400">Prefill from upcoming WPBA/WPA events (same data as Future Tournaments).</p>
          {directorUpcoming.length > 0 && (
            <p className="text-xs text-emerald-400 mt-2">{directorUpcoming.length} upcoming event(s)</p>
          )}
        </button>
      </div>
    </div>
  )

  const renderScheduledPicker = () => (
    <div className="setup-step">
      <button
        type="button"
        className="text-sm text-slate-400 hover:text-white mb-4"
        onClick={() => setSetupEntryMode('choose')}
      >
        ← Back to start options
      </button>
      <div className="step-header">
        <h2>Set up scheduled test tournament</h2>
        <p>Pick an event to prefill Step 1. All fields stay editable before Activate Tournament.</p>
      </div>
      {directorUpcoming.length === 0 ? (
        <div className="rounded-lg border border-slate-600 p-6 text-center text-slate-400">
          <p className="mb-4">No upcoming events for your associations. Run Settings → Refresh future tournaments, or start a custom test.</p>
          <button type="button" className="action-button primary" onClick={beginNewTestSetup}>
            Start new test tournament
          </button>
        </div>
      ) : (
        <ul className="space-y-3">
          {directorUpcoming.map((evt) => (
            <li
              key={upcomingEventKey(evt)}
              className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 rounded-lg border border-slate-600 bg-slate-800/50 p-4"
            >
              <div>
                <p className="font-semibold text-white">{evt.name}</p>
                <p className="text-sm text-slate-400">
                  {evt.association}
                  {formatEventDateLabel(evt) ? ` · ${formatEventDateLabel(evt)}` : ''}
                  {evt.location ? ` · ${evt.location}` : ''}
                  {evt.max_players ? ` · ${evt.max_players} players` : ''}
                </p>
              </div>
              <button
                type="button"
                className="action-button primary shrink-0"
                onClick={() => beginScheduledFromEvent(evt)}
              >
                Continue setup →
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )

  const renderStepIndicator = () => (
    <div className="step-indicator">
      {WORKFLOW_STEPS.map(({ id, number, label }) => {
        const completed =
          id === 'setup'
            ? currentStep !== 'setup'
            : id === 'registration'
              ? ['brackets', 'matches', 'results'].includes(currentStep)
              : id === 'brackets'
                ? ['matches', 'results'].includes(currentStep)
                : id === 'matches'
                  ? currentStep === 'results'
                  : false
        const active = currentStep === id
        const navigable = canNavigateToWorkflowStep(id, tournament, matches.length)
        return (
          <button
            key={id}
            type="button"
            className={`step step-nav ${active ? 'active' : completed ? 'completed' : ''}`}
            onClick={() => handleWorkflowStepClick(id)}
            disabled={!navigable && !active}
            title={
              navigable || active
                ? `Go to ${label}`
                : `Complete earlier steps to open ${label}`
            }
          >
            <span className="step-number">{number}</span>
            <span className="step-label">{label}</span>
          </button>
        )
      })}
    </div>
  )

  return (
    <div className="tournament-workflow">
      <div className="workflow-header">
        <div className="header-content">
          <div>
            <h3>🏆 Tournament Workflow Testing</h3>
            <p>Complete step-by-step tournament testing - Isolated test environment</p>
          </div>
          <div className="persistence-controls">
            <button
              className="action-button secondary small"
              onClick={onOpenPersistenceManager}
              title="Manage saved tournaments"
            >
              💾 Manage
            </button>
            <button
              className="action-button secondary small"
              onClick={onOpenExportImportManager}
              title="Export/Import tournament data"
            >
              📤📥 Export/Import
            </button>
            <button
              className="action-button primary small"
              onClick={() => onSaveTournament()}
              title="Save current tournament state"
            >
              💾 Save
            </button>
            <button
              className="action-button danger small"
              onClick={onResetTournament}
              title="Reset tournament to defaults"
            >
              🔄 Reset
            </button>
          </div>
        </div>
        {(lastAutoSaved || isAutoSaving) && (
          <div className="auto-save-status">
            {isAutoSaving && <span className="auto-saving">💾 Auto-saving...</span>}
            {lastAutoSaved && !isAutoSaving && (
              <span className="last-saved">
                💾 Last auto-saved: {lastAutoSaved.toLocaleTimeString()}
              </span>
            )}
          </div>
        )}
      </div>

      {renderStepIndicator()}

      {hasBracket && (
        <TestCenterBracketPanel
          tournamentId={tournament!.tournament_id}
          matches={matches}
          isDirectorMode={isDirectorMode}
          isLoading={isLoading}
          tournamentStatus={tournament?.status}
          title={
            tournament?.status === 'completed'
              ? 'Final bracket'
              : 'Tournament bracket'
          }
        />
      )}

      <div className="step-content">
        {currentStep === 'setup' && !tournament && setupEntryMode === 'choose' && renderSetupEntryChooser()}

        {currentStep === 'setup' && !tournament && setupEntryMode === 'pick-scheduled' && renderScheduledPicker()}

        {currentStep === 'setup' && !tournament && setupEntryMode === 'form' && (
          <>
            {!tournament && (
              <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                <button
                  type="button"
                  className="text-sm text-slate-400 hover:text-white"
                  onClick={() => setSetupEntryMode('choose')}
                >
                  ← Start options
                </button>
                {wizardSource === 'scheduled' && tournamentSetup.name && (
                  <span className="text-sm text-emerald-400">
                    Scheduled prefill: {tournamentSetup.name} (editable)
                  </span>
                )}
                {wizardSource === 'new' && (
                  <span className="text-sm text-sky-400">Custom new test tournament</span>
                )}
              </div>
            )}
          <TournamentSetupStep
            setup={tournamentSetup}
            onChange={(updates) => onUpdateTournamentState({ tournamentSetup: { ...tournamentSetup, ...updates } })}
            onComplete={handleSetupComplete}
            isLoading={isCreating}
            associationOptions={associationOptions}
            bracketTemplates={bracketTemplates}
            bracketTemplatesLoading={bracketTemplatesLoading}
            isAdmin={isAdmin}
            isSuperAdmin={isSuperAdmin}
          />
          </>
        )}

        {currentStep === 'registration' && (
          <PlayerRegistrationStep
            players={players}
            maxPlayers={tournament ? tournament.max_players : tournamentSetup.maxPlayers}
            bracketDrawSize={tournament?.bracket_draw_size ?? tournamentSetup.bracketDrawSize ?? undefined}
            onNext={() => handleStepTransition('registration', 'brackets')}
            onUpdatePlayerName={onUpdatePlayerName}
            onAutoFill={onAutoFill}
            onSeedClassicsDemo={onSeedClassicsDemo}
            onRandomizeSeeding={onRandomizeSeeding}
            onClearRegistration={onClearRegistration}
            onAddPlayer={onAddPlayer}
            onImportWpbaFromProduction={onImportWpbaFromProduction}
            onCloneProduction={onCloneProduction}
            isAutoFilling={isAutoFilling}
            isSeedingClassics={isSeedingClassics}
            isRandomizingSeeding={isRandomizingSeeding}
            randomizationCount={randomizationCount}
            isClearingRegistration={isClearingRegistration}
            isUpdatingPlayerName={isUpdatingPlayerName}
            isAddingPlayer={isAddingPlayer}
            isImportingWpba={isImportingWpba}
            isCloningProduction={isCloningProduction}
            isLoading={isLoading}
          />
        )}

        {currentStep === 'brackets' && (
          <BracketSetupStep
            setup={bracketSetup}
            onChange={(updates) => onUpdateTournamentState({ bracketSetup: { ...bracketSetup, ...updates } })}
            tournamentSetup={tournament || tournamentSetup}
            onGenerate={handleGenerateBracket}
            isLoading={isGenerating}
            hasExistingBracket={hasBracket}
          />
        )}

        {['matches', 'results'].includes(currentStep) && (
          <TournamentDashboard
            tournament={tournament}
            players={players}
            matches={matches}
            leaderboard={leaderboard}
            bracketTree={bracketTree}
            activeMatches={activeMatches}
            completedMatches={completedMatches}
            pendingMatches={pendingMatches}
            onSimulateMatch={(matchId, winnerBias) => onSimulateMatch(matchId, winnerBias)}
            onSimulateAll={onSimulateAll}
            isSimulating={isSimulating}
            isSimulatingAll={isSimulatingAll}
            isLoading={isLoading}
            isDirectorMode={isDirectorMode}
          />
        )}
      </div>
    </div>
  )
}

// API Testing Tab Component
interface ApiTestingTabProps {
  testResults: TestResult[]
  isRunningTests: boolean
  onRunTests: () => void
}

function ApiTestingTab({ testResults, isRunningTests, onRunTests }: ApiTestingTabProps) {
  return (
    <div className="api-testing">
      <div className="testing-section">
        <h3>🔌 API Endpoint Tests</h3>
        <p>Test all test tournament API endpoints for functionality and performance.</p>

        <div className="test-controls">
          <button
            className="action-button primary"
            onClick={onRunTests}
            disabled={isRunningTests}
          >
            {isRunningTests ? '🧪 Running Tests...' : '🚀 Run API Tests'}
          </button>
        </div>
      </div>

      <div className="testing-section">
        <h3>📊 Test Results</h3>
        {testResults.length === 0 ? (
          <p className="no-results">No tests run yet. Click "Run API Tests" to start.</p>
        ) : (
          <div className="test-results">
            {testResults.map((result, index) => (
              <div key={index} className={`test-result ${result.status}`}>
                <div className="test-header">
                  <span className="test-name">{result.test}</span>
                  <span className={`test-status status-${result.status}`}>
                    {result.status.toUpperCase()}
                    {result.duration && ` (${result.duration}ms)`}
                  </span>
                </div>
                <div className="test-message">{result.message}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// Database Testing Tab Component
interface DatabaseTestingTabProps {
  testResults: TestResult[]
  isRunningTests: boolean
  onRunTests: () => void
}

function DatabaseTestingTab({ testResults, isRunningTests, onRunTests }: DatabaseTestingTabProps) {
  return (
    <div className="database-testing">
      <div className="testing-section">
        <h3>🗄️ Database Tests</h3>
        <p>Test database connectivity, persistence, and data integrity.</p>

        <div className="test-controls">
          <button
            className="action-button primary"
            onClick={onRunTests}
            disabled={isRunningTests}
          >
            {isRunningTests ? '🧪 Running Tests...' : '🚀 Run Database Tests'}
          </button>
        </div>
      </div>

      <div className="testing-section">
        <h3>📊 Test Results</h3>
        {testResults.length === 0 ? (
          <p className="no-results">No tests run yet. Click "Run Database Tests" to start.</p>
        ) : (
          <div className="test-results">
            {testResults.map((result, index) => (
              <div key={index} className={`test-result ${result.status}`}>
                <div className="test-header">
                  <span className="test-name">{result.test}</span>
                  <span className={`test-status status-${result.status}`}>
                    {result.status.toUpperCase()}
                    {result.duration && ` (${result.duration}ms)`}
                  </span>
                </div>
                <div className="test-message">{result.message}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

const RANKING_SYSTEMS = [
  { value: 'WPBA_Women', label: 'WPBA Women' },
  { value: 'WPBA', label: 'WPBA' },
  { value: 'WPA_Women', label: 'WPA Women' },
  { value: 'WPA_Men', label: 'WPA Men' },
  { value: 'WPA', label: 'WPA' },
  { value: 'WPA_Heyball', label: 'WPA Heyball' },
  { value: 'WPA_Heyball_Men', label: 'WPA Heyball Men' },
  { value: 'WPA_Heyball_Women', label: 'WPA Heyball Women' },
  { value: 'WPA_Artistic', label: 'WPA Artistic' },
]

const GAME_TYPES = [
  { value: '9-ball', label: '9-Ball' },
  { value: '8-ball', label: '8-Ball' },
  { value: '10-ball', label: '10-Ball' },
  { value: 'straight-pool', label: 'Straight Pool' },
  { value: 'one-pocket', label: 'One Pocket' },
  { value: 'bank-pool', label: 'Bank Pool' },
  { value: 'other', label: 'Other' },
]

// Tournament Setup Step Component
interface TournamentSetupStepProps {
  setup: TournamentWorkflowState['tournamentSetup']
  onChange: (setup: Partial<TournamentWorkflowState['tournamentSetup']>) => void
  onComplete: () => void
  isLoading: boolean
  associationOptions: string[]
  bracketTemplates: BracketTemplate[]
  bracketTemplatesLoading: boolean
  isAdmin: boolean
  isSuperAdmin: boolean
}

function TournamentSetupStep({
  setup,
  onChange,
  onComplete,
  isLoading,
  associationOptions,
  bracketTemplates,
  bracketTemplatesLoading,
  isAdmin,
  isSuperAdmin
}: TournamentSetupStepProps) {
  const handleInputChange = (field: string, value: string | number | boolean | null) => {
    onChange({ ...setup, [field]: value })
  }

  const isWpba =
    /wpba/i.test(setup.association || '') || /wpba/i.test(setup.rankingSystem || '')
  const gameTypeLocked = isWpba && !setup.adminUnlockGameType
  const canUnlockGameType = isAdmin || isSuperAdmin

  const templateForSize = useMemo(() => {
    const m = new Map<number, BracketTemplate>()
    for (const t of bracketTemplates) {
      if (t.format !== 'single_elimination') continue
      if (!m.has(t.player_count)) m.set(t.player_count, t)
    }
    return m
  }, [bracketTemplates])

  const applyPreset = (playerCount: number) => {
    const t = templateForSize.get(playerCount)
    const draw = t?.bracket_draw_size ?? (playerCount === 80 ? 128 : playerCount)
    onChange({
      ...setup,
      bracketTemplateId: t?.id ?? null,
      bracketDrawSize: draw,
      maxPlayers: Math.max(setup.maxPlayers || 0, playerCount)
    })
  }

  const coachMessage =
    !(setup.association || '').trim()
      ? { label: 'Getting started', body: 'Choose your association, then ranking system and bracket size. Red is only used when something must be fixed before you continue.' }
      : !(setup.rankingSystem || '').trim()
        ? { label: 'Next', body: 'Select who this test event is for (ranking system) so Auto Fill can pull the right player list.' }
        : { label: 'Heads up', body: 'Bracket draw size should be a power of two (16, 32, 64, or 128 for 80 players). Match Max players to your test scenario.' }

  return (
    <div className="setup-step">
      <div className="step-header">
        <h2>Step 1: Tournament Setup</h2>
        <p>Aligned with production New Tournament: association, bracket template, game rules, then basics.</p>
      </div>

      <div className="rounded-lg border border-purple-500/40 bg-gradient-to-r from-purple-950/30 to-indigo-950/20 p-4 mb-4">
        <div className="text-xs font-semibold text-violet-300 uppercase tracking-wide">{coachMessage.label}</div>
        <p className="text-slate-200 text-sm mt-1">{coachMessage.body}</p>
      </div>

      <div className="setup-form">
        <div className="form-row">
          <label className="form-label">
            Association <span className="required-asterisk">*</span>
            <select
              value={setup.association ?? ''}
              onChange={(e) => handleInputChange('association', e.target.value)}
              className="form-select"
              required
            >
              <option value="">— Select —</option>
              {associationOptions.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
            {associationOptions.length === 0 && (
              <span className="text-amber-200 text-sm block mt-1">No associations on your account. Use Settings (admin) to assign association tags.</span>
            )}
          </label>
        </div>

        <div className="form-row">
          <label className="form-label">
            Bracket template (single elim.) {bracketTemplatesLoading && <span className="text-slate-400 text-sm">(loading…)</span>}
          </label>
        </div>
        <div className="flex flex-wrap gap-2 mb-4">
          {[16, 32, 64, 80].map((n) => (
            <button
              key={n}
              type="button"
              className="action-button secondary small"
              onClick={() => applyPreset(n)}
            >
              {n === 80 ? '80 (128 draw)' : `${n} players`}
            </button>
          ))}
        </div>
        <div className="form-row">
          <label className="form-label">
            Bracket draw size (power of 2)
            <input
              type="number"
              value={setup.bracketDrawSize ?? ''}
              onChange={(e) =>
                handleInputChange(
                  'bracketDrawSize',
                  e.target.value === '' ? null : parseInt(e.target.value, 10)
                )
              }
              className="form-input"
              min="2"
              placeholder="e.g. 32 or 128"
            />
          </label>
        </div>

        <div className="form-row">
          <label className="form-label">
            Tournament Name
            <input
              type="text"
              value={setup.name}
              onChange={(e) => handleInputChange('name', e.target.value)}
              className="form-input"
              placeholder="Enter tournament name"
            />
          </label>
        </div>

        <div className="form-row">
          <label className="form-label">
            Location
            <input
              type="text"
              value={setup.location ?? ''}
              onChange={(e) => handleInputChange('location', e.target.value)}
              className="form-input"
              placeholder="e.g. Sparta, TN"
            />
          </label>
          <label className="form-label">
            Start date
            <input
              type="date"
              value={(setup.startDate || '').slice(0, 10)}
              onChange={(e) => handleInputChange('startDate', e.target.value)}
              className="form-input"
            />
          </label>
          <label className="form-label">
            End date
            <input
              type="date"
              value={(setup.endDate || '').slice(0, 10)}
              onChange={(e) => handleInputChange('endDate', e.target.value)}
              className="form-input"
            />
          </label>
        </div>

        <div className="form-row">
          <label className="form-label">
            Prize pool ($)
            <input
              type="number"
              value={setup.prizePool === 0 || setup.prizePool == null ? '' : setup.prizePool}
              onChange={(e) =>
                handleInputChange('prizePool', e.target.value === '' ? 0 : parseInt(e.target.value, 10))
              }
              className="form-input"
              min={0}
              placeholder="e.g. 20000"
            />
          </label>
          <label className="form-label">
            Grand final race to (WPBA often 10)
            <input
              type="number"
              value={setup.raceToFinal ?? 10}
              onChange={(e) =>
                handleInputChange('raceToFinal', e.target.value === '' ? 10 : parseInt(e.target.value, 10))
              }
              className="form-input"
              min={1}
            />
          </label>
        </div>

        <div className="form-row">
          <label className="form-label">
            Tournament for (ranking system) <span className="required-asterisk">*</span>
            <select
              value={setup.rankingSystem ?? ''}
              onChange={(e) => handleInputChange('rankingSystem', e.target.value)}
              className="form-select"
              title="Auto Fill uses this ranking system"
              required
            >
              <option value="">— Select —</option>
              {RANKING_SYSTEMS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>

          <label className="form-label">
            Game type <span className="required-asterisk">*</span>
            {gameTypeLocked && (
              <span className="text-slate-400 text-xs block">WPBA: 9-ball default. Admin can unlock other disciplines.</span>
            )}
            <select
              value={gameTypeLocked ? '9-ball' : (setup.gameType ?? '')}
              onChange={(e) => handleInputChange('gameType', e.target.value)}
              className="form-select"
              disabled={gameTypeLocked}
              required
            >
              <option value="">— Select —</option>
              {GAME_TYPES.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            {canUnlockGameType && isWpba && (
              <label className="flex items-center gap-2 mt-2 text-sm text-slate-300">
                <input
                  type="checkbox"
                  checked={!!setup.adminUnlockGameType}
                  onChange={(e) => handleInputChange('adminUnlockGameType', e.target.checked)}
                />
                Admin: allow other game types (WPBA)
              </label>
            )}
          </label>
        </div>

        <div className="form-row">
          <label className="form-label">
            Format
            <select
              value={setup.format ?? ''}
              onChange={(e) =>
                handleInputChange('format', e.target.value as 'single_elimination' | 'double_elimination')
              }
              className="form-select"
            >
              <option value="">— Select —</option>
              <option value="single_elimination">Single Elimination</option>
              <option value="double_elimination">Double Elimination (64 players: full winners + losers + final)</option>
            </select>
          </label>

          <label className="form-label">
            Entry Fee ($)
            <input
              type="number"
              value={setup.entryFee === 0 ? '' : setup.entryFee}
              onChange={(e) =>
                handleInputChange('entryFee', e.target.value === '' ? 0 : parseInt(e.target.value, 10))
              }
              className="form-input"
              min="0"
              step="100"
              placeholder="0"
            />
          </label>
        </div>

        <div className="form-row">
          <label className="form-label">
            Max Players
            <input
              type="number"
              value={setup.maxPlayers === 0 ? '' : setup.maxPlayers}
              onChange={(e) =>
                handleInputChange('maxPlayers', e.target.value === '' ? 0 : parseInt(e.target.value, 10))
              }
              className="form-input"
              min="4"
              max="128"
              step="1"
              placeholder="e.g. 32"
            />
          </label>

          <label className="form-label">
            Tables
            <input
              type="number"
              value={setup.tables === 0 ? '' : setup.tables}
              onChange={(e) =>
                handleInputChange('tables', e.target.value === '' ? 0 : parseInt(e.target.value, 10))
              }
              className="form-input"
              min="1"
              max="32"
              placeholder="1"
            />
          </label>

          <label className="form-label">
            Race To
            <input
              type="number"
              value={setup.raceTo === 0 ? '' : setup.raceTo}
              onChange={(e) =>
                handleInputChange('raceTo', e.target.value === '' ? 0 : parseInt(e.target.value, 10))
              }
              className="form-input"
              min="3"
              max="15"
              placeholder="9"
            />
          </label>
        </div>

        <div className="tournament-summary">
          <h3>Tournament Summary</h3>
          <div className="summary-grid">
            <div className="summary-item">
              <span className="summary-label">Association:</span>
              <span className="summary-value">{setup.association || '—'}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Draw size:</span>
              <span className="summary-value">{setup.bracketDrawSize ?? '—'}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Tournament for:</span>
              <span className="summary-value">
                {setup.rankingSystem
                  ? RANKING_SYSTEMS.find((r) => r.value === setup.rankingSystem)?.label ?? setup.rankingSystem
                  : '—'}
              </span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Game type:</span>
              <span className="summary-value">{gameTypeLocked ? '9-ball' : setup.gameType || '—'}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Format:</span>
              <span className="summary-value">{setup.format ? setup.format.replace('_', ' ') : '—'}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Players:</span>
              <span className="summary-value">{setup.maxPlayers || '—'}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Entry Fee:</span>
              <span className="summary-value">
                {setup.entryFee != null && setup.entryFee > 0 ? `$${setup.entryFee}` : '—'}
              </span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Prize Pool:</span>
              <span className="summary-value">
                {setup.entryFee > 0 && setup.maxPlayers > 0 ? `$${setup.entryFee * setup.maxPlayers}` : '—'}
              </span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Tables:</span>
              <span className="summary-value">{setup.tables}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Race To:</span>
              <span className="summary-value">{setup.raceTo}</span>
            </div>
          </div>
        </div>

        <div className="step-actions">
          <button className="next-btn" onClick={onComplete} disabled={isLoading}>
            {isLoading ? 'Setting up...' : 'Activate Tournament'}
          </button>
        </div>
      </div>
    </div>
  )
}

// Player Registration Step Component
interface PlayerRegistrationStepProps {
  players: any[]
  maxPlayers: number
  bracketDrawSize?: number
  onNext: () => void
  onUpdatePlayerName?: (playerId: string, name: string) => void
  onAutoFill?: () => void
  onSeedClassicsDemo?: () => void
  onRandomizeSeeding?: () => void
  onClearRegistration?: () => void
  onAddPlayer?: (body: { first_name: string; last_name: string; country?: string }) => void
  onImportWpbaFromProduction?: () => void
  onCloneProduction?: () => void
  isAutoFilling?: boolean
  isSeedingClassics?: boolean
  isRandomizingSeeding?: boolean
  randomizationCount?: number
  isClearingRegistration?: boolean
  isUpdatingPlayerName?: boolean
  isAddingPlayer?: boolean
  isImportingWpba?: boolean
  isCloningProduction?: boolean
  isLoading: boolean
}

function PlayerRegistrationStep({
  players,
  maxPlayers,
  bracketDrawSize,
  onNext,
  onUpdatePlayerName,
  onAutoFill,
  onSeedClassicsDemo,
  onRandomizeSeeding,
  onClearRegistration,
  onAddPlayer,
  onImportWpbaFromProduction,
  onCloneProduction,
  isAutoFilling,
  isSeedingClassics,
  isRandomizingSeeding,
  randomizationCount,
  isClearingRegistration,
  isUpdatingPlayerName,
  isAddingPlayer,
  isImportingWpba,
  isCloningProduction,
  isLoading
}: PlayerRegistrationStepProps) {
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [search, setSearch] = useState('')
  const [newFirst, setNewFirst] = useState('')
  const [newLast, setNewLast] = useState('')
  const [newCountry, setNewCountry] = useState('')

  const filteredPlayers = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return players
    return players.filter((p) => (p.name || '').toLowerCase().includes(q))
  }, [players, search])

  const namedCount = players.filter((p) => (p.name || '').trim()).length

  const startEdit = (player: { player_id: string; name: string }) => {
    setEditingId(player.player_id)
    setEditValue(player.name || '')
  }

  const saveEdit = (playerId: string) => {
    if (onUpdatePlayerName) {
      onUpdatePlayerName(playerId, editValue.trim())
    }
    setEditingId(null)
    setEditValue('')
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditValue('')
  }

  if (isLoading) {
    return <PageLoader />
  }

  return (
    <div className="registration-step">
      <div className="step-header">
        <h2>👥 Step 2: Player Registration</h2>
        <p>Review registered players before proceeding to brackets</p>
      </div>

      <div className="rounded-lg border border-blue-500/40 bg-slate-900/40 p-3 mb-4 text-sm text-slate-200">
        Search filters the list. Add new players for first-time tour tests. Auto Fill uses the ranking system from setup.
        {bracketDrawSize != null && bracketDrawSize > 0 && (
          <span className="block mt-1 text-slate-400">
            Bracket draw size: {bracketDrawSize} — aim for enough <strong>named</strong> players ({namedCount} now).
          </span>
        )}
      </div>

      <div className="form-row mb-4">
        <label className="form-label flex-1">
          Search players
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="form-input"
            placeholder="Filter by name"
          />
        </label>
      </div>

      {onAddPlayer && (
        <div className="border border-slate-600 rounded p-4 mb-4">
          <h4 className="text-slate-200 mb-2">Add new player</h4>
          <div className="form-row">
            <input
              className="form-input"
              placeholder="First name"
              value={newFirst}
              onChange={(e) => setNewFirst(e.target.value)}
            />
            <input
              className="form-input"
              placeholder="Last name"
              value={newLast}
              onChange={(e) => setNewLast(e.target.value)}
            />
            <input
              className="form-input"
              placeholder="Country (optional)"
              value={newCountry}
              onChange={(e) => setNewCountry(e.target.value)}
              maxLength={3}
            />
            <button
              type="button"
              className="action-button primary small"
              disabled={isAddingPlayer || !newFirst.trim() || !newLast.trim()}
              onClick={() => {
                onAddPlayer({
                  first_name: newFirst.trim(),
                  last_name: newLast.trim(),
                  country: newCountry.trim() || undefined
                })
                setNewFirst('')
                setNewLast('')
                setNewCountry('')
              }}
            >
              {isAddingPlayer ? 'Adding…' : 'Add player'}
            </button>
          </div>
        </div>
      )}

      <div className="registration-summary">
        <div className="summary-stats">
          <div className="stat-box">
            <span className="stat-number">{players.length}</span>
            <span className="stat-label">Registered</span>
          </div>
          <div className="stat-box">
            <span className="stat-number">{namedCount}</span>
            <span className="stat-label">With names</span>
          </div>
          <div className="stat-box">
            <span className="stat-number">{maxPlayers - players.length}</span>
            <span className="stat-label">Slots left</span>
          </div>
          <div className="stat-box">
            <span className="stat-number">{maxPlayers}</span>
            <span className="stat-label">Max players</span>
          </div>
        </div>

        <div className="progress-bar">
          <div
            className="progress-fill"
            style={{ width: `${(players.length / maxPlayers) * 100}%` }}
          />
        </div>
      </div>

      <div className="players-list">
        <div className="players-list-header">
          <h3>Registered Players</h3>
          <div className="players-list-actions">
            {onClearRegistration && players.length > 0 && (
              <button
                type="button"
                className="clear-registration-btn"
                onClick={() => onClearRegistration()}
                disabled={isClearingRegistration}
                title="Clear all players so you can use Auto Fill again"
              >
                {isClearingRegistration ? 'Clearing...' : 'Clear registration'}
              </button>
            )}
            {onAutoFill && (
              <button
                type="button"
                className="auto-fill-btn"
                onClick={() => onAutoFill()}
                disabled={isAutoFilling || players.length >= maxPlayers}
                title={players.length >= maxPlayers ? 'Tournament full' : 'Add top players to fill the tournament'}
              >
                {isAutoFilling ? 'Adding...' : players.length >= maxPlayers ? '✨ Auto Fill (full)' : '✨ Auto Fill'}
              </button>
            )}
            {onSeedClassicsDemo && (
              <button
                type="button"
                className="auto-fill-btn ml-2 border border-amber-600/50"
                onClick={() => onSeedClassicsDemo()}
                disabled={isSeedingClassics}
                title="Replace registration with 64 demo players (seeds 1–32) for WPBA double-elim test"
              >
                {isSeedingClassics ? 'Seeding…' : 'Seed 64 classics demo'}
              </button>
            )}
            {onRandomizeSeeding && players.length >= 2 && (
              <button
                type="button"
                className="auto-fill-btn ml-2 border border-violet-600/50"
                onClick={() => onRandomizeSeeding()}
                disabled={isRandomizingSeeding || (randomizationCount ?? 0) >= 3}
                title={
                  (randomizationCount ?? 0) >= 3
                    ? 'Maximum 3 randomizations reached'
                    : 'Randomize player seeding (each press produces a dissimilar order)'
                }
              >
                {isRandomizingSeeding
                  ? 'Shuffling…'
                  : (randomizationCount ?? 0) >= 3
                    ? `Randomized (3/3)`
                    : `Randomize Seeding (${randomizationCount ?? 0}/3)`}
              </button>
            )}
            {onImportWpbaFromProduction && (
              <button
                type="button"
                className="auto-fill-btn ml-2 border border-emerald-600/50"
                onClick={() => onImportWpbaFromProduction()}
                disabled={isImportingWpba || players.length >= maxPlayers}
                title={
                  players.length >= maxPlayers
                    ? 'Tournament full'
                    : 'Copy real WPBA player names from the production DB into this test tournament. Each first_name is prefixed with "test " so no un-prefixed row is ever stored. Read-only from production; writes go to the Test Center DB only.'
                }
              >
                {isImportingWpba
                  ? 'Copying…'
                  : 'Copy WPBA players from production (prefix: test)'}
              </button>
            )}
            {onCloneProduction && (
              <button
                type="button"
                className="auto-fill-btn ml-2 border border-sky-600/50"
                onClick={() => onCloneProduction()}
                disabled={isCloningProduction || isImportingWpba}
                title='Replace Test Center mirror tables (players, rankings, tournament history, Fargo history) with read-only copies from production; names prefixed with "test ". Requires a current test tournament.'
              >
                {isCloningProduction ? 'Cloning…' : 'Clone production → Test Center'}
              </button>
            )}
          </div>
        </div>
        <div className="players-grid">
          {filteredPlayers.map(player => (
            <div key={player.player_id} className="player-card">
              {editingId === player.player_id ? (
                <>
                  <input
                    className="player-name-input"
                    value={editValue}
                    onChange={e => setEditValue(e.target.value)}
                    onBlur={() => saveEdit(player.player_id)}
                    onKeyDown={e => {
                      if (e.key === 'Enter') saveEdit(player.player_id)
                      if (e.key === 'Escape') cancelEdit()
                    }}
                    autoFocus
                    aria-label="Edit player name"
                  />
                  <div className="player-card-edit-actions">
                    <button
                      type="button"
                      className="edit-btn save"
                      onClick={() => saveEdit(player.player_id)}
                      disabled={isUpdatingPlayerName}
                    >
                      Save
                    </button>
                    <button type="button" className="edit-btn cancel" onClick={cancelEdit}>
                      Cancel
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <div className="player-name">
                    {(player.name || '').trim() ? player.name : '—'}
                  </div>
                  {onUpdatePlayerName && (
                    <button
                      type="button"
                      className="player-edit-btn"
                      onClick={() => startEdit(player)}
                      title="Edit name"
                      aria-label={`Edit ${player.name}`}
                    >
                      ✏️ Edit
                    </button>
                  )}
                </>
              )}
              {(player.license_number != null && player.license_number !== '') ||
               player.total_points != null ||
               player.rank != null ||
               player.country ? (
                <div className="player-details">
                  {player.license_number != null && player.license_number !== '' && (
                    <span title="License">Lic: {player.license_number}</span>
                  )}
                  {player.total_points != null && (
                    <span title="Total points">Pts: {Number(player.total_points).toLocaleString()}</span>
                  )}
                  {player.rank != null && (
                    <span title="Rank">#{player.rank}</span>
                  )}
                  {player.country && <span>{player.country}</span>}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </div>

      <div className="step-actions">
        <button
          className="next-btn"
          onClick={onNext}
        >
          🎯 Proceed to Bracket Setup
        </button>
      </div>
    </div>
  )
}

// Bracket Setup Step Component
interface BracketSetupStepProps {
  setup: {
    shuffleSeeds: boolean
    raceTo: number
    byePlayerIds: string[]
    byeSeedPositions: number[]
  }
  onChange: (setup: any) => void
  tournamentSetup: any
  onGenerate: () => void
  isLoading: boolean
  hasExistingBracket?: boolean
}

function BracketSetupStep({
  setup,
  onChange,
  tournamentSetup,
  onGenerate,
  isLoading,
  hasExistingBracket = false,
}: BracketSetupStepProps) {
  const handleInputChange = (field: string, value: boolean | number) => {
    onChange({
      ...setup,
      [field]: value
    })
  }

  return (
    <div className="bracket-step">
      <div className="step-header">
        <h2>🎱 Step 3: Bracket Setup</h2>
        <p>Configure bracket generation options</p>
      </div>

      <div className="bracket-options">
        <div className="option-group">
          <label className="checkbox-option">
            <input
              type="checkbox"
              checked={setup.shuffleSeeds}
              onChange={(e) => handleInputChange('shuffleSeeds', e.target.checked)}
            />
            <span>Shuffle Seeds (Randomize player positions)</span>
          </label>
        </div>

        <div className="option-group">
          <label className="form-label">
            Race To
            <input
              type="number"
              value={setup.raceTo}
              onChange={(e) => handleInputChange('raceTo', parseInt(e.target.value))}
              className="form-input"
              min="3"
              max="15"
            />
          </label>
        </div>

        <div className="bracket-summary">
          <h3>📋 Bracket Configuration</h3>
          <div className="summary-grid">
            <div className="summary-item">
              <span className="summary-label">Tournament:</span>
              <span className="summary-value">{tournamentSetup.name}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Format:</span>
              <span className="summary-value">{tournamentSetup.format?.replace('_', ' ') || tournamentSetup.format}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Players:</span>
              <span className="summary-value">{tournamentSetup.max_players || tournamentSetup.maxPlayers}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Shuffle Seeds:</span>
              <span className="summary-value">{setup.shuffleSeeds ? 'Yes' : 'No'}</span>
            </div>
            <div className="summary-item">
              <span className="summary-label">Race To:</span>
              <span className="summary-value">{setup.raceTo}</span>
            </div>
          </div>
        </div>

        <div className="step-actions">
          <button
            className="next-btn"
            onClick={onGenerate}
            disabled={isLoading}
          >
            {isLoading ? 'Generating...' : hasExistingBracket ? '🔄 Regenerate Brackets' : '🎯 Generate Brackets'}
          </button>
        </div>
      </div>

      {hasExistingBracket && (
        <p className="text-sm text-slate-400 mt-4">
          Bracket is shown above and stays available on every step, including after the tournament finishes.
        </p>
      )}
    </div>
  )
}

// Tournament Dashboard Component
interface TournamentDashboardProps {
  tournament: any
  players: any[]
  matches: any[]
  leaderboard: any[]
  bracketTree?: import('@/api/testTournaments').TestBracketTree
  activeMatches: any[]
  completedMatches: any[]
  pendingMatches: any[]
  onSimulateMatch: (matchId: string, winnerBias: string) => void
  onSimulateAll: () => void
  isSimulating: boolean
  isSimulatingAll?: boolean
  isLoading: boolean
  isDirectorMode?: boolean
}

function isPlayablePending(m: any): boolean {
  if (m.status !== 'pending') return false
  const n1 = (m.operator_name || '').trim()
  const n2 = (m.player2_name || '').trim()
  if (!m.operator_id || !m.player2_id) return false
  if (n1 === 'TBD' || n2 === 'TBD' || n1 === 'BYE' || n2 === 'BYE') return false
  if (!n1 || !n2) return false
  return true
}

function TournamentDashboard({
  tournament,
  players,
  matches,
  leaderboard,
  activeMatches,
  completedMatches,
  pendingMatches,
  onSimulateMatch,
  onSimulateAll,
  isSimulating,
  isSimulatingAll,
  isLoading,
  isDirectorMode = false,
}: TournamentDashboardProps) {
  const playablePending = pendingMatches.filter(isPlayablePending)

  if (isLoading) {
    return <PageLoader />
  }

  return (
    <div className="tournament-dashboard">
      <div className="step-header">
        <h2>{tournament?.status === 'completed' ? 'Tournament Results' : 'Tournament Dashboard'}</h2>
        <p>
          {tournament?.status === 'completed'
            ? 'Final standings below. The full bracket stays visible above for review.'
            : 'Simulate matches in round order; winners advance automatically. Use Simulate all to finish the bracket.'}
        </p>
        {tournament?.status === 'completed' && (
          <p className="text-green-400 text-sm mt-2">Tournament complete.</p>
        )}
      </div>

      <div className="dashboard-stats">
        <div className="stat-card">
          <div className="stat-value">{players.length}</div>
          <div className="stat-label">Total Players</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{matches.length}</div>
          <div className="stat-label">Total Matches</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{completedMatches.length}</div>
          <div className="stat-label">Completed</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{playablePending.length}</div>
          <div className="stat-label">Ready to play</div>
        </div>
      </div>

      {playablePending.length > 0 && (
        <div className="simulation-section mb-4">
          <button
            type="button"
            className="action-button primary mb-2"
            onClick={onSimulateAll}
            disabled={isSimulatingAll || isSimulating}
          >
            {isSimulatingAll ? 'Simulating all…' : 'Simulate all remaining (fair)'}
          </button>
        </div>
      )}

      {pendingMatches.length > 0 && (
        <div className="simulation-section">
          <h3>Simulate one match</h3>
          <div className="match-simulation">
            <select id="match-select" className="match-select">
              <option value="">Select a match to simulate...</option>
              {playablePending.slice(0, 120).map(match => (
                <option key={match.match_id} value={match.match_id}>
                  [{match.bracket_type || 'winners'}] R{match.round_number}: {match.operator_name} vs {match.player2_name}
                </option>
              ))}
            </select>

            <div className="simulation-buttons">
              <button
                className="action-button small"
                onClick={() => {
                  const select = document.getElementById('match-select') as HTMLSelectElement
                  const matchId = select.value
                  if (matchId) onSimulateMatch(matchId, 'fair')
                }}
                disabled={isSimulating}
              >
                🎲 Fair Play
              </button>
              <button
                className="action-button small"
                onClick={() => {
                  const select = document.getElementById('match-select') as HTMLSelectElement
                  const matchId = select.value
                  if (matchId) onSimulateMatch(matchId, 'operator')
                }}
                disabled={isSimulating}
              >
                🥇 Player 1 Wins
              </button>
              <button
                className="action-button small"
                onClick={() => {
                  const select = document.getElementById('match-select') as HTMLSelectElement
                  const matchId = select.value
                  if (matchId) onSimulateMatch(matchId, 'player2')
                }}
                disabled={isSimulating}
              >
                🥈 Player 2 Wins
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="leaderboard-section">
        <h3>Leaderboard</h3>
        <div className="leaderboard-preview">
          {leaderboard.slice(0, 64).map((entry, index) => (
            <div key={entry.player_id} className="leaderboard-row">
              <span className="rank">#{index + 1}</span>
              {entry.placement != null && <span className="text-amber-300 text-xs mr-2">P{entry.placement}</span>}
              <span className="player-name">{entry.name}</span>
              <span className="stats">{entry.wins}W-{entry.losses}L</span>
              {entry.wpba_r_points != null && (
                <span className="text-sky-300 text-xs mr-2" title="WPBA-style R-points (banded)">
                  {entry.wpba_r_points} pts
                </span>
              )}
              <span className="rating">{entry.current_rating?.toFixed(1) || 'N/A'}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// System Testing Tab Component
function SystemTestingTab() {
  return (
    <div className="system-testing">
      <div className="testing-section">
        <h3>⚙️ System Tests</h3>
        <p>Monitor system health, performance, and configuration.</p>
      </div>

      <div className="testing-section">
        <h3>🔍 System Information</h3>
        <div className="system-info">
          <div className="info-row">
            <span className="info-label">Environment:</span>
            <span className="info-value">Development</span>
          </div>
          <div className="info-row">
            <span className="info-label">Database:</span>
            <span className="info-value">PostgreSQL (Test Schema)</span>
          </div>
          <div className="info-row">
            <span className="info-label">API Status:</span>
            <span className="info-value status-healthy">✅ Healthy</span>
          </div>
          <div className="info-row">
            <span className="info-label">Test Data:</span>
            <span className="info-value">✅ Available</span>
          </div>
        </div>
      </div>

      <div className="testing-section">
        <h3>🛠️ Development Tools</h3>
        <div className="dev-tools">
          <button className="action-button secondary" onClick={() => window.location.reload()}>
            🔄 Reload Page
          </button>
          <button className="action-button secondary" onClick={() => localStorage.clear()}>
            🗑️ Clear Local Storage
          </button>
          <button
            type="button"
            className="action-button secondary"
            onClick={() => {
              toast.info('Use the "Reset & Cleanup" tab to clear test tournament data on the server.')
            }}
          >
            Reset Test Data (see Reset tab)
          </button>
        </div>
      </div>
    </div>
  )
}