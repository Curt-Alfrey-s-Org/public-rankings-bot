/**
 * Comprehensive Export/Import Service for TestCenter
 * Handles tournament configurations, test scenarios, and bulk operations
 * with validation, error handling, and format compatibility
 */

import { testCenterLogger } from './testCenterLogger'
import { TournamentWorkflowState, SavedTournament, tournamentPersistence } from './tournamentPersistence'
import { testTournamentsApi } from '@/api/testTournaments'
import { migrationService } from './migrationService'

// Export/Import Format Versions
export const EXPORT_FORMAT_VERSIONS = {
  TOURNAMENT_CONFIG: '1.0',
  TEST_SCENARIO: '1.0',
  BULK_EXPORT: '1.0',
  TEMPLATE: '1.0'
} as const

// Export Types
export type ExportType = 'tournament' | 'scenario' | 'bulk' | 'template'

// Export Formats
export interface TournamentExport {
  type: 'tournament'
  version: string
  exportedAt: string
  metadata: {
    name: string
    description?: string
    tournamentType: string
    maxPlayers: number
    format: string
  }
  data: {
    workflowState: TournamentWorkflowState
    tournament?: any
    players?: any[]
    matches?: any[]
    leaderboard?: any[]
  }
  checksum: string
}

export interface ScenarioExport {
  type: 'scenario'
  version: string
  exportedAt: string
  metadata: {
    name: string
    description?: string
    scenarioType: 'setup' | 'bracket_generation' | 'match_simulation' | 'full_workflow'
    expectedDuration?: number
    testParameters: Record<string, any>
  }
  data: {
    workflowState: TournamentWorkflowState
    testSequence: ScenarioStep[]
    expectedResults: ScenarioExpectedResults
  }
  checksum: string
}

export interface BulkExport {
  type: 'bulk'
  version: string
  exportedAt: string
  metadata: {
    name: string
    description?: string
    itemCount: number
    items: BulkExportItem[]
  }
  data: {
    tournaments?: TournamentExport[]
    scenarios?: ScenarioExport[]
    templates?: TemplateExport[]
  }
  checksum: string
}

export interface TemplateExport {
  type: 'template'
  version: string
  exportedAt: string
  metadata: {
    name: string
    description?: string
    category: string
    tags: string[]
    recommendedFor: string[]
  }
  data: {
    workflowState: TournamentWorkflowState
    templateSettings: TemplateSettings
  }
  checksum: string
}

// Scenario Types
export interface ScenarioStep {
  id: string
  name: string
  type: 'setup' | 'generate_bracket' | 'simulate_match' | 'validate_results'
  parameters: Record<string, any>
  expectedDuration?: number
  dependencies?: string[]
}

export interface ScenarioExpectedResults {
  finalState: Partial<TournamentWorkflowState>
  matchResults?: ExpectedMatchResult[]
  leaderboardExpectations?: ExpectedLeaderboard
  validationRules: ValidationRule[]
}

export interface ExpectedMatchResult {
  matchId: string
  expectedWinner: string
  expectedScore: { operator: number; player2: number }
  tolerance?: number
}

export interface ExpectedLeaderboard {
  expectedOrder: string[]
  positionRanges: { position: number; minRating: number; maxRating: number }[]
}

export interface ValidationRule {
  type: 'state_check' | 'data_integrity' | 'performance'
  field: string
  operator: 'equals' | 'contains' | 'greater_than' | 'less_than' | 'range'
  expectedValue: any
  tolerance?: number
}

// Template Types
export interface TemplateSettings {
  isTemplate: true
  category: string
  difficulty: 'beginner' | 'intermediate' | 'advanced' | 'expert'
  estimatedDuration: number // minutes
  recommendedPlayers: number
  customizationHints: string[]
  presetConfigurations: Record<string, any>
}

// Bulk Export Types
export interface BulkExportItem {
  id: string
  name: string
  type: ExportType
  size: number
  exportedAt: string
}

// Import Results
export interface ImportResult {
  success: boolean
  importedId?: string
  warnings?: string[]
  errors?: string[]
  metadata: {
    type: ExportType
    version: string
    importedAt: string
    source: string
  }
}

export interface BulkImportResult {
  totalItems: number
  successfulImports: number
  failedImports: number
  results: ImportResult[]
  warnings: string[]
  errors: string[]
}

// Validation Errors
export interface ValidationError {
  field: string
  message: string
  severity: 'error' | 'warning' | 'info'
  suggestion?: string
}

// Export Options
export interface ExportOptions {
  includeFullData?: boolean
  compress?: boolean
  generateChecksum?: boolean
  addMetadata?: boolean
  format?: 'json' | 'compressed'
}

// Import Options
export interface ImportOptions {
  validateOnly?: boolean
  skipValidation?: boolean
  overwriteExisting?: boolean
  createBackup?: boolean
  migrationStrategy?: 'strict' | 'lenient' | 'auto'
}

// Service Class
class ExportImportService {
  private readonly logger = testCenterLogger

