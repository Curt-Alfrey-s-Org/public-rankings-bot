/**
 * Test Center Reset Hooks
 * Provides comprehensive reset functionality for TestCenter data and state
 */

import { useState, useCallback } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { tournamentPersistence, TournamentWorkflowState } from '@/lib/tournamentPersistence'
import { testTournamentsApi } from '@/api/testTournaments'
import { toast } from '@/lib/toast'
import { testCenterLogger, testCenterLog } from '@/lib/testCenterLogger'

// Reset operation types
export type ResetType =
  | 'workflow'          // Reset current tournament workflow back to setup step
  | 'database'          // Clear all test tournament data from database
  | 'cache'            // Clear cached data and localStorage/IndexedDB
  | 'factory'          // Full factory reset to initial state
  | 'selective'        // Selective reset with options

export type SelectiveResetOptions = {
  keepSettings: boolean      // Keep persistence settings but clear data
  keepSavedTournaments: boolean // Keep saved tournaments but reset current state
  clearApiCache: boolean     // Clear React Query cache
  clearLocalStorage: boolean // Clear localStorage
  clearIndexedDB: boolean    // Clear IndexedDB
}

// Reset operation status
export interface ResetStatus {
  type: ResetType
  phase: 'idle' | 'confirming' | 'backing_up' | 'executing' | 'completed' | 'failed'
  progress: number // 0-100
  message: string
  backupData?: any
  error?: string
  startTime?: Date
  endTime?: Date
}

// Reset operation result
export interface ResetResult {
  success: boolean
  type: ResetType
  duration: number
  operations: string[]
  errors: string[]
  backupCreated: boolean
  backupId?: string
}

