/**
 * ALFa Rating API — premium rating system (Fargo on steroids).
 * Sandbagger data requires director/admin or POOL_SHARK+ tier.
 */

import apiClient from './client'

export interface AlfaRatingItem {
  player_name: string
  rank: number
  points: number
  country?: string | null
  ranking_system: string
  alfa_rating: number
  sandbagger_score?: number | null
  sandbagger_flags?: string[] | null
}

export interface AlfaRatingsResponse {
  total: number
  rankings: AlfaRatingItem[]
  system?: string | null
}

export interface AlfaPlayerResponse {
  player_name: string
  rank: number
  points: number
  country?: string | null
  ranking_system: string
  alfa_rating: number
  sandbagger_score?: number | null
  sandbagger_flags?: string[] | null
}

export interface PredictionFactor {
  name: string
  contribution: number
  weight: number
  direction?: string
}

export interface AlfaPredictRequest {
  operator_id: number
  player2_id: number
  race_to: number
  table_size: string
  format: string
  location: string
  match_id?: string
}

export interface AlfaPredictResponse {
  match_id?: string
  predicted_win_prob_p1: number
  predicted_win_prob_p2: number
  factors: PredictionFactor[]
  confidence: number
  predicted_race_length?: number
  prediction_brier_score?: number
  model_version: string
  timestamp: string
}

export const alfaApi = {
  getRatings: (system?: string) =>
    apiClient.get<AlfaRatingsResponse>('/alfa/ratings', { params: system ? { system } : undefined }).then((r) => r.data),
  getPlayer: (playerName: string) =>
    apiClient.get<AlfaPlayerResponse>(`/alfa/player/${encodeURIComponent(playerName)}`).then((r) => r.data),
  predict: (request: AlfaPredictRequest) =>
    apiClient.post<AlfaPredictResponse>('/alfa/predict', request).then((r) => r.data),
}