  // Core export methods
  async exportTournament(
    tournament: SavedTournament,
    options: ExportOptions = {}
  ): Promise<TournamentExport> {
    try {
      this.logger.userInteraction('export_tournament_started', {
        tournamentId: tournament.id,
        options
      })

      // Fetch current live tournament data if requested
      let liveData: {
        tournament?: any
        players?: any[]
        matches?: any[]
        leaderboard?: any[]
      } = {}

      if (options.includeFullData) {
        try {
          this.logger.dataFlow('fetching_live_tournament_data', 4, {
            tournamentId: tournament.id,
            includeFullData: true
          })

          const [tournamentData, playersData, matchesData, leaderboardData] = await Promise.all([
            testTournamentsApi.getCurrentTournament(),
            testTournamentsApi.getPlayers(),
            testTournamentsApi.getMatches(),
            testTournamentsApi.getLeaderboard()
          ])

          liveData = {
            tournament: tournamentData,
            players: playersData,
            matches: matchesData,
            leaderboard: leaderboardData
          }

          this.logger.dataFlow('live_tournament_data_fetched', Object.keys(liveData).length, {
            tournamentId: tournament.id,
            playersCount: playersData?.length || 0,
            matchesCount: matchesData?.length || 0
          })
        } catch (error) {
          this.logger.errorRecovery('fetch_live_data', 'fallback_to_saved_state', true, {
            tournamentId: tournament.id,
            error: error.message
          })

          // Fallback to saved state data
          liveData = {
            tournament: tournament.state.tournament,
            players: tournament.state.players,
            matches: tournament.state.matches,
            leaderboard: tournament.state.leaderboard
          }
        }
      }

      const exportData: TournamentExport = {
        type: 'tournament',
        version: EXPORT_FORMAT_VERSIONS.TOURNAMENT_CONFIG,
        exportedAt: new Date().toISOString(),
        metadata: {
          name: tournament.name,
          description: tournament.description,
          tournamentType: tournament.state.tournamentSetup.format,
          maxPlayers: tournament.state.tournamentSetup.maxPlayers,
          format: tournament.state.tournamentSetup.format
        },
        data: {
          workflowState: tournament.state,
          ...liveData
        },
        checksum: ''
      }

      // Generate checksum
      if (options.generateChecksum !== false) {
        exportData.checksum = await this.generateChecksum(exportData)
      }

      this.logger.userInteraction('export_tournament_completed', {
        tournamentId: tournament.id,
        exportSize: JSON.stringify(exportData).length,
        includedLiveData: options.includeFullData
      })

      return exportData
    } catch (error) {
      this.logger.criticalError(error, {
        operation: 'export_tournament',
        tournamentId: tournament.id
      })
      throw new Error(`Failed to export tournament: ${error.message}`)
    }
  }

  async exportScenario(
    name: string,
    workflowState: TournamentWorkflowState,
    testSequence: ScenarioStep[],
    expectedResults: ScenarioExpectedResults,
    options: ExportOptions = {}
  ): Promise<ScenarioExport> {
    try {
      this.logger.userInteraction('export_scenario_started', {
        scenarioName: name,
        stepCount: testSequence.length
      })

      // Calculate estimated duration from test sequence
      const estimatedDuration = testSequence.reduce((total, step) => {
        return total + (step.expectedDuration || 5000) // Default 5 seconds per step
      }, 0)

      const exportData: ScenarioExport = {
        type: 'scenario',
        version: EXPORT_FORMAT_VERSIONS.TEST_SCENARIO,
        exportedAt: new Date().toISOString(),
        metadata: {
          name,
          description: this.generateScenarioDescription(testSequence, workflowState),
          scenarioType: this.determineScenarioType(testSequence),
          expectedDuration: estimatedDuration,
          testParameters: this.extractTestParameters(testSequence)
        },
        data: {
          workflowState: { ...workflowState }, // Deep copy
          testSequence: [...testSequence], // Deep copy
          expectedResults: { ...expectedResults } // Deep copy
        },
        checksum: ''
      }

      // Enhance with additional metadata
      exportData.metadata = {
        ...exportData.metadata,
        ...this.generateScenarioMetadata(workflowState, testSequence, expectedResults)
      }

      // Generate checksum
      if (options.generateChecksum !== false) {
        exportData.checksum = await this.generateChecksum(exportData)
      }

      this.logger.userInteraction('export_scenario_completed', {
        scenarioName: name,
        scenarioType: exportData.metadata.scenarioType,
        estimatedDuration,
        exportSize: JSON.stringify(exportData).length
      })

      return exportData
    } catch (error) {
      this.logger.criticalError(error, {
        operation: 'export_scenario',
        scenarioName: name
      })
      throw new Error(`Failed to export scenario: ${error.message}`)
    }
  }

  async exportBulk(
    items: Array<TournamentExport | ScenarioExport | TemplateExport>,
    name: string,
    options: ExportOptions = {}
  ): Promise<BulkExport> {
    try {
      this.logger.userInteraction('export_bulk_started', {
        itemCount: items.length,
        exportName: name
      })

      // Validate items
      const validationErrors: string[] = []
      for (let i = 0; i < items.length; i++) {
        const item = items[i]
        if (!item.type || !item.metadata?.name) {
          validationErrors.push(`Item ${i + 1}: Missing required fields (type or metadata.name)`)
        }
        if (!['tournament', 'scenario', 'template'].includes(item.type)) {
          validationErrors.push(`Item ${i + 1}: Invalid type '${item.type}'`)
        }
      }

      if (validationErrors.length > 0) {
        throw new Error(`Bulk export validation failed:\n${validationErrors.join('\n')}`)
      }

      // Create bulk export with enhanced metadata
      const exportData: BulkExport = {
        type: 'bulk',
        version: EXPORT_FORMAT_VERSIONS.BULK_EXPORT,
        exportedAt: new Date().toISOString(),
        metadata: {
          name,
          description: `Bulk export containing ${items.length} items`,
          itemCount: items.length,
          items: items.map((item, index) => ({
            id: this.generateId(),
            name: item.metadata.name,
            type: item.type,
            size: JSON.stringify(item).length,
            exportedAt: item.exportedAt,
            index
          })),
          summary: this.generateBulkSummary(items)
        },
        data: {},
        checksum: ''
      }

      // Organize items by type with progress tracking
      let processedItems = 0
      for (const item of items) {
        const type = item.type + 's' as keyof BulkExport['data']
        if (!exportData.data[type]) {
          exportData.data[type] = []
        }
        (exportData.data[type] as any[]).push(item)
        processedItems++

        this.logger.dataFlow('bulk_export_progress', processedItems, {
          totalItems: items.length,
          currentItemType: item.type,
          currentItemName: item.metadata.name
        })
      }

      // Generate checksum
      if (options.generateChecksum !== false) {
        exportData.checksum = await this.generateChecksum(exportData)
      }

      this.logger.userInteraction('export_bulk_completed', {
        itemCount: items.length,
        exportSize: JSON.stringify(exportData).length,
        typesIncluded: Object.keys(exportData.data)
      })

      return exportData
    } catch (error) {
      this.logger.criticalError(error, {
        operation: 'export_bulk',
        itemCount: items.length
      })
      throw new Error(`Failed to export bulk data: ${error.message}`)
    }
  }

