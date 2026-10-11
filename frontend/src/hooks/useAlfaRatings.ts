/**
 * React Query hooks for Alfa — aligned with FastAPI /api/alfa routes.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  alfaDashboardApi,
  FilterParams,
  AlfaPredictBody,
  type AlfaRatingsListRow,
} from '@/api/alfaDashboard'

/** Table row shape expected by AlfaPlayerRatings.tsx */
export interface AlfaPlayerTableRow {
  player_id: string
  name: string
  current_rating: number
  fargo_equivalent: number
  games_played: number
  rating_change: number
  experience_level: string
}

export interface PaginatedAlfaPlayers {
  data: AlfaPlayerTableRow[]
  total: number
  page: number
  page_size: number
  pages: number
}

function rowFromRanking(r: AlfaRatingsListRow): AlfaPlayerTableRow {
  const rating = r.alfa_rating ?? r.points ?? 0
  const fargo = r.fargo_rating ?? r.points ?? 0
  return {
    player_id: r.player_name,
    name: r.player_name,
    current_rating: typeof rating === 'number' ? rating : Number(rating) || 0,
    fargo_equivalent: typeof fargo === 'number' ? fargo : Number(fargo) || 0,
    games_played: r.tournaments_analyzed ?? 0,
    rating_change: typeof r.deviation_from_fargo === 'number' ? r.deviation_from_fargo : 0,
    experience_level: 'experienced',
  }
}

function parsePositiveInt(s: string): number | null {
  const n = Number.parseInt(s, 10)
  if (!Number.isFinite(n) || n <= 0) return null
  if (String(n) !== s.trim()) return null
  return n
}

/** GET /alfa/ratings then paginate/filter client-side (API has no server pagination). */
export function useAlfaPlayerRatings(
  params?: FilterParams & {
    rating_min?: number
    rating_max?: number
    experience_level?: string
    last_updated_days?: number
    system?: string
  },
) {
  return useQuery({
    queryKey: ['alfa-players', params],
    queryFn: async (): Promise<PaginatedAlfaPlayers> => {
      const list = await alfaDashboardApi.getAlfaRatings(
        params?.system ? { system: params.system } : undefined,
      )
      let rows = (list.rankings ?? []).map(rowFromRanking)

      const search = params?.search?.trim().toLowerCase()
      if (search) {
        rows = rows.filter((x) => x.name.toLowerCase().includes(search))
      }
      if (params?.rating_min != null) {
        rows = rows.filter((x) => x.current_rating >= params.rating_min!)
      }
      if (params?.rating_max != null) {
        rows = rows.filter((x) => x.current_rating <= params.rating_max!)
      }

      const sortBy = params?.sort_by ?? 'rating'
      const sortOrder = params?.sort_order ?? 'desc'
      const dir = sortOrder === 'asc' ? 1 : -1
      rows = [...rows].sort((a, b) => {
        if (sortBy === 'games') return dir * (a.games_played - b.games_played)
        if (sortBy === 'change') return dir * (a.rating_change - b.rating_change)
        return dir * (a.current_rating - b.current_rating)
      })

      const total = rows.length
      const pageSize = params?.page_size ?? 20
      const page = params?.page ?? 1
      const pages = Math.max(1, Math.ceil(total / pageSize))
      const start = (page - 1) * pageSize
      const data = rows.slice(start, start + pageSize)
      return { data, total, page, page_size: pageSize, pages }
    },
    staleTime: 1000 * 60 * 5,
  })
}

/** Numeric id uses prediction player endpoint; otherwise name-based Alfa player. */
export function useAlfaPlayerDetail(playerId: string | undefined) {
  return useQuery({
    queryKey: ['alfa-player-detail', playerId],
    queryFn: async () => {
      const id = playerId!
      const num = parsePositiveInt(id)
      if (num !== null) {
        return alfaDashboardApi.getPredictionPlayer(num)
      }
      return alfaDashboardApi.getAlfaPlayerByName(id)
    },
    enabled: !!playerId,
    staleTime: 1000 * 60 * 2,
  })
}

export function useAlfaPlayerHistory(playerId: string | undefined, limit?: number) {
  return useQuery({
    queryKey: ['alfa-player-history', playerId, limit],
    queryFn: async () => {
      const id = playerId!
      const num = parsePositiveInt(id)
      if (num === null) {
        return []
      }
      const detail = await alfaDashboardApi.getPredictionPlayer(num)
      const hist = (detail as { rating_history?: unknown[] }).rating_history ?? []
      const lim = limit ?? hist.length
      return Array.isArray(hist) ? hist.slice(0, lim) : []
    },
    enabled: !!playerId && parsePositiveInt(playerId!) !== null,
    staleTime: 1000 * 60 * 5,
  })
}

export function useAlfaPlayerComparison(playerId1?: string, playerId2?: string) {
  const n1 = playerId1 ? parsePositiveInt(playerId1) : null
  const n2 = playerId2 ? parsePositiveInt(playerId2) : null
  return useQuery({
    queryKey: ['alfa-player-comparison', playerId1, playerId2],
    queryFn: () => alfaDashboardApi.getPlayerComparison(n1!, n2!),
    enabled: n1 !== null && n2 !== null,
    staleTime: 1000 * 60 * 10,
  })
}

