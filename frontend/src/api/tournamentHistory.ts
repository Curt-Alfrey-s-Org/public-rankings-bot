/**
 * Tournament History API Service
 * Services for fetching tournament history and player tournament records
 */

import { apiClient } from './client'
import type { LiveLogStarted } from './liveLogStream'

export interface Tournament {
  id?: number
  tournament_id: string
  name: string
  year: number
  date: string
  location: string
  association: string
  championship: string
  prize_pool?: string
  status?: string
}

export interface TournamentResult {
  id?: number
  tournament_id: string
  player_name: string
  placement: number
  points?: number
  tournament_name?: string
  year?: number
  championship?: string
  date?: string
  association?: string
  location?: string
  seed?: number | null
  race_to?: number | null
  current_round?: string | null
  player_status?: string | null
  is_eliminated?: boolean | null
}

export interface HistoryMatch {
  id?: number
  tournament_id?: string
  operator_name?: string
  player2_name?: string
  operator_score?: number | null
  player2_score?: number | null
  winner_name?: string | null
  round_num?: string | null
  match_num?: number | null
  match_date?: string | null
  notes?: string | null
}

export interface PlayerTournamentHistory {
  success?: boolean
  player_name: string
  tournament_results: TournamentResult[]
  statistics: {
    total_tournaments: number
    first_place_finishes: number
    top_3_finishes: number
    average_placement: number | null
  }
  narrative?: string
  narrative_unchanged?: boolean
}

export interface TournamentStatistics {
  total_tournaments: number
  by_association: Record<string, number>
  years_covered: number[]
  total_players_in_history?: number
}