  async exportTemplate(
    name: string,
    workflowState: TournamentWorkflowState,
    templateSettings: TemplateSettings,
    options: ExportOptions = {}
  ): Promise<TemplateExport> {
    try {
      this.logger.userInteraction('export_template_started', {
        templateName: name,
        category: templateSettings.category,
        difficulty: templateSettings.difficulty
      })

      // Generate comprehensive metadata
      const metadata: TemplateExport['metadata'] = {
        name,
        description: this.generateTemplateDescription(templateSettings),
        category: templateSettings.category,
        tags: this.generateTemplateTags(templateSettings),
        recommendedFor: this.generateRecommendedFor(templateSettings)
      }

      // Add additional metadata from template settings
      if (templateSettings.estimatedDuration) {
        metadata.estimatedDuration = templateSettings.estimatedDuration
      }

      if (templateSettings.recommendedPlayers) {
        metadata.recommendedPlayers = templateSettings.recommendedPlayers
      }

      const exportData: TemplateExport = {
        type: 'template',
        version: EXPORT_FORMAT_VERSIONS.TEMPLATE,
        exportedAt: new Date().toISOString(),
        metadata,
        data: {
          workflowState: { ...workflowState }, // Deep copy
          templateSettings: { ...templateSettings } // Deep copy
        },
        checksum: ''
      }

      // Add usage statistics if available
      exportData.metadata.usageStats = {
        timesUsed: 0,
        averageRating: 0,
        lastUsed: null,
        createdBy: 'system'
      }

      // Generate checksum
      if (options.generateChecksum !== false) {
        exportData.checksum = await this.generateChecksum(exportData)
      }

      this.logger.userInteraction('export_template_completed', {
        templateName: name,
        category: templateSettings.category,
        exportSize: JSON.stringify(exportData).length
      })

      return exportData
    } catch (error) {
      this.logger.criticalError(error, {
        operation: 'export_template',
        templateName: name
      })
      throw new Error(`Failed to export template: ${error.message}`)
    }
  }

  // Core import methods
  async importTournament(
    jsonData: string,
    options: ImportOptions = {}
  ): Promise<ImportResult> {
    try {
      this.logger.userInteraction('import_tournament_started')

      const importData = JSON.parse(jsonData) as TournamentExport

      // Validate import data
      const validation = await this.validateTournamentImport(importData, options)
      if (validation.errors.length > 0 && !options.skipValidation) {
        return {
          success: false,
          errors: validation.errors.map(e => e.message),
          warnings: validation.warnings.map(w => w.message),
          metadata: {
            type: 'tournament',
            version: importData.version,
            importedAt: new Date().toISOString(),
            source: 'json'
          }
        }
      }

      if (options.validateOnly) {
        return {
          success: true,
          metadata: {
            type: 'tournament',
            version: importData.version,
            importedAt: new Date().toISOString(),
            source: 'json'
          }
        }
      }

      // Perform migration if needed
      const migratedData = await this.migrateTournamentData(importData, options)

      // Import the tournament
      const importedId = await this.performTournamentImport(migratedData, options)

      this.logger.userInteraction('import_tournament_completed', {
        importedId,
        originalName: importData.metadata.name
      })

      return {
        success: true,
        importedId,
        warnings: validation.warnings.map(w => w.message),
        metadata: {
          type: 'tournament',
          version: importData.version,
          importedAt: new Date().toISOString(),
          source: 'json'
        }
      }
    } catch (error) {
      this.logger.criticalError(error, {
        operation: 'import_tournament'
      })
      return {
        success: false,
        errors: [`Import failed: ${error.message}`],
        metadata: {
          type: 'tournament',
          version: 'unknown',
          importedAt: new Date().toISOString(),
          source: 'json'
        }
      }
    }
  }

