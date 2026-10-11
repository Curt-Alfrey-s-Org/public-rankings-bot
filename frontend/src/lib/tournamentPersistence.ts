/**
 * Tournament Persistence Service
 * Handles saving and loading tournament configurations and states across browser sessions
 * Uses IndexedDB for large data storage and localStorage as fallback
 */

import { testCenterLogger } from './testCenterLogger'

// Tournament state interfaces
export interface TournamentState {
  tournamentId?: string
  name: string
  format: 'single_elimination' | 'double_elimination' | ''
  maxPlayers: number
  entryFee: number
  prizePool?: number
  tables: number
  raceTo: number
  rankingSystem?: string
  gameType?: string
  /** Association tag (mirrors production wizard). */
  association?: string
  bracketTemplateId?: number | null
  bracketDrawSize?: number | null
  adminUnlockGameType?: boolean
  /** Venue / city (Test Center → API location). */
  location?: string
  startDate?: string
  endDate?: string
  /** Grand final race (e.g. WPBA 10). */
  raceToFinal?: number
  status?: string
  createdAt: string
  updatedAt: string
}

export interface TournamentWorkflowState {
  currentStep: 'setup' | 'registration' | 'brackets' | 'matches' | 'results'
  tournamentSetup: TournamentState
  bracketSetup: {
    shuffleSeeds: boolean
    raceTo: number
    byePlayerIds: string[]
    byeSeedPositions: number[]
  }
  tournament?: any // Full tournament data
  players?: any[]
  matches?: any[]
  leaderboard?: any[]
}

export interface SavedTournament {
  id: string
  name: string
  description?: string
  state: TournamentWorkflowState
  createdAt: string
  updatedAt: string
  lastAccessedAt: string
  version: string
}

// Storage keys
const STORAGE_KEYS = {
  SAVED_TOURNAMENTS: 'testcenter_saved_tournaments',
  CURRENT_TOURNAMENT: 'testcenter_current_tournament',
  PERSISTENCE_SETTINGS: 'testcenter_persistence_settings'
}

// Persistence settings
interface PersistenceSettings {
  autoSave: boolean
  maxSavedTournaments: number
  storageType: 'indexeddb' | 'localstorage'
  enableCompression: boolean
}

// Default settings
const DEFAULT_SETTINGS: PersistenceSettings = {
  autoSave: true,
  maxSavedTournaments: 10,
  storageType: 'indexeddb',
  enableCompression: false
}

// IndexedDB setup
class TournamentDB {
  private db: IDBDatabase | null = null
  private readonly dbName = 'TestCenterTournaments'
  private readonly version = 1

  async init(): Promise<void> {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, this.version)

      request.onerror = () => {
        testCenterLogger.criticalError(new Error('IndexedDB initialization failed'), {
          operation: 'init_indexeddb',
          errorType: 'IndexedDBError'
        })
        reject(new Error('Failed to initialize IndexedDB'))
      }

      request.onsuccess = (event) => {
        this.db = (event.target as IDBOpenDBRequest).result
        testCenterLogger.userInteraction('indexeddb_initialized', {
          operation: 'init_indexeddb'
        })
        resolve()
      }

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result

        // Create tournaments store
        if (!db.objectStoreNames.contains('tournaments')) {
          const store = db.createObjectStore('tournaments', { keyPath: 'id' })
          store.createIndex('name', 'name', { unique: false })
          store.createIndex('createdAt', 'createdAt', { unique: false })
          store.createIndex('updatedAt', 'updatedAt', { unique: false })
        }

        // Create settings store
        if (!db.objectStoreNames.contains('settings')) {
          db.createObjectStore('settings', { keyPath: 'key' })
        }

