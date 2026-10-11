/**
 * AI Coach API - Video analysis, polling, history, usage
 */

import { apiClient } from './client'

export interface AnalyzeRequest {
  bot_type: string
  video_source: 'youtube' | 'upload'
  video_url?: string
  frames_base64?: string[]
  player_name?: string
  opponent_name?: string
  game_format?: string
  transcript?: string
  promo_code?: string
}

export interface AnalyzeResponse {
  analysis_id: string
  status: string
  estimated_time_seconds: number
  message: string
}

export interface PollResponse {
  analysis_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  progress: number  // 0-100
  result?: Record<string, unknown>  // when completed
  results?: Record<string, unknown>  // legacy alias
  error_message?: string
  estimated_remaining_seconds?: number
}

export interface HistoryItem {
  analysis_id: string
  created_at: string
  title: string
  status: string
  overall_score?: number
  summary?: string
}

export interface UsageResponse {
  tier: string
  analyses_used: number
  analyses_limit: number | null
  analyses_remaining: number
  lifetime_analyses: number
  lifetime_limit: number | null
  max_video_duration_seconds: number
  month_reset_date: string
}

export const aiCoachApi = {
  async analyze(body: AnalyzeRequest): Promise<AnalyzeResponse> {
    const { data } = await apiClient.post<AnalyzeResponse>('/ai-coach/analyze', body, {
      timeout: 60000, // 60s for large frame payloads
    })
    return data
  },

  async poll(analysisId: string): Promise<PollResponse> {
    const { data } = await apiClient.get<PollResponse>(`/ai-coach/analyses/${analysisId}/poll`)
    return data
  },

  async getStatus(analysisId: string): Promise<PollResponse> {
    const { data } = await apiClient.get<PollResponse>(`/ai-coach/analyze/${analysisId}`)
    return data
  },

  async getHistory(limit = 20, offset = 0): Promise<{ analyses: HistoryItem[]; total: number; limit: number; offset: number }> {
    const { data } = await apiClient.get('/ai-coach/history', { params: { limit, offset } })
    return data
  },

  async getUsage(): Promise<UsageResponse> {
    const { data } = await apiClient.get<UsageResponse>('/ai-coach/usage')
    return data
  },

  async updateAnalysis(analysisId: string, body: { summary_text?: string | null }): Promise<{ success: boolean; message: string }> {
    const { data } = await apiClient.patch<{ success: boolean; analysis_id: string; message: string }>(
      `/ai-coach/analyses/${analysisId}`,
      body
    )
    return data
  },

  async deleteAnalysis(analysisId: string): Promise<{ success: boolean; message: string }> {
    const { data } = await apiClient.delete<{ success: boolean; message: string }>(
      `/ai-coach/analyses/${analysisId}`
    )
    return data
  },

  async submitProgression(
    previousAnalysisId: string,
    body: { frames_base64: string[]; bot_type?: string; player_name?: string; opponent_name?: string; game_format?: string }
  ): Promise<AnalyzeResponse> {
    const { data } = await apiClient.post<AnalyzeResponse>('/ai-coach/progression', {
      previous_analysis_id: previousAnalysisId,
      bot_type: body.bot_type ?? 'rankings',
      frames_base64: body.frames_base64,
      player_name: body.player_name,
      opponent_name: body.opponent_name,
      game_format: body.game_format,
    }, { timeout: 60000 })
    return data
  },
}