  async importScenario(
    jsonData: string,
    options: ImportOptions = {}
  ): Promise<ImportResult> {
    try {
      this.logger.userInteraction('import_scenario_started')

      const importData = JSON.parse(jsonData) as ScenarioExport

      // Validate import data
      const validation = await this.validateScenarioImport(importData, options)
      if (validation.errors.length > 0 && !options.skipValidation) {
        return {
          success: false,
          errors: validation.errors.map(e => e.message),
          warnings: validation.warnings.map(w => w.message),
          metadata: {
            type: 'scenario',
            version: importData.version,
            importedAt: new Date().toISOString(),
            source: 'json'
          }
        }
      }

      if (options.validateOnly) {
        return {
          success: true,
          metadata: {
            type: 'scenario',
            version: importData.version,
            importedAt: new Date().toISOString(),
            source: 'json'
          }
        }
      }

      // Perform migration if needed
      const migratedData = await this.migrateScenarioData(importData, options)

      // Import the scenario
      const importedId = await this.performScenarioImport(migratedData, options)

      this.logger.userInteraction('import_scenario_completed', {
        importedId,
        scenarioName: importData.metadata.name
      })

      return {
        success: true,
        importedId,
        warnings: validation.warnings.map(w => w.message),
        metadata: {
          type: 'scenario',
          version: importData.version,
          importedAt: new Date().toISOString(),
          source: 'json'
        }
      }
    } catch (error) {
      this.logger.criticalError(error, {
        operation: 'import_scenario'
      })
      return {
        success: false,
        errors: [`Import failed: ${error.message}`],
        metadata: {
          type: 'scenario',
          version: 'unknown',
          importedAt: new Date().toISOString(),
          source: 'json'
        }
      }
    }
  }

  async importBulk(
    jsonData: string,
    options: ImportOptions = {}
  ): Promise<BulkImportResult> {
    try {
      this.logger.userInteraction('import_bulk_started')

      const importData = JSON.parse(jsonData) as BulkExport

      // Validate bulk import data
      const validation = await this.validateBulkImport(importData, options)
      if (validation.errors.length > 0 && !options.skipValidation) {
        return {
          totalItems: 0,
          successfulImports: 0,
          failedImports: 1,
          results: [{
            success: false,
            errors: validation.errors.map(e => e.message),
            warnings: validation.warnings.map(w => w.message),
            metadata: {
              type: 'bulk',
              version: importData.version,
              importedAt: new Date().toISOString(),
              source: 'bulk'
            }
          }],
          warnings: [],
          errors: validation.errors.map(e => e.message)
        }
      }

      const results: ImportResult[] = []
      let successfulImports = 0
      let failedImports = 0
      const warnings: string[] = []
      const errors: string[] = []

      // Collect all items to import
      const allItems = [
        ...(importData.data.tournaments || []),
        ...(importData.data.scenarios || []),
        ...(importData.data.templates || [])
      ]

      this.logger.dataFlow('bulk_import_items_collected', allItems.length, {
        tournaments: importData.data.tournaments?.length || 0,
        scenarios: importData.data.scenarios?.length || 0,
        templates: importData.data.templates?.length || 0
      })

      // Import each item with progress tracking
      for (let i = 0; i < allItems.length; i++) {
        const item = allItems[i]
        let result: ImportResult

        try {
          this.logger.dataFlow('bulk_import_progress', i + 1, {
            totalItems: allItems.length,
            currentItemType: item.type,
            currentItemName: item.metadata.name
          })

          switch (item.type) {
            case 'tournament':
              result = await this.importTournament(JSON.stringify(item), {
                ...options,
                validateOnly: false
              })
              break
            case 'scenario':
              result = await this.importScenario(JSON.stringify(item), {
                ...options,
                validateOnly: false
              })
              break
            case 'template':
              result = await this.importTemplate(JSON.stringify(item), {
                ...options,
                validateOnly: false
              })
              break
            default:
              result = {
                success: false,
                errors: [`Unknown item type: ${item.type}`],
                metadata: {
                  type: item.type as ExportType,
                  version: item.version,
                  importedAt: new Date().toISOString(),
                  source: 'bulk'
                }
              }
          }

          if (result.success) {
            successfulImports++
          } else {
            failedImports++
          }

          if (result.warnings) {
            warnings.push(...result.warnings)
          }
          if (result.errors) {
            errors.push(...result.errors)
          }

          results.push(result)
        } catch (error) {
          failedImports++
          const errorMsg = `Failed to import item ${item.metadata.name}: ${error.message}`
          errors.push(errorMsg)

          this.logger.errorRecovery('bulk_import_item_failed', 'continuing', false, {
            itemName: item.metadata.name,
            itemType: item.type,
            error: error.message
          })

          results.push({
            success: false,
            errors: [`Import failed: ${error.message}`],
            metadata: {
              type: item.type as ExportType,
              version: item.version,
              importedAt: new Date().toISOString(),
              source: 'bulk'
            }
          })
        }
      }

      this.logger.userInteraction('import_bulk_completed', {
        totalItems: allItems.length,
        successfulImports,
        failedImports,
        successRate: allItems.length > 0 ? (successfulImports / allItems.length) * 100 : 0
      })

      return {
        totalItems: allItems.length,
        successfulImports,
        failedImports,
        results,
        warnings,
        errors
      }
    } catch (error) {
      this.logger.criticalError(error, {
        operation: 'import_bulk'
      })
      throw new Error(`Bulk import failed: ${error.message}`)
    }
  }

