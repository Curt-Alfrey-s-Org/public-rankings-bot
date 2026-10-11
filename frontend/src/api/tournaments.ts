/**
 * API Client for Tournament Management Endpoints
 */

import { apiClient, API_BASE_URL } from './client'
import { logger } from '@/lib/logger'

// ==========================================
// Player Models
// ==========================================

export interface Player {
  player_id: string
  first_name: string
  last_name: string
  nickname?: string
  email?: string
  phone?: string
  license_number?: string
  license_expiry_date?: string
  license_overdue?: boolean
  avatar_url?: string
  fargo_score?: number
  est_rating?: number | null
  nationality?: string
  hometown?: string
  state?: string
  membership_status: 'active' | 'inactive' | 'suspended' | 'lifetime'
  hall_of_fame: boolean
  total_tournaments_played: number
  total_points: number
  current_rank?: number | null
  hot_streak_count: number
  created_at: string
  updated_at: string
}

export interface HotStreakPlayer {
  player_id: string
  first_name: string
  last_name: string
  avatar_url?: string
  fargo_score?: number
  current_rank?: number
  total_tournaments_played: number
  last_placements: number[]
  /** 0–100 from last 365 days of events in tab association; null if fewer than 2 events */
  resilience_1yr?: number | null
  /** 0–100 from all events in tab association; null if fewer than 2 events */
  resilience_career?: number | null
  fargo_history?: Array<{ tournament: string; date: string; rating: number }>
  fargo_trend_score?: number
  trend_score: number
  recent_tournaments_count: number
}

export interface TournamentPerformancePlayer {
  player_name: string
  placement?: number
  finish_percentile?: number
  matches_played: number
  matches_won: number
  matches_lost: number
  win_rate?: number
  points_for: number
  points_against: number
  score_diff: number
}

export interface TournamentPerformance {
  tournament_id: string
  tournament_name: string
  association?: string
  tournament_date?: string
  field_size: number
  players: TournamentPerformancePlayer[]
}

export interface TournamentTabCoverage {
  tournament_id: string
  tournament_name?: string
  association?: string
  tournament_date?: string
  latest_archive_file?: string
  captured_at?: string
  archive_dir?: string
  has_overview: boolean
  has_bracket: boolean
  has_live_scores: boolean
  has_matches: boolean
  has_schedule: boolean
  has_players: boolean
  has_stats: boolean
  has_performance: boolean
  players_count: number
  bracket_matches_count: number
  matches_count: number
  /** Present when include_payload=true */
  tab_overview?: Record<string, unknown> | null
  tab_players?: Array<Record<string, unknown>> | null
  tab_brackets?: Array<Record<string, unknown>> | null
  tab_matches?: Array<Record<string, unknown>> | null
  /** External Pool harvest explicit tab slices (GraphQL-derived) */
  tab_schedule?: Record<string, unknown> | unknown[] | null
  tab_live_scores?: Record<string, unknown> | unknown[] | null
  tab_stats?: Array<Record<string, unknown>> | null
  tab_performance?: Record<string, unknown> | unknown[] | null
}

export interface TournamentTabCoverageListResponse {
  total: number
  items: TournamentTabCoverage[]
}

export interface PlayerCreate {
  first_name: string
  last_name: string
  nickname?: string
  email?: string
  phone?: string
  license_number?: string
  license_expiry_date?: string
  avatar_url?: string
  fargo_score?: number
  nationality?: string
  hometown?: string
  state?: string
  membership_status?: 'active' | 'inactive' | 'suspended' | 'lifetime'
  hall_of_fame?: boolean
}

// ==========================================
// Tournament Models
// ==========================================

export interface TournamentTemplate {
  id: number
  template_name: string
  elimination_type: 'single' | 'double' | 'round_robin'
  max_players: number
  points_structure: Record<string, number>
  description?: string
  times_used: number
  created_by?: string
  created_at: string
  updated_at: string
}