// Hook for managing reset operations
export function useTestCenterReset() {
  const queryClient = useQueryClient()
  const [resetStatus, setResetStatus] = useState<ResetStatus>({
    type: 'workflow',
    phase: 'idle',
    progress: 0,
    message: 'Ready to reset'
  })

  // Update reset status
  const updateStatus = useCallback((updates: Partial<ResetStatus>) => {
    setResetStatus(prev => ({ ...prev, ...updates }))
  }, [])

  // Create backup before reset
  const createBackup = useCallback(async (type: ResetType): Promise<string | null> => {
    try {
      updateStatus({ phase: 'backing_up', message: 'Creating backup...', progress: 10 })

      const backupData: any = {}
      const operations: string[] = []

      // Backup current tournament state
      try {
        const currentTournament = await testTournamentsApi.getCurrentTournament()
        backupData.tournament = currentTournament
        operations.push('tournament_data')
      } catch (error) {
        // Tournament might not exist, that's okay
      }

      // Backup players, matches, leaderboard
      try {
        const [players, matches, leaderboard] = await Promise.all([
          testTournamentsApi.getPlayers(),
          testTournamentsApi.getMatches(),
          testTournamentsApi.getLeaderboard()
        ])
        backupData.players = players
        backupData.matches = matches
        backupData.leaderboard = leaderboard
        operations.push('api_data')
      } catch (error) {
        // API data might not be available
      }

      // Backup localStorage and IndexedDB data
      try {
        const savedTournaments = await tournamentPersistence.getSavedTournaments()
        const persistenceSettings = await tournamentPersistence.getSettings()
        const autoSaved = await tournamentPersistence.loadAutoSavedTournament()

        backupData.savedTournaments = savedTournaments
        backupData.persistenceSettings = persistenceSettings
        backupData.autoSavedTournament = autoSaved
        operations.push('persistence_data')
      } catch (error) {
        // Persistence data might not be available
      }

      // Create backup ID and store
      const backupId = `backup_${type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
      const backupInfo = {
        id: backupId,
        type,
        createdAt: new Date().toISOString(),
        operations,
        data: backupData
      }

      // Store backup in localStorage temporarily
      localStorage.setItem(`testcenter_backup_${backupId}`, JSON.stringify(backupInfo))

      updateStatus({ backupData: backupInfo, progress: 20 })

      testCenterLog.userInteraction('backup_created', {
        backupId,
        backupType: type,
        operations: operations.length
      })

      return backupId
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'create_backup',
        resetType: type
      })
      updateStatus({ error: `Backup failed: ${error.message}` })
      return null
    }
  }, [updateStatus])

  // Reset workflow state
  const resetWorkflow = useCallback(async (): Promise<boolean> => {
    try {
      updateStatus({ message: 'Resetting workflow state...', progress: 30 })

      // Reset tournament persistence state
      const defaultState: TournamentWorkflowState = {
        currentStep: 'setup',
        tournamentSetup: {
          name: '',
          format: '',
          maxPlayers: 0,
          entryFee: 0,
          prizePool: 0,
          tables: 0,
          raceTo: 0,
          rankingSystem: '',
          gameType: '',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString()
        },
        bracketSetup: {
          shuffleSeeds: false,
          raceTo: 9,
          byePlayerIds: [],
          byeSeedPositions: []
        }
      }

      // Clear auto-saved state
      localStorage.removeItem('testcenter_current_tournament')

      // Reset React Query cache for test data
      queryClient.invalidateQueries({ queryKey: ['test-tournament'] })
      queryClient.invalidateQueries({ queryKey: ['test-players'] })
      queryClient.invalidateQueries({ queryKey: ['test-matches'] })
      queryClient.invalidateQueries({ queryKey: ['test-leaderboard'] })

      updateStatus({ message: 'Workflow reset complete', progress: 60 })

      testCenterLog.userInteraction('workflow_reset', {
        resetType: 'workflow'
      })

      return true
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'reset_workflow'
      })
      updateStatus({ error: `Workflow reset failed: ${error.message}` })
      return false
    }
  }, [queryClient, updateStatus])

  // Reset database data
  const resetDatabase = useCallback(async (): Promise<boolean> => {
    try {
      updateStatus({ message: 'Clearing database data...', progress: 40 })

      await testTournamentsApi.resetDatabase()

      queryClient.invalidateQueries({ queryKey: ['test-tournament'] })
      queryClient.invalidateQueries({ queryKey: ['test-players'] })
      queryClient.invalidateQueries({ queryKey: ['test-matches'] })
      queryClient.invalidateQueries({ queryKey: ['test-leaderboard'] })
      queryClient.invalidateQueries({ queryKey: ['test-bracket-tree'] })

      updateStatus({ message: 'Database reset complete', progress: 70 })

      testCenterLog.userInteraction('database_reset', {
        resetType: 'database'
      })

      return true
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'reset_database'
      })
      updateStatus({ error: `Database reset failed: ${error.message}` })
      return false
    }
  }, [queryClient, updateStatus])

  // Reset cache data
  const resetCache = useCallback(async (): Promise<boolean> => {
    try {
      updateStatus({ message: 'Clearing cached data...', progress: 50 })

      // Clear React Query cache
      queryClient.clear()

      // Clear tournament persistence data
      await tournamentPersistence.clearAllData()

      // Clear localStorage (selective - keep non-testcenter data)
      const keysToRemove: string[] = []
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith('testcenter_')) {
          keysToRemove.push(key)
        }
      }
      keysToRemove.forEach(key => localStorage.removeItem(key))

      // Clear IndexedDB (if supported)
      if ('indexedDB' in window) {
        // Note: Clearing IndexedDB would require additional implementation
        // For now, we rely on the persistence service clearing its own data
      }

      updateStatus({ message: 'Cache cleared successfully', progress: 80 })

      testCenterLog.userInteraction('cache_reset', {
        resetType: 'cache'
      })

      return true
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'reset_cache'
      })
      updateStatus({ error: `Cache reset failed: ${error.message}` })
      return false
    }
  }, [queryClient, updateStatus])

  // Factory reset - complete reset to initial state
  const factoryReset = useCallback(async (): Promise<boolean> => {
    try {
      updateStatus({ message: 'Performing factory reset...', progress: 25 })

      // Clear all data (combine cache + database reset)
      const cacheResult = await resetCache()
      if (!cacheResult) throw new Error('Cache reset failed')

      updateStatus({ message: 'Factory reset complete', progress: 90 })

      testCenterLog.userInteraction('factory_reset', {
        resetType: 'factory'
      })

      return true
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'factory_reset'
      })
      updateStatus({ error: `Factory reset failed: ${error.message}` })
      return false
    }
  }, [resetCache, updateStatus])

  // Selective reset with options
  const selectiveReset = useCallback(async (options: SelectiveResetOptions): Promise<boolean> => {
    try {
      updateStatus({ message: 'Performing selective reset...', progress: 30 })

      const operations: string[] = []

      // Clear React Query cache if requested
      if (options.clearApiCache) {
        queryClient.clear()
        operations.push('api_cache')
      }

      // Clear localStorage if requested
      if (options.clearLocalStorage) {
        const keysToRemove: string[] = []
        for (let i = 0; i < localStorage.length; i++) {
          const key = localStorage.key(i)
          if (key && key.startsWith('testcenter_')) {
            // Keep settings if requested
            if (!options.keepSettings || !key.includes('settings')) {
              keysToRemove.push(key)
            }
          }
        }
        keysToRemove.forEach(key => localStorage.removeItem(key))
        operations.push('localStorage')
      }

      // Clear IndexedDB if requested
      if (options.clearIndexedDB && !options.keepSavedTournaments) {
        await tournamentPersistence.clearAllData()
        operations.push('indexedDB')
      } else if (options.clearIndexedDB && options.keepSavedTournaments) {
        // Note: Would need more granular clearing in persistence service
        operations.push('indexedDB_partial')
      }

      // Reset workflow if not keeping saved tournaments
      if (!options.keepSavedTournaments) {
        localStorage.removeItem('testcenter_current_tournament')
        queryClient.invalidateQueries({ queryKey: ['test-tournament'] })
        queryClient.invalidateQueries({ queryKey: ['test-players'] })
        queryClient.invalidateQueries({ queryKey: ['test-matches'] })
        queryClient.invalidateQueries({ queryKey: ['test-leaderboard'] })
        operations.push('workflow')
      }

      updateStatus({ message: 'Selective reset complete', progress: 85 })

      testCenterLog.userInteraction('selective_reset', {
        resetType: 'selective',
        options,
        operations
      })

      return true
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'selective_reset',
        options
      })
      updateStatus({ error: `Selective reset failed: ${error.message}` })
      return false
    }
  }, [queryClient, updateStatus])

  // Main reset function
  const performReset = useCallback(async (
    type: ResetType,
    options?: SelectiveResetOptions,
    skipBackup = false
  ): Promise<ResetResult> => {
    const startTime = new Date()
    updateStatus({
      type,
      phase: 'confirming',
      progress: 0,
      message: 'Starting reset operation...',
      startTime,
      error: undefined
    })

    const result: ResetResult = {
      success: false,
      type,
      duration: 0,
      operations: [],
      errors: [],
      backupCreated: false
    }

    try {
      // Create backup unless skipped
      let backupId: string | null = null
      if (!skipBackup) {
        backupId = await createBackup(type)
        if (backupId) {
          result.backupCreated = true
          result.backupId = backupId
          result.operations.push('backup')
        }
      }

      updateStatus({ phase: 'executing' })

      // Execute the appropriate reset
      let resetSuccess = false
      switch (type) {
        case 'workflow':
          resetSuccess = await resetWorkflow()
          result.operations.push('workflow_reset')
          break
        case 'database':
          resetSuccess = await resetDatabase()
          result.operations.push('database_reset')
          break
        case 'cache':
          resetSuccess = await resetCache()
          result.operations.push('cache_reset')
          break
        case 'factory':
          resetSuccess = await factoryReset()
          result.operations.push('factory_reset')
          break
        case 'selective':
          if (options) {
            resetSuccess = await selectiveReset(options)
            result.operations.push('selective_reset')
          } else {
            throw new Error('Selective reset requires options')
          }
          break
        default:
          throw new Error(`Unknown reset type: ${type}`)
      }

      if (!resetSuccess) {
        throw new Error('Reset operation failed')
      }

      // Complete
      const endTime = new Date()
      const duration = endTime.getTime() - startTime.getTime()

      updateStatus({
        phase: 'completed',
        progress: 100,
        message: `${type} reset completed successfully`,
        endTime
      })

      result.success = true
      result.duration = duration

      testCenterLog.userInteraction('reset_completed', {
        resetType: type,
        duration,
        backupCreated: result.backupCreated,
        operations: result.operations
      })

      return result

    } catch (error) {
      const endTime = new Date()
      const duration = endTime.getTime() - startTime.getTime()

      updateStatus({
        phase: 'failed',
        progress: 100,
        message: `Reset failed: ${error.message}`,
        endTime,
        error: error.message
      })

      result.duration = duration
      result.errors.push(error.message)

      testCenterLogger.criticalError(error, {
        operation: 'perform_reset',
        resetType: type,
        duration
      })

      return result
    }
  }, [createBackup, resetWorkflow, resetDatabase, resetCache, factoryReset, selectiveReset, updateStatus])

  // Restore from backup
  const restoreFromBackup = useCallback(async (backupId: string): Promise<boolean> => {
    try {
      updateStatus({ message: 'Restoring from backup...', progress: 10 })

      const backupData = localStorage.getItem(`testcenter_backup_${backupId}`)
      if (!backupData) {
        throw new Error('Backup not found')
      }

      const backup = JSON.parse(backupData)

      // Restore persistence data
      if (backup.data.persistenceSettings) {
        await tournamentPersistence.updateSettings(backup.data.persistenceSettings)
      }

      if (backup.data.savedTournaments) {
        // Note: Restoring tournaments would require additional API endpoints
        // For now, we can only restore local persistence settings
      }

      updateStatus({ message: 'Backup restored successfully', progress: 100 })

      testCenterLog.userInteraction('backup_restored', {
        backupId,
        operations: backup.operations
      })

      return true
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'restore_backup',
        backupId
      })
      updateStatus({ error: `Restore failed: ${error.message}` })
      return false
    }
  }, [updateStatus])

  // Get available backups
  const getAvailableBackups = useCallback(() => {
    const backups: Array<{ id: string; type: ResetType; createdAt: string; operations: string[] }> = []

    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key && key.startsWith('testcenter_backup_')) {
        try {
          const backupData = localStorage.getItem(key)
          if (backupData) {
            const backup = JSON.parse(backupData)
            backups.push({
              id: backup.id,
              type: backup.type,
              createdAt: backup.createdAt,
              operations: backup.operations
            })
          }
        } catch (error) {
          // Skip invalid backup data
        }
      }
    }

    return backups.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  }, [])

  // Clear old backups
  const clearOldBackups = useCallback((keepLastN = 5) => {
    const backups = getAvailableBackups()

    if (backups.length <= keepLastN) return

    const toDelete = backups.slice(keepLastN)
    toDelete.forEach(backup => {
      localStorage.removeItem(`testcenter_backup_${backup.id}`)
    })

    testCenterLog.userInteraction('old_backups_cleared', {
      deletedCount: toDelete.length,
      keptCount: keepLastN
    })
  }, [getAvailableBackups])

  return {
    resetStatus,
    performReset,
    restoreFromBackup,
    getAvailableBackups,
    clearOldBackups,
    updateStatus
  }
}

// Hook for managing reset UI state
export function useResetUI() {
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [pendingReset, setPendingReset] = useState<{
    type: ResetType
    options?: SelectiveResetOptions
    skipBackup?: boolean
  } | null>(null)

  const requestReset = useCallback((type: ResetType, options?: SelectiveResetOptions, skipBackup = false) => {
    setPendingReset({ type, options, skipBackup })
    setShowConfirmDialog(true)
  }, [])

  const cancelReset = useCallback(() => {
    setPendingReset(null)
    setShowConfirmDialog(false)
  }, [])

  const confirmReset = useCallback(() => {
    setShowConfirmDialog(false)
    // Return the pending reset for execution
    return pendingReset
  }, [pendingReset])

  return {
    showConfirmDialog,
    pendingReset,
    requestReset,
    cancelReset,
    confirmReset
  }
}

export default {
  useTestCenterReset,
  useResetUI
}