  async importTemplate(
    jsonData: string,
    options: ImportOptions = {}
  ): Promise<ImportResult> {
    try {
      this.logger.userInteraction('import_template_started')

      const importData = JSON.parse(jsonData) as TemplateExport

      // Validate import data
      const validation = await this.validateTemplateImport(importData, options)
      if (validation.errors.length > 0 && !options.skipValidation) {
        return {
          success: false,
          errors: validation.errors.map(e => e.message),
          warnings: validation.warnings.map(w => w.message),
          metadata: {
            type: 'template',
            version: importData.version,
            importedAt: new Date().toISOString(),
            source: 'json'
          }
        }
      }

      if (options.validateOnly) {
        return {
          success: true,
          metadata: {
            type: 'template',
            version: importData.version,
            importedAt: new Date().toISOString(),
            source: 'json'
          }
        }
      }

      // Perform migration if needed
      const migratedData = await this.migrateTemplateData(importData, options)

      // Import the template
      const importedId = await this.performTemplateImport(migratedData, options)

      this.logger.userInteraction('import_template_completed', {
        importedId,
        templateName: importData.metadata.name
      })

      return {
        success: true,
        importedId,
        warnings: validation.warnings.map(w => w.message),
        metadata: {
          type: 'template',
          version: importData.version,
          importedAt: new Date().toISOString(),
          source: 'json'
        }
      }
    } catch (error) {
      this.logger.criticalError(error, {
        operation: 'import_template'
      })
      return {
        success: false,
        errors: [`Import failed: ${error.message}`],
        metadata: {
          type: 'template',
          version: 'unknown',
          importedAt: new Date().toISOString(),
          source: 'json'
        }
      }
    }
  }

  // Validation methods
  private async validateTournamentImport(
    data: TournamentExport,
    options: ImportOptions
  ): Promise<{ errors: ValidationError[]; warnings: ValidationError[] }> {
    const errors: ValidationError[] = []
    const warnings: ValidationError[] = []

    // Basic structure validation
    if (data.type !== 'tournament') {
      errors.push({
        field: 'type',
        message: 'Invalid export type for tournament import',
        severity: 'error',
        suggestion: 'Ensure you are importing a tournament export file'
      })
    }

    if (!data.metadata.name) {
      errors.push({
        field: 'metadata.name',
        message: 'Tournament name is required',
        severity: 'error'
      })
    }

    if (!data.data.workflowState) {
      errors.push({
        field: 'data.workflowState',
        message: 'Tournament workflow state is required',
        severity: 'error'
      })
    }

    // Version compatibility check
    if (data.version !== EXPORT_FORMAT_VERSIONS.TOURNAMENT_CONFIG) {
      if (options.migrationStrategy === 'strict') {
        errors.push({
          field: 'version',
          message: `Unsupported version ${data.version}. Expected ${EXPORT_FORMAT_VERSIONS.TOURNAMENT_CONFIG}`,
          severity: 'error'
        })
      } else {
        warnings.push({
          field: 'version',
          message: `Version ${data.version} may require migration`,
          severity: 'warning'
        })
      }
    }

    // Checksum validation
    if (data.checksum && !await this.verifyChecksum(data)) {
      errors.push({
        field: 'checksum',
        message: 'Export file checksum verification failed',
        severity: 'error',
        suggestion: 'The file may be corrupted or tampered with'
      })
    }

    return { errors, warnings }
  }

  private async validateScenarioImport(
    data: ScenarioExport,
    options: ImportOptions
  ): Promise<{ errors: ValidationError[]; warnings: ValidationError[] }> {
    const errors: ValidationError[] = []
    const warnings: ValidationError[] = []

    // Basic structure validation
    if (data.type !== 'scenario') {
      errors.push({
        field: 'type',
        message: 'Invalid export type for scenario import',
        severity: 'error'
      })
    }

    if (!data.metadata.name) {
      errors.push({
        field: 'metadata.name',
        message: 'Scenario name is required',
        severity: 'error'
      })
    }

    if (!data.data.testSequence || data.data.testSequence.length === 0) {
      errors.push({
        field: 'data.testSequence',
        message: 'Test sequence is required and cannot be empty',
        severity: 'error'
      })
    }

    // Version compatibility check
    if (data.version !== EXPORT_FORMAT_VERSIONS.TEST_SCENARIO) {
      warnings.push({
        field: 'version',
        message: `Version ${data.version} may require migration`,
        severity: 'warning'
      })
    }

    // Checksum validation
    if (data.checksum && !await this.verifyChecksum(data)) {
      errors.push({
        field: 'checksum',
        message: 'Export file checksum verification failed',
        severity: 'error'
      })
    }

    return { errors, warnings }
  }

  private async validateTemplateImport(
    data: TemplateExport,
    options: ImportOptions
  ): Promise<{ errors: ValidationError[]; warnings: ValidationError[] }> {
    const errors: ValidationError[] = []
    const warnings: ValidationError[] = []

    // Basic structure validation
    if (data.type !== 'template') {
      errors.push({
        field: 'type',
        message: 'Invalid export type for template import',
        severity: 'error'
      })
    }

    if (!data.metadata.name) {
      errors.push({
        field: 'metadata.name',
        message: 'Template name is required',
        severity: 'error'
      })
    }

    if (!data.data.templateSettings) {
      errors.push({
        field: 'data.templateSettings',
        message: 'Template settings are are required',
        severity: 'error'
      })
    }

    return { errors, warnings }
  }

