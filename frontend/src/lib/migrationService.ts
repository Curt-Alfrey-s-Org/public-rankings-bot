/**
 * Migration Service for Export/Import Formats
 * Handles upgrading export formats between versions
 */

import { testCenterLogger } from './testCenterLogger'
import {
  TournamentExport,
  ScenarioExport,
  BulkExport,
  TemplateExport,
  EXPORT_FORMAT_VERSIONS
} from './exportImportService'

// Migration function type
type MigrationFunction<T = any> = (data: T, options?: MigrationOptions) => T

interface MigrationOptions {
  strict?: boolean
  preserveOriginal?: boolean
  logMigrations?: boolean
}

// Migration registry
interface MigrationRegistry {
  [fromVersion: string]: {
    [toVersion: string]: MigrationFunction
  }
}

// Tournament migrations
const TOURNAMENT_MIGRATIONS: MigrationRegistry = {
  '0.9': {
    '1.0': (data: TournamentExport) => {
      // Migrate from 0.9 to 1.0
      const migrated = { ...data }

      // Add checksum if missing
      if (!migrated.checksum) {
        migrated.checksum = ''
      }

      // Ensure metadata structure
      if (!migrated.metadata.tournamentType) {
        migrated.metadata.tournamentType = migrated.metadata.format || 'single_elimination'
      }

      // Update version
      migrated.version = '1.0'

      testCenterLogger.userInteraction('data_migration_applied', {
        type: 'tournament',
        fromVersion: '0.9',
        toVersion: '1.0'
      })

      return migrated
    }
  },
  '1.0': {
    // Current version - no migrations needed
  }
}

// Scenario migrations
const SCENARIO_MIGRATIONS: MigrationRegistry = {
  '0.9': {
    '1.0': (data: ScenarioExport) => {
      const migrated = { ...data }

      // Add checksum if missing
      if (!migrated.checksum) {
        migrated.checksum = ''
      }

      // Add scenario type if missing
      if (!migrated.metadata.scenarioType) {
        migrated.metadata.scenarioType = 'full_workflow'
      }

      // Add expected duration if missing
      if (!migrated.metadata.expectedDuration) {
        migrated.metadata.expectedDuration = migrated.data.testSequence.length * 30000 // 30 seconds per step
      }

      // Update version
      migrated.version = '1.0'

      testCenterLogger.userInteraction('data_migration_applied', {
        type: 'scenario',
        fromVersion: '0.9',
        toVersion: '1.0'
      })

      return migrated
    }
  },
  '1.0': {
    // Current version - no migrations needed
  }
}

// Bulk export migrations
const BULK_MIGRATIONS: MigrationRegistry = {
  '0.9': {
    '1.0': (data: BulkExport) => {
      const migrated = { ...data }

      // Add checksum if missing
      if (!migrated.checksum) {
        migrated.checksum = ''
      }

      // Add summary if missing
      if (!migrated.metadata.summary) {
        migrated.metadata.summary = {
          totalSize: 0,
          typeBreakdown: {},
          oldestItem: migrated.metadata.items?.[0]?.exportedAt || migrated.exportedAt,
          newestItem: migrated.metadata.items?.[migrated.metadata.items.length - 1]?.exportedAt || migrated.exportedAt,
          averageComplexity: 0.5
        }
      }

      // Update version
      migrated.version = '1.0'

      testCenterLogger.userInteraction('data_migration_applied', {
        type: 'bulk',
        fromVersion: '0.9',
        toVersion: '1.0'
      })

      return migrated
    }
  },
  '1.0': {
    // Current version - no migrations needed
  }
}

// Template migrations
const TEMPLATE_MIGRATIONS: MigrationRegistry = {
  '0.9': {
    '1.0': (data: TemplateExport) => {
      const migrated = { ...data }

      // Add checksum if missing
      if (!migrated.checksum) {
        migrated.checksum = ''
      }

      // Ensure template settings structure
      if (!migrated.data.templateSettings) {
        migrated.data.templateSettings = {
          isTemplate: true,
          category: migrated.metadata.category || 'custom',
          difficulty: 'intermediate',
          estimatedDuration: migrated.metadata.estimatedDuration || 180,
          recommendedPlayers: migrated.metadata.recommendedPlayers || 16,
          customizationHints: migrated.metadata.tags || [],
          presetConfigurations: {}
        }
      }

      // Add usage stats if missing
      if (!migrated.metadata.usageStats) {
        migrated.metadata.usageStats = {
          timesUsed: 0,
          averageRating: 0,
          lastUsed: null,
          createdBy: 'system'
        }
      }

      // Update version
      migrated.version = '1.0'

      testCenterLogger.userInteraction('data_migration_applied', {
        type: 'template',
        fromVersion: '0.9',
        toVersion: '1.0'
      })

      return migrated
    }
  },
  '1.0': {
    // Current version - no migrations needed
  }
}

