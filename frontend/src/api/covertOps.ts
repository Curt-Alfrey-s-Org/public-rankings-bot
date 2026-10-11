/**
 * Covert Ops API
 * Recon: submit opponent ("victim") name; get AI analysis of their latest YouTube match and weaknesses.
 */

import { apiClient } from './client'

export interface ReconRequest {
  victim_name: string
}

export interface ReconResponse {
  victim_name: string
  video_url?: string
  video_title?: string
  weaknesses: string[]
  summary?: string
  status: 'completed' | 'no_video' | 'error'
}

export const covertOpsApi = {
  recon: (victimName: string) =>
    apiClient.post<ReconResponse>('/covert-ops/recon', { victim_name: victimName }).then((r) => r.data),
}
