/**
 * API Client for Rankings Endpoints
 *
 * Doc refs (AI / maintainers): docs/RANKINGS_DATA_DOC_HOOKS.md; docs/WPA_RANKINGS_DATA_FLOW.md;
 *   docs/RANKINGS_TABLE_DESIGN.md
 */

import apiClient, { API_BASE_URL } from './client'
import type { LiveLogStarted } from './liveLogStream'

/** WPBA PDF and full WPA crawl can exceed the default 15s axios timeout. */
const SCRAPER_HTTP_TIMEOUT_MS = 180_000

export type ScraperName = 'wpba' | 'wpa' | 'externalpool' | 'insidesp' | 'insidesp_tier2'

export interface RunScraperResponse {
  success: boolean
  scraper: ScraperName
  /** "started" when a fresh background run was launched; "already_running" when the lock was held. */
  status: 'started' | 'already_running'
  log_file?: string
  message?: string
}

/**
 * Headers for fetch() — mirror apiClient (localStorage + legacy keys). Mirrors the helper in
 * api/admin.ts so the scraper log stream uses the same auth path the user already has.
 */
function _scraperAuthHeaders(explicitToken?: string | null): Record<string, string> {
  const headers: Record<string, string> = {}
  const apiKey =
    typeof import.meta.env.VITE_API_KEY === 'string' && import.meta.env.VITE_API_KEY
      ? import.meta.env.VITE_API_KEY
      : ''
  if (apiKey) headers['X-API-Key'] = apiKey
  let token = (explicitToken && explicitToken.trim()) || null
  if (!token) token = localStorage.getItem('access_token')
  if (!token) token = localStorage.getItem('auth_token')
  if (!token) {
    try {
      const authData = localStorage.getItem('rankings_bot_auth')
      if (authData) {
        const parsed = JSON.parse(authData) as { token?: string; access_token?: string }
        token = parsed?.token ?? parsed?.access_token ?? null
      }
    } catch {
      /* ignore */
    }
  }
  if (!token) {
    token = sessionStorage.getItem('access_token') || sessionStorage.getItem('auth_token')
  }
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

/**
 * Stream the per-scraper live log (mirrors streamRebuildWebsiteLog in api/admin.ts).
 * Calls onChunk with each decoded text chunk; resolves when the stream ends or errors.
 */
export async function streamScraperLog(
  scraperName: ScraperName,
  onChunk: (text: string) => void,
  signal?: AbortSignal,
  /** Prefer AuthContext user.token so fetch uses the same session axios already uses. */
  authToken?: string | null,
): Promise<void> {
  const url = `${API_BASE_URL}/rankings/scrapers/${scraperName}/log`
  const res = await fetch(url, { headers: _scraperAuthHeaders(authToken), signal })
  if (!res.ok) throw new Error(res.statusText || `Failed to stream scraper log (HTTP ${res.status})`)
  const reader = res.body?.getReader()
  if (!reader) throw new Error('No response body')
  const dec = new TextDecoder()
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      if (value) onChunk(dec.decode(value, { stream: true }))
    }
    const tail = dec.decode()
    if (tail) onChunk(tail)
  } finally {
    reader.releaseLock()
  }
}

export interface Ranking {
  id?: number
  name: string
  rank: number
  points: number
  country?: string
  license_number?: string
  fargo_rating?: number | null
  fargo_robustness?: number | null
  est_rating?: number | null
  est_rating_confidence?: number | null
  est_rating_robustness?: number | null
  /** 1 = trending up, -1 = trending down, 0 or undefined = stable */
  est_rating_trend?: number | null
  stops_played?: number
  alfa_rating?: number | null
  date: string
  /** All other columns from source (Heyball 18, WPA, WPBA PDF) merged from source_data */
  [key: string]: string | number | null | undefined
}

/** Payload for updating a ranking row (Director/Admin). */
export interface RankingRowUpdatePayload {
  name?: string
  rank?: number
  points?: number
  country?: string
  license_number?: string
  stops_played?: number
}

export interface RankingsResponse {
  total: number
  limit: number
  offset: number
  count: number
  rankings: Ranking[]
  association: string
}

