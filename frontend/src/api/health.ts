/**
 * Health check API
 */

import apiClient from './client'

export interface HealthDetailedResponse {
  status: 'healthy' | 'degraded' | 'unhealthy'
  service: string
  version: string
  timestamp: string
  uptime_seconds: number | null
  database: {
    status: string
    latency_ms: number | null
    error: string | null
  }
  rankings_db?: {
    status: string
    latency_ms: number | null
    error: string | null
  }
  redis: {
    configured: boolean
    status: string
    latency_ms: number | null
    error: string | null
  }
  error_logs: string[]
}

export const healthApi = {
  getBasic: () => apiClient.get<{ status: string; service: string; version: string }>('/health'),
  getDetailed: () => apiClient.get<HealthDetailedResponse>('/health/detailed'),
}
