/**
 * TypeScript types for Alfa Rating System Dashboard
 */

// Player Rating Data
export interface AlfaPlayer {
  player_id: string
  name: string
  current_rating: number
  fargo_equivalent: number
  games_played: number
  rating_change?: number
  last_updated?: string
  experience_level: 'new' | 'intermediate' | 'experienced'
  converged_percentage: number
  is_anomaly: boolean
  anomaly_score?: number
}

// Rating History Point
export interface RatingHistoryPoint {
  game_number: number
  rating: number
  opponent_rating: number
  result: 'win' | 'loss'
  timestamp: string
}

// Anomaly Detection Data
export interface AnomalyFlag {
  flag_type: 'sudden_jump' | 'winning_weak_only' | 'losing_strong_only' | 'rating_mismatch' | 'variance' | 'break_dominance'
  threshold: number
  actual_value: number
  explanation: string
  severity: 'low' | 'medium' | 'high'
}

export interface AnomalyAlert {
  player_id: string
  name: string
  anomaly_score: number
  severity: 'low' | 'medium' | 'high'
  flags: AnomalyFlag[]
  detected_at: string
  review_status: 'pending' | 'accepted' | 'false_positive' | 'review_later'
}

// Prediction Explainability Data
export interface MatchContext {
  format: string
  table_size: string
  location?: string
}

export interface PredictionExplanation {
  match_id: string
  operator: {
    id: string
    name: string
    rating: number
  }
  player2: {
    id: string
    name: string
    rating: number
  }
  race_to: number
  context: MatchContext
  predicted_probability: {
    operator_win: number
    player2_win: number
    confidence: number
  }
  actual_result?: 'operator' | 'player2'
  factors: {
    rating_gap_contribution: number
    race_to_contribution: number
    context_contribution: number
  }
  fargo_baseline?: number
}

// A/B Test Results
export interface PerformanceMetric {
  name: string
  fargo_value?: number
  logistic_regression_value?: number
  alfa_full_system_value?: number
}

export interface ABTestResults {
  metrics: PerformanceMetric[]
  brier_score: {
    fargo: number
    logistic_regression: number
    alfa_full_system: number
  }
  accuracy: {
    fargo: number
    logistic_regression: number
    alfa_full_system: number
  }
  calibration_rmse: {
    fargo: number
    logistic_regression: number
    alfa_full_system: number
  }
  auc_roc: {
    fargo: number
    logistic_regression: number
    alfa_full_system: number
  }
  log_loss: {
    fargo: number
    logistic_regression: number
    alfa_full_system: number
  }
  by_rating_gap: {
    rating_gap: string
    fargo_accuracy: number
    logistic_regression_accuracy: number
    alfa_full_system_accuracy: number
  }[]
  by_player_type: {
    player_type: 'new' | 'intermediate' | 'experienced'
    fargo_accuracy: number
    logistic_regression_accuracy: number
    alfa_full_system_accuracy: number
  }[]
}

// System Health Data
export interface HealthStatus {
  model_loaded: boolean
  database_connected: boolean
  cache_status: {
    hit_rate: number
    memory_used_mb: number
    total_entries: number
  }
  api_latency: {
    p50: number
    p95: number
    p99: number
  }
}

export interface PredictionMetric {
  timestamp: string
  count: number
}

export interface CacheHitRateMetric {
  timestamp: string
  hit_rate: number
}

export interface APIErrorLog {
  timestamp: string
  endpoint: string
  status_code: number
  error_message: string
}

export interface SystemStatus {
  health: HealthStatus
  predictions_per_hour: PredictionMetric[]
  cache_hit_rate_trend: CacheHitRateMetric[]
  api_errors: APIErrorLog[]
}

// Player Comparison
export interface PlayerComparison {
  operator: AlfaPlayer & {
    history: RatingHistoryPoint[]
    context_analysis: {
      table_preference: Record<string, number>
      format_win_rate: Record<string, number>
      venue_performance: Record<string, number>
    }
    head_to_head_record: {
      vs_player2: {
        wins: number
        losses: number
        fair_match_probability: number
      }
    }
  }
  player2: AlfaPlayer & {
    history: RatingHistoryPoint[]
    context_analysis: {
      table_preference: Record<string, number>
      format_win_rate: Record<string, number>
      venue_performance: Record<string, number>
    }
    head_to_head_record: {
      vs_operator: {
        wins: number
        losses: number
        fair_match_probability: number
      }
    }
  }
  fair_match_recommendation: {
    handicap_rating: number
    suggested_race_to: number
    confidence: number
  }
}

// Rating Adjustment
export interface RatingAdjustment {
  player_id: string
  player_name: string
  old_rating: number
  new_rating: number
  justification: string
  admin_notes: string
  approved_by?: string
  applied_at?: string
  status: 'pending' | 'approved' | 'rejected'
}

// Dashboard Statistics
export interface DashboardStats {
  total_players: number
  new_players: number
  anomalies_detected: number
  predictions_today: number
  avg_rating_change: number
  system_health_score: number
}