/** History entry from API (date, rank, points) */
export interface RankingHistoryEntry {
  date: string
  rank: number
  points: number
}

export interface PlayerData {
  player_name: string
  wpba: {
    current: (Ranking | RankingHistoryEntry) | null
    history: RankingHistoryEntry[]
  }
  wpa: {
    current: (Ranking | RankingHistoryEntry) | null
    history: RankingHistoryEntry[]
  }
}

export interface LastUpdateResponse {
  wpba: string | null
  wpa: string | null
}

export interface SnapshotsResponse {
  system: string
  snapshot_dates: string[]
}

export interface DataQualityIssue {
  check: string
  severity: 'error' | 'warning'
  message: string
  count?: number
  system?: string
  details?: unknown[]
}

export interface DataQualityResponse {
  passed: boolean
  issues_count: number
  warnings_count: number
  issues: DataQualityIssue[]
}

export interface AuditLogEntry {
  id: number
  created_at: string
  actor_role: string
  actor_subject: string
  action: string
  details?: Record<string, unknown>
}

export interface AuditLogResponse {
  entries: AuditLogEntry[]
}

export interface PlayersWithoutFargoPlayer {
  name: string
  source?: string
}

export interface PlayersWithoutFargoResponse {
  players: PlayersWithoutFargoPlayer[]
  from_players_table: number
  from_rankings: number
}

/** Single movement (ranking change) entry from API */
export interface MovementEntry {
  player_name: string
  ranking_system: string
  old_rank: number | null
  new_rank: number | null
  old_points: number | null
  new_points: number | null
  change_date: string
  change_type: string
}

export interface MovementResponse {
  system: string
  movement: MovementEntry[]
}

export interface RefreshResponse {
  timestamp: string
  wpba_women: {
    success: boolean
    count: number
    error: string | null
    message?: string
    tournament_imports_created?: number
    skipped_no_weights?: boolean
    skipped_message?: string
  }
  wpa_women: {
    success: boolean
    count: number
    error: string | null
  }
  wpa_men: {
    success: boolean
    count: number
    error: string | null
  }
  metadata: {
    success: boolean
    error: string | null
  }
  // Legacy fields for backwards compatibility
  wpba: {
    success: boolean
    count: number
    error: string | null
    message?: string
    tournament_imports_created?: number
    skipped_no_weights?: boolean
    skipped_message?: string
  }
  wpa: {
    success: boolean
    count: number
    error: string | null
  }
}