        testCenterLogger.userInteraction('indexeddb_upgraded', {
          operation: 'upgrade_indexeddb',
          newVersion: this.version
        })
      }
    })
  }

  async saveTournament(tournament: SavedTournament): Promise<void> {
    if (!this.db) throw new Error('Database not initialized')

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['tournaments'], 'readwrite')
      const store = transaction.objectStore('tournaments')

      const request = store.put(tournament)

      request.onsuccess = () => {
        testCenterLogger.dataFlow('tournament_saved_indexeddb', 1, {
          tournamentId: tournament.id,
          tournamentName: tournament.name
        })
        resolve()
      }

      request.onerror = () => {
        testCenterLogger.criticalError(new Error('Failed to save tournament to IndexedDB'), {
          operation: 'save_tournament_indexeddb',
          tournamentId: tournament.id
        })
        reject(new Error('Failed to save tournament'))
      }
    })
  }

  async loadTournament(id: string): Promise<SavedTournament | null> {
    if (!this.db) throw new Error('Database not initialized')

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['tournaments'], 'readonly')
      const store = transaction.objectStore('tournaments')

      const request = store.get(id)

      request.onsuccess = () => {
        const result = request.result as SavedTournament | undefined
        if (result) {
          testCenterLogger.dataFlow('tournament_loaded_indexeddb', 1, {
            tournamentId: result.id,
            tournamentName: result.name
          })
          resolve(result)
        } else {
          resolve(null)
        }
      }

      request.onerror = () => {
        testCenterLogger.criticalError(new Error('Failed to load tournament from IndexedDB'), {
          operation: 'load_tournament_indexeddb',
          tournamentId: id
        })
        reject(new Error('Failed to load tournament'))
      }
    })
  }

  async getAllTournaments(): Promise<SavedTournament[]> {
    if (!this.db) throw new Error('Database not initialized')

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['tournaments'], 'readonly')
      const store = transaction.objectStore('tournaments')
      const index = store.index('updatedAt')

      const request = index.openCursor(null, 'prev') // Most recent first
      const results: SavedTournament[] = []

      request.onsuccess = (event) => {
        const cursor = (event.target as IDBRequest).result as IDBCursorWithValue | null
        if (cursor) {
          results.push(cursor.value)
          cursor.continue()
        } else {
          testCenterLogger.dataFlow('tournaments_listed_indexeddb', results.length, {
            operation: 'list_tournaments'
          })
          resolve(results)
        }
      }

      request.onerror = () => {
        testCenterLogger.criticalError(new Error('Failed to list tournaments from IndexedDB'), {
          operation: 'list_tournaments_indexeddb'
        })
        reject(new Error('Failed to list tournaments'))
      }
    })
  }

  async deleteTournament(id: string): Promise<void> {
    if (!this.db) throw new Error('Database not initialized')

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['tournaments'], 'readwrite')
      const store = transaction.objectStore('tournaments')

      const request = store.delete(id)

      request.onsuccess = () => {
        testCenterLogger.userInteraction('tournament_deleted_indexeddb', {
          tournamentId: id,
          operation: 'delete_tournament'
        })
        resolve()
      }

      request.onerror = () => {
        testCenterLogger.criticalError(new Error('Failed to delete tournament from IndexedDB'), {
          operation: 'delete_tournament_indexeddb',
          tournamentId: id
        })
        reject(new Error('Failed to delete tournament'))
      }
    })
  }

  async saveSetting(key: string, value: any): Promise<void> {
    if (!this.db) throw new Error('Database not initialized')

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['settings'], 'readwrite')
      const store = transaction.objectStore('settings')

      const request = store.put({ key, value })

      request.onsuccess = () => resolve()
      request.onerror = () => reject(new Error('Failed to save setting'))
    })
  }

  async loadSetting(key: string): Promise<any> {
    if (!this.db) throw new Error('Database not initialized')

    return new Promise((resolve, reject) => {
      const transaction = this.db!.transaction(['settings'], 'readonly')
      const store = transaction.objectStore('settings')

      const request = store.get(key)

      request.onsuccess = () => {
        const result = request.result
        resolve(result ? result.value : null)
      }

      request.onerror = () => reject(new Error('Failed to load setting'))
    })
  }
}

// Main persistence service
class TournamentPersistenceService {
  private db: TournamentDB | null = null
  private settings: PersistenceSettings = DEFAULT_SETTINGS
  private initialized = false

