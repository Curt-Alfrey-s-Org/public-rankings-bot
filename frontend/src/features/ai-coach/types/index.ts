/**
 * AI Coach component prop types and shared types
 * @module features/ai-coach/types
 */

import type { AnalysisHistory, AnalysisResult, SubmitAnalysisRequest } from './api'

export * from './api'

/** Props for UploadForm component */
export interface UploadFormProps {
  onSubmit: (request: SubmitAnalysisRequest) => void | Promise<void>
  isSubmitting?: boolean
  error?: string | null
  maxFrames?: number
  maxVideoDurationSeconds?: number
}

/** Props for ResultsDisplay component */
export interface ResultsDisplayProps {
  result: AnalysisResult | null | undefined
  status?: 'pending' | 'processing' | 'completed' | 'failed'
  progress?: number
  errorMessage?: string | null
}

/** Props for UsageMeter component */
export interface UsageMeterProps {
  tier: string
  analysesUsed: number
  analysesLimit: number | null
  analysesRemaining: number
  maxVideoDurationSeconds: number
  monthResetDate?: string
}

/** Props for AnalysisHistory component */
export interface AnalysisHistoryProps {
  analyses: AnalysisHistory[]
  total: number
  limit: number
  offset: number
  onPageChange?: (offset: number) => void
  onEdit?: (analysisId: string, summary: string | null) => void | Promise<void>
  onDelete?: (analysisId: string) => void | Promise<void>
  onProgression?: (analysisId: string) => void
  isLoading?: boolean
}
