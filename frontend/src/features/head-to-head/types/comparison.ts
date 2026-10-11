/** Head-to-head comparison types */

export interface RankingTrendItem {
  old: number | null
  new: number | null
}

export interface PlayerComparison {
  id: string
  name: string
  rank: number
  fargo_rating: number | null
  alfa_rating?: number | null
  wins?: number
  losses?: number
  win_pct?: number
  ranking_trend?: RankingTrendItem[]
  recent_matches?: unknown[]
}

export interface HeadToHeadMatch {
  id: number
  tournament_id: string
  tournament_name: string
  date: string | null
  location: string
  year: number
  round: number | null
  operator_name: string
  player2_name: string
  operator_score: number | null
  player2_score: number | null
  winner: string
  notes: string | null
}

export interface HeadToHeadRecord {
  direct_wins_p1: number
  direct_losses_p1: number
  fargo_win_probability_p1?: number | null
  fargo_win_probability_p2?: number | null
  common_opponents: unknown[]
  matches: HeadToHeadMatch[]
}

export interface HeadToHeadResponse {
  operator: PlayerComparison
  player2: PlayerComparison
  head_to_head: HeadToHeadRecord
  narrative?: string
  narrative_unchanged?: boolean
}