  private async validateBulkImport(
    data: BulkExport,
    options: ImportOptions
  ): Promise<{ errors: ValidationError[]; warnings: ValidationError[] }> {
    const errors: ValidationError[] = []
    const warnings: ValidationError[] = []

    // Basic structure validation
    if (data.type !== 'bulk') {
      errors.push({
        field: 'type',
        message: 'Invalid export type for bulk import',
        severity: 'error'
      })
    }

    if (!data.metadata.itemCount || data.metadata.itemCount <= 0) {
      errors.push({
        field: 'metadata.itemCount',
        message: 'Bulk export must contain at least one item',
        severity: 'error'
      })
    }

    // Check if any data is present
    const hasTournaments = data.data.tournaments && data.data.tournaments.length > 0
    const hasScenarios = data.data.scenarios && data.data.scenarios.length > 0
    const hasTemplates = data.data.templates && data.data.templates.length > 0

    if (!hasTournaments && !hasScenarios && !hasTemplates) {
      errors.push({
        field: 'data',
        message: 'Bulk export contains no importable items',
        severity: 'error'
      })
    }

    // Validate item count matches
    const actualCount = (data.data.tournaments?.length || 0) +
                       (data.data.scenarios?.length || 0) +
                       (data.data.templates?.length || 0)

    if (actualCount !== data.metadata.itemCount) {
      warnings.push({
        field: 'metadata.itemCount',
        message: `Item count mismatch: metadata says ${data.metadata.itemCount}, found ${actualCount}`,
        severity: 'warning'
      })
    }

    // Check for very large imports
    if (actualCount > 50) {
      warnings.push({
        field: 'metadata.itemCount',
        message: `Large bulk import (${actualCount} items) may take significant time`,
        severity: 'warning',
        suggestion: 'Consider importing in smaller batches'
      })
    }

    // Version compatibility check
    if (data.version !== EXPORT_FORMAT_VERSIONS.BULK_EXPORT) {
      if (options.migrationStrategy === 'strict') {
        errors.push({
          field: 'version',
          message: `Unsupported bulk export version ${data.version}`,
          severity: 'error'
        })
      } else {
        warnings.push({
          field: 'version',
          message: `Bulk export version ${data.version} may require migration`,
          severity: 'warning'
        })
      }
    }

    return { errors, warnings }
  }

  // Migration methods
  private async migrateTournamentData(
    data: TournamentExport,
    options: ImportOptions
  ): Promise<TournamentExport> {
    try {
      // Check if migration is needed
      if (!migrationService.needsMigration(data)) {
        return data
      }

      // Get migration preview
      const preview = migrationService.getMigrationPreview(data)

      this.logger.userInteraction('migration_preview', {
        type: data.type,
        currentVersion: preview.currentVersion,
        targetVersion: preview.targetVersion,
        steps: preview.migrationSteps.length
      })

      // Apply migration
      const migrationOptions = {
        strict: options.migrationStrategy === 'strict',
        preserveOriginal: false,
        logMigrations: true
      }

      const migratedData = await migrationService.migrateToLatest(data, migrationOptions)

      this.logger.userInteraction('data_migrated', {
        type: data.type,
        fromVersion: preview.currentVersion,
        toVersion: preview.targetVersion,
        success: true
      })

      return migratedData
    } catch (error) {
      this.logger.errorRecovery('tournament_migration_failed', 'fallback_to_original', true, {
        error: error.message,
        version: data.version
      })

      if (options.migrationStrategy === 'strict') {
        throw error
      }

      return data // Return original data if migration fails
    }
  }

  private async migrateScenarioData(
    data: ScenarioExport,
    options: ImportOptions
  ): Promise<ScenarioExport> {
    try {
      if (!migrationService.needsMigration(data)) {
        return data
      }

      const preview = migrationService.getMigrationPreview(data)

      this.logger.userInteraction('migration_preview', {
        type: data.type,
        currentVersion: preview.currentVersion,
        targetVersion: preview.targetVersion,
        steps: preview.migrationSteps.length
      })

      const migrationOptions = {
        strict: options.migrationStrategy === 'strict',
        preserveOriginal: false,
        logMigrations: true
      }

      const migratedData = await migrationService.migrateToLatest(data, migrationOptions)

      this.logger.userInteraction('data_migrated', {
        type: data.type,
        fromVersion: preview.currentVersion,
        toVersion: preview.targetVersion,
        success: true
      })

      return migratedData
    } catch (error) {
      this.logger.errorRecovery('scenario_migration_failed', 'fallback_to_original', true, {
        error: error.message,
        version: data.version
      })

      if (options.migrationStrategy === 'strict') {
        throw error
      }

      return data
    }
  }

  private async migrateTemplateData(
    data: TemplateExport,
    options: ImportOptions
  ): Promise<TemplateExport> {
    try {
      if (!migrationService.needsMigration(data)) {
        return data
      }

      const preview = migrationService.getMigrationPreview(data)

      this.logger.userInteraction('migration_preview', {
        type: data.type,
        currentVersion: preview.currentVersion,
        targetVersion: preview.targetVersion,
        steps: preview.migrationSteps.length
      })

      const migrationOptions = {
        strict: options.migrationStrategy === 'strict',
        preserveOriginal: false,
        logMigrations: true
      }

      const migratedData = await migrationService.migrateToLatest(data, migrationOptions)

      this.logger.userInteraction('data_migrated', {
        type: data.type,
        fromVersion: preview.currentVersion,
        toVersion: preview.targetVersion,
        success: true
      })

      return migratedData
    } catch (error) {
      this.logger.errorRecovery('template_migration_failed', 'fallback_to_original', true, {
        error: error.message,
        version: data.version
      })

      if (options.migrationStrategy === 'strict') {
        throw error
      }

      return data
    }
  }

