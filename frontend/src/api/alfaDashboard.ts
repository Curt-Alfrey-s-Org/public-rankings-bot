/**
 * Alfa Rating — calls match FastAPI routes under /api (via api client base URL).
 * Sandbagging/anomaly dashboard APIs were removed server-side (Feb 2026).
 */

import apiClient from './client'

/** Listing row from GET /api/alfa/ratings (alfa.py) */
export interface AlfaRatingsListRow {
  player_name: string
  rank: number
  points: number
  country?: string | null
  ranking_system: string
  fargo_rating?: number | null
  alfa_rating?: number | null
  deviation_from_fargo?: number | null
  tournaments_analyzed?: number | null
}

export interface AlfaRatingsListResponse {
  total: number
  rankings: AlfaRatingsListRow[]
  system?: string | null
}

export interface FilterParams {
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: 'asc' | 'desc'
  search?: string
}

/** Body for POST /api/alfa/predict (required fields per AlfaPredictRequest). */
export interface AlfaPredictBody {
  operator_id: number
  player2_id: number
  race_to: number
  table_size: '7ft' | '8ft' | '9ft' | '10ft' | '8.5ft'
  format: '9-ball' | '10-ball' | '8-ball' | 'mixed'
  location: string
  match_id?: string
}

export interface AlfaHealthResponse {
  status: string
  models?: unknown
  timestamp?: string
}

/** Normalized for dashboard UI (legacy shape expected by some components). */
export interface AlfaHealthNormalized {
  health_score: number
  checks: {
    model_loaded: boolean
    database_connected: boolean
  }
}

function normalizeHealth(h: AlfaHealthResponse): AlfaHealthNormalized {
  const modelLoaded = h.status === 'healthy'
  return {
    health_score: modelLoaded ? 100 : 0,
    checks: {
      model_loaded: modelLoaded,
      database_connected: true,
    },
  }
}

/** Minimal system status when detailed metrics are not exposed by the API. */
export interface AlfaSystemStatusPlaceholder {
  health: {
    api_latency: { p50: number; p95: number; p99: number }
    cache_status: { hit_rate: number }
  }
  predictions_today: number
}

export const alfaDashboardApi = {
  getAlfaRatings: (params?: { system?: string }) =>
    apiClient.get<AlfaRatingsListResponse>('/alfa/ratings', { params }).then((r) => r.data),

  getAlfaSummary: () => apiClient.get('/alfa/summary').then((r) => r.data),

  /** Name-keyed player from Alfa engine list (public-ish Fargo-style page). */
  getAlfaPlayerByName: (playerName: string) =>
    apiClient.get(`/alfa/player/${encodeURIComponent(playerName)}`).then((r) => r.data),

  /** Numeric player id — prediction / ML tables (alfa_ratings router). */
  getPredictionPlayer: (playerId: number) =>
    apiClient.get(`/alfa/player/${playerId}`).then((r) => r.data),

  getPlayerComparison: (playerId1: number, playerId2: number) =>
    apiClient.get(`/alfa/comparison/${playerId1}/${playerId2}`).then((r) => r.data),

  explainPrediction: (matchId: string) =>
    apiClient.post('/alfa/explain', { match_id: matchId }).then((r) => r.data),

  predictMatch: (body: AlfaPredictBody) =>
    apiClient.post('/alfa/predict', body).then((r) => r.data),

  getDashboardStats: () =>
    apiClient.get<{
      total_players: number
      new_players: number
      anomalies_detected: number
      predictions_today: number
      avg_rating_change: number
      system_health_score: number
    }>('/alfa/dashboard/stats').then((r) => r.data),

  getAlfaHealthRaw: () =>
    apiClient.get<AlfaHealthResponse>('/alfa/health').then((r) => r.data),

  getAlfaHealthNormalized: async (): Promise<AlfaHealthNormalized> => {
    const h = await alfaDashboardApi.getAlfaHealthRaw()
    return normalizeHealth(h)
  },

  /** Placeholder until latency/cache metrics are exposed on the API. */
  getSystemStatusPlaceholder: async (): Promise<AlfaSystemStatusPlaceholder> => {
    const stats = await alfaDashboardApi.getDashboardStats()
    return {
      health: {
        api_latency: { p50: 0, p95: 0, p99: 0 },
        cache_status: { hit_rate: 0 },
      },
      predictions_today: stats.predictions_today ?? 0,
    }
  },

  postRecompute: () => apiClient.post('/alfa/recompute').then((r) => r.data),

  /**
   * Build CSV from GET /alfa/ratings (no server export endpoint).
   */
  exportRatingsCsvFromApi: async (system?: string): Promise<Blob> => {
    const data = await alfaDashboardApi.getAlfaRatings(system ? { system } : undefined)
    const rows = data.rankings ?? []
    const header = [
      'player_name',
      'rank',
      'points',
      'country',
      'ranking_system',
      'fargo_rating',
      'alfa_rating',
      'tournaments_analyzed',
    ]
    const esc = (v: unknown) => {
      const s = v === null || v === undefined ? '' : String(v)
      if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`
      return s
    }
    const lines = [header.join(',')]
    for (const r of rows) {
      lines.push(
        [
          esc(r.player_name),
          esc(r.rank),
          esc(r.points),
          esc(r.country),
          esc(r.ranking_system),
          esc(r.fargo_rating),
          esc(r.alfa_rating),
          esc(r.tournaments_analyzed),
        ].join(','),
      )
    }
    return new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  },
}