  async init(): Promise<void> {
    if (this.initialized) return

    try {
      // Load settings from localStorage first
      const savedSettings = localStorage.getItem(STORAGE_KEYS.PERSISTENCE_SETTINGS)
      if (savedSettings) {
        this.settings = { ...DEFAULT_SETTINGS, ...JSON.parse(savedSettings) }
      }

      // Initialize IndexedDB if preferred, fallback to localStorage
      if (this.settings.storageType === 'indexeddb' && this.isIndexedDBSupported()) {
        this.db = new TournamentDB()
        await this.db.init()

        // Load settings from IndexedDB
        const dbSettings = await this.db.loadSetting('persistence_settings')
        if (dbSettings) {
          this.settings = { ...this.settings, ...dbSettings }
        }
      }

      this.initialized = true
      testCenterLogger.userInteraction('persistence_service_initialized', {
        storageType: this.settings.storageType,
        autoSave: this.settings.autoSave
      })

    } catch (error) {
      // Fallback to localStorage
      testCenterLogger.errorRecovery('IndexedDB', 'fallback_to_localstorage', true, {
        error: error.message
      })
      this.settings.storageType = 'localstorage'
      this.initialized = true
    }
  }

  private isIndexedDBSupported(): boolean {
    return typeof window !== 'undefined' && 'indexedDB' in window
  }

  async getSettings(): Promise<PersistenceSettings> {
    await this.ensureInitialized()
    return { ...this.settings }
  }

  async updateSettings(newSettings: Partial<PersistenceSettings>): Promise<void> {
    await this.ensureInitialized()
    this.settings = { ...this.settings, ...newSettings }

    // Save to localStorage
    localStorage.setItem(STORAGE_KEYS.PERSISTENCE_SETTINGS, JSON.stringify(this.settings))

    // Save to IndexedDB if available
    if (this.db) {
      await this.db.saveSetting('persistence_settings', this.settings)
    }

    testCenterLogger.userInteraction('persistence_settings_updated', {
      newSettings: Object.keys(newSettings)
    })
  }