  // Import execution methods
  private async performTournamentImport(
    data: TournamentExport,
    options: ImportOptions
  ): Promise<string> {
    // Create a new tournament state from the imported data
    const importedTournament: SavedTournament = {
      id: `imported_tournament_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      name: `${data.metadata.name} (Imported)`,
      description: data.metadata.description || `Imported on ${new Date().toLocaleDateString()}`,
      state: data.data.workflowState,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      lastAccessedAt: new Date().toISOString(),
      version: data.version
    }

    // Save through the persistence service
    const savedId = await tournamentPersistence.saveTournament(
      importedTournament.state,
      importedTournament.name,
      importedTournament.description
    )

    // If we have live data, we might want to recreate the tournament in the database
    if (data.data.tournament && options.overwriteExisting) {
      try {
        // Attempt to recreate the tournament in the test database
        await testTournamentsApi.setupTournament({
          name: data.data.tournament.name,
          format: data.data.tournament.format,
          max_players: data.data.tournament.max_players,
          entry_fee: data.data.tournament.entry_fee,
          tables: data.data.tournament.tables,
          race_to: data.data.tournament.race_to
        })

        this.logger.dataFlow('tournament_recreated_in_db', 1, {
          importedId: savedId,
          tournamentName: data.metadata.name
        })
      } catch (error) {
        this.logger.errorRecovery('recreate_tournament_db', 'persistence_only', true, {
          importedId: savedId,
          error: error.message
        })
        // Continue with just persistence import
      }
    }

    return savedId
  }

  private async performScenarioImport(
    data: ScenarioExport,
    options: ImportOptions
  ): Promise<string> {
    // Import scenario
    const importedId = `imported_scenario_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    // TODO: Implement actual scenario import logic

    return importedId
  }

  private async performTemplateImport(
    data: TemplateExport,
    options: ImportOptions
  ): Promise<string> {
    // Import template
    const importedId = `imported_template_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    // TODO: Implement actual template import logic

    return importedId
  }

  // Utility methods
  private async generateChecksum(data: any): Promise<string> {
    const dataString = JSON.stringify(data, Object.keys(data).sort())
    const encoder = new TextEncoder()
    const dataBuffer = encoder.encode(dataString)
    const hashBuffer = await crypto.subtle.digest('SHA-256', dataBuffer)
    const hashArray = Array.from(new Uint8Array(hashBuffer))
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
  }

  private async verifyChecksum(data: any): Promise<boolean> {
    if (!data.checksum) return true

    const calculatedChecksum = await this.generateChecksum({ ...data, checksum: undefined })
    return calculatedChecksum === data.checksum
  }

  private determineScenarioType(steps: ScenarioStep[]): ScenarioExport['metadata']['scenarioType'] {
    const stepTypes = steps.map(s => s.type)
    if (stepTypes.includes('setup') && stepTypes.includes('generate_bracket') && stepTypes.includes('simulate_match')) {
      return 'full_workflow'
    } else if (stepTypes.includes('generate_bracket')) {
      return 'bracket_generation'
    } else if (stepTypes.includes('simulate_match')) {
      return 'match_simulation'
    } else {
      return 'setup'
    }
  }

  private extractTestParameters(steps: ScenarioStep[]): Record<string, any> {
    const parameters: Record<string, any> = {}

    for (const step of steps) {
      Object.assign(parameters, step.parameters)
    }

    return parameters
  }

  private generateScenarioDescription(
    testSequence: ScenarioStep[],
    workflowState: TournamentWorkflowState
  ): string {
    const stepTypes = testSequence.map(s => s.type)
    const uniqueSteps = [...new Set(stepTypes)]

    let description = `Test scenario with ${testSequence.length} steps: `

    const stepDescriptions = uniqueSteps.map(type => {
      switch (type) {
        case 'setup':
          return 'tournament setup'
        case 'generate_bracket':
          return 'bracket generation'
        case 'simulate_match':
          return `match simulation (${testSequence.filter(s => s.type === 'simulate_match').length} matches)`
        case 'validate_results':
          return 'result validation'
        default:
          return type
      }
    })

    description += stepDescriptions.join(', ')

    if (workflowState.tournamentSetup) {
      description += `. Tournament: ${workflowState.tournamentSetup.name} (${workflowState.tournamentSetup.format} format, ${workflowState.tournamentSetup.maxPlayers} players)`
    }

    return description
  }

  private generateScenarioMetadata(
    workflowState: TournamentWorkflowState,
    testSequence: ScenarioStep[],
    expectedResults: ScenarioExpectedResults
  ): Partial<ScenarioExport['metadata']> {
    const metadata: Partial<ScenarioExport['metadata']> = {}

    // Add tournament context
    if (workflowState.tournamentSetup) {
      metadata.tournamentConfig = {
        format: workflowState.tournamentSetup.format,
        maxPlayers: workflowState.tournamentSetup.maxPlayers,
        entryFee: workflowState.tournamentSetup.entryFee,
        tables: workflowState.tournamentSetup.tables,
        raceTo: workflowState.tournamentSetup.raceTo
      }
    }

    // Add test metrics
    metadata.testMetrics = {
      totalSteps: testSequence.length,
      stepTypes: testSequence.reduce((acc, step) => {
        acc[step.type] = (acc[step.type] || 0) + 1
        return acc
      }, {} as Record<string, number>),
      hasValidations: expectedResults.validationRules.length > 0,
      validationCount: expectedResults.validationRules.length
    }

    // Add complexity score (simple heuristic)
    const complexityScore = this.calculateScenarioComplexity(testSequence, expectedResults)
    metadata.complexity = complexityScore < 0.3 ? 'simple' : complexityScore < 0.7 ? 'medium' : 'complex'

    return metadata
  }

  private calculateScenarioComplexity(
    testSequence: ScenarioStep[],
    expectedResults: ScenarioExpectedResults
  ): number {
    let complexity = 0

    // Base complexity from step count
    complexity += Math.min(testSequence.length / 10, 0.3)

    // Complexity from step types
    const stepTypes = new Set(testSequence.map(s => s.type))
    complexity += (stepTypes.size / 4) * 0.2

    // Complexity from validation rules
    complexity += Math.min(expectedResults.validationRules.length / 5, 0.2)

    // Complexity from expected results
    if (expectedResults.matchResults) {
      complexity += Math.min(expectedResults.matchResults.length / 10, 0.2)
    }

    if (expectedResults.expectedLeaderboard) {
      complexity += 0.1
    }

    return Math.min(complexity, 1.0)
  }

  private generateBulkSummary(items: Array<TournamentExport | ScenarioExport | TemplateExport>): BulkExport['metadata']['summary'] {
    const summary = {
      totalSize: 0,
      typeBreakdown: {} as Record<string, number>,
      oldestItem: '',
      newestItem: '',
      averageComplexity: 0,
      tags: [] as string[]
    }

    let totalComplexity = 0
    let complexityCount = 0
    const allTags = new Set<string>()
    let oldestDate = new Date().toISOString()
    let newestDate = '1970-01-01T00:00:00.000Z'

    for (const item of items) {
      // Calculate total size
      summary.totalSize += JSON.stringify(item).length

      // Count types
      summary.typeBreakdown[item.type] = (summary.typeBreakdown[item.type] || 0) + 1

      // Track dates
      if (item.exportedAt < oldestDate) oldestDate = item.exportedAt
      if (item.exportedAt > newestDate) newestDate = item.exportedAt

      // Collect tags
      if ('tags' in item.metadata && item.metadata.tags) {
        item.metadata.tags.forEach(tag => allTags.add(tag))
      }

      // Calculate complexity for scenarios
      if (item.type === 'scenario') {
        const scenarioItem = item as ScenarioExport
        const complexity = this.calculateScenarioComplexity(
          scenarioItem.data.testSequence,
          scenarioItem.data.expectedResults
        )
        totalComplexity += complexity
        complexityCount++
      }
    }

    summary.oldestItem = oldestDate
    summary.newestItem = newestDate
    summary.averageComplexity = complexityCount > 0 ? totalComplexity / complexityCount : 0
    summary.tags = Array.from(allTags)

    return summary
  }

  private generateTemplateDescription(templateSettings: TemplateSettings): string {
    const { category, difficulty, estimatedDuration, recommendedPlayers } = templateSettings

    let description = `A ${difficulty} ${category} tournament template `

    if (recommendedPlayers) {
      description += `designed for ${recommendedPlayers} players `
    }

    if (estimatedDuration) {
      const hours = Math.floor(estimatedDuration / 60)
      const minutes = estimatedDuration % 60
      const durationStr = hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`
      description += `with an estimated duration of ${durationStr}.`
    }

    description += ' Includes optimized settings for a successful tournament experience.'

    return description
  }

