/**
 * API Client for Test Tournament Endpoints
 * Isolated from live tournament data for testing purposes
 */

import { apiClient } from './client'
import { logger } from '@/lib/logger'

// ==========================================
// Test Tournament Models
// ==========================================

export interface TestTournament {
  tournament_id: string
  name: string
  format: string
  max_players: number
  race_to: number
  race_to_final?: number | null
  status: string
  start_date: string
  end_date?: string | null
  location?: string
  prize_pool?: number
  points_structure?: Record<string, number> | null
  ranking_system?: string
  game_type?: string
  association?: string | null
  bracket_template_id?: number | null
  bracket_draw_size?: number | null
  bye_strategy?: string | null
}

export interface TestPlayer {
  player_id: string
  name: string
  fargo_rating?: number
  current_rating: number
  country?: string
  license_number?: string | null
  total_points?: number | null
  rank?: number | null
}

export interface TestMatch {
  match_id: string
  tournament_id: string
  bracket_type?: string
  round_number?: number
  operator_id?: string | null
  player2_id?: string | null
  operator_name: string
  player2_name: string
  operator_score?: number
  player2_score?: number
  winner_id?: string
  status: string
  table_number?: number
  race_to?: number
}

export interface TestLeaderboardEntry {
  player_id: string
  name: string
  wins: number
  losses: number
  racks_won: number
  racks_lost: number
  win_percentage: number
  current_rating: number
  placement?: number | null
  wpba_r_points?: number | null
}

export interface BracketSections {
  winners: Record<string, TestMatch[]>
  losers: Record<string, TestMatch[]>
  grand_final: TestMatch[]
}

export interface TestBracketTree {
  tournament: TestTournament | null
  rounds: Record<string, TestMatch[]>
  sections?: BracketSections
  matches: TestMatch[]
}

export interface TestTournamentSetupPayload {
  name: string
  format: 'single_elimination' | 'double_elimination'
  max_players: number
  entry_fee: number
  tables: number
  race_to: number
  race_to_final?: number
  ranking_system?: string
  game_type?: string
  association?: string | null
  bracket_template_id?: number | null
  bracket_draw_size?: number | null
  bye_strategy?: string
  location?: string
  start_date?: string
  end_date?: string
  prize_pool?: number
  points_structure?: Record<string, number>
}

// ==========================================
// API Client Functions
// ==========================================

