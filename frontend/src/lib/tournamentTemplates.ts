/**
 * Tournament Template System
 * Provides predefined tournament configurations for common scenarios
 */

import { TournamentWorkflowState, TemplateExport } from './exportImportService'
import { exportImportService } from './exportImportService'

// Template categories
export type TemplateCategory =
  | 'beginner'
  | 'casual'
  | 'competitive'
  | 'professional'
  | 'special_event'
  | 'training'

// Template difficulty levels
export type TemplateDifficulty = 'beginner' | 'intermediate' | 'advanced' | 'expert'

// Tournament template definition
export interface TournamentTemplate {
  id: string
  name: string
  description: string
  category: TemplateCategory
  difficulty: TemplateDifficulty
  estimatedDuration: number // minutes
  recommendedPlayers: number
  tags: string[]
  customizationHints: string[]
  presetConfigurations: Record<string, any>
  baseWorkflowState: TournamentWorkflowState
}

// Predefined tournament templates
export const TOURNAMENT_TEMPLATES: Record<string, TournamentTemplate> = {
  // Beginner templates
  'beginner-8-player': {
    id: 'beginner-8-player',
    name: 'Beginner 8-Player Single Elimination',
    description: 'Perfect for new players learning tournament basics. Simple format with quick matches.',
    category: 'beginner',
    difficulty: 'beginner',
    estimatedDuration: 120, // 2 hours
    recommendedPlayers: 8,
    tags: ['beginner', 'single-elimination', 'quick', 'educational'],
    customizationHints: [
      'Consider adding more tables if players finish quickly',
      'Use race-to-3 for even faster matches',
      'Great for teaching tournament etiquette'
    ],
    presetConfigurations: {
      suggestedEntryFee: 25,
      recommendedTables: 2,
      alternativeRaceTo: 3
    },
    baseWorkflowState: {
      currentStep: 'setup',
      tournamentSetup: {
        name: 'Beginner Tournament',
        format: 'single_elimination',
        maxPlayers: 8,
        entryFee: 25,
        prizePool: 200,
        tables: 2,
        raceTo: 5,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      },
      bracketSetup: {
        shuffleSeeds: false,
        raceTo: 5,
        byePlayerIds: [],
        byeSeedPositions: []
      }
    }
  },

  'beginner-16-player': {
    id: 'beginner-16-player',
    name: 'Beginner 16-Player Double Elimination',
    description: 'Introduces double elimination format while keeping it simple for beginners.',
    category: 'beginner',
    difficulty: 'beginner',
    estimatedDuration: 240, // 4 hours
    recommendedPlayers: 16,
    tags: ['beginner', 'double-elimination', 'educational', 'losers-bracket'],
    customizationHints: [
      'Ensure players understand the losers bracket concept',
      'Consider a short break after winners bracket completion',
      'Good format for learning comeback mechanics'
    ],
    presetConfigurations: {
      suggestedEntryFee: 50,
      recommendedTables: 4,
      breakDuration: 15 // minutes
    },
    baseWorkflowState: {
      currentStep: 'setup',
      tournamentSetup: {
        name: 'Beginner Double Elimination',
        format: 'double_elimination',
        maxPlayers: 16,
        entryFee: 50,
        prizePool: 800,
        tables: 4,
        raceTo: 7,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      },
      bracketSetup: {
        shuffleSeeds: true,
        raceTo: 7,
        byePlayerIds: [],
        byeSeedPositions: []
      }
    }
  },

  // Casual templates
  'casual-32-group-stage': {
    id: 'casual-32-group-stage',
    name: 'Casual 32-Player Group Stage Tournament',
    description: 'Relaxed tournament with group stage to ensure fair matchups.',
    category: 'casual',
    difficulty: 'intermediate',
    estimatedDuration: 360, // 6 hours
    recommendedPlayers: 32,
    tags: ['casual', 'group-stage', 'fair-matchups', 'social'],
    customizationHints: [
      'Groups of 4 players each advancing 2 to knockout stage',
      'Consider player skill levels when forming groups',
      'Great for social events with food and drinks'
    ],
    presetConfigurations: {
      suggestedEntryFee: 75,
      recommendedTables: 8,
      groupsOf: 4,
      advanceFromEachGroup: 2
    },
    baseWorkflowState: {
      currentStep: 'setup',
      tournamentSetup: {
        name: 'Casual Group Stage Tournament',
        format: 'group_stage',
        maxPlayers: 32,
        entryFee: 75,
        prizePool: 2400,
        tables: 8,
        raceTo: 7,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        num_groups: 8,
        players_per_group: 4,
        group_advance_count: 2,
        group_format: 'round_robin'
      },
      bracketSetup: {
        shuffleSeeds: true,
        raceTo: 7,
        byePlayerIds: [],
        byeSeedPositions: []
      }
    }
  },

  // Competitive templates
  'competitive-64-pro': {
    id: 'competitive-64-pro',
    name: 'Professional 64-Player Championship',
    description: 'High-stakes professional tournament with rigorous bracket structure.',
    category: 'professional',
    difficulty: 'expert',
    estimatedDuration: 720, // 12 hours
    recommendedPlayers: 64,
    tags: ['professional', 'championship', 'high-stakes', 'rigorous'],
    customizationHints: [
      'Requires dedicated tournament director',
      'Consider player ratings for seeding',
      'Professional commentary and streaming recommended',
      'Multiple days may be needed'
    ],
    presetConfigurations: {
      suggestedEntryFee: 500,
      recommendedTables: 16,
      requiresSeeding: true,
      suggestedDays: 2,
      prizePool: 32000
    },
    baseWorkflowState: {
      currentStep: 'setup',
      tournamentSetup: {
        name: 'Professional Championship',
        format: 'single_elimination',
        maxPlayers: 64,
        entryFee: 500,
        prizePool: 32000,
        tables: 16,
        raceTo: 9,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      },
      bracketSetup: {
        shuffleSeeds: false, // Use proper seeding
        raceTo: 9,
        byePlayerIds: [],
        byeSeedPositions: []
      }
    }
  },

  // Special event templates
  'special-christmas-32': {
    id: 'special-christmas-32',
    name: 'Holiday 32-Player Christmas Tournament',
    description: 'Festive tournament perfect for holiday celebrations with themed brackets.',
    category: 'special_event',
    difficulty: 'intermediate',
    estimatedDuration: 300, // 5 hours
    recommendedPlayers: 32,
    tags: ['holiday', 'christmas', 'themed', 'celebration', 'special-event'],
    customizationHints: [
      'Add holiday-themed player names or brackets',
      'Consider ugly sweater contest alongside tournament',
      'Great for company holiday parties',
      'Include festive prizes and decorations'
    ],
    presetConfigurations: {
      suggestedEntryFee: 100,
      recommendedTables: 8,
      theme: 'christmas',
      festivePrizes: true,
      holidayMusic: true
    },
    baseWorkflowState: {
      currentStep: 'setup',
      tournamentSetup: {
        name: 'Christmas Pool Tournament',
        format: 'single_elimination',
        maxPlayers: 32,
        entryFee: 100,
        prizePool: 3200,
        tables: 8,
        raceTo: 7,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        notes: '🎄 Merry Christmas! 🎄'
      },
      bracketSetup: {
        shuffleSeeds: true,
        raceTo: 7,
        byePlayerIds: [],
        byeSeedPositions: []
      }
    }
  },

  // Training templates
  'training-skill-builder': {
    id: 'training-skill-builder',
    name: 'Skill Building Training Tournament',
    description: 'Focus on player development with emphasis on learning and improvement.',
    category: 'training',
    difficulty: 'intermediate',
    estimatedDuration: 180, // 3 hours
    recommendedPlayers: 16,
    tags: ['training', 'skill-building', 'educational', 'development'],
    customizationHints: [
      'Include skill drills between matches',
      'Focus on sportsmanship and learning',
      'Provide coaching feedback',
      'Track improvement metrics'
    ],
    presetConfigurations: {
      suggestedEntryFee: 0, // Free training
      recommendedTables: 4,
      includeCoaching: true,
      skillDrills: true,
      feedbackSessions: true
    },
    baseWorkflowState: {
      currentStep: 'setup',
      tournamentSetup: {
        name: 'Skill Building Training',
        format: 'single_elimination',
        maxPlayers: 16,
        entryFee: 0,
        prizePool: 0,
        tables: 4,
        raceTo: 5,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        notes: 'Focus on learning and improvement'
      },
      bracketSetup: {
        shuffleSeeds: true,
        raceTo: 5,
        byePlayerIds: [],
        byeSeedPositions: []
      }
    }
  }
}

