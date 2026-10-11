/**
 * Comprehensive Testing and Validation for Export/Import Features
 * Provides automated tests and validation utilities
 */

import { exportImportService, TournamentExport, ScenarioExport, BulkExport, TemplateExport } from './exportImportService'
import { sharingUtils } from './sharingUtils'
import { migrationService } from './migrationService'
import { templateManager } from './tournamentTemplates'
import { testCenterLogger } from './testCenterLogger'

// Test result types
export interface TestResult {
  testName: string
  passed: boolean
  duration: number
  error?: string
  details?: any
}

export interface TestSuiteResult {
  suiteName: string
  totalTests: number
  passedTests: number
  failedTests: number
  duration: number
  results: TestResult[]
  summary: {
    successRate: number
    criticalFailures: number
    warnings: string[]
  }
}

// Validation result types
export interface ValidationResult {
  isValid: boolean
  errors: string[]
  warnings: string[]
  suggestions: string[]
  score: number // 0-100 validation score
}

// Test utilities
export class ExportImportTester {
  private logger = testCenterLogger

  /**
   * Run comprehensive export/import test suite
   */
  async runFullTestSuite(): Promise<TestSuiteResult> {
    const startTime = Date.now()
    const results: TestResult[] = []

    // Test data
    const mockTournament = {
      state: {
        currentStep: 'setup',
        tournamentSetup: {
          name: 'Test Tournament',
          format: 'single_elimination',
          maxPlayers: 8,
          entryFee: 50,
          prizePool: 400,
          tables: 2,
          raceTo: 7,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString()
        },
        bracketSetup: {
          shuffleSeeds: false,
          raceTo: 7,
          byePlayerIds: [],
          byeSeedPositions: []
        }
      }
    } as any

    const mockScenario = {
      name: 'Test Scenario',
      workflowState: mockTournament.state,
      testSequence: [
        { id: '1', name: 'Setup Tournament', type: 'setup', parameters: {}, expectedDuration: 5000 },
        { id: '2', name: 'Generate Bracket', type: 'generate_bracket', parameters: {}, expectedDuration: 10000 }
      ],
      expectedResults: {
        finalState: { currentStep: 'matches' },
        matchResults: [],
        leaderboardExpectations: { expectedOrder: [], positionRanges: [] },
        validationRules: []
      }
    }

    // Run individual tests
    results.push(await this.testTournamentExport(mockTournament))
    results.push(await this.testScenarioExport(mockScenario))
    results.push(await this.testBulkExport([mockTournament], [mockScenario]))
    results.push(await this.testTemplateExport())
    results.push(await this.testDataValidation())
    results.push(await this.testMigration())
    results.push(await this.testSharing(mockTournament))
    results.push(await this.testErrorHandling())

    // Calculate summary
    const passedTests = results.filter(r => r.passed).length
    const failedTests = results.filter(r => !r.passed).length
    const criticalFailures = results.filter(r => !r.passed && this.isCriticalTest(r.testName)).length
    const warnings = results.filter(r => !r.passed).map(r => `${r.testName}: ${r.error}`).slice(0, 10)

    const duration = Date.now() - startTime

    return {
      suiteName: 'Export/Import Full Test Suite',
      totalTests: results.length,
      passedTests,
      failedTests,
      duration,
      results,
      summary: {
        successRate: (passedTests / results.length) * 100,
        criticalFailures,
        warnings
      }
    }
  }

  /**
   * Test tournament export functionality
   */
  private async testTournamentExport(mockTournament: any): Promise<TestResult> {
    const startTime = Date.now()

    try {
      const exportData = await exportImportService.exportTournament(mockTournament, {
        includeFullData: true,
        generateChecksum: true
      })

      // Validate export structure
      const validation = this.validateTournamentExport(exportData)

      const duration = Date.now() - startTime
      return {
        testName: 'Tournament Export',
        passed: validation.isValid,
        duration,
        error: validation.errors.length > 0 ? validation.errors[0] : undefined,
        details: {
          exportSize: JSON.stringify(exportData).length,
          validationScore: validation.score,
          warnings: validation.warnings
        }
      }
    } catch (error) {
      const duration = Date.now() - startTime
      return {
        testName: 'Tournament Export',
        passed: false,
        duration,
        error: error.message,
        details: { error: error.message }
      }
    }
  }

