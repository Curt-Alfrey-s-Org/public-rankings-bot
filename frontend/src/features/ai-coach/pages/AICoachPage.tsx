/**
 * AICoachPage - Main layout for AI Coach feature
 * @module features/ai-coach/pages/AICoachPage
 */

import { useState, useEffect } from 'react'
import { UploadForm } from '../components/UploadForm'
import { ResultsDisplay } from '../components/ResultsDisplay'
import { UsageMeter } from '../components/UsageMeter'
import { AnalysisHistoryList } from '../components/AnalysisHistory'
import { ProgressionUpload } from '../components/ProgressionUpload'
import {
  useSubmitAnalysis,
  usePollAnalysis,
  useAnalysisHistory,
  useUpdateAnalysis,
  useDeleteAnalysis,
  useUsageMeter,
} from '../hooks'
import type { SubmitAnalysisRequest } from '../types'
import { logger } from '@/lib/logger'

const AI_COACH_ANALYSIS_KEY = 'ai-coach-analysis-id'

/** How to use AI Coach — steps and behavior (video discard, edit/delete, progression, throttling) */
function InstructionsBlock() {
  const [open, setOpen] = useState(false)
  return (
    <div className="rounded-lg border border-slate-600 bg-slate-800/50 p-3">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between text-left text-slate-300 hover:text-white"
      >
        <span className="font-medium">How to use AI Coach</span>
        <span className="text-slate-500">{open ? '▼' : '▶'}</span>
      </button>
      {open && (
        <ul className="mt-3 space-y-2 text-sm text-slate-400">
          <li><strong className="text-slate-300">Video:</strong> Paste a YouTube URL or upload a short clip (phone, tablet, or PC).</li>
          <li><strong className="text-slate-300">Analysis:</strong> After the AI runs, only the written assessment is kept; your video is not stored.</li>
          <li><strong className="text-slate-300">Edit or delete:</strong> Use Edit or Delete on any past assessment in Your Coaching History below.</li>
          <li><strong className="text-slate-300">Progression:</strong> You can later compare a past assessment with a new video to see how you’ve improved.</li>
          <li><strong className="text-slate-300">Fair use:</strong> There is a per-hour limit for most accounts; admins are exempt.</li>
        </ul>
      )}
    </div>
  )
}

/** Minimal valid JPEG base64 for demo (1x1 pixel) */
const DEMO_FRAMES = [
  '/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBEQACEQADAPgA/9k=',
  '/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBEQACEQADAPgA/9k=',
  '/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBEQACEQADAPgA/9k=',
]

