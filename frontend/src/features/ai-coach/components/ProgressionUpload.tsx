/**
 * ProgressionUpload - Upload new video to compare with a previous assessment
 * @module features/ai-coach/components/ProgressionUpload
 */

import { useState, useRef } from 'react'
import { aiCoachApi } from '@/api/aiCoach'

async function extractFramesFromVideo(video: HTMLVideoElement, canvas: HTMLCanvasElement): Promise<string[]> {
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Canvas context not available')
  const frames: string[] = []
  const duration = video.duration
  const frameCount = Math.min(20, Math.max(1, Math.floor(duration / 2)))
  for (let i = 0; i < frameCount; i++) {
    const time = (frameCount - 1) > 0 ? (i / (frameCount - 1)) * duration : 0
    video.currentTime = time
    await new Promise<void>((resolve, reject) => {
      const onSeeked = () => {
        video.removeEventListener('seeked', onSeeked)
        video.removeEventListener('error', onErr)
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
        const dataUrl = canvas.toDataURL('image/jpeg', 0.8)
        frames.push(dataUrl.split(',')[1] ?? '')
        resolve()
      }
      const onErr = () => {
        video.removeEventListener('seeked', onSeeked)
        video.removeEventListener('error', onErr)
        reject(new Error('Video failed to load'))
      }
      video.addEventListener('seeked', onSeeked)
      video.addEventListener('error', onErr)
    })
  }
  return frames
}

export interface ProgressionUploadProps {
  previousAnalysisId: string
  onSubmitted: (analysisId: string) => void
  onCancel: () => void
}

export function ProgressionUpload({ previousAnalysisId, onSubmitted, onCancel }: ProgressionUploadProps) {
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const handleSubmit = async () => {
    if (!file || !videoRef.current || !canvasRef.current) {
      setError('Select a video first')
      return
    }
    setError(null)
    setIsSubmitting(true)
    try {
      const video = videoRef.current
      const canvas = canvasRef.current
      canvas.width = 640
      canvas.height = 360
      const frames = await extractFramesFromVideo(video, canvas)
      if (frames.length === 0) {
        setError('Could not extract frames from video')
        return
      }
      const res = await aiCoachApi.submitProgression(previousAnalysisId, {
        bot_type: 'rankings',
        frames_base64: frames,
      })
      onSubmitted(res.analysis_id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Progression submission failed')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="rounded-lg border border-sky-700 bg-slate-800/50 p-4 space-y-3">
      <h4 className="text-lg font-semibold text-sky-400">Progression review</h4>
      <p className="text-sm text-slate-400">
        Upload a new video to compare with the selected past assessment. The AI will report what improved and what still needs work.
      </p>
      <input
        type="file"
        accept="video/*"
        onChange={(e) => {
          const f = e.target.files?.[0]
          setFile(f ?? null)
          setError(null)
        }}
        className="block w-full text-sm text-slate-300 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:bg-sky-600 file:text-white"
      />
      {file && (
        <>
          <video
            ref={videoRef}
            src={URL.createObjectURL(file)}
            preload="metadata"
            className="w-full max-w-md rounded border border-slate-600"
            onLoadedMetadata={() => {}}
          />
          <canvas ref={canvasRef} className="hidden" />
        </>
      )}
      {error && <p className="text-sm text-red-400">{error}</p>}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!file || isSubmitting}
          className="rounded bg-sky-600 px-3 py-1.5 text-white hover:bg-sky-500 disabled:opacity-50"
        >
          {isSubmitting ? 'Submitting…' : 'Submit progression'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded border border-slate-500 px-3 py-1.5 text-slate-300 hover:bg-slate-700"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