  /**
   * Test scenario export functionality
   */
  private async testScenarioExport(mockScenario: any): Promise<TestResult> {
    const startTime = Date.now()

    try {
      const exportData = await exportImportService.exportScenario(
        mockScenario.name,
        mockScenario.workflowState,
        mockScenario.testSequence,
        mockScenario.expectedResults,
        { generateChecksum: true }
      )

      const validation = this.validateScenarioExport(exportData)

      const duration = Date.now() - startTime
      return {
        testName: 'Scenario Export',
        passed: validation.isValid,
        duration,
        error: validation.errors.length > 0 ? validation.errors[0] : undefined,
        details: {
          exportSize: JSON.stringify(exportData).length,
          validationScore: validation.score,
          stepCount: mockScenario.testSequence.length
        }
      }
    } catch (error) {
      const duration = Date.now() - startTime
      return {
        testName: 'Scenario Export',
        passed: false,
        duration,
        error: error.message,
        details: { error: error.message }
      }
    }
  }

  /**
   * Test bulk export functionality
   */
  private async testBulkExport(tournaments: any[], scenarios: any[]): Promise<TestResult> {
    const startTime = Date.now()

    try {
      // Create export data for bulk
      const tournamentExports = await Promise.all(
        tournaments.map(t => exportImportService.exportTournament(t))
      )
      const scenarioExports = await Promise.all(
        scenarios.map(s => exportImportService.exportScenario(
          s.name, s.workflowState, s.testSequence, s.expectedResults
        ))
      )

      const allExports = [...tournamentExports, ...scenarioExports]

      const bulkExport = await exportImportService.exportBulk(allExports, 'Test Bulk Export', {
        generateChecksum: true
      })

      const validation = this.validateBulkExport(bulkExport)

      const duration = Date.now() - startTime
      return {
        testName: 'Bulk Export',
        passed: validation.isValid,
        duration,
        error: validation.errors.length > 0 ? validation.errors[0] : undefined,
        details: {
          totalItems: allExports.length,
          exportSize: JSON.stringify(bulkExport).length,
          validationScore: validation.score
        }
      }
    } catch (error) {
      const duration = Date.now() - startTime
      return {
        testName: 'Bulk Export',
        passed: false,
        duration,
        error: error.message,
        details: { error: error.message }
      }
    }
  }

  /**
   * Test template export functionality
   */
  private async testTemplateExport(): Promise<TestResult> {
    const startTime = Date.now()

    try {
      const template = templateManager.getTemplateById('beginner-8-player')
      if (!template) {
        throw new Error('Template not found')
      }

      const exportData = await exportImportService.exportTemplate(
        template.name,
        template.baseWorkflowState,
        {
          isTemplate: true,
          category: template.category,
          difficulty: template.difficulty,
          estimatedDuration: template.estimatedDuration,
          recommendedPlayers: template.recommendedPlayers,
          customizationHints: template.customizationHints,
          presetConfigurations: template.presetConfigurations
        },
        { generateChecksum: true }
      )

      const validation = this.validateTemplateExport(exportData)

      const duration = Date.now() - startTime
      return {
        testName: 'Template Export',
        passed: validation.isValid,
        duration,
        error: validation.errors.length > 0 ? validation.errors[0] : undefined,
        details: {
          templateName: template.name,
          exportSize: JSON.stringify(exportData).length,
          validationScore: validation.score
        }
      }
    } catch (error) {
      const duration = Date.now() - startTime
      return {
        testName: 'Template Export',
        passed: false,
        duration,
        error: error.message,
        details: { error: error.message }
      }
    }
  }