  async saveTournament(state: TournamentWorkflowState, name?: string, description?: string): Promise<string> {
    await this.ensureInitialized()

    const id = `tournament_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    const now = new Date().toISOString()

    const savedTournament: SavedTournament = {
      id,
      name: name || state.tournamentSetup.name || `Tournament ${new Date().toLocaleDateString()}`,
      description,
      state: { ...state },
      createdAt: now,
      updatedAt: now,
      lastAccessedAt: now,
      version: '1.0'
    }

    try {
      if (this.db && this.settings.storageType === 'indexeddb') {
        await this.db.saveTournament(savedTournament)
      } else {
        await this.saveToLocalStorage(savedTournament)
      }

      // Auto-cleanup old tournaments
      await this.cleanupOldTournaments()

      testCenterLogger.userInteraction('tournament_saved', {
        tournamentId: id,
        tournamentName: savedTournament.name,
        storageType: this.settings.storageType
      })

      return id
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'save_tournament',
        tournamentId: id
      })
      throw new Error('Failed to save tournament')
    }
  }

  async loadTournament(id: string): Promise<SavedTournament | null> {
    await this.ensureInitialized()

    try {
      let tournament: SavedTournament | null = null

      if (this.db && this.settings.storageType === 'indexeddb') {
        tournament = await this.db.loadTournament(id)
      } else {
        tournament = await this.loadFromLocalStorage(id)
      }

      if (tournament) {
        // Update last accessed time
        tournament.lastAccessedAt = new Date().toISOString()
        await this.updateTournamentAccessTime(tournament)

        testCenterLogger.userInteraction('tournament_loaded', {
          tournamentId: id,
          tournamentName: tournament.name
        })
      }

      return tournament
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'load_tournament',
        tournamentId: id
      })
      return null
    }
  }

  async getSavedTournaments(): Promise<SavedTournament[]> {
    await this.ensureInitialized()

    try {
      let tournaments: SavedTournament[] = []

      if (this.db && this.settings.storageType === 'indexeddb') {
        tournaments = await this.db.getAllTournaments()
      } else {
        tournaments = await this.getAllFromLocalStorage()
      }

      testCenterLogger.dataFlow('tournaments_listed', tournaments.length, {
        operation: 'list_saved_tournaments'
      })

      return tournaments
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'list_saved_tournaments'
      })
      return []
    }
  }

  async deleteTournament(id: string): Promise<void> {
    await this.ensureInitialized()

    try {
      if (this.db && this.settings.storageType === 'indexeddb') {
        await this.db.deleteTournament(id)
      } else {
        await this.deleteFromLocalStorage(id)
      }

      testCenterLogger.userInteraction('tournament_deleted', {
        tournamentId: id
      })
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'delete_tournament',
        tournamentId: id
      })
      throw new Error('Failed to delete tournament')
    }
  }

  async exportTournament(id: string): Promise<string> {
    const tournament = await this.loadTournament(id)
    if (!tournament) {
      throw new Error('Tournament not found')
    }

    const exportData = {
      ...tournament,
      exportedAt: new Date().toISOString(),
      exportVersion: '1.0'
    }

    testCenterLogger.userInteraction('tournament_exported', {
      tournamentId: id,
      tournamentName: tournament.name
    })

    return JSON.stringify(exportData, null, 2)
  }

  async importTournament(jsonData: string): Promise<string> {
    try {
      const importData = JSON.parse(jsonData)

      // Validate import data structure
      if (!importData.id || !importData.state || !importData.name) {
        throw new Error('Invalid tournament data format')
      }

      const tournament: SavedTournament = {
        id: importData.id,
        name: importData.name,
        description: importData.description || 'Imported tournament',
        state: importData.state,
        createdAt: importData.createdAt || new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        lastAccessedAt: new Date().toISOString(),
        version: importData.version || '1.0'
      }

      // Generate new ID to avoid conflicts
      const newId = `tournament_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
      tournament.id = newId

      await this.saveTournament(tournament.state, tournament.name, tournament.description)

      testCenterLogger.userInteraction('tournament_imported', {
        tournamentId: newId,
        originalName: importData.name
      })

      return newId
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'import_tournament'
      })
      throw new Error('Failed to import tournament: ' + error.message)
    }
  }

  async clearAllData(): Promise<void> {
    await this.ensureInitialized()

    try {
      if (this.db && this.settings.storageType === 'indexeddb') {
        // Clear IndexedDB
        const transaction = this.db['db']!.transaction(['tournaments', 'settings'], 'readwrite')
        transaction.objectStore('tournaments').clear()
        transaction.objectStore('settings').clear()
        await new Promise((resolve, reject) => {
          transaction.oncomplete = resolve
          transaction.onerror = reject
        })
      }

      // Clear localStorage
      localStorage.removeItem(STORAGE_KEYS.SAVED_TOURNAMENTS)
      localStorage.removeItem(STORAGE_KEYS.CURRENT_TOURNAMENT)

      testCenterLogger.userInteraction('all_tournament_data_cleared', {
        storageType: this.settings.storageType
      })
    } catch (error) {
      testCenterLogger.criticalError(error, {
        operation: 'clear_all_data'
      })
      throw new Error('Failed to clear all data')
    }
  }

  // Auto-save current tournament state
  async autoSaveCurrentTournament(state: TournamentWorkflowState): Promise<void> {
    if (!this.settings.autoSave) return

    await this.ensureInitialized()

    const currentData = {
      state,
      savedAt: new Date().toISOString(),
      version: '1.0'
    }

    try {
      localStorage.setItem(STORAGE_KEYS.CURRENT_TOURNAMENT, JSON.stringify(currentData))

      testCenterLogger.userInteraction('current_tournament_autosaved', {
        currentStep: state.currentStep,
        tournamentName: state.tournamentSetup.name
      })
    } catch (error) {
      testCenterLogger.errorRecovery('localStorage', 'autosave_current_tournament', false, {
        error: error.message
      })
    }
  }

  // Load auto-saved current tournament state
  async loadAutoSavedTournament(): Promise<TournamentWorkflowState | null> {
    await this.ensureInitialized()

    try {
      const saved = localStorage.getItem(STORAGE_KEYS.CURRENT_TOURNAMENT)
      if (!saved) return null

      const data = JSON.parse(saved)

      // Check if data is recent (within last 24 hours)
      const savedAt = new Date(data.savedAt)
      const now = new Date()
      const hoursDiff = (now.getTime() - savedAt.getTime()) / (1000 * 60 * 60)

      if (hoursDiff > 24) {
        // Clear old auto-save
        localStorage.removeItem(STORAGE_KEYS.CURRENT_TOURNAMENT)
        return null
      }

      testCenterLogger.userInteraction('autosaved_tournament_loaded', {
        currentStep: data.state.currentStep,
        hoursOld: Math.round(hoursDiff * 10) / 10
      })

      return data.state
    } catch (error) {
      testCenterLogger.errorRecovery('localStorage', 'load_autosaved_tournament', false, {
        error: error.message
      })
      return null
    }
  }

  private async ensureInitialized(): Promise<void> {
    if (!this.initialized) {
      await this.init()
    }
  }

  private async saveToLocalStorage(tournament: SavedTournament): Promise<void> {
    const saved = localStorage.getItem(STORAGE_KEYS.SAVED_TOURNAMENTS)
    const tournaments: SavedTournament[] = saved ? JSON.parse(saved) : []

    // Remove existing tournament with same ID
    const filtered = tournaments.filter(t => t.id !== tournament.id)
    filtered.push(tournament)

    localStorage.setItem(STORAGE_KEYS.SAVED_TOURNAMENTS, JSON.stringify(filtered))
  }

  private async loadFromLocalStorage(id: string): Promise<SavedTournament | null> {
    const saved = localStorage.getItem(STORAGE_KEYS.SAVED_TOURNAMENTS)
    if (!saved) return null

    const tournaments: SavedTournament[] = JSON.parse(saved)
    return tournaments.find(t => t.id === id) || null
  }

  private async getAllFromLocalStorage(): Promise<SavedTournament[]> {
    const saved = localStorage.getItem(STORAGE_KEYS.SAVED_TOURNAMENTS)
    return saved ? JSON.parse(saved) : []
  }

  private async deleteFromLocalStorage(id: string): Promise<void> {
    const saved = localStorage.getItem(STORAGE_KEYS.SAVED_TOURNAMENTS)
    if (!saved) return

    const tournaments: SavedTournament[] = JSON.parse(saved)
    const filtered = tournaments.filter(t => t.id !== id)

    localStorage.setItem(STORAGE_KEYS.SAVED_TOURNAMENTS, JSON.stringify(filtered))
  }

  private async updateTournamentAccessTime(tournament: SavedTournament): Promise<void> {
    tournament.lastAccessedAt = new Date().toISOString()

    if (this.db && this.settings.storageType === 'indexeddb') {
      await this.db.saveTournament(tournament)
    } else {
      await this.saveToLocalStorage(tournament)
    }
  }

  private async cleanupOldTournaments(): Promise<void> {
    const tournaments = await this.getSavedTournaments()

    if (tournaments.length <= this.settings.maxSavedTournaments) {
      return
    }

    // Sort by last accessed time, keep most recent
    const sorted = tournaments.sort((a, b) =>
      new Date(b.lastAccessedAt).getTime() - new Date(a.lastAccessedAt).getTime()
    )

    const toDelete = sorted.slice(this.settings.maxSavedTournaments)

    for (const tournament of toDelete) {
      await this.deleteTournament(tournament.id)
    }

    testCenterLogger.userInteraction('old_tournaments_cleaned_up', {
      deletedCount: toDelete.length,
      remainingCount: this.settings.maxSavedTournaments
    })
  }
}

