/**
 * React hooks for tournament persistence operations
 * Provides easy-to-use hooks for saving, loading, and managing tournament states
 */

import { useState, useEffect, useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  tournamentPersistence,
  TournamentWorkflowState,
  SavedTournament,
  PersistenceSettings
} from '@/lib/tournamentPersistence'
import { toast } from '@/lib/toast'
import { testCenterLogger } from '@/lib/testCenterLogger'

// Hook for initializing persistence service
export function useTournamentPersistenceInit() {
  return useQuery({
    queryKey: ['tournament-persistence-init'],
    queryFn: () => tournamentPersistence.init(),
    staleTime: Infinity, // Only initialize once
    retry: false
  })
}

// Hook for persistence settings
export function usePersistenceSettings() {
  const [settings, setSettings] = useState<PersistenceSettings | null>(null)

  const { data: initialSettings, isLoading } = useQuery({
    queryKey: ['persistence-settings'],
    queryFn: () => tournamentPersistence.getSettings(),
    staleTime: 5 * 60 * 1000 // 5 minutes
  })

  const updateSettingsMutation = useMutation({
    mutationFn: (newSettings: Partial<PersistenceSettings>) =>
      tournamentPersistence.updateSettings(newSettings),
    onSuccess: (updatedSettings) => {
      setSettings(updatedSettings)
      toast.success('Persistence settings updated')
      testCenterLogger.userInteraction('persistence_settings_saved', {
        settings: Object.keys(updatedSettings)
      })
    },
    onError: (error) => {
      toast.error('Failed to update persistence settings')
      testCenterLogger.criticalError(error, {
        operation: 'update_persistence_settings'
      })
    }
  })

  useEffect(() => {
    if (initialSettings) {
      setSettings(initialSettings)
    }
  }, [initialSettings])

  return {
    settings,
    isLoading,
    updateSettings: updateSettingsMutation.mutate,
    isUpdating: updateSettingsMutation.isPending
  }
}

// Hook for saving tournaments
export function useSaveTournament() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      state,
      name,
      description
    }: {
      state: TournamentWorkflowState
      name?: string
      description?: string
    }) => {
      const id = await tournamentPersistence.saveTournament(state, name, description)
      return { id, state, name, description }
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['saved-tournaments'] })
      toast.success(`Tournament "${result.name || 'Unnamed'}" saved successfully`)
      testCenterLogger.userInteraction('tournament_save_success', {
        tournamentId: result.id,
        tournamentName: result.name
      })
    },
    onError: (error) => {
      toast.error('Failed to save tournament')
      testCenterLogger.criticalError(error, {
        operation: 'save_tournament_hook'
      })
    }
  })
}

// Hook for loading tournaments
export function useLoadTournament() {
  return useMutation({
    mutationFn: (id: string) => tournamentPersistence.loadTournament(id),
    onSuccess: (tournament) => {
      if (tournament) {
        toast.success(`Tournament "${tournament.name}" loaded successfully`)
        testCenterLogger.userInteraction('tournament_load_success', {
          tournamentId: tournament.id,
          tournamentName: tournament.name
        })
      }
    },
    onError: (error) => {
      toast.error('Failed to load tournament')
      testCenterLogger.criticalError(error, {
        operation: 'load_tournament_hook'
      })
    }
  })
}

// Hook for getting saved tournaments list
export function useSavedTournaments() {
  return useQuery({
    queryKey: ['saved-tournaments'],
    queryFn: () => tournamentPersistence.getSavedTournaments(),
    staleTime: 30 * 1000 // 30 seconds
  })
}

// Hook for deleting tournaments
export function useDeleteTournament() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => tournamentPersistence.deleteTournament(id),
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['saved-tournaments'] })
      toast.success('Tournament deleted successfully')
      testCenterLogger.userInteraction('tournament_delete_success', {
        tournamentId: id
      })
    },
    onError: (error) => {
      toast.error('Failed to delete tournament')
      testCenterLogger.criticalError(error, {
        operation: 'delete_tournament_hook'
      })
    }
  })
}