  /**
   * Test data validation functionality
   */
  private async testDataValidation(): Promise<TestResult> {
    const startTime = Date.now()

    try {
      // Test invalid data
      const invalidData = { type: 'tournament', version: '1.0' } as any

      let validationPassed = false
      try {
        await exportImportService.importTournament(JSON.stringify(invalidData))
      } catch (error) {
        // Expected to fail
        validationPassed = true
      }

      // Test valid data structure
      const validData = {
        type: 'tournament',
        version: '1.0',
        exportedAt: new Date().toISOString(),
        metadata: { name: 'Test', format: 'single_elimination', maxPlayers: 8 },
        data: { workflowState: { currentStep: 'setup', tournamentSetup: {}, bracketSetup: {} } },
        checksum: ''
      }

      const importResult = await exportImportService.importTournament(JSON.stringify(validData), {
        validateOnly: true
      })

      const duration = Date.now() - startTime
      return {
        testName: 'Data Validation',
        passed: validationPassed && importResult.success,
        duration,
        error: !validationPassed ? 'Invalid data was not rejected' : undefined,
        details: {
          invalidDataRejected: validationPassed,
          validDataAccepted: importResult.success
        }
      }
    } catch (error) {
      const duration = Date.now() - startTime
      return {
        testName: 'Data Validation',
        passed: false,
        duration,
        error: error.message,
        details: { error: error.message }
      }
    }
  }

  /**
   * Test migration functionality
   */
  private async testMigration(): Promise<TestResult> {
    const startTime = Date.now()

    try {
      // Create old format data
      const oldFormatData = {
        type: 'tournament',
        version: '0.9',
        exportedAt: new Date().toISOString(),
        metadata: { name: 'Test', format: 'single_elimination', maxPlayers: 8 },
        data: { workflowState: { currentStep: 'setup', tournamentSetup: {}, bracketSetup: {} } },
        checksum: ''
      }

      // Test migration
      const needsMigration = migrationService.needsMigration(oldFormatData)
      const preview = migrationService.getMigrationPreview(oldFormatData)

      let migrationWorked = false
      if (needsMigration) {
        const migratedData = await migrationService.migrateToLatest(oldFormatData)
        migrationWorked = migratedData.version === '1.0'
      }

      const duration = Date.now() - startTime
      return {
        testName: 'Data Migration',
        passed: needsMigration && migrationWorked,
        duration,
        error: needsMigration && !migrationWorked ? 'Migration failed' : undefined,
        details: {
          needsMigration,
          migrationSteps: preview.migrationSteps.length,
          migratedSuccessfully: migrationWorked
        }
      }
    } catch (error) {
      const duration = Date.now() - startTime
      return {
        testName: 'Data Migration',
        passed: false,
        duration,
        error: error.message,
        details: { error: error.message }
      }
    }
  }

  /**
   * Test sharing functionality
   */
  private async testSharing(mockTournament: any): Promise<TestResult> {
    const startTime = Date.now()

    try {
      const exportData = await exportImportService.exportTournament(mockTournament)

      // Test clipboard (will fail in test environment, but tests the code path)
      let clipboardWorked = false
      try {
        await sharingUtils.copyToClipboard(JSON.stringify(exportData, null, 2))
        clipboardWorked = true
      } catch (error) {
        // Expected in test environment
        clipboardWorked = false
      }

      // Test compression/decompression
      const compressed = await sharingUtils.compress(JSON.stringify(exportData))
      const decompressed = await sharingUtils.decompress(compressed)
      const compressionWorked = JSON.stringify(exportData) === decompressed

      const duration = Date.now() - startTime
      return {
        testName: 'Sharing Features',
        passed: compressionWorked,
        duration,
        error: !compressionWorked ? 'Compression/decompression failed' : undefined,
        details: {
          clipboardTested: true,
          clipboardWorked,
          compressionWorked,
          originalSize: JSON.stringify(exportData).length,
          compressedSize: compressed.length
        }
      }
    } catch (error) {
      const duration = Date.now() - startTime
      return {
        testName: 'Sharing Features',
        passed: false,
        duration,
        error: error.message,
        details: { error: error.message }
      }
    }
  }

