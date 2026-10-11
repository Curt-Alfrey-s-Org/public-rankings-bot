/**
 * System API functions
 */

import apiClient from './client'

export interface SelfTestResult {
  name: string
  status: 'PASS' | 'FAIL'
  passed: boolean
  error?: string
}

export interface SystemHealthResponse {
  status: 'healthy' | 'degraded' | 'error'
  self_test: {
    passed: boolean
    total: number
    passed_count: number
    failed_count: number
    success_rate: number
    results: SelfTestResult[]
    timings?: {
      total_duration_ms: number
      total_duration_s: number
      start_time: string
      end_time: string
      test_timings?: Record<string, number>
    }
    error?: string
  }
  startup_timings?: Record<string, {
    duration_s: number
    duration_ms: number
    timestamp: string
  }>
  system?: {
    platform: string
    python_version: string
  }
  error?: string
}

export interface SystemInfoResponse {
  system: {
    platform: string
    platform_version?: string
    architecture?: string
    processor?: string
    python_version: string
  }
  resources: {
    cpu_count?: number
    memory_total?: number
    memory_available?: number
    memory_percent?: number
    disk_usage?: {
      total: number
      used: number
      free: number
      percent: number
    }
    note?: string
  }
  error?: string
}

/** Last built-in self-check snapshot (from GET /system/health) for the fail-details popup. */
export interface RunTestsResponse {
  success: boolean
  total: number
  passed: number
  failed: number
  warnings: number
  duration_s: number
  failed_tests?: Array<{
    name: string
    passed: boolean
    error?: string
  }>
  output?: string
  error?: string
  timestamp: string
  source?: 'health'
}

export interface ModuleLightsResponse {
  modules: Record<string, {
    status: 'ok' | 'loading' | 'down'
    message: string
  }>
  error?: string
}

/** GET /api/app-version — pairing + force-update (see UpdateRequiredGate). */
export interface AppVersionResponse {
  version: string
  min_app_version: string
  build_hash: string
}

export const systemApi = {
  getHealth: async (): Promise<SystemHealthResponse> => {
    const response = await apiClient.get<SystemHealthResponse>('/system/health')
    return response.data
  },

  getSystemInfo: async (): Promise<SystemInfoResponse> => {
    const response = await apiClient.get<SystemInfoResponse>('/system')
    return response.data
  },

  getModuleLights: async (): Promise<ModuleLightsResponse> => {
    const response = await apiClient.get<ModuleLightsResponse>('/system/module-lights')
    return response.data
  },

  getAppVersion: async (): Promise<AppVersionResponse> => {
    const response = await apiClient.get<AppVersionResponse>('/app-version', {
      skipGlobalErrorUI: true,
    })
    return response.data
  },
}