// Template utilities
export class TournamentTemplateManager {
  static getTemplatesByCategory(category: TemplateCategory): TournamentTemplate[] {
    return Object.values(TOURNAMENT_TEMPLATES).filter(template => template.category === category)
  }

  static getTemplatesByDifficulty(difficulty: TemplateDifficulty): TournamentTemplate[] {
    return Object.values(TOURNAMENT_TEMPLATES).filter(template => template.difficulty === difficulty)
  }

  static getTemplatesByPlayerCount(playerCount: number): TournamentTemplate[] {
    return Object.values(TOURNAMENT_TEMPLATES).filter(template =>
      Math.abs(template.recommendedPlayers - playerCount) <= template.recommendedPlayers * 0.2
    )
  }

  static searchTemplates(query: string): TournamentTemplate[] {
    const lowercaseQuery = query.toLowerCase()
    return Object.values(TOURNAMENT_TEMPLATES).filter(template =>
      template.name.toLowerCase().includes(lowercaseQuery) ||
      template.description.toLowerCase().includes(lowercaseQuery) ||
      template.tags.some(tag => tag.toLowerCase().includes(lowercaseQuery)) ||
      template.category.toLowerCase().includes(lowercaseQuery)
    )
  }

  static getTemplateById(id: string): TournamentTemplate | null {
    return TOURNAMENT_TEMPLATES[id] || null
  }

