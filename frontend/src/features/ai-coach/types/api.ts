/**
 * AI Coach API Types
 * @module features/ai-coach/types/api
 */

/** Analysis submission response from POST /api/ai-coach/analyze */
export interface AnalysisResponse {
  analysis_id: string
  status: 'pending' | 'processing'
  estimated_time_seconds: number
  message: string
}

/** Poll response from GET /api/ai-coach/analyses/{id}/poll */
export interface PollResponse {
  analysis_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number
  result?: AnalysisResult
  results?: AnalysisResult
  error_message?: string
  estimated_remaining_seconds?: number
}

/** Full analysis result from Grok (stroke mechanics, strategy, drills, etc.) */
export interface AnalysisResult {
  stroke_mechanics?: { score?: number; strengths?: string[]; improvements?: string[]; technical_notes?: string }
  strategy?: { score?: number; strengths?: string[]; improvements?: string[]; analysis?: string }
  mental_game?: { score?: number; observations?: string[]; pressure_handling?: string }
  performance_stats?: { balls_made?: number; shots_attempted?: number; accuracy_percent?: number }
  praise?: string[]
  improvements?: string[]
  critical_focus_area?: string
  daily_drills?: Array<{
    name?: string
    objective?: string
    setup?: string
    success_criteria?: string
    duration_minutes?: number
    frequency?: string
  }>
  overall_assessment?: {
    skill_estimate?: string
    six_month_goals?: string[]
    recommended_focus_hours_per_week?: number
  }
  overall_score?: number
}

/** Usage meter response from GET /api/ai-coach/usage */
export interface UsageResponse {
  tier: TierName
  analyses_used: number
  analyses_limit: number | null
  analyses_remaining: number
  lifetime_analyses: number
  lifetime_limit: number | null
  max_video_duration_seconds: number
  trial_expires_at?: string | null
  discount_percent: number
  discount_expires_at?: string | null
  month_reset_date: string
}

/** Tier configuration with limits */
export interface TierConfig {
  name: string
  monthly_limit: number | null
  lifetime_limit: number | null
  max_video_duration: number
  price_monthly: number
  features: string[]
}

/** Tier names */
export type TierName = 'FREEBIE' | 'ROOKIE' | 'WEEKEND_WARRIOR' | 'POOL_SHARK' | 'PRO'

/** Tier config map */
export type TierConfigMap = Record<TierName, TierConfig>

/** History item from GET /api/ai-coach/history */
export interface AnalysisHistory {
  analysis_id: string
  created_at: string
  title: string
  status: string
  overall_score?: number
  summary?: string
}

/** Request payload for POST /api/ai-coach/analyze */
export interface SubmitAnalysisRequest {
  bot_type: 'rankings' | 'trading' | 'contracts' | 'credit'
  video_source: 'youtube' | 'upload'
  video_url?: string
  frames_base64?: string[]
  transcript?: string
  promo_code?: string
  player_name?: string
  opponent_name?: string
  /** Optional: help AI distinguish players in video */
  player_hair_color?: string
  player_shirt_color?: string
  opponent_hair_color?: string
  opponent_shirt_color?: string
}

/** Game metadata for analysis */
export interface GameInfo {
  player_name?: string
  opponent_name?: string
  game_format?: string
}

/** Coupon redeem request */
export interface RedeemCodeRequest {
  code: string
}

/** Coupon redeem response */
export interface RedeemCodeResponse {
  success: boolean
  message: string
  tier_granted?: string
  duration_days?: number
}

/** Payment intent creation request */
export interface PaymentIntentRequest {
  hours?: number
  amount_cents?: number
}

/** Payment intent creation response */
export interface PaymentIntentResponse {
  client_secret: string
  intent_id: string
  status: string
  amount: number
}

/** Payment confirmation request */
export interface ConfirmPaymentRequest {
  payment_intent_id: string
}

/** Payment confirmation response */
export interface ConfirmPaymentResponse {
  intent_id: string
  status: string
  hours_added: number
  hours_remaining: number
}

/** Referral info response for influencers */
export interface ReferralResponse {
  code: string
  total_referrals: number
  active_conversions: number
  revenue_generated: number
  bonus_earned: number
  upcoming_bonuses: Record<string, number>
}