/** Draw structure preset (16/32/64/80/custom saved layouts). */
export interface BracketTemplate {
  id: number
  name: string
  player_count: number
  bracket_draw_size: number
  format: string
  bye_strategy: string
  rounds: Array<Record<string, unknown>>
  association?: string | null
  is_system: boolean
  created_by?: number | null
  created_at?: string | null
  updated_at?: string | null
}

export interface BracketTemplateCreate {
  name: string
  player_count: number
  bracket_draw_size: number
  format: string
  bye_strategy?: string
  rounds: Array<Record<string, unknown>>
  association?: string | null
}

export interface Tournament {
  tournament_id: string
  tournament_name: string
  tournament_date: string
  location?: string
  elimination_type: 'single' | 'double' | 'round_robin'
  max_players: number
  actual_players: number
  points_structure: Record<string, number>
  status: 'setup' | 'registration' | 'in_progress' | 'completed' | 'cancelled'
  stage2_cutoff?: number
  stage2_elimination_type?: 'single' | 'double'
  stage2_seed_strategy?: 'placement' | 'seed' | 'manual'
  stage2_started_at?: string
  notes?: string
  game_type?: string
  tables_available?: number
  rules?: string
  template_id?: number
  created_by?: string
  winner_player_id?: string
  runner_up_player_id?: string
  created_at: string
  updated_at: string
  completed_at?: string
  association?: string | null
  tournament_end_date?: string | null
  bracket_template_id?: number | null
}

export interface TournamentDetail extends Tournament {
  players: Player[]
  matches_count: number
  completed_matches: number
}

export interface TournamentCreate {
  tournament_name: string
  tournament_date: string
  tournament_end_date?: string
  location?: string
  elimination_type: 'single' | 'double' | 'round_robin' | 'group_stage'
  max_players: number
  points_structure: Record<string, number>
  stage2_cutoff?: number
  stage2_elimination_type?: 'single' | 'double'
  stage2_seed_strategy?: 'placement' | 'seed' | 'manual'
  stage2_started_at?: string
  notes?: string
  game_type?: string
  tables_available?: number
  rules?: string
  template_id?: number
  created_by?: string
  association?: string
  bracket_template_id?: number
}

// ==========================================
// Match Models
// ==========================================

export interface Match {
  match_id: string
  tournament_id: string
  round?: number
  round_number?: number
  match_number: number
  bracket_type: 'winners' | 'losers' | 'grand_final' | 'stage2'
  operator_id?: string
  player2_id?: string
  operator_name?: string
  player2_name?: string
  operator_games?: number
  player2_games?: number
  operator_score?: number
  player2_score?: number
  winner_player_id?: string
  status: 'pending' | 'in_progress' | 'completed' | 'bye'
  table_number?: number
  forfeit_reason?: string
  started_at?: string
  completed_at?: string
  scheduled_time?: string
  race_to?: number
  operator_handicapped_race?: number
  player2_handicapped_race?: number
  handicap_applied?: boolean
  projected_start_time?: string
  projected_end_time?: string
  notes?: string
  /** Live in-match odds (Phase 3, denorm on matches) */
  live_p1_win_prob?: number | null
  live_p2_win_prob?: number | null
  odds_updated_at?: string | null
  created_at: string
  updated_at: string
}

/** Server live odds snapshot (GET /matches/{id}/odds) */
export interface MatchLiveOdds {
  match_id: string
  tournament_id?: string | null
  operator_id?: string | null
  player2_id?: string | null
  p1_score?: number
  p2_score?: number
  p1_win_prob: number
  p2_win_prob: number
  p_rack_p1?: number
  rating_source?: string
  formula_version?: string
  trigger?: string
  created_at?: string
}

/** Request body for marking a match as forfeit/DQ. Backend may expose POST /matches/{id}/forfeit. */
export interface ForfeitRequest {
  winner_player_id: string
  reason: string
}

export interface TableCall {
  id: number
  match_id: string
  tournament_id: string
  table_number: number
  report_by_utc: string
  warning_minutes: number[]
  sent_warnings: number[]
  created_at?: string
}

// ==========================================
// API Methods
// ==========================================