/** Prefix e.g. `/tournament-history` or `/test-center/tournament-history`. */
export function createTournamentHistoryApi(prefix: string = '/tournament-history') {
  const P = prefix.replace(/\/$/, '') || '/tournament-history'

  return {
  /**
   * Get tournament history
   */
  async getTournaments(
    year?: number,
    association?: string,
    limit = 100
  ): Promise<{ success: boolean; count: number; tournaments: Tournament[] }> {
    const params = new URLSearchParams()
    if (year) params.append('year', year.toString())
    if (association) params.append('association', association)
    params.append('limit', limit.toString())

    const response = await apiClient.get(
      `${P}/tournaments?${params.toString()}`
    )
    return response.data
  },

  /**
   * Get specific tournament details with rankings
   */
  async getTournamentDetails(
    tournamentId: string
  ): Promise<{
    success: boolean
    tournament: Tournament
    results: TournamentResult[]
    total_participants: number
  }> {
    const response = await apiClient.get(`${P}/tournaments/${tournamentId}`)
    return response.data
  },

  /** Harvested bracket/match rows for history drawer */
  async getTournamentMatches(
    tournamentId: string,
    limit = 500
  ): Promise<{ success: boolean; tournament_id: string; matches: HistoryMatch[]; total: number }> {
    const response = await apiClient.get(
      `${P}/tournaments/${encodeURIComponent(tournamentId)}/matches`,
      { params: { limit } }
    )
    return response.data
  },

  /**
   * Bulk results-count lookup for tournament cards (avoids N+1).
   */
  async getResultsCounts(
    tournamentIds: string[]
  ): Promise<Record<string, number>> {
    if (!tournamentIds.length) return {}
    try {
      const response = await apiClient.get(
        `${P}/tournaments/results-counts?tournament_ids=${tournamentIds.join(',')}`,
        { skipGlobalErrorUI: true },
      )
      return response.data?.counts ?? {}
    } catch {
      return {}
    }
  },

  /**
   * Get points structure from most recent same-named tournament (for Wizard Step 2 prefill)
   */
  async getPointsByTournamentName(
    name: string
  ): Promise<{ success: boolean; points_structure: Record<string, number>; source: string | null }> {
    const response = await apiClient.get(
      `${P}/points-by-name?name=${encodeURIComponent(name)}`
    )
    return response.data
  },

  /**
   * Get player's tournament history
   */
  async getPlayerTournamentHistory(
    playerName: string
  ): Promise<PlayerTournamentHistory> {
    const response = await apiClient.get(`${P}/players/${encodeURIComponent(playerName)}/history`)
    return response.data
  },

  /**
   * Get overall tournament statistics
   */
  async getTournamentStatistics(year?: number): Promise<{
    success: boolean
    statistics: TournamentStatistics
  }> {
    const params = year ? `?year=${year}` : ''
    const response = await apiClient.get(`${P}/statistics${params}`)
    return response.data
  },

  /**
   * Search tournaments
   */
  async searchTournaments(
    query: string,
    limit = 20
  ): Promise<{ success: boolean; query: string; results: Tournament[]; count: number }> {
    const response = await apiClient.get(
      `${P}/search?q=${encodeURIComponent(query)}&limit=${limit}`
    )
    return response.data
  },

  /**
   * Get available years
   */
  async getAvailableYears(): Promise<{ success: boolean; years: number[] }> {
    const response = await apiClient.get(`${P}/years`)
    return response.data
  },

  /**
   * Get upcoming/future events (scraped from WPBA and WPA)
   */
  async getUpcomingEvents(
    association?: string,
    limit = 50
  ): Promise<{ success: boolean; events: UpcomingEvent[]; count: number }> {
    const params = new URLSearchParams()
    if (association) params.append('association', association)
    params.append('limit', limit.toString())
    const response = await apiClient.get(`${P}/upcoming?${params.toString()}`)
    return response.data
  },

  /**
   * Refresh upcoming events (Admin only) — scrapes WPBA and WPA in a background
   * thread. Fire-and-forget: returns immediately. Watch progress by streaming
   * `/tournament-history/refresh-upcoming/log` via `streamLog(...)` from
   * `@/api/liveLogStream`. Earlier `count` / `by_association` summary now
   * appears in the streamed log instead of the response.
   */
  async refreshUpcomingEvents(): Promise<LiveLogStarted> {
    const response = await apiClient.post(`${P}/refresh-upcoming`, undefined, {
      timeout: 15_000,
    })
    return response.data as LiveLogStarted
  },

  /**
   * Refresh past tournament history (super admin in production UI) — reads DB only:
   * `rankings` snapshots + WPBA Women per-event fill. Fire-and-forget; watch progress at
   * `/tournament-history/refresh-past/log`.
   */
  async refreshPastTournaments(): Promise<LiveLogStarted> {
    const response = await apiClient.post(`${P}/refresh-past`)
    return response.data as LiveLogStarted
  },

  /** Alias for refreshPastTournaments — syncs tournament_history from existing scraped rankings (no external HTTP). */
  async triggerScrape(): Promise<LiveLogStarted> {
    const response = await apiClient.post(`${P}/refresh-past`)
    return response.data as LiveLogStarted
  },

  /** Get scrape status (stub - no background scrape status endpoint) */
  async getScrapeStatus(): Promise<{ running: boolean }> {
    return { running: false }
  },

  /** Leaderboard results: recent tournaments with 1st/2nd/3rd place names from tournament history. */
  async getLeaderboardResults(limit = 15): Promise<{
    tournaments: Array<{
      tournament_id: string
      tournament_name: string
      tournament_date: string
      first_place_name?: string | null
      second_place_name?: string | null
      third_place_name?: string | null
      association?: string
    }>
  }> {
    const response = await apiClient.get<{ success: boolean; tournaments: Array<{
      tournament_id: string
      tournament_name: string
      tournament_date: string
      first_place_name?: string | null
      second_place_name?: string | null
      third_place_name?: string | null
      association?: string
    }> }>(`${P}/leaderboard-results`, { params: { limit } })
    const data = response.data
    return {
      tournaments: (data.tournaments ?? []).map((t) => ({
        tournament_id: t.tournament_id,
        tournament_name: t.tournament_name,
        tournament_date: t.tournament_date,
        association: t.association,
        first_place_name: t.first_place_name ?? undefined,
        second_place_name: t.second_place_name ?? undefined,
        third_place_name: t.third_place_name ?? undefined,
      })),
    }
  },

  /** Leaderboard results grouped by association: top N per association (single source: tournament_history). */
  async getLeaderboardResultsByAssociation(limitPerAssociation = 3): Promise<{
    by_association: Record<string, Array<{
      tournament_id: string
      tournament_name: string
      tournament_date: string
      first_place_name?: string | null
      second_place_name?: string | null
      third_place_name?: string | null
      association?: string
    }>>
  }> {
    const response = await apiClient.get<{ success: boolean; by_association: Record<string, Array<{
      tournament_id: string
      tournament_name: string
      tournament_date: string
      first_place_name?: string | null
      second_place_name?: string | null
      third_place_name?: string | null
      association?: string
    }>> }>(`${P}/leaderboard-results-by-association`, {
      params: { limit_per_association: limitPerAssociation },
    })
    return { by_association: response.data.by_association ?? {} }
  },
  }
}

export const tournamentHistoryApi = createTournamentHistoryApi()

export interface UpcomingEnrichmentHint {
  field: string
  value: string | number
  source: string
  source_url?: string
  article_title?: string
  confidence?: number
}

export interface UpcomingEnrichment {
  hints?: UpcomingEnrichmentHint[]
  matched_articles?: Array<{
    title: string
    url: string
    source: string
    match_score?: number
  }>
  enriched_at?: string
}

export interface UpcomingEvent {
  id?: number
  event_id?: string
  name: string
  date: string | null
  start_date?: string | null
  end_date?: string | null
  location: string | null
  venue_address?: string | null
  association: string
  url: string | null
  bracket_url?: string | null
  registration_url?: string | null
  prize_pool?: string | null
  format?: string | null
  max_players?: number | null
  enrichment?: UpcomingEnrichment | null
  status: string
  scraped_at?: string
}

/**
 * Historical response shapes from the synchronous /refresh-upcoming and
 * /refresh-past endpoints. Kept for any consumer still typing against the old
 * fields (count / statistics) — production now returns `LiveLogStarted` from
 * `@/api/liveLogStream` instead, with the rich detail streamed into the live log.
 */
export interface RefreshUpcomingResult {
  success: boolean
  count?: number
  by_association?: Record<string, number>
  timestamp?: string
  started?: boolean
  message?: string
}

export interface RefreshPastResult {
  success: boolean
  message: string
  statistics: { total_tournaments?: number; by_association?: Record<string, number>; years_covered?: number[] }
  timestamp: string
}