  /**
   * Test error handling
   */
  private async testErrorHandling(): Promise<TestResult> {
    const startTime = Date.now()

    try {
      // Test invalid JSON
      let invalidJsonHandled = false
      try {
        await exportImportService.importTournament('invalid json')
      } catch (error) {
        invalidJsonHandled = true
      }

      // Test missing required fields
      let missingFieldsHandled = false
      try {
        await exportImportService.importTournament(JSON.stringify({ type: 'tournament' }))
      } catch (error) {
        missingFieldsHandled = true
      }

      const duration = Date.now() - startTime
      return {
        testName: 'Error Handling',
        passed: invalidJsonHandled && missingFieldsHandled,
        duration,
        error: !invalidJsonHandled ? 'Invalid JSON not handled' :
               !missingFieldsHandled ? 'Missing fields not handled' : undefined,
        details: {
          invalidJsonHandled,
          missingFieldsHandled
        }
      }
    } catch (error) {
      const duration = Date.now() - startTime
      return {
        testName: 'Error Handling',
        passed: false,
        duration,
        error: error.message,
        details: { error: error.message }
      }
    }
  }

  // Validation methods
  private validateTournamentExport(data: TournamentExport): ValidationResult {
    const errors: string[] = []
    const warnings: string[] = []
    let score = 100

    if (data.type !== 'tournament') {
      errors.push('Invalid type')
      score -= 50
    }

    if (!data.metadata.name) {
      errors.push('Missing tournament name')
      score -= 20
    }

    if (!data.data.workflowState) {
      errors.push('Missing workflow state')
      score -= 50
    }

    if (!data.checksum) {
      warnings.push('Missing checksum')
      score -= 10
    }

    return {
      isValid: errors.length === 0,
      errors,
      warnings,
      suggestions: [],
      score: Math.max(0, score)
    }
  }

  private validateScenarioExport(data: ScenarioExport): ValidationResult {
    const errors: string[] = []
    const warnings: string[] = []
    let score = 100

    if (data.type !== 'scenario') {
      errors.push('Invalid type')
      score -= 50
    }

    if (!data.metadata.name) {
      errors.push('Missing scenario name')
      score -= 20
    }

    if (!data.data.testSequence || data.data.testSequence.length === 0) {
      errors.push('Missing or empty test sequence')
      score -= 30
    }

    if (!data.checksum) {
      warnings.push('Missing checksum')
      score -= 10
    }

    return {
      isValid: errors.length === 0,
      errors,
      warnings,
      suggestions: [],
      score: Math.max(0, score)
    }
  }

  private validateBulkExport(data: BulkExport): ValidationResult {
    const errors: string[] = []
    const warnings: string[] = []
    let score = 100

    if (data.type !== 'bulk') {
      errors.push('Invalid type')
      score -= 50
    }

    if (!data.metadata.itemCount || data.metadata.itemCount === 0) {
      errors.push('Invalid item count')
      score -= 30
    }

    const hasItems = Object.values(data.data).some(arr => arr && arr.length > 0)
    if (!hasItems) {
      errors.push('No items in bulk export')
      score -= 50
    }

    if (!data.checksum) {
      warnings.push('Missing checksum')
      score -= 10
    }

    return {
      isValid: errors.length === 0,
      errors,
      warnings,
      suggestions: [],
      score: Math.max(0, score)
    }
  }

  private validateTemplateExport(data: TemplateExport): ValidationResult {
    const errors: string[] = []
    const warnings: string[] = []
    let score = 100

    if (data.type !== 'template') {
      errors.push('Invalid type')
      score -= 50
    }

    if (!data.metadata.name) {
      errors.push('Missing template name')
      score -= 20
    }

    if (!data.data.templateSettings) {
      errors.push('Missing template settings')
      score -= 30
    }

    if (!data.checksum) {
      warnings.push('Missing checksum')
      score -= 10
    }

    return {
      isValid: errors.length === 0,
      errors,
      warnings,
      suggestions: [],
      score: Math.max(0, score)
    }
  }

  private isCriticalTest(testName: string): boolean {
    const criticalTests = [
      'Tournament Export',
      'Data Validation',
      'Error Handling'
    ]
    return criticalTests.includes(testName)
  }
}

// Export convenience functions
export const runExportImportTests = () => new ExportImportTester().runFullTestSuite()
export const validateExportData = (data: any) => new ExportImportTester().validateTournamentExport(data)

export default ExportImportTester