export const testTournamentsApi = {
  async getCurrentTournament(): Promise<TestTournament | null> {
    try {
      const response = await apiClient.get('/test-tournaments/current')
      return response.data.tournament ?? null
    } catch (error) {
      logger.error('Failed to get test tournament:', error)
      throw error
    }
  },

  async getPlayers(): Promise<TestPlayer[]> {
    try {
      const response = await apiClient.get('/test-tournaments/players')
      return response.data.players || []
    } catch (error) {
      logger.error('Failed to get test players:', error)
      throw error
    }
  },

  async updatePlayerName(playerId: string, name: string): Promise<TestPlayer> {
    const response = await apiClient.put(`/test-tournaments/players/${encodeURIComponent(playerId)}/name`, { name })
    return response.data.player
  },

  async addPlayer(body: {
    first_name: string
    last_name: string
    country?: string
    fargo_rating?: number
  }): Promise<TestPlayer> {
    const response = await apiClient.post('/test-tournaments/players', body)
    return response.data.player
  },

  async autoFill(): Promise<{ added: number }> {
    const response = await apiClient.post('/test-tournaments/auto-fill')
    return { added: response.data.added ?? 0 }
  },

  async clearRegistration(): Promise<{ removed: number }> {
    const response = await apiClient.post('/test-tournaments/clear-registration')
    return { removed: response.data.removed ?? 0 }
  },

  async getMatches(): Promise<TestMatch[]> {
    try {
      const response = await apiClient.get('/test-tournaments/matches')
      return response.data.matches || []
    } catch (error) {
      logger.error('Failed to get test matches:', error)
      throw error
    }
  },

  async getLeaderboard(): Promise<TestLeaderboardEntry[]> {
    try {
      const response = await apiClient.get('/test-tournaments/leaderboard')
      return response.data.leaderboard || []
    } catch (error) {
      logger.error('Failed to get test leaderboard:', error)
      throw error
    }
  },

  async setupTournament(setup: TestTournamentSetupPayload): Promise<TestTournament> {
    try {
      const response = await apiClient.post('/test-tournaments/setup', setup)
      return response.data.tournament
    } catch (error) {
      logger.error('Failed to setup test tournament:', error)
      throw error
    }
  },

  async generateBracket(options?: {
    shuffle_seeds?: boolean
    race_to?: number
    bye_player_ids?: string[]
    bye_seed_positions?: number[]
  }): Promise<{ matches_created: number }> {
    try {
      const response = await apiClient.post('/test-tournaments/generate-bracket', options ?? {})
      return response.data
    } catch (error) {
      logger.error('Failed to generate test bracket:', error)
      throw error
    }
  },

  async randomizeSeeding(): Promise<{
    randomization_count: number
    players: { seed: number; player_id: string; name: string }[]
  }> {
    const response = await apiClient.post('/test-tournaments/randomize-seeding', {})
    return {
      randomization_count: response.data.randomization_count ?? 0,
      players: response.data.players ?? [],
    }
  },

  async getBracketTree(): Promise<TestBracketTree> {
    const response = await apiClient.get('/test-tournaments/bracket-tree')
    return {
      tournament: response.data.tournament ?? null,
      rounds: response.data.rounds ?? {},
      sections: response.data.sections ?? undefined,
      matches: response.data.matches ?? [],
    }
  },

  async seedClassicsDemoPlayers(): Promise<{ added: number }> {
    const response = await apiClient.post('/test-tournaments/seed-classics-demo-players')
    return { added: response.data.added ?? 0 }
  },

  async importWpbaFromProduction(limit?: number): Promise<{
    copied: number
    skipped_duplicates: number
    limit: number
    source_ranking_system: string
    message?: string
  }> {
    const response = await apiClient.post(
      '/test-tournaments/import-wpba-players-from-production',
      limit != null ? { limit } : {},
    )
    return {
      copied: response.data.copied ?? 0,
      skipped_duplicates: response.data.skipped_duplicates ?? 0,
      limit: response.data.limit ?? 0,
      source_ranking_system: response.data.source_ranking_system ?? 'WPBA*',
      message: response.data.message,
    }
  },

  async cloneProductionToTestCenter(options?: {
    tournament_limit?: number
    fargo_history_limit?: number
    register_players_for_current_tournament?: boolean
  }): Promise<{
    success: boolean
    message?: string
    players_copied: number
    rankings_copied: number
    tournaments_copied: number
    tournament_results_copied: number
    tournament_matches_copied: number
    fargo_rating_history_copied: number
    test_tournament_players_registered: number
    tournament_limit: number
    fargo_history_limit: number
  }> {
    const response = await apiClient.post('/test-tournaments/clone-production-to-test-center', options ?? {})
    return {
      success: response.data.success ?? true,
      message: response.data.message,
      players_copied: response.data.players_copied ?? 0,
      rankings_copied: response.data.rankings_copied ?? 0,
      tournaments_copied: response.data.tournaments_copied ?? 0,
      tournament_results_copied: response.data.tournament_results_copied ?? 0,
      tournament_matches_copied: response.data.tournament_matches_copied ?? 0,
      fargo_rating_history_copied: response.data.fargo_rating_history_copied ?? 0,
      test_tournament_players_registered: response.data.test_tournament_players_registered ?? 0,
      tournament_limit: response.data.tournament_limit ?? 50,
      fargo_history_limit: response.data.fargo_history_limit ?? 20000,
    }
  },

  async updateMatchScore(matchId: string, player1Score: number, player2Score: number): Promise<TestMatch> {
    const response = await apiClient.put(
      `/test-tournaments/matches/${encodeURIComponent(matchId)}/score`,
      { operator_score: player1Score, player2_score: player2Score },
    )
    return response.data.match
  },

  async resetDatabase(): Promise<{
    matches_removed: number
    players_removed: number
    tournaments_removed: number
  }> {
    const response = await apiClient.post('/test-tournaments/reset-database', {})
    return {
      matches_removed: response.data.matches_removed ?? 0,
      players_removed: response.data.players_removed ?? 0,
      tournaments_removed: response.data.tournaments_removed ?? 0,
    }
  },

  async simulateMatch(matchId: string, winnerBias: string = 'fair'): Promise<TestMatch> {
    try {
      const response = await apiClient.post('/test-tournaments/simulate-match', {
        match_id: matchId,
        winner_bias: winnerBias,
      })
      return response.data.match
    } catch (error) {
      logger.error('Failed to simulate test match:', error)
      throw error
    }
  },

  async simulateAllRemaining(options?: { winner_bias?: string }): Promise<{
    simulated_match_ids: string[]
    count: number
  }> {
    const response = await apiClient.post('/test-tournaments/simulate-all-remaining', options ?? {})
    return {
      simulated_match_ids: response.data.simulated_match_ids ?? [],
      count: response.data.count ?? 0,
    }
  },
}