export function createTournamentsApi(basePath: string = '/tournaments') {
  const BASE = basePath.replace(/\/$/, '') || '/tournaments'

  return {
  // Tournament Templates
  getTemplates: async (): Promise<TournamentTemplate[]> => {
    const response = await apiClient.get(`${BASE}/templates`)
    return response.data
  },

  getTemplate: async (templateId: number): Promise<TournamentTemplate> => {
    const response = await apiClient.get(`${BASE}/templates/${templateId}`)
    return response.data
  },

  createTemplate: async (
    data: Omit<TournamentTemplate, 'id' | 'times_used' | 'created_at' | 'updated_at'>
  ): Promise<TournamentTemplate> => {
    const response = await apiClient.post(`${BASE}/templates`, data)
    return response.data
  },

  getBracketTemplates: async (association?: string): Promise<BracketTemplate[]> => {
    const response = await apiClient.get(`${BASE}/bracket-templates`, {
      params: association ? { association } : {},
    })
    return response.data
  },

  getBracketTemplate: async (id: number): Promise<BracketTemplate> => {
    const response = await apiClient.get(`${BASE}/bracket-templates/${id}`)
    return response.data
  },

  createBracketTemplate: async (data: BracketTemplateCreate): Promise<BracketTemplate> => {
    const response = await apiClient.post(`${BASE}/bracket-templates`, data)
    return response.data
  },

  deleteBracketTemplate: async (id: number): Promise<void> => {
    await apiClient.delete(`${BASE}/bracket-templates/${id}`)
  },

  // Players (pass false to include inactive/suspended for admin filtering)
  getPlayers: async (activeOnly = true, association?: string): Promise<Player[]> => {
    const response = await apiClient.get(`${BASE}/players`, {
      params: {
        active_only: activeOnly,
        ...(association ? { association } : {}),
      },
    })
    return response.data
  },

  getPlayersFromHistory: async (association: string): Promise<Player[]> => {
    const response = await apiClient.get(`${BASE}/players/from-history`, {
      params: { association },
    })
    return response.data
  },

  getPlayer: async (playerId: string): Promise<Player> => {
    const response = await apiClient.get(`${BASE}/players/${playerId}`)
    return response.data
  },

  createPlayer: async (data: PlayerCreate): Promise<Player> => {
    const response = await apiClient.post(`${BASE}/players`, data)
    return response.data
  },

  updatePlayer: async (playerId: string, data: Partial<PlayerCreate>): Promise<Player> => {
    const response = await apiClient.put(`${BASE}/players/${playerId}`, data)
    return response.data
  },

  deletePlayer: async (playerId: string): Promise<void> => {
    await apiClient.delete(`${BASE}/players/${playerId}`)
  },

  /** Sync Fargo rating for a single player from FairMatch. Director/admin only. */
  syncPlayerFargo: async (playerId: string): Promise<Player> => {
    const response = await apiClient.post(`${BASE}/players/${playerId}/sync-fargo`)
    return response.data
  },

  /** Sync Fargo ratings for all active players. Director/admin only. */
  syncAllFargo: async (): Promise<{ synced: number; failed: number; errors: { player_id: string; error: string }[] }> => {
    const response = await apiClient.post(`${BASE}/sync-all-fargo`)
    return response.data
  },

  /** Create a player from a WPBA/WPA rankings row (partial info allowed). Director/admin only. */
  createPlayerFromRanking: async (data: { name: string; country?: string; fargo_rating?: number; license_number?: string }): Promise<Player> => {
    const response = await apiClient.post(`${BASE}/players/from-ranking`, data)
    return response.data
  },

  /** Remove duplicate players (by license_number and by first_name+last_name). Director/admin only. */
  dedupePlayers: async (): Promise<{ removed: number; by_license: number; by_name: number; details: { player_id: string; reason: string; keep: string }[] }> => {
    const response = await apiClient.post(`${BASE}/players/dedupe`)
    return response.data
  },

  /** Scrape hometown from WPBA/WPA public player profiles and update players. Director/admin only. */
  scrapeHometowns: async (): Promise<{ updated: number; scraped: number; errors: string[] }> => {
    const response = await apiClient.post(`${BASE}/players/scrape-hometowns`)
    return response.data
  },

  // Tournaments
  getTournaments: async (status?: string, includeTest?: boolean): Promise<Tournament[]> => {
    const params: any = {}
    if (status) params.status_filter = status
    if (includeTest) params.include_test = includeTest

    const response = await apiClient.get(BASE, { params })
    return response.data
  },

  getCompletedResults: async (limit = 20): Promise<{
    tournaments: { tournament_id: string; tournament_name: string; tournament_date: string; first_place_name: string | null; second_place_name: string | null; third_place_name: string | null }[]
  }> => {
    const response = await apiClient.get(`${BASE}/completed-results`, { params: { limit } })
    return response.data
  },

  getTournament: async (tournamentId: string): Promise<TournamentDetail> => {
    const response = await apiClient.get(`${BASE}/${tournamentId}`)
    return response.data
  },

  getTournamentPerformance: async (tournamentId: string): Promise<TournamentPerformance> => {
    const response = await apiClient.get(`${BASE}/history/${tournamentId}/performance`)
    return response.data
  },

  getTournamentTabCoverage: async (
    tournamentId: string,
    options?: { includePayload?: boolean }
  ): Promise<TournamentTabCoverage> => {
    const response = await apiClient.get(`${BASE}/history/${tournamentId}/tab-coverage`, {
      params: { include_payload: options?.includePayload ?? false },
    })
    return response.data
  },

  getTournamentTabCoverageList: async (params?: {
    limit?: number
    association?: string
    year?: number
    incomplete_only?: boolean
  }): Promise<TournamentTabCoverageListResponse> => {
    const response = await apiClient.get(`${BASE}/history/tab-coverage`, { params })
    return response.data
  },

  getTournamentPlayers: async (
    tournamentId: string
  ): Promise<{ player_id: string; first_name: string; last_name: string; check_in_at?: string }[]> => {
    const response = await apiClient.get(`${BASE}/${tournamentId}/players`)
    return response.data
  },

  /** Fill tournament with top players from the tournament's ranking system (wizard step 1). */
  autoFillPlayers: async (
    tournamentId: string
  ): Promise<{ success: boolean; added: number; message: string }> => {
    const response = await apiClient.post(`${BASE}/${tournamentId}/players/auto-fill`)
    return response.data
  },

  /** Remove all registered players from the tournament (director/admin). */
  clearRegistration: async (
    tournamentId: string
  ): Promise<{ success: boolean; removed: number; message: string }> => {
    const response = await apiClient.post(`${BASE}/${tournamentId}/players/clear-registration`)
    return response.data
  },

  createTournament: async (data: TournamentCreate): Promise<Tournament> => {
    const response = await apiClient.post(`${BASE}/`, data)
    return response.data
  },

  importCompetitors: async (
    tournamentId: string,
    body: { slug: string; generate_bracket?: boolean; race_to?: number }
  ): Promise<{
    actual_players?: number
    matches_updated?: number
    [key: string]: unknown
  }> => {
    const response = await apiClient.post(`${BASE}/${tournamentId}/import-competitors`, {
      slug: body.slug,
      generate_bracket: body.generate_bracket ?? true,
      race_to: body.race_to ?? 7,
    })
    return response.data
  },

  updateTournament: async (
    tournamentId: string,
    data: Partial<TournamentCreate>
  ): Promise<Tournament> => {
    const response = await apiClient.put(`${BASE}/${tournamentId}`, data)
    return response.data
  },

  deleteTournament: async (tournamentId: string): Promise<void> => {
    await apiClient.delete(`${BASE}/${tournamentId}`)
  },

  // Register Players
  registerPlayer: async (
    tournamentId: string,
    playerId: string,
    seedPosition?: number
  ): Promise<{ message: string; tournament_id: string; player_id: string }> => {
    const response = await apiClient.post(`${BASE}/${tournamentId}/players`, {
      player_id: playerId,
      seed_position: seedPosition,
    })
    return response.data
  },

  registerPlayers: async (
    tournamentId: string,
    playerIds: string[]
  ): Promise<{ registered: number; failed: number }> => {
    const response = await apiClient.post(`${BASE}/${tournamentId}/players/bulk`, {
      player_ids: playerIds,
    })
    return response.data
  },

  /** Create payment intent for tournament entry fee. Returns client_secret for Stripe. */
  createRegistrationPaymentIntent: async (
    tournamentId: string,
    playerId: string
  ): Promise<{ client_secret: string; intent_id: string; amount: number }> => {
    const response = await apiClient.post(`${BASE}/${tournamentId}/payment-intent`, { player_id: playerId })
    return response.data
  },

  /** Confirm payment and optionally register player. */
  confirmRegistrationPayment: async (
    tournamentId: string,
    paymentIntentId: string,
    registerPlayer: boolean
  ): Promise<{ message: string; tournament_id: string; player_id: string; status: string }> => {
    const response = await apiClient.post(`${BASE}/${tournamentId}/payment-confirm`, {
      payment_intent_id: paymentIntentId,
      register_player: registerPlayer,
    })
    return response.data
  },

  /** Get registration settings (entry fee, etc.). */
  getRegistrationSettings: async (
    tournamentId: string
  ): Promise<{ entry_fee_cents: number; payment_required: number }> => {
    const response = await apiClient.get(`${BASE}/${tournamentId}/registration-settings`)
    return response.data
  },

  /** Update registration settings. Director/admin only. */
  updateRegistrationSettings: async (
    tournamentId: string,
    data: { entry_fee_cents: number; payment_required?: boolean }
  ): Promise<{ message: string }> => {
    const response = await apiClient.put(`${BASE}/${tournamentId}/registration-settings`, data)
    return response.data
  },

  /** Add player to waitlist when tournament is full. */
  addToWaitlist: async (
    tournamentId: string,
    playerId: string
  ): Promise<{ message: string; position: number }> => {
    const response = await apiClient.post(`${BASE}/${tournamentId}/waitlist`, { player_id: playerId })
    return response.data
  },

  /** Get waitlist for tournament. */
  getWaitlist: async (tournamentId: string): Promise<{ waitlist: { player_id: string; position: number }[] }> => {
    const response = await apiClient.get(`${BASE}/${tournamentId}/waitlist`)
    return response.data
  },

  // Generate Bracket
  generateBracket: async (
    tournamentId: string,
    options?: GenerateBracketOptions
  ): Promise<{ matches_created: number }> => {
    const response = await apiClient.post(`${BASE}/${tournamentId}/generate-bracket`, options ?? {})
    return response.data
  },

  startStage2: async (
    tournamentId: string,
    data: Stage2StartRequest
  ): Promise<{ matches_created: number; advancing_count: number; bracket_size: number }> => {
    const response = await apiClient.post(`${BASE}/${tournamentId}/start-stage2`, data)
    return response.data
  },

  /** Get check-in URL for a player (for QR code). Scan opens this URL to record check-in. */
  getCheckInUrl: (tournamentId: string, playerId: string): string => {
    const base =
      typeof window !== 'undefined' && !API_BASE_URL.startsWith('http')
        ? `${window.location.origin}${API_BASE_URL}`
        : API_BASE_URL
    return `${base}/tournaments/${tournamentId}/check-in/${playerId}`
  },

  /** Tournament completion percentage (completed / total matches, excluding byes). */
  getTournamentProgress: async (
    tournamentId: string
  ): Promise<{ tournament_id: string; completed: number; total: number; percent: number }> => {
    const response = await apiClient.get(`${BASE}/${tournamentId}/progress`)
    return response.data
  },

  /** SSE stream URL for live bracket updates (EventSource). */
  getStreamUrl: (tournamentId: string): string => {
    const base =
      typeof window !== 'undefined' && !API_BASE_URL.startsWith('http')
        ? `${window.location.origin}${API_BASE_URL}`
        : API_BASE_URL || '/api'
    return `${base}/tournaments/${tournamentId}/stream`
  },

  /** Apply Fargo handicaps to all matches in tournament. Director/admin only. */
  applyFargoHandicaps: async (tournamentId: string): Promise<{ applied: number; skipped: number; errors: string[] }> => {
    const response = await apiClient.post(`${BASE}/${tournamentId}/apply-fargo-handicaps`)
    return response.data
  },

  /** Calculate handicap suggestion for a match. */
  calculateMatchHandicap: async (matchId: string): Promise<{ match_id: string; operator_handicapped_race: number; player2_handicapped_race: number; handicap_applied: boolean }> => {
    const response = await apiClient.get(`${BASE}/matches/${matchId}/calculate-handicap`)
    return response.data
  },

  /** Submit a single rack/game (drives live EST + odds). Director/scorekeeper. */
  submitGame: async (payload: {
    match_id: string
    game_number: number
    winner_id: string
    breaking_player_id?: string
    run_out?: boolean
    break_and_run?: boolean
    notes?: string
  }): Promise<Record<string, unknown>> => {
    const response = await apiClient.post(`${BASE}/games`, payload)
    return response.data
  },

  getMatchGames: async (matchId: string): Promise<Array<Record<string, unknown>>> => {
    const response = await apiClient.get(`${BASE}/matches/${matchId}/games`)
    return response.data
  },

  /** Latest in-match live odds (score-state + est/Fargo). */
  getMatchOdds: async (matchId: string): Promise<MatchLiveOdds> => {
    const response = await apiClient.get(`${BASE}/matches/${matchId}/odds`)
    return response.data
  },

  getMatchOddsHistory: async (
    matchId: string,
    limit = 50
  ): Promise<{ match_id: string; snapshots: MatchLiveOdds[] }> => {
    const response = await apiClient.get(`${BASE}/matches/${matchId}/odds/history`, {
      params: { limit },
    })
    return response.data
  },

  // Matches (normalize backend round_number, operator_score, player2_score to frontend round, operator_games, player2_games)
  getMatches: async (tournamentId: string): Promise<Match[]> => {
    const response = await apiClient.get(`${BASE}/${tournamentId}/matches`)
    const raw = response.data as Array<Record<string, unknown>>
    const mapped = raw.map((m) => ({
      ...m,
      round: m.round ?? m.round_number,
      round_number: m.round_number ?? m.round,
      operator_games: m.operator_games ?? m.operator_score,
      player2_games: m.player2_games ?? m.player2_score,
      operator_score: m.operator_score ?? m.operator_games,
      player2_score: m.player2_score ?? m.player2_games,
      winner_player_id: m.winner_player_id ?? m.winner_id,
      live_p1_win_prob: m.live_p1_win_prob ?? null,
      live_p2_win_prob: m.live_p2_win_prob ?? null,
      odds_updated_at: m.odds_updated_at ?? null,
    }))
    return mapped as unknown as Match[]
  },

  updateMatchScore: async (
    matchId: string,
    player1Games: number,
    player2Games: number
  ): Promise<Match> => {
    const response = await apiClient.put(`${BASE}/matches/${matchId}/score`, {
      operator_score: player1Games,
      player2_score: player2Games,
    })
    return response.data
  },

  /** Update match fields (e.g. table_number). Director/admin only. */
  updateMatch: async (
    matchId: string,
    data: { table_number?: number; notes?: string; scheduled_time?: string }
  ): Promise<{ message: string; match_id: string }> => {
    const response = await apiClient.patch(`${BASE}/matches/${matchId}`, data)
    return response.data
  },

  /** Mark match as forfeit/DQ. Director/admin only. Backend: POST .../matches/{id}/forfeit with winner_player_id, reason. */
  forfeitMatch: async (matchId: string, data: ForfeitRequest): Promise<Match> => {
    const response = await apiClient.post(`${BASE}/matches/${matchId}/forfeit`, data)
    const raw = response.data as Record<string, unknown>
    return {
      ...raw,
      round: raw.round ?? raw.round_number,
      round_number: raw.round_number ?? raw.round,
      operator_games: raw.operator_games ?? raw.operator_score,
      player2_games: raw.player2_games ?? raw.player2_score,
    } as Match
  },

  /** Get matches for a specific table. Score keeper mode. Expects backend GET .../matches?table_number=N or filter client-side. */
  getMatchesByTable: async (tournamentId: string, tableNumber: number): Promise<Match[]> => {
    try {
      const response = await apiClient.get(`${BASE}/${tournamentId}/matches`, {
        params: { table_number: tableNumber },
      })
      const raw = (response.data as Array<Record<string, unknown>>) || []
      return raw.map((m) => ({
        ...m,
        round: m.round ?? m.round_number,
        round_number: m.round_number ?? m.round,
        operator_games: m.operator_games ?? m.operator_score,
        player2_games: m.player2_games ?? m.player2_score,
        winner_player_id: m.winner_player_id ?? (m as { winner_id?: string }).winner_id,
      })) as Match[]
    } catch (error) {
      logger.warn(
        'Table-specific matches query failed, falling back to client-side filtering',
        { tournamentId, tableNumber },
        error as Error
      )
      const all = await tournamentsApi.getMatches(tournamentId)
      return all.filter((m) => m.table_number === tableNumber)
    }
  },

  /** Match state for timers (started_at, match_time_limit from tournament). Used by player-facing and score keeper views. */
  getMatchStateForTimers: async (tournamentId: string, matchId: string): Promise<{
    match_id: string
    started_at?: string
    scheduled_time?: string
    race_to?: number
    table_number?: number
    status: string
    match_time_limit_minutes?: number
    shot_clock_seconds?: number
  }> => {
    const [matches, tournament] = await Promise.all([
      tournamentsApi.getMatches(tournamentId),
      tournamentsApi.getTournament(tournamentId),
    ])
    const match = matches.find((m) => m.match_id === matchId)
    const detail = tournament as TournamentDetail & { match_time_limit_minutes?: number; shot_clock_seconds?: number }
    return {
      match_id: matchId,
      started_at: match?.started_at,
      scheduled_time: match?.scheduled_time,
      race_to: match?.race_to,
      table_number: match?.table_number,
      status: match?.status ?? 'pending',
      match_time_limit_minutes: detail?.match_time_limit_minutes,
      shot_clock_seconds: detail?.shot_clock_seconds,
    }
  },

  /** Table calls: report-to-table warnings (20/15/10/5/1 min). Director/admin only. */
  createTableCall: async (
    tournamentId: string,
    data: { match_id: string; table_number: number; report_by: string; warning_minutes?: number[] }
  ): Promise<TableCall> => {
    const response = await apiClient.post(`${BASE}/${tournamentId}/table-calls`, data)
    return response.data
  },

  getTableCalls: async (tournamentId: string): Promise<TableCall[]> => {
    const response = await apiClient.get(`${BASE}/${tournamentId}/table-calls`)
    return response.data
  },

  /** Process due table-call warnings and send emails. Director/admin only. */
  processWarnings: async (): Promise<{ message: string; sent: number; errors: number }> => {
    const response = await apiClient.post(`${BASE}/process-warnings`)
    return response.data
  },

  // Rankings
  getCurrentRankings: async (system?: string): Promise<Player[]> => {
    const params: any = {}
    if (system) params.system = system
    const response = await apiClient.get(`${BASE}/rankings/current`, { params })
    return response.data
  },

  getHotStreakPlayers: async (params?: {
    lookback?: number
    min_tournaments?: number
    limit?: number
    association?: string
  }): Promise<HotStreakPlayer[]> => {
    const response = await apiClient.get(`${BASE}/hot-streak`, { params })
    return response.data
  },

  getFargoHotStreakPlayers: async (params?: {
    lookback?: number
    min_tournaments?: number
    limit?: number
    association?: string
  }): Promise<HotStreakPlayer[]> => {
    const response = await apiClient.get(`${BASE}/hot-streak/fargo`, { params })
    return response.data
  },

  recalculateRankings: async (): Promise<{ updated: number }> => {
    const response = await apiClient.post(`${BASE}/rankings/recalculate`)
    return response.data
  },
  }
}

export const tournamentsApi = createTournamentsApi()