  static getAllTemplates(): TournamentTemplate[] {
    return Object.values(TOURNAMENT_TEMPLATES)
  }

  static async createTemplateFromTournament(
    tournament: TournamentWorkflowState,
    name: string,
    description: string,
    category: TemplateCategory,
    difficulty: TemplateDifficulty,
    tags: string[] = []
  ): Promise<TournamentTemplate> {
    const template: TournamentTemplate = {
      id: `custom_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      name,
      description,
      category,
      difficulty,
      estimatedDuration: 180, // Default 3 hours
      recommendedPlayers: tournament.tournamentSetup.maxPlayers,
      tags: [...tags, 'custom'],
      customizationHints: [
        'This is a custom template created from an existing tournament',
        'Review settings before using in production'
      ],
      presetConfigurations: {},
      baseWorkflowState: { ...tournament }
    }

    // Add to templates (in a real app, this would be saved to a database)
    TOURNAMENT_TEMPLATES[template.id] = template

    return template
  }

  static async exportTemplate(
    templateId: string,
    options: { includeFullData?: boolean } = {}
  ): Promise<TemplateExport> {
    const template = this.getTemplateById(templateId)
    if (!template) {
      throw new Error(`Template not found: ${templateId}`)
    }

    const templateSettings: any = {
      isTemplate: true,
      category: template.category,
      difficulty: template.difficulty,
      estimatedDuration: template.estimatedDuration,
      recommendedPlayers: template.recommendedPlayers,
      customizationHints: template.customizationHints,
      presetConfigurations: template.presetConfigurations
    }

    return await exportImportService.exportTemplate(
      template.name,
      template.baseWorkflowState,
      templateSettings,
      options
    )
  }

  static getTemplateCategories(): { value: TemplateCategory; label: string; description: string }[] {
    return [
      { value: 'beginner', label: 'Beginner', description: 'Perfect for new players and simple tournaments' },
      { value: 'casual', label: 'Casual', description: 'Relaxed tournaments for social play' },
      { value: 'competitive', label: 'Competitive', description: 'Serious competition with proper structure' },
      { value: 'professional', label: 'Professional', description: 'High-stakes professional events' },
      { value: 'special_event', label: 'Special Event', description: 'Themed or special occasion tournaments' },
      { value: 'training', label: 'Training', description: 'Educational tournaments focused on skill development' }
    ]
  }

  static getDifficultyLevels(): { value: TemplateDifficulty; label: string; description: string }[] {
    return [
      { value: 'beginner', label: 'Beginner', description: 'Very easy to set up and run' },
      { value: 'intermediate', label: 'Intermediate', description: 'Requires some tournament experience' },
      { value: 'advanced', label: 'Advanced', description: 'Complex setup, requires planning' },
      { value: 'expert', label: 'Expert', description: 'Professional level complexity' }
    ]
  }

  static estimateTournamentDuration(template: TournamentTemplate): {
    estimatedMinutes: number
    breakdown: { phase: string; minutes: number; description: string }[]
  } {
    const baseDuration = template.estimatedDuration
    const players = template.recommendedPlayers

    // Rough estimation based on tournament type and size
    const breakdown = []

    if (template.category === 'training') {
      breakdown.push(
        { phase: 'Setup & Registration', minutes: 30, description: 'Player registration and equipment setup' },
        { phase: 'Skill Drills', minutes: 45, description: 'Training drills between matches' },
        { phase: 'Matches', minutes: baseDuration - 75, description: 'Actual tournament matches' },
        { phase: 'Feedback & Wrap-up', minutes: 30, description: 'Coaching feedback and conclusion' }
      )
    } else if (template.category === 'professional') {
      breakdown.push(
        { phase: 'Setup & Registration', minutes: 60, description: 'Professional registration and preparation' },
        { phase: 'Opening Ceremony', minutes: 30, description: 'Official tournament opening' },
        { phase: 'Matches', minutes: baseDuration - 150, description: 'Tournament matches with breaks' },
        { phase: 'Breaks', minutes: 60, description: 'Scheduled breaks and meals' },
        { phase: 'Closing Ceremony', minutes: 30, description: 'Awards and conclusion' }
      )
    } else {
      // Standard tournament
      const matchTime = Math.max(45, baseDuration - 30) // At least 45 minutes for matches
      breakdown.push(
        { phase: 'Setup & Registration', minutes: 15, description: 'Player registration and setup' },
        { phase: 'Matches', minutes: matchTime, description: 'Tournament matches' },
        { phase: 'Breaks & Transitions', minutes: Math.max(15, baseDuration - matchTime - 15), description: 'Breaks between rounds' }
      )
    }

    return {
      estimatedMinutes: breakdown.reduce((sum, phase) => sum + phase.minutes, 0),
      breakdown
    }
  }
}

// Export convenience functions
export const templateManager = {
  getAllTemplates: TournamentTemplateManager.getAllTemplates,
  getTemplateById: TournamentTemplateManager.getTemplateById,
  getTemplatesByCategory: TournamentTemplateManager.getTemplatesByCategory,
  getTemplatesByDifficulty: TournamentTemplateManager.getTemplatesByDifficulty,
  getTemplatesByPlayerCount: TournamentTemplateManager.getTemplatesByPlayerCount,
  searchTemplates: TournamentTemplateManager.searchTemplates,
  createTemplateFromTournament: TournamentTemplateManager.createTemplateFromTournament,
  exportTemplate: TournamentTemplateManager.exportTemplate,
  getTemplateCategories: TournamentTemplateManager.getTemplateCategories,
  getDifficultyLevels: TournamentTemplateManager.getDifficultyLevels,
  estimateTournamentDuration: TournamentTemplateManager.estimateTournamentDuration
}

export default templateManager