class MigrationService {
  private logger = testCenterLogger

  /**
   * Migrate data to the latest version
   */
  async migrateToLatest<T extends { version: string; type: string }>(
    data: T,
    options: MigrationOptions = {}
  ): Promise<T> {
    const { strict = false, preserveOriginal = false, logMigrations = true } = options

    try {
      const currentVersion = data.version
      const targetVersion = this.getLatestVersion(data.type)

      if (currentVersion === targetVersion) {
        return data // Already at latest version
      }

      if (logMigrations) {
        this.logger.userInteraction('migration_started', {
          type: data.type,
          fromVersion: currentVersion,
          toVersion: targetVersion
        })
      }

      const originalData = preserveOriginal ? JSON.parse(JSON.stringify(data)) : null
      let migratedData = data

      // Apply migrations step by step
      const migrationPath = this.findMigrationPath(data.type, currentVersion, targetVersion)

      for (const step of migrationPath) {
        const migrationFunc = this.getMigrationFunction(data.type, step.fromVersion, step.toVersion)
        if (migrationFunc) {
          migratedData = migrationFunc(migratedData, options) as T

          if (logMigrations) {
            this.logger.dataFlow('migration_step_completed', 1, {
              type: data.type,
              fromVersion: step.fromVersion,
              toVersion: step.toVersion
            })
          }
        } else if (strict) {
          throw new Error(`No migration path found from ${step.fromVersion} to ${step.toVersion} for type ${data.type}`)
        }
      }

      if (logMigrations) {
        this.logger.userInteraction('migration_completed', {
          type: data.type,
          fromVersion: currentVersion,
          toVersion: targetVersion,
          success: true
        })
      }

      return migratedData

    } catch (error) {
      this.logger.criticalError(error, {
        operation: 'data_migration',
        type: data.type,
        version: data.version
      })

      if (strict) {
        throw error
      }

      // Return original data if migration fails and not strict
      this.logger.errorRecovery('migration_failed', 'returning_original', true, {
        type: data.type,
        version: data.version,
        error: error.message
      })

      return data
    }
  }

  /**
   * Check if data needs migration
   */
  needsMigration(data: { version: string; type: string }): boolean {
    const currentVersion = data.version
    const latestVersion = this.getLatestVersion(data.type)
    return currentVersion !== latestVersion
  }

  /**
   * Get the latest version for a data type
   */
  getLatestVersion(type: string): string {
    switch (type) {
      case 'tournament':
        return EXPORT_FORMAT_VERSIONS.TOURNAMENT_CONFIG
      case 'scenario':
        return EXPORT_FORMAT_VERSIONS.TEST_SCENARIO
      case 'bulk':
        return EXPORT_FORMAT_VERSIONS.BULK_EXPORT
      case 'template':
        return EXPORT_FORMAT_VERSIONS.TEMPLATE
      default:
        return '1.0'
    }
  }

  /**
   * Get supported versions for a data type
   */
  getSupportedVersions(type: string): string[] {
    switch (type) {
      case 'tournament':
        return Object.keys(TOURNAMENT_MIGRATIONS)
      case 'scenario':
        return Object.keys(SCENARIO_MIGRATIONS)
      case 'bulk':
        return Object.keys(BULK_MIGRATIONS)
      case 'template':
        return Object.keys(TEMPLATE_MIGRATIONS)
      default:
        return ['1.0']
    }
  }

  /**
   * Validate data version compatibility
   */
  isVersionSupported(data: { version: string; type: string }): boolean {
    const supportedVersions = this.getSupportedVersions(data.type)
    return supportedVersions.includes(data.version)
  }

