/**
 * Logs API functions
 */

import apiClient from './client'

export interface LogEntry {
  raw: string
  timestamp: string
  level: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL' | 'DEBUG'
  logger: string
  message: string
}

export interface LogsResponse {
  logs: LogEntry[]
  total: number
  file: string
  exists: boolean
}

export interface LogsQueryParams {
  limit?: number
  level?: string
  logger_name?: string
  search?: string
  sort_by?: 'timestamp' | 'level' | 'logger'
  sort_order?: 'asc' | 'desc'
  tail?: boolean
}

export const logsApi = {
  getLogs: async (params?: LogsQueryParams): Promise<LogsResponse> => {
    const queryParams = new URLSearchParams()
    if (params?.limit) queryParams.append('limit', params.limit.toString())
    if (params?.level && params.level !== 'all') queryParams.append('level', params.level)
    if (params?.logger_name) queryParams.append('logger_name', params.logger_name)
    if (params?.search) queryParams.append('search', params.search)
    if (params?.sort_by) queryParams.append('sort_by', params.sort_by)
    if (params?.sort_order) queryParams.append('sort_order', params.sort_order)
    if (params?.tail !== undefined) queryParams.append('tail', params.tail.toString())
    
    try {
      const response = await apiClient.get<LogsResponse>(`/logs?${queryParams.toString()}`)
      return response.data
    } catch (error: any) {
      if (error.response?.status === 404) {
        return {
          logs: [],
          total: 0,
          file: '',
          exists: false,
        }
      }
      throw error
    }
  },
}