/** Removed server-side — hooks kept as no-ops so imports do not break during migration. */
export function useAlfaAnomalies(_params?: FilterParams & { severity?: string; flag_type?: string; date_range_days?: number }) {
  return useQuery({
    queryKey: ['alfa-anomalies-removed'],
    queryFn: async () => ({ data: [] as never[], total: 0, page: 1, page_size: 0, pages: 0 }),
    enabled: false,
  })
}

export function useAlfaReviewAnomaly() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      throw new Error('Anomaly review API was removed (Feb 2026).')
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alfa-anomalies'] })
    },
  })
}

export function useAlfaAnomalyStatistics() {
  return useQuery({
    queryKey: ['alfa-anomaly-statistics-removed'],
    queryFn: async () => ({
      anomaly_rate_over_time: [] as { date: string; rate: number }[],
      flag_distribution: {} as Record<string, number>,
    }),
    enabled: false,
  })
}

export function useAlfaPredictionExplain(matchId?: string) {
  return useQuery({
    queryKey: ['alfa-prediction-explain', matchId],
    queryFn: () => alfaDashboardApi.explainPrediction(matchId!),
    enabled: !!matchId?.trim(),
    staleTime: 1000 * 60 * 30,
  })
}

const DEFAULT_PREDICT: Partial<AlfaPredictBody> = {
  race_to: 7,
  table_size: '9ft',
  format: '9-ball',
  location: 'venue_default',
}

export function useAlfaPredictMatch() {
  return useMutation({
    mutationFn: (params: {
      playerId1: string
      playerId2: string
      raceToNumber?: number
      context?: Partial<AlfaPredictBody>
    }) => {
      const p1 = parsePositiveInt(params.playerId1)
      const p2 = parsePositiveInt(params.playerId2)
      if (p1 === null || p2 === null) {
        throw new Error('Prediction requires numeric operator_id and player2_id.')
      }
      const body: AlfaPredictBody = {
        operator_id: p1,
        player2_id: p2,
        race_to: params.raceToNumber ?? DEFAULT_PREDICT.race_to!,
        table_size: (params.context?.table_size as AlfaPredictBody['table_size']) ?? DEFAULT_PREDICT.table_size!,
        format: (params.context?.format as AlfaPredictBody['format']) ?? DEFAULT_PREDICT.format!,
        location: params.context?.location ?? DEFAULT_PREDICT.location!,
        match_id: params.context?.match_id,
      }
      return alfaDashboardApi.predictMatch(body)
    },
  })
}

export function useAlfaABTestResults() {
  return useQuery({
    queryKey: ['alfa-ab-test-removed'],
    queryFn: async () => null,
    enabled: false,
  })
}

export function useAlfaSystemStatus() {
  return useQuery({
    queryKey: ['alfa-system-status'],
    queryFn: () => alfaDashboardApi.getSystemStatusPlaceholder(),
    staleTime: 1000 * 30,
    refetchInterval: 1000 * 60,
  })
}

export function useAlfaSystemHealth() {
  return useQuery({
    queryKey: ['alfa-system-health'],
    queryFn: () => alfaDashboardApi.getAlfaHealthNormalized(),
    staleTime: 1000 * 30,
    refetchInterval: 1000 * 30,
  })
}

export function useAlfaDashboardStats() {
  return useQuery({
    queryKey: ['alfa-dashboard-stats'],
    queryFn: () => alfaDashboardApi.getDashboardStats(),
    staleTime: 1000 * 60 * 5,
  })
}

export function useAlfaRatingAdjustments(_params?: FilterParams & { status?: string }) {
  return useQuery({
    queryKey: ['alfa-rating-adjustments-removed'],
    queryFn: async () => ({ data: [] as never[], total: 0, page: 1, pages: 0 }),
    enabled: false,
  })
}

export function useAlfaSubmitAdjustment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      throw new Error('Rating adjustments API is not implemented on this server.')
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alfa-rating-adjustments'] })
    },
  })
}

export function useAlfaApproveAdjustment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      throw new Error('Rating adjustments API is not implemented on this server.')
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alfa-rating-adjustments'] })
    },
  })
}

export function useAlfaRejectAdjustment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      throw new Error('Rating adjustments API is not implemented on this server.')
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alfa-rating-adjustments'] })
    },
  })
}

export function useAlfaExportRatings(_format: 'csv' | 'json' = 'csv') {
  return useMutation({
    mutationFn: () => alfaDashboardApi.exportRatingsCsvFromApi(),
    onSuccess: (blob) => {
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `alfa-ratings-${new Date().toISOString().split('T')[0]}.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    },
  })
}

export function useAlfaImportAdjustments() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      throw new Error('Import adjustments API is not implemented.')
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['alfa-rating-adjustments'] })
    },
  })
}

export function useAlfaSendNotifications() {
  return useMutation({
    mutationFn: async () => {
      throw new Error('Bulk notify API is not implemented.')
    },
  })
}

export function useAlfaExportPredictionPDF() {
  return useMutation({
    mutationFn: async () => {
      throw new Error('PDF export is not implemented for Alfa predictions.')
    },
  })
}