  /**
   * Get migration preview (what will change)
   */
  getMigrationPreview(data: { version: string; type: string }): {
    needsMigration: boolean
    currentVersion: string
    targetVersion: string
    migrationSteps: Array<{ fromVersion: string; toVersion: string; description: string }>
  } {
    const currentVersion = data.version
    const targetVersion = this.getLatestVersion(data.type)
    const needsMigration = currentVersion !== targetVersion

    const migrationSteps = needsMigration
      ? this.findMigrationPath(data.type, currentVersion, targetVersion).map(step => ({
          fromVersion: step.fromVersion,
          toVersion: step.toVersion,
          description: this.getMigrationDescription(data.type, step.fromVersion, step.toVersion)
        }))
      : []

    return {
      needsMigration,
      currentVersion,
      targetVersion,
      migrationSteps
    }
  }

  /**
   * Batch migrate multiple items
   */
  async migrateBatch<T extends { version: string; type: string }>(
    items: T[],
    options: MigrationOptions & { continueOnError?: boolean } = {}
  ): Promise<{
    migrated: T[]
    failed: Array<{ item: T; error: string }>
    summary: {
      total: number
      migrated: number
      failed: number
      skipped: number
    }
  }> {
    const { continueOnError = true, ...migrationOptions } = options
    const migrated: T[] = []
    const failed: Array<{ item: T; error: string }> = []
    let skipped = 0

    for (const item of items) {
      try {
        if (this.needsMigration(item)) {
          const migratedItem = await this.migrateToLatest(item, migrationOptions)
          migrated.push(migratedItem)
        } else {
          migrated.push(item)
          skipped++
        }
      } catch (error) {
        if (continueOnError) {
          failed.push({ item, error: error.message })
        } else {
          throw error
        }
      }
    }

    return {
      migrated,
      failed,
      summary: {
        total: items.length,
        migrated: migrated.length - skipped,
        failed: failed.length,
        skipped
      }
    }
  }

  // Private helper methods

  private findMigrationPath(
    type: string,
    fromVersion: string,
    toVersion: string
  ): Array<{ fromVersion: string; toVersion: string }> {
    // Simple linear migration path for now
    // In a more complex system, this could find the shortest path through version graph
    const path: Array<{ fromVersion: string; toVersion: string }> = []

    const migrations = this.getMigrationsForType(type)
    const versions = Object.keys(migrations).sort()

    let currentVersion = fromVersion
    for (const version of versions) {
      if (version > currentVersion && version <= toVersion) {
        if (migrations[currentVersion]?.[version]) {
          path.push({ fromVersion: currentVersion, toVersion: version })
          currentVersion = version
        }
      }
    }

    return path
  }

  private getMigrationFunction(
    type: string,
    fromVersion: string,
    toVersion: string
  ): MigrationFunction | null {
    const migrations = this.getMigrationsForType(type)
    return migrations[fromVersion]?.[toVersion] || null
  }

  private getMigrationsForType(type: string): MigrationRegistry {
    switch (type) {
      case 'tournament':
        return TOURNAMENT_MIGRATIONS
      case 'scenario':
        return SCENARIO_MIGRATIONS
      case 'bulk':
        return BULK_MIGRATIONS
      case 'template':
        return TEMPLATE_MIGRATIONS
      default:
        return {}
    }
  }

  private getMigrationDescription(
    type: string,
    fromVersion: string,
    toVersion: string
  ): string {
    // Provide human-readable descriptions of what each migration does
    const descriptions: Record<string, Record<string, Record<string, string>>> = {
      tournament: {
        '0.9': {
          '1.0': 'Add checksum validation and improved metadata structure'
        }
      },
      scenario: {
        '0.9': {
          '1.0': 'Add scenario type classification and expected duration estimation'
        }
      },
      bulk: {
        '0.9': {
          '1.0': 'Add bulk summary statistics and improved item tracking'
        }
      },
      template: {
        '0.9': {
          '1.0': 'Add template settings structure and usage statistics'
        }
      }
    }

    return descriptions[type]?.[fromVersion]?.[toVersion] || 'General format improvements'
  }
}

// Export singleton instance
export const migrationService = new MigrationService()

// Export convenience functions
export const migrateData = migrationService.migrateToLatest.bind(migrationService)
export const needsMigration = migrationService.needsMigration.bind(migrationService)
export const getMigrationPreview = migrationService.getMigrationPreview.bind(migrationService)
export const migrateBatch = migrationService.migrateBatch.bind(migrationService)

export default migrationService