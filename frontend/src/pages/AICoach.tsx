/**
 * AI Coach Page - Pool/billiards video analysis
 * Upload video frames, poll for results, display coaching feedback
 */

import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { aiCoachApi, type PollResponse, type UsageResponse } from '@/api/aiCoach'

const POLL_INTERVAL_MS = 3000

// Minimal valid JPEG base64 for demo (1x1 pixel) - replace with real frames from ffmpeg.wasm
const DEMO_FRAMES = [
  '/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBEQACEQADAPgA/9k=',
  '/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBEQACEQADAPgA/9k=',
  '/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBEQACEQADAPgA/9k=',
]

export default function AICoach() {
  const [analysisId, setAnalysisId] = useState<string | null>(null)
  const [pollData, setPollData] = useState<PollResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const { data: usage } = useQuery({
    queryKey: ['ai-coach-usage'],
    queryFn: () => aiCoachApi.getUsage(),
  })

  const submitAnalysis = async (frames: string[]) => {
    setError(null)
    setSubmitting(true)
    try {
      const res = await aiCoachApi.analyze({
        bot_type: 'rankings',
        video_source: 'upload',
        frames_base64: frames,
      })
      setAnalysisId(res.analysis_id)
      setPollData({
        analysis_id: res.analysis_id,
        status: res.status as PollResponse['status'],
        progress: 0,
        estimated_remaining_seconds: res.estimated_time_seconds,
      })
    } catch (e: unknown) {
      const msg = e && typeof e === 'object' && 'response' in e
        ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? 'Analysis failed'
        : 'Analysis failed'
      setError(String(msg))
    } finally {
      setSubmitting(false)
    }
  }

  useEffect(() => {
    if (!analysisId) return
    const poll = async () => {
      try {
        const data = await aiCoachApi.poll(analysisId)
        setPollData(data)
        if (data.status === 'completed' || data.status === 'failed') {
          if (pollTimerRef.current) {
            clearInterval(pollTimerRef.current)
            pollTimerRef.current = null
          }
        }
      } catch (e) {
        console.error('Poll error:', e)
      }
    }
    poll()
    pollTimerRef.current = setInterval(poll, POLL_INTERVAL_MS)
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current)
      }
    }
  }, [analysisId])

  const renderResults = () => {
    const r = pollData?.result ?? pollData?.results
    if (!r) return null
    const data = r as Record<string, unknown>
    return (
      <div className="mt-6 space-y-4 rounded-lg bg-slate-800/50 p-4">
        <h3 className="text-lg font-semibold text-sky-400">Coaching Analysis</h3>
        {data.critical_focus_area && (
          <p className="text-slate-200">
            <span className="font-medium text-amber-400">Focus area: </span>
            {String(data.critical_focus_area)}
          </p>
        )}
        {data.stroke_mechanics && typeof data.stroke_mechanics === 'object' && (
          <div>
            <h4 className="font-medium text-slate-300">Stroke mechanics</h4>
            <pre className="mt-1 overflow-auto rounded bg-slate-900/80 p-2 text-sm text-slate-300">
              {JSON.stringify(data.stroke_mechanics, null, 2)}
            </pre>
          </div>
        )}
        {data.strategy && typeof data.strategy === 'object' && (
          <div>
            <h4 className="font-medium text-slate-300">Strategy</h4>
            <pre className="mt-1 overflow-auto rounded bg-slate-900/80 p-2 text-sm text-slate-300">
              {JSON.stringify(data.strategy, null, 2)}
            </pre>
          </div>
        )}
        {data.mental_game && typeof data.mental_game === 'object' && (
          <div>
            <h4 className="font-medium text-slate-300">Mental game</h4>
            <pre className="mt-1 overflow-auto rounded bg-slate-900/80 p-2 text-sm text-slate-300">
              {JSON.stringify(data.mental_game, null, 2)}
            </pre>
          </div>
        )}
        {data.daily_drills && Array.isArray(data.daily_drills) && data.daily_drills.length > 0 && (
          <div>
            <h4 className="font-medium text-slate-300">Daily drills</h4>
            <ul className="mt-1 list-inside list-disc space-y-1 text-slate-300">
              {(data.daily_drills as Record<string, unknown>[]).map((d, i) => (
                <li key={i}>{String(d.name ?? d.objective ?? JSON.stringify(d))}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-4">
      <header>
        <h1 className="text-2xl font-bold text-white">AI Pool Coach</h1>
        <p className="mt-1 text-slate-400">
          Upload your pool session video frames for personalized coaching feedback.
        </p>
      </header>

      {usage && (
        <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-3">
          <p className="text-sm text-slate-300">
            <span className="font-medium text-sky-400">{usage.tier}</span> ·{' '}
            {usage.analyses_remaining} analyses remaining
            {usage.analyses_limit != null && ` (${usage.analyses_used}/${usage.analyses_limit})`}
          </p>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-800 bg-red-900/30 p-3 text-red-200">
          {error}
        </div>
      )}

      {!pollData || pollData.status === 'pending' || pollData.status === 'processing' ? (
        <div className="space-y-4">
          <p className="text-slate-400">
            Extract frames client-side with ffmpeg.wasm, or use the demo to test the flow.
          </p>
          <button
            onClick={() => submitAnalysis(DEMO_FRAMES)}
            disabled={submitting}
            className="rounded-lg bg-sky-600 px-4 py-2 font-medium text-white hover:bg-sky-500 disabled:opacity-50"
          >
            {submitting ? 'Submitting...' : 'Run demo analysis (3 sample frames)'}
          </button>

          {(pollData?.status === 'pending' || pollData?.status === 'processing') && (
            <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
              <p className="text-sky-400">
                Analyzing frames... {pollData.progress}%
              </p>
              <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-700">
                <div
                  className="h-full bg-sky-500 transition-all duration-300"
                  style={{ width: `${pollData.progress}%` }}
                />
              </div>
              <p className="mt-1 text-sm text-slate-400">
                ~{pollData.estimated_remaining_seconds ?? 0}s remaining
              </p>
            </div>
          )}
        </div>
      ) : pollData.status === 'completed' ? (
        <div>
          <div className="mb-4 rounded-lg border border-green-800 bg-green-900/20 p-3 text-green-200">
            Analysis complete
          </div>
          {renderResults()}
          <button
            onClick={() => {
              setAnalysisId(null)
              setPollData(null)
            }}
            className="mt-4 rounded-lg border border-slate-600 px-4 py-2 text-slate-300 hover:bg-slate-800"
          >
            New analysis
          </button>
        </div>
      ) : pollData.status === 'failed' ? (
        <div className="rounded-lg border border-red-800 bg-red-900/30 p-4">
          <p className="font-medium text-red-200">Analysis failed</p>
          <p className="mt-1 text-sm text-red-300">{pollData.error_message ?? 'Unknown error'}</p>
          <button
            onClick={() => {
              setAnalysisId(null)
              setPollData(null)
            }}
            className="mt-4 rounded-lg border border-red-700 px-4 py-2 text-red-200 hover:bg-red-900/50"
          >
            Try again
          </button>
        </div>
      ) : null}
    </div>
  )
}