  private generateTemplateTags(templateSettings: TemplateSettings): string[] {
    const tags = []

    // Add category and difficulty
    tags.push(templateSettings.category, templateSettings.difficulty)

    // Add player count range
    if (templateSettings.recommendedPlayers) {
      if (templateSettings.recommendedPlayers <= 16) tags.push('small')
      else if (templateSettings.recommendedPlayers <= 32) tags.push('medium')
      else if (templateSettings.recommendedPlayers <= 64) tags.push('large')
      else tags.push('xl')
    }

    // Add duration tags
    if (templateSettings.estimatedDuration) {
      if (templateSettings.estimatedDuration <= 120) tags.push('quick')
      else if (templateSettings.estimatedDuration <= 240) tags.push('standard')
      else if (templateSettings.estimatedDuration <= 480) tags.push('long')
      else tags.push('extended')
    }

    // Add customization hints as tags
    if (templateSettings.customizationHints) {
      templateSettings.customizationHints.slice(0, 3).forEach(hint => {
        const words = hint.toLowerCase().split(' ')
        words.forEach(word => {
          if (word.length > 3 && !tags.includes(word)) {
            tags.push(word)
          }
        })
      })
    }

    return [...new Set(tags)] // Remove duplicates
  }

  private generateRecommendedFor(templateSettings: TemplateSettings): string[] {
    const recommendations = []

    // Difficulty-based recommendations
    switch (templateSettings.difficulty) {
      case 'beginner':
        recommendations.push('New tournament directors', 'Small venues', 'Learning environments')
        break
      case 'intermediate':
        recommendations.push('Experienced directors', 'Medium venues', 'Regular tournaments')
        break
      case 'advanced':
        recommendations.push('Professional directors', 'Large venues', 'Competitive events')
        break
      case 'expert':
        recommendations.push('Tournament professionals', 'Major events', 'Championships')
        break
    }

    // Category-based recommendations
    switch (templateSettings.category) {
      case 'training':
        recommendations.push('Skill development programs', 'Educational events')
        break
      case 'special_event':
        recommendations.push('Holiday tournaments', 'Company events', 'Celebrations')
        break
      case 'professional':
        recommendations.push('Professional competitions', 'Ranked tournaments')
        break
    }

    return recommendations
  }

  private generateId(): string {
    return `export_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  }
}

// Export singleton instance
export const exportImportService = new ExportImportService()

// Export convenience functions
export const exportService = {
  exportTournament: exportImportService.exportTournament.bind(exportImportService),
  exportScenario: exportImportService.exportScenario.bind(exportImportService),
  exportBulk: exportImportService.exportBulk.bind(exportImportService),
  exportTemplate: exportImportService.exportTemplate.bind(exportImportService),
  importTournament: exportImportService.importTournament.bind(exportImportService),
  importScenario: exportImportService.importScenario.bind(exportImportService),
  importBulk: exportImportService.importBulk.bind(exportImportService),
  importTemplate: exportImportService.importTemplate.bind(exportImportService)
}

export default exportImportService