export function createRankingsApi(rankingsPath: string = '/rankings') {
  const R = rankingsPath.replace(/\/$/, '') || '/rankings'

  return {
  getWPBA: async (limit = 100, offset = 0): Promise<RankingsResponse> => {
    const response = await apiClient.get(`${R}/wpba`, {
      params: { limit, offset }
    })
    return response.data
  },
  
  getWPBAWomen: async (limit = 100, offset = 0): Promise<RankingsResponse> => {
    const response = await apiClient.get(`${R}/wpba-women`, {
      params: { limit, offset }
    })
    return response.data
  },
  
  getWPA: async (limit = 100, offset = 0): Promise<RankingsResponse> => {
    const response = await apiClient.get(`${R}/wpa`, {
      params: { limit, offset }
    })
    return response.data
  },
  
  getWPAWomen: async (limit = 100, offset = 0): Promise<RankingsResponse> => {
    const response = await apiClient.get(`${R}/wpa-women`, {
      params: { limit, offset }
    })
    return response.data
  },
  
  getWPAMen: async (limit = 100, offset = 0): Promise<RankingsResponse> => {
    const response = await apiClient.get(`${R}/wpa-men`, {
      params: { limit, offset }
    })
    return response.data
  },

  getWPAHeyballMen: async (limit = 100, offset = 0): Promise<RankingsResponse> => {
    const response = await apiClient.get(`${R}/wpa-heyball-men`, {
      params: { limit, offset }
    })
    return response.data
  },

  getWPAHeyballWomen: async (limit = 100, offset = 0): Promise<RankingsResponse> => {
    const response = await apiClient.get(`${R}/wpa-heyball-women`, {
      params: { limit, offset }
    })
    return response.data
  },

  getWPAArtistic: async (limit = 100, offset = 0): Promise<RankingsResponse> => {
    const response = await apiClient.get(`${R}/wpa-artistic`, {
      params: { limit, offset }
    })
    return response.data
  },

  // CP Rankings
  getCp9Ball: async (limit = 100, offset = 0): Promise<RankingsResponse> => {
    const response = await apiClient.get(`${R}/cp-9ball`, {
      params: { limit, offset }
    })
    return response.data
  },

  getCp10Ball: async (limit = 100, offset = 0): Promise<RankingsResponse> => {
    const response = await apiClient.get(`${R}/cp-10ball`, {
      params: { limit, offset }
    })
    return response.data
  },

  getCp8Ball: async (limit = 100, offset = 0): Promise<RankingsResponse> => {
    const response = await apiClient.get(`${R}/cp-8ball`, {
      params: { limit, offset }
    })
    return response.data
  },

  getCpWomen9Ball: async (limit = 100, offset = 0): Promise<RankingsResponse> => {
    const response = await apiClient.get(`${R}/cp-women-9ball`, {
      params: { limit, offset }
    })
    return response.data
  },

  getCpMen9Ball: async (limit = 100, offset = 0): Promise<RankingsResponse> => {
    const response = await apiClient.get(`${R}/cp-men-9ball`, {
      params: { limit, offset }
    })
    return response.data
  },

  /** Dynamic WPBA tournament systems (one button per tournament) for Rankings submenu. */
  getWpbaTournamentSystems: async (): Promise<{ systems: { ranking_system: string; label: string }[] }> => {
    const response = await apiClient.get(`${R}/wpba-tournament-systems`)
    return response.data
  },

  /** Dynamic WPA Men tournament systems for Rankings submenu. */
  getWpaMenTournamentSystems: async (): Promise<{ systems: { ranking_system: string; label: string }[] }> => {
    const response = await apiClient.get(`${R}/wpa-men-tournament-systems`)
    return response.data
  },

  /** Dynamic WPA Women tournament systems for Rankings submenu. */
  getWpaWomenTournamentSystems: async (): Promise<{ systems: { ranking_system: string; label: string }[] }> => {
    const response = await apiClient.get(`${R}/wpa-women-tournament-systems`)
    return response.data
  },

  /** Fetch rankings for any system (e.g. WPA_Men_Yalin_8Ball, one button per column). */
  getBySystem: async (rankingSystem: string, limit = 100, offset = 0): Promise<RankingsResponse> => {
    const response = await apiClient.get(`${R}/by-system/${encodeURIComponent(rankingSystem)}`, {
      params: { limit, offset }
    })
    return response.data
  },

  /** Update a single ranking row (fix name, points, country, etc.). Director or Admin only. */
  updateRankingRow: async (rowId: number, body: RankingRowUpdatePayload): Promise<{ message: string; row_id: number }> => {
    const response = await apiClient.patch(`${R}/rows/${rowId}`, body)
    return response.data
  },

  /** Distinct player names from rankings (for Head-to-Head, Player Performance dropdowns). */
  getPlayerNames: async (limit = 2000): Promise<{ names: string[] }> => {
    const response = await apiClient.get(`${R}/player-names`, { params: { limit } })
    return response.data
  },

  getPlayer: async (playerName: string): Promise<PlayerData> => {
    const response = await apiClient.get(`${R}/player/${encodeURIComponent(playerName)}`)
    return response.data
  },
  
  refresh: async (tournamentName?: string): Promise<RefreshResponse> => {
    const params = tournamentName?.trim() ? { tournament_name: tournamentName.trim() } : {}
    const response = await apiClient.post(`${R}/refresh`, null, { params })
    return response.data
  },

  /**
   * Load WPBA rankings from the official PDF (director/admin). Fire-and-forget:
   * the API spawns a background thread and returns immediately. Watch progress by
   * calling `streamLog('/rankings/refresh-wpba/log', ...)` from `@/api/liveLogStream`.
   */
  refreshWpba: async (): Promise<LiveLogStarted> => {
    const response = await apiClient.post(`${R}/refresh-wpba`, null, {
      timeout: SCRAPER_HTTP_TIMEOUT_MS,
    })
    return response.data as LiveLogStarted
  },

  /**
   * Run an individual scraper (super admin only). Fire-and-forget:
   * the API spawns a background thread and returns immediately. Use
   * `streamScraperLog(scraperName, ...)` to follow live progress.
   */
  runScraper: async (scraperName: ScraperName): Promise<RunScraperResponse> => {
    const response = await apiClient.post(`${R}/scrapers/${scraperName}/run`, null, {
      timeout: SCRAPER_HTTP_TIMEOUT_MS,
    })
    return response.data as RunScraperResponse
  },

  getLastUpdate: async (): Promise<LastUpdateResponse> => {
    try {
      const response = await apiClient.get(`${R}/last-update`)
      return response.data
    } catch (error: any) {
      // Return default if endpoint doesn't exist
      if (error.response?.status === 404) {
        return { wpba: null, wpa: null }
      }
      throw error
    }
  },

  /** List snapshot dates for a system (for trend views). Newest first. */
  getSnapshots: async (system: 'WPBA' | 'WPA', limit = 30): Promise<SnapshotsResponse> => {
    const response = await apiClient.get(`${R}/snapshots`, {
      params: { system, limit }
    })
    return response.data
  },

  /** Data quality checks: duplicate players, missing/invalid fields, point consistency. */
  getDataQuality: async (): Promise<DataQualityResponse> => {
    const response = await apiClient.get(`${R}/quality`)
    return response.data
  },

  /** Audit log: who submitted what (Director/Admin only). */
  getAuditLog: async (limit = 50): Promise<AuditLogResponse> => {
    const response = await apiClient.get(`${R}/audit`, { params: { limit } })
    return response.data
  },

  /** Recent ranking changes (movement) for a system. Newest first. */
  getMovement: async (system: 'WPBA' | 'WPA', limit = 50): Promise<MovementResponse> => {
    const response = await apiClient.get(`${R}/movement`, { params: { system, limit } })
    return response.data
  },

  /** Subscribe to email when a player's ranking changes. No auth. */
  notifySubscribe: async (email: string, playerName: string, system: string): Promise<{ ok: boolean; message: string }> => {
    const response = await apiClient.post(`${R}/notify-subscribe`, {
      email: email.trim().toLowerCase(),
      player_name: playerName.trim(),
      system,
    })
    return response.data
  },

  /** Download rankings DB backup (Admin only). Returns blob for download. */
  getBackup: async (): Promise<Blob> => {
    const response = await apiClient.get(`${R}/backup`, { responseType: 'blob' })
    return response.data
  },

  /** List players without a Fargo rating (Admin only). */
  getPlayersWithoutFargo: async (): Promise<PlayersWithoutFargoResponse> => {
    const response = await apiClient.get(`${R}/players-without-fargo`)
    return response.data
  },

  /** Export players without Fargo as plain text (Admin only). */
  exportPlayersWithoutFargo: async (): Promise<Blob> => {
    const response = await apiClient.get(`${R}/players-without-fargo/export`, {
      responseType: 'blob',
    })
    return response.data
  },

  /** Systems/scopes the current user may use for file and manual import (Director filtered by association). */
  getImportEligibility: async (): Promise<ImportEligibilityResponse> => {
    const response = await apiClient.get(`${R}/import/eligibility`)
    return response.data
  },

  /** Import rankings from file (PDF, DOCX, XLSX, XML, CSV, TXT). Director or Admin only. */
  importFile: async (file: File, system: string): Promise<{ message: string; count: number; system: string }> => {
    const form = new FormData()
    form.append('file', file)
    const response = await apiClient.post(`${R}/import?system=${system}`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  /** Import rankings from manually entered rows. Director or Admin only. system = game type column (WPBA, WPA Men, 8-Ball, 9-Ball, etc.). */
  importManual: async (
    system: string,
    rows: { rank: number; name: string; points?: number; country?: string }[]
  ): Promise<{ message: string; count: number; system: string }> => {
    const response = await apiClient.post(`${R}/import/manual`, { system, rows })
    return response.data
  },

  /** Copy latest snapshot from one ranking system to others (populate buttons from imported data). Director or Admin only. */
  copyFromImport: async (
    source: string,
    targets: string[]
  ): Promise<{ message: string; source: string; targets: Record<string, number>; total: number }> => {
    const response = await apiClient.post(`${R}/copy-from-import`, { source, targets })
    return response.data
  },

  /** Tournament definitions: list (Director/Admin). */
  getTournamentDefinitions: async (): Promise<{ definitions: TournamentDefinition[] }> => {
    const response = await apiClient.get(`${R}/tournament-definitions`)
    return response.data
  },

  /** Tournament definitions: create (Director/Admin). */
  createTournamentDefinition: async (body: {
    name: string
    points_by_place: number[]
    is_default_for_import?: boolean
  }): Promise<{ id: number; definition: TournamentDefinition }> => {
    const response = await apiClient.post(`${R}/tournament-definitions`, body)
    return response.data
  },

  /** Tournament definitions: update (Director/Admin). */
  updateTournamentDefinition: async (
    id: number,
    body: { name?: string; points_by_place?: number[]; is_default_for_import?: boolean }
  ): Promise<{ definition: TournamentDefinition }> => {
    const response = await apiClient.put(`${R}/tournament-definitions/${id}`, body)
    return response.data
  },

  /** Tournament definitions: set as default for import (Director/Admin). */
  setDefaultTournamentDefinition: async (id: number): Promise<{ definition: TournamentDefinition }> => {
    const response = await apiClient.post(`${R}/tournament-definitions/${id}/set-default`)
    return response.data
  },

  /** Tournament definitions: delete (Director/Admin). */
  deleteTournamentDefinition: async (id: number): Promise<{ ok: boolean }> => {
    const response = await apiClient.delete(`${R}/tournament-definitions/${id}`)
    return response.data
  },

  /** Tournament imports: list (Director/Admin). */
  getTournamentImports: async (system: 'WPBA' | 'WPA' = 'WPBA'): Promise<{ imports: TournamentImport[] }> => {
    const response = await apiClient.get(`${R}/tournament-imports`, { params: { system } })
    return response.data
  },

  /** Tournament imports: get one (Director/Admin). */
  getTournamentImport: async (id: number): Promise<TournamentImport> => {
    const response = await apiClient.get(`${R}/tournament-imports/${id}`)
    return response.data
  },

  /** Tournament imports: update name and/or weights (Director/Admin). */
  updateTournamentImport: async (
    id: number,
    body: { name?: string; points_by_place?: number[] }
  ): Promise<{ import: TournamentImport }> => {
    const response = await apiClient.put(`${R}/tournament-imports/${id}`, body)
    return response.data
  },

  /** Tournament imports: confirm (Director/Admin). */
  confirmTournamentImport: async (id: number): Promise<{ import: TournamentImport }> => {
    const response = await apiClient.post(`${R}/tournament-imports/${id}/confirm`)
    return response.data
  },

  /** Tournament imports: merge confirmed into rankings (Director/Admin). */
  updateRankingsFromTournamentImports: async (
    system: 'WPBA' | 'WPA' = 'WPBA'
  ): Promise<{ message: string; count: number; system: string }> => {
    const response = await apiClient.post(`${R}/tournament-imports/update-rankings`, null, {
      params: { system },
    })
    return response.data
  },

  /** Tournament imports: delete (Director/Admin). */
  deleteTournamentImport: async (id: number): Promise<{ ok: boolean }> => {
    const response = await apiClient.delete(`${R}/tournament-imports/${id}`)
    return response.data
  },
  }
}

export const rankingsApi = createRankingsApi()

export interface TournamentImport {
  id: number
  name: string
  raw_results: { rank: number; name: string; points: number; country?: string }[]
  points_by_place: number[]
  status: 'incomplete' | 'complete' | 'confirmed'
  ranking_system: string
  created_at?: string
  updated_at?: string
}

export interface TournamentDefinition {
  id: number
  name: string
  points_by_place: number[]
  is_default_for_import: boolean
  created_at?: string
  updated_at?: string
}

/** GET /rankings/import/eligibility — systems a director may import (from user_associations). */
export interface ImportEligibilityResponse {
  role: string
  scopes: string[]
  allowed_systems: string[]
  full_access: boolean
  dynamic_patterns: { pattern: string; scope: string }[]
  needs_association_assignment: boolean
}