/** Main AI Coach page with upload, results, usage, and history */
export function AICoachPage() {
  const [analysisId, setAnalysisId] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem(AI_COACH_ANALYSIS_KEY) || null
    } catch (error) {
      logger.warn('Failed to load AI Coach analysis session key', undefined, error as Error)
      return null
    }
  })
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [progressionFromId, setProgressionFromId] = useState<string | null>(null)

  useEffect(() => {
    if (analysisId) {
      try {
        sessionStorage.setItem(AI_COACH_ANALYSIS_KEY, analysisId)
      } catch (error) {
        logger.warn('Failed to persist AI Coach analysis session key', { analysisId }, error as Error)
      }
    } else {
      try {
        sessionStorage.removeItem(AI_COACH_ANALYSIS_KEY)
      } catch (error) {
        logger.warn('Failed to clear AI Coach analysis session key', undefined, error as Error)
      }
    }
  }, [analysisId])

  const { mutate: submitAnalysis, isPending: isSubmitting } = useSubmitAnalysis({
    onSuccess: (data) => {
      setAnalysisId(data.analysis_id)
      setSubmitError(null)
    },
    onError: (err) => {
      setSubmitError(err instanceof Error ? err.message : 'Analysis failed')
    },
  })

  const { data: pollData } = usePollAnalysis(analysisId)
  const { data: usageData } = useUsageMeter()
  const { data: historyData, isLoading: historyLoading } = useAnalysisHistory(20, 0)
  const { mutateAsync: updateAnalysis } = useUpdateAnalysis()
  const { mutateAsync: deleteAnalysis } = useDeleteAnalysis()

  const handleSubmit = (request: SubmitAnalysisRequest) => {
    const withFrames: SubmitAnalysisRequest = {
      ...request,
      frames_base64: request.frames_base64 ?? DEMO_FRAMES,
    }
    submitAnalysis(withFrames)
  }

  const handleDemoSubmit = () => {
    submitAnalysis({
      bot_type: 'rankings',
      video_source: 'upload',
      frames_base64: DEMO_FRAMES,
    })
  }

  const handleNewAnalysis = () => {
    setAnalysisId(null)
    setSubmitError(null)
    try {
      sessionStorage.removeItem(AI_COACH_ANALYSIS_KEY)
    } catch (error) {
      logger.warn('Failed to clear AI Coach analysis session key on new analysis', undefined, error as Error)
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-4">
      <header>
        <h1 className="text-2xl font-bold text-white">AI Pool Coach</h1>
        <p className="mt-1 text-slate-400">
          Send a short practice clip or a YouTube link and get plain-language feedback on your game.
        </p>
      </header>

      <InstructionsBlock />

      {usageData && (
        <UsageMeter
          tier={usageData.tier}
          analysesUsed={usageData.analyses_used}
          analysesLimit={usageData.analyses_limit}
          analysesRemaining={usageData.analyses_remaining}
          maxVideoDurationSeconds={usageData.max_video_duration_seconds}
          monthResetDate={usageData.month_reset_date}
        />
      )}

      {!pollData || pollData.status === 'pending' || pollData.status === 'processing' ? (
        <>
          <UploadForm
            onSubmit={handleSubmit}
            isSubmitting={isSubmitting}
            error={submitError}
          />
          <p className="text-sm text-slate-500">
            Or{' '}
            <button
              type="button"
              onClick={handleDemoSubmit}
              disabled={isSubmitting}
              className="text-sky-400 hover:underline disabled:opacity-50"
            >
              try a quick demo (sample frames)
            </button>
          </p>
        </>
      ) : pollData.status === 'completed' ? (
        <div>
          <div className="mb-4 rounded-lg border border-green-800 bg-green-900/20 p-3 text-green-200">
            Analysis complete
          </div>
          <ResultsDisplay
            result={pollData.result ?? pollData.results}
            status="completed"
            progress={100}
          />
          <button
            type="button"
            onClick={handleNewAnalysis}
            className="mt-4 rounded-lg border border-slate-600 px-4 py-2 text-slate-300 hover:bg-slate-800"
          >
            New analysis
          </button>
        </div>
      ) : pollData.status === 'failed' ? (
        <div>
          <ResultsDisplay
            result={null}
            status="failed"
            errorMessage={pollData.error_message}
          />
          <button
            type="button"
            onClick={handleNewAnalysis}
            className="mt-4 rounded-lg border border-red-700 px-4 py-2 text-red-200 hover:bg-red-900/50"
          >
            Try again
          </button>
        </div>
      ) : null}

      {(pollData?.status === 'pending' || pollData?.status === 'processing') && (
        <ResultsDisplay
          result={null}
          status={pollData.status}
          progress={pollData.progress}
        />
      )}

      {progressionFromId && (
        <ProgressionUpload
          previousAnalysisId={progressionFromId}
          onSubmitted={(newAnalysisId) => {
            setAnalysisId(newAnalysisId)
            setProgressionFromId(null)
          }}
          onCancel={() => setProgressionFromId(null)}
        />
      )}

      {historyData && (
        <AnalysisHistoryList
          analyses={historyData.analyses}
          total={historyData.total}
          limit={historyData.limit}
          offset={historyData.offset}
          isLoading={historyLoading}
          onEdit={async (id, summary) => {
            await updateAnalysis({ analysisId: id, summary_text: summary ?? undefined })
          }}
          onDelete={async (id) => {
            await deleteAnalysis(id)
          }}
          onProgression={(id) => setProgressionFromId(id)}
        />
      )}
    </div>
  )
}
