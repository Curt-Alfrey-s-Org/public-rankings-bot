/**
 * UploadForm - File upload and game metadata form for AI Coach.
 * Player name prefilled from logged-in user; opponent and optional YouTube link.
 * Game type removed — AI can infer or ask.
 */

import { useState, useEffect } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import type { UploadFormProps, SubmitAnalysisRequest } from '@/features/ai-coach/types'

/** File upload and game metadata form for pool coaching analysis */
export function UploadForm({
  onSubmit,
  isSubmitting = false,
  error = null,
  maxFrames = 100,
  maxVideoDurationSeconds = 120,
}: UploadFormProps) {
  const { user } = useAuth()
  const [playerName, setPlayerName] = useState('')
  const [opponentName, setOpponentName] = useState('')
  const [youtubeUrl, setYoutubeUrl] = useState('')
  const [playerHairColor, setPlayerHairColor] = useState('')
  const [playerShirtColor, setPlayerShirtColor] = useState('')
  const [opponentHairColor, setOpponentHairColor] = useState('')
  const [opponentShirtColor, setOpponentShirtColor] = useState('')
  const [promoCode, setPromoCode] = useState('')

  useEffect(() => {
    if (user?.user) setPlayerName(user.user)
  }, [user?.user])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const request: SubmitAnalysisRequest = {
      bot_type: 'rankings',
      video_source: youtubeUrl.trim() ? 'youtube' : 'upload',
      video_url: youtubeUrl.trim() || undefined,
      player_name: playerName.trim() || undefined,
      opponent_name: opponentName.trim() || undefined,
      player_hair_color: playerHairColor.trim() || undefined,
      player_shirt_color: playerShirtColor.trim() || undefined,
      opponent_hair_color: opponentHairColor.trim() || undefined,
      opponent_shirt_color: opponentShirtColor.trim() || undefined,
      promo_code: promoCode.trim() || undefined,
    }
    onSubmit(request)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-slate-700 bg-slate-800/50 p-4">
      <h3 className="text-lg font-semibold text-sky-400">Upload Video Frames</h3>
      <p className="text-sm text-slate-400">
        Extract frames client-side (ffmpeg.wasm) and submit, or add a YouTube link to a game to watch. Max {maxFrames} frames, {maxVideoDurationSeconds}s video.
      </p>

      <div>
        <label htmlFor="youtube-url" className="block text-sm font-medium text-slate-300">
          YouTube link (optional)
        </label>
        <input
          id="youtube-url"
          type="url"
          value={youtubeUrl}
          onChange={(e) => setYoutubeUrl(e.target.value)}
          className="mt-1 w-full rounded-md border border-slate-600 bg-slate-900 px-3 py-2 text-white placeholder-slate-500"
          placeholder="https://youtube.com/watch?v=..."
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="player-name" className="block text-sm font-medium text-slate-300">
            Your name
          </label>
          <input
            id="player-name"
            type="text"
            value={playerName}
            onChange={(e) => setPlayerName(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-600 bg-slate-900 px-3 py-2 text-white placeholder-slate-500"
            placeholder="Prefilled from your account"
          />
        </div>
        <div>
          <label htmlFor="opponent-name" className="block text-sm font-medium text-slate-300">
            Opponent
          </label>
          <input
            id="opponent-name"
            type="text"
            value={opponentName}
            onChange={(e) => setOpponentName(e.target.value)}
            className="mt-1 w-full rounded-md border border-slate-600 bg-slate-900 px-3 py-2 text-white placeholder-slate-500"
            placeholder="Optional"
          />
        </div>
      </div>

      <p className="text-xs text-slate-400">Help the AI tell which player is which in the video:</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="player-hair" className="block text-sm font-medium text-slate-300">Your hair color</label>
          <input id="player-hair" type="text" value={playerHairColor} onChange={(e) => setPlayerHairColor(e.target.value)} className="mt-1 w-full rounded-md border border-slate-600 bg-slate-900 px-3 py-2 text-white placeholder-slate-500" placeholder="e.g. brown" />
        </div>
        <div>
          <label htmlFor="player-shirt" className="block text-sm font-medium text-slate-300">Your shirt color</label>
          <input id="player-shirt" type="text" value={playerShirtColor} onChange={(e) => setPlayerShirtColor(e.target.value)} className="mt-1 w-full rounded-md border border-slate-600 bg-slate-900 px-3 py-2 text-white placeholder-slate-500" placeholder="e.g. blue" />
        </div>
        <div>
          <label htmlFor="opponent-hair" className="block text-sm font-medium text-slate-300">Opponent hair color</label>
          <input id="opponent-hair" type="text" value={opponentHairColor} onChange={(e) => setOpponentHairColor(e.target.value)} className="mt-1 w-full rounded-md border border-slate-600 bg-slate-900 px-3 py-2 text-white placeholder-slate-500" placeholder="e.g. blonde" />
        </div>
        <div>
          <label htmlFor="opponent-shirt" className="block text-sm font-medium text-slate-300">Opponent shirt color</label>
          <input id="opponent-shirt" type="text" value={opponentShirtColor} onChange={(e) => setOpponentShirtColor(e.target.value)} className="mt-1 w-full rounded-md border border-slate-600 bg-slate-900 px-3 py-2 text-white placeholder-slate-500" placeholder="e.g. red" />
        </div>
      </div>

      <div>
        <label htmlFor="promo-code" className="block text-sm font-medium text-slate-300">
          Promo code
        </label>
        <input
          id="promo-code"
          type="text"
          value={promoCode}
          onChange={(e) => setPromoCode(e.target.value)}
          className="mt-1 w-full rounded-md border border-slate-600 bg-slate-900 px-3 py-2 text-white placeholder-slate-500"
          placeholder="Optional"
        />
      </div>

      {error && (
        <div className="rounded-md border border-red-800 bg-red-900/30 p-3 text-sm text-red-200">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded-lg bg-sky-600 px-4 py-2 font-medium text-white hover:bg-sky-500 disabled:opacity-50"
      >
        {isSubmitting ? 'Submitting...' : 'Submit for analysis'}
      </button>
    </form>
  )
}