// Hook for exporting tournaments
export function useExportTournament() {
  return useMutation({
    mutationFn: (id: string) => tournamentPersistence.exportTournament(id),
    onSuccess: (jsonData, id) => {
      // Create and trigger download
      const blob = new Blob([jsonData], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `tournament_${id}_${new Date().toISOString().split('T')[0]}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      toast.success('Tournament exported successfully')
      testCenterLogger.userInteraction('tournament_export_success', {
        tournamentId: id
      })
    },
    onError: (error) => {
      toast.error('Failed to export tournament')
      testCenterLogger.criticalError(error, {
        operation: 'export_tournament_hook'
      })
    }
  })
}

// Hook for importing tournaments
export function useImportTournament() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (jsonData: string) => tournamentPersistence.importTournament(jsonData),
    onSuccess: (id) => {
      queryClient.invalidateQueries({ queryKey: ['saved-tournaments'] })
      toast.success('Tournament imported successfully')
      testCenterLogger.userInteraction('tournament_import_success', {
        tournamentId: id
      })
    },
    onError: (error) => {
      toast.error('Failed to import tournament')
      testCenterLogger.criticalError(error, {
        operation: 'import_tournament_hook'
      })
    }
  })
}

// Hook for clearing all data
export function useClearAllTournamentData() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => tournamentPersistence.clearAllData(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['saved-tournaments'] })
      toast.success('All tournament data cleared')
      testCenterLogger.userInteraction('all_tournament_data_cleared_success')
    },
    onError: (error) => {
      toast.error('Failed to clear tournament data')
      testCenterLogger.criticalError(error, {
        operation: 'clear_all_data_hook'
      })
    }
  })
}

// Hook for auto-saving current tournament state
export function useAutoSaveTournament() {
  const [lastSaved, setLastSaved] = useState<Date | null>(null)

  const autoSaveMutation = useMutation({
    mutationFn: (state: TournamentWorkflowState) =>
      tournamentPersistence.autoSaveCurrentTournament(state),
    onSuccess: () => {
      setLastSaved(new Date())
    },
    onError: (error) => {
      // Don't show toast for auto-save failures to avoid spam
      testCenterLogger.errorRecovery('localStorage', 'auto_save_failed', false, {
        error: error.message
      })
    }
  })

  // Auto-save with debouncing
  const debouncedAutoSave = useCallback(
    (() => {
      let timeoutId: NodeJS.Timeout
      return (state: TournamentWorkflowState, delay = 2000) => {
        clearTimeout(timeoutId)
        timeoutId = setTimeout(() => {
          autoSaveMutation.mutate(state)
        }, delay)
      }
    })(),
    [autoSaveMutation]
  )

  return {
    autoSave: debouncedAutoSave,
    lastSaved,
    isAutoSaving: autoSaveMutation.isPending
  }
}

// Hook for loading auto-saved tournament
export function useLoadAutoSavedTournament() {
  return useQuery({
    queryKey: ['auto-saved-tournament'],
    queryFn: () => tournamentPersistence.loadAutoSavedTournament(),
    staleTime: 60 * 1000, // 1 minute
    retry: false
  })
}

// Hook for managing tournament persistence UI state
export function useTournamentPersistenceUI() {
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  const [showLoadDialog, setShowLoadDialog] = useState(false)
  const [showSettingsDialog, setShowSettingsDialog] = useState(false)
  const [selectedTournament, setSelectedTournament] = useState<SavedTournament | null>(null)

  const openSaveDialog = useCallback(() => setShowSaveDialog(true), [])
  const closeSaveDialog = useCallback(() => setShowSaveDialog(false), [])
  const openLoadDialog = useCallback(() => setShowLoadDialog(true), [])
  const closeLoadDialog = useCallback(() => setShowLoadDialog(false), [])
  const openSettingsDialog = useCallback(() => setShowSettingsDialog(true), [])
  const closeSettingsDialog = useCallback(() => setShowSettingsDialog(false), [])

  return {
    dialogs: {
      save: { show: showSaveDialog, open: openSaveDialog, close: closeSaveDialog },
      load: { show: showLoadDialog, open: openLoadDialog, close: closeLoadDialog },
      settings: { show: showSettingsDialog, open: openSettingsDialog, close: closeSettingsDialog }
    },
    selectedTournament,
    setSelectedTournament
  }
}

// Hook for tournament state management with persistence
export function useTournamentStateWithPersistence(initialState?: Partial<TournamentWorkflowState>) {
  const [tournamentState, setTournamentState] = useState<TournamentWorkflowState>({
    currentStep: 'setup',
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
      association: '',
      bracketTemplateId: null,
      bracketDrawSize: null,
      adminUnlockGameType: false,
      location: '',
      startDate: '',
      endDate: '',
      raceToFinal: 10,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    },
    bracketSetup: {
      shuffleSeeds: false,
      raceTo: 9,
      byePlayerIds: [],
      byeSeedPositions: []
    },
    ...initialState
  })

  const { autoSave, lastSaved, isAutoSaving } = useAutoSaveTournament()
  const saveMutation = useSaveTournament()

  // Auto-save when state changes
  useEffect(() => {
    autoSave(tournamentState)
  }, [tournamentState, autoSave])

  const updateTournamentState = useCallback((updates: Partial<TournamentWorkflowState>) => {
    setTournamentState(prev => ({
      ...prev,
      ...updates,
      tournamentSetup: {
        ...prev.tournamentSetup,
        ...(updates.tournamentSetup ?? {}),
        updatedAt: new Date().toISOString()
      },
      bracketSetup: updates.bracketSetup
        ? { ...prev.bracketSetup, ...updates.bracketSetup }
        : prev.bracketSetup,
    }))
  }, [setTournamentState])

  const resetTournamentState = useCallback(() => {
    setTournamentState({
      currentStep: 'setup',
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
        association: '',
        bracketTemplateId: null,
        bracketDrawSize: null,
        adminUnlockGameType: false,
        location: '',
        startDate: '',
        endDate: '',
        raceToFinal: 10,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      },
      bracketSetup: {
        shuffleSeeds: false,
        raceTo: 9,
        byePlayerIds: [],
        byeSeedPositions: []
      }
    })
  }, [])

  const saveTournament = useCallback((name?: string, description?: string) => {
    saveMutation.mutate({ state: tournamentState, name, description })
  }, [tournamentState, saveMutation])

  return {
    tournamentState,
    updateTournamentState,
    resetTournamentState,
    saveTournament,
    lastAutoSaved: lastSaved,
    isAutoSaving,
    isSaving: saveMutation.isPending,
    saveError: saveMutation.error
  }
}

export default {
  useTournamentPersistenceInit,
  usePersistenceSettings,
  useSaveTournament,
  useLoadTournament,
  useSavedTournaments,
  useDeleteTournament,
  useExportTournament,
  useImportTournament,
  useClearAllTournamentData,
  useAutoSaveTournament,
  useLoadAutoSavedTournament,
  useTournamentPersistenceUI,
  useTournamentStateWithPersistence
}