// Create singleton instance
export const tournamentPersistence = new TournamentPersistenceService()

// Export convenience functions
export const tournamentPersistenceApi = {
  init: tournamentPersistence.init.bind(tournamentPersistence),
  getSettings: tournamentPersistence.getSettings.bind(tournamentPersistence),
  updateSettings: tournamentPersistence.updateSettings.bind(tournamentPersistence),
  saveTournament: tournamentPersistence.saveTournament.bind(tournamentPersistence),
  loadTournament: tournamentPersistence.loadTournament.bind(tournamentPersistence),
  getSavedTournaments: tournamentPersistence.getSavedTournaments.bind(tournamentPersistence),
  deleteTournament: tournamentPersistence.deleteTournament.bind(tournamentPersistence),
  exportTournament: tournamentPersistence.exportTournament.bind(tournamentPersistence),
  importTournament: tournamentPersistence.importTournament.bind(tournamentPersistence),
  clearAllData: tournamentPersistence.clearAllData.bind(tournamentPersistence),
  autoSaveCurrentTournament: tournamentPersistence.autoSaveCurrentTournament.bind(tournamentPersistence),
  loadAutoSavedTournament: tournamentPersistence.loadAutoSavedTournament.bind(tournamentPersistence)
}

export default tournamentPersistence