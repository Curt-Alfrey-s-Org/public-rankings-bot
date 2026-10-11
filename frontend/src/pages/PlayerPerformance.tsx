/**
 * Player Performance Page
 * Shows comprehensive player statistics, ranking history charts, and tournament results
 * Similar to CP FargoRate feature
 */

import { useState, useMemo, useEffect, useRef } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
  Legend,
  Bar,
  BarChart,
} from 'recharts'
import { useAuth } from '@/contexts/AuthContext'
import { alfaApi } from '@/api/alfa'
import { rankingsApi } from '@/api/rankings'
import { API_BASE_URL } from '@/api/client'
import { aiCoachApi, type PollResponse } from '@/api/aiCoach'
import { logger } from '@/lib/logger'
import { useAlfaAskAiRegistration } from '@alfa-ai/chat-widget'

const GO_PUBLIC_KEY = 'player_performance_go_public'
function getGoPublic(): boolean {
  try {
    return localStorage.getItem(GO_PUBLIC_KEY) === 'true'
  } catch (error) {
    logger.warn('Failed reading go-public preference from localStorage', undefined, error as Error)
    return false
  }
}

function PerformanceCurveChart({
  history,
  tournaments
}: {
  history: RankingHistory[]
  tournaments: Tournament[]
}) {
  const sortedHistory = useMemo(() =>
    [...history].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()),
    [history]
  )

  const sortedTournaments = useMemo(() =>
    [...tournaments].sort((a, b) => {
      const da = a.tournament_date ?? a.start_date ?? ''
      const db = b.tournament_date ?? b.start_date ?? ''
      return new Date(da).getTime() - new Date(db).getTime()
    }),
    [tournaments]
  )

  const width = 600
  const height = 280
  const pad = { left: 50, right: 100, top: 20, bottom: 50 }

  if (sortedHistory.length === 0) {
    return (
      <div className="bg-slate-900/50 p-4 rounded-lg">
        <p className="text-xs text-muted-foreground mb-2">Your ranking progress with tournament events</p>
        <div className="text-center py-16 text-slate-400">
          <div className="text-4xl mb-4">📊</div>
          <p>No ranking history available for this division</p>
        </div>
      </div>
    )
  }

  // Calculate time range for consistent X-axis
  const allDates = [
    ...sortedHistory.map(h => new Date(h.date).getTime()),
    ...sortedTournaments.map(t => new Date(t.tournament_date ?? t.start_date ?? 0).getTime())
  ]
  const minTime = Math.min(...allDates)
  const maxTime = Math.max(...allDates)
  const timeRange = maxTime - minTime || 1

  // Calculate rating range
  const minRating = Math.min(...sortedHistory.map((r) => r.rating))
  const maxRating = Math.max(...sortedHistory.map((r) => r.rating))
  const ratingRange = maxRating - minRating || 1

  const scaleY = (y: number) =>
    pad.top + height - pad.top - pad.bottom -
    ((y - minRating) / ratingRange) * (height - pad.top - pad.bottom)

  const scaleX = (time: number) =>
    pad.left + ((time - minTime) / timeRange) * (width - pad.left - pad.right)

  const historyPoints = sortedHistory.map((r) =>
    `${scaleX(new Date(r.date).getTime())},${scaleY(r.rating)}`
  ).join(' ')

  return (
    <div className="bg-slate-900/50 p-4 rounded-lg">
      <p className="text-xs text-muted-foreground mb-2">
        Your ranking progress with tournament events marked as points
      </p>
      <svg width={width} height={height} className="overflow-visible">
        {/* Grid lines */}
        <defs>
          <pattern id="grid" width="40" height="20" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 20" fill="none" stroke="rgba(148, 163, 184, 0.1)" strokeWidth="1"/>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid)" />

        {/* Y-axis */}
        <text
          x={pad.left - 12}
          y={pad.top + (height - pad.top - pad.bottom) / 2}
          fill="currentColor"
          className="text-[10px] fill-slate-400"
          textAnchor="middle"
          transform={`rotate(-90, ${pad.left - 12}, ${pad.top + (height - pad.top - pad.bottom) / 2})`}
        >
          Rating
        </text>
        <line
          x1={pad.left}
          y1={pad.top}
          x2={pad.left}
          y2={height - pad.bottom}
          stroke="currentColor"
          className="stroke-slate-600"
          strokeWidth="1"
        />

        {/* X-axis */}
        <line
          x1={pad.left}
          y1={height - pad.bottom}
          x2={width - pad.right}
          y2={height - pad.bottom}
          stroke="currentColor"
          className="stroke-slate-600"
          strokeWidth="1"
        />

        {/* Rating curve */}
        <polyline
          fill="none"
          stroke="var(--color-accent, #22d3ee)"
          strokeWidth="3"
          strokeLinejoin="round"
          strokeLinecap="round"
          points={historyPoints}
        />

        {/* Ranking history points */}
        {sortedHistory.map((r, i) => (
          <g key={`history-${i}`}>
            <circle
              cx={scaleX(new Date(r.date).getTime())}
              cy={scaleY(r.rating)}
              r="5"
              fill="var(--color-accent, #22d3ee)"
              stroke="white"
              strokeWidth="2"
            />
            <title>
              {new Date(r.date).toLocaleDateString()}: Rating {r.rating.toFixed(1)} (Rank #{r.rank})
            </title>
          </g>
        ))}

        {/* Tournament markers */}
        {sortedTournaments.map((tournament, i) => {
          const tournamentTime = new Date(tournament.tournament_date ?? tournament.start_date ?? 0).getTime()
          // Find closest rating point for Y position
          const closestHistory = sortedHistory.reduce((closest, current) => {
            const currentDiff = Math.abs(new Date(current.date).getTime() - tournamentTime)
            const closestDiff = Math.abs(new Date(closest.date).getTime() - tournamentTime)
            return currentDiff < closestDiff ? current : closest
          })

          const y = scaleY(closestHistory.rating)
          const x = scaleX(tournamentTime)

          return (
            <g key={`tournament-${i}`}>
              {/* Tournament marker */}
              <circle
                cx={x}
                cy={y}
                r="8"
                fill={
                  tournament.placement === 1 ? '#fbbf24' : // gold
                  tournament.placement === 2 ? '#c0c0c0' : // silver
                  tournament.placement === 3 ? '#cd7f32' : // bronze
                  '#60a5fa' // blue for others
                }
                stroke="white"
                strokeWidth="2"
                className="drop-shadow-md"
              />
              {/* Medal emoji or placement number */}
              <text
                x={x}
                y={y + 2}
                textAnchor="middle"
                className="text-[10px] font-bold fill-white pointer-events-none"
                style={{ fontSize: '10px' }}
              >
                {tournament.placement === 1 ? '🥇' :
                 tournament.placement === 2 ? '🥈' :
                 tournament.placement === 3 ? '🥉' :
                 tournament.placement <= 9 ? tournament.placement.toString() : '•'}
              </text>
              <title>
                {tournament.tournament_name}
                {'\n'}{new Date(tournament.tournament_date ?? tournament.start_date ?? '').toLocaleDateString()}
                {'\n'}Placement: #{tournament.placement}
                {'\n'}Points: {tournament.points}
                {'\n'}{tournament.location}
              </title>
            </g>
          )
        })}

        {/* Legend */}
        <g transform={`translate(${width - 85}, ${pad.top + 10})`}>
          <rect width="80" height="45" fill="rgba(30, 41, 59, 0.9)" rx="4" stroke="rgba(148, 163, 184, 0.3)" />
          <circle cx="10" cy="15" r="4" fill="var(--color-accent, #22d3ee)" />
          <text x="18" y="18" className="text-[10px] fill-slate-300">Rating</text>
          <circle cx="10" cy="30" r="4" fill="#fbbf24" />
          <text x="18" y="33" className="text-[10px] fill-slate-300">Tournament</text>
        </g>

        {/* X-axis label */}
        <text
          x={width / 2}
          y={height - 15}
          fill="currentColor"
          className="text-[10px] fill-slate-400"
          textAnchor="middle"
        >
          Timeline
        </text>
      </svg>
    </div>
  )
}

interface DivisionStats {
  rank: number
  rating: number
  country: string
  fargo_rating?: number | null
  fargo_last_updated?: string | null
  alfa_rating?: number | null
}

interface PlayerOverview {
  player_name: string
  narrative?: string | null
  /** True when overview data matched cache — no new Ollama call */
  narrative_unchanged?: boolean
  wpba: DivisionStats | null
  wpa_women: DivisionStats | null
  wpa_men: DivisionStats | null
  tournament_stats: {
    total_tournaments: number
    first_place_finishes: number
    top_3_finishes: number
    avg_placement: number
    last_tournament_date: string
  } | null
}

type TournamentAnalyticsWindow = 'recent_3' | 'season' | 'all_time'

interface TournamentAnalyticsResponse {
  player_name: string
  resolved_player_name?: string
  window: string
  calendar_year: number | null
  label: string
  counts: { events: number; first_place: number; top_3: number; top_8: number }
  rates_pct: { first_place: number | null; top_3: number | null; top_8: number | null }
  avg_placement: number | null
  best_placement: number | null
  total_points: number | null
  match_record: {
    matches_with_winner: number
    match_wins: number
    match_losses: number
    match_win_rate_pct: number | null
  } | null
  events: Array<{
    tournament_id: string
    tournament_name: string | null
    tournament_date: string | null
    association: string | null
    placement: number | null
    points: number | null
  }>
}

interface RankingHistory {
  rank: number
  rating: number
  date: string
  association: string
}

interface Tournament {
  tournament_name: string
  association: string
  start_date?: string
  tournament_date?: string
  placement: number
  points: number
  location: string
  fargo_rating_at_scrape?: number | null
}

type HistoryAssociation = 'WPBA' | 'WPA_Women' | 'WPA_Men'

// Video Analysis Section Component
function VideoAnalysisSection({ selectedPlayer }: { selectedPlayer: string | null }) {
  const [selectedVideo, setSelectedVideo] = useState<File | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [currentAnalysis, setCurrentAnalysis] = useState<PollResponse | null>(null)
  const [pollInterval, setPollInterval] = useState<NodeJS.Timeout | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const { data: usageData } = useQuery({
    queryKey: ['ai-coach-usage'],
    queryFn: () => aiCoachApi.getUsage(),
    enabled: !!selectedPlayer,
  })

  const { data: analysisHistory } = useQuery({
    queryKey: ['ai-coach-history', selectedPlayer],
    queryFn: () => aiCoachApi.getHistory(5, 0), // Get last 5 analyses
    enabled: !!selectedPlayer,
  })

  const handleVideoSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      setSelectedVideo(file)
    }
  }

  const extractFrames = async (video: HTMLVideoElement, canvas: HTMLCanvasElement): Promise<string[]> => {
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Canvas context not available')

    const frames: string[] = []
    const duration = video.duration
    const frameCount = Math.min(20, Math.floor(duration / 2)) // Extract frames every 2 seconds, max 20 frames

    for (let i = 0; i < frameCount; i++) {
      const time = (i / (frameCount - 1)) * duration
      video.currentTime = time

      await new Promise<void>((resolve) => {
        const onSeeked = () => {
          video.removeEventListener('seeked', onSeeked)
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
          const dataUrl = canvas.toDataURL('image/jpeg', 0.8)
          frames.push(dataUrl.split(',')[1]) // Remove data:image/jpeg;base64, prefix
          resolve()
        }
        video.addEventListener('seeked', onSeeked)
      })
    }

    return frames
  }

  const handleAnalyze = async () => {
    if (!selectedVideo || !videoRef.current || !canvasRef.current) return

    setIsProcessing(true)

    try {
      // Extract frames from video
      const video = videoRef.current
      const canvas = canvasRef.current
      canvas.width = 640
      canvas.height = 360

      const frames = await extractFrames(video, canvas)

      // Submit for analysis
      const response = await aiCoachApi.analyze({
        bot_type: 'rankings',
        video_source: 'upload',
        frames_base64: frames,
        player_name: selectedPlayer || undefined,
        game_format: 'pool', // Default to pool
      })

      setCurrentAnalysis({
        analysis_id: response.analysis_id,
        status: 'pending',
        progress: 0,
      })

      // Start polling for results
      startPolling(response.analysis_id)

    } catch (error) {
      console.error('Analysis failed:', error)
      setIsProcessing(false)
    }
  }

  const startPolling = (analysisId: string) => {
    const interval = setInterval(async () => {
      try {
        const status = await aiCoachApi.poll(analysisId)
        setCurrentAnalysis(status)

        if (status.status === 'completed' || status.status === 'failed') {
          setIsProcessing(false)
          clearInterval(interval)
          setPollInterval(null)
        }
      } catch (error) {
        console.error('Polling failed:', error)
        clearInterval(interval)
        setPollInterval(null)
        setIsProcessing(false)
      }
    }, 2000) // Poll every 2 seconds

    setPollInterval(interval)
  }

  useEffect(() => {
    return () => {
      if (pollInterval) {
        clearInterval(pollInterval)
      }
    }
  }, [pollInterval])

  const canAnalyze = usageData && usageData.analyses_remaining > 0 && selectedVideo && !isProcessing

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-400">
        Upload a short clip or use the full AI Coach page with a YouTube URL. Only the written assessment is kept; you can edit or delete past assessments and compare with new video for progression.
      </p>

      {/* Usage Info */}
      {usageData && (
        <div className="bg-slate-900/50 p-4 rounded-lg">
          <div className="flex justify-between items-center text-sm">
            <span className="text-slate-300">
              Tier: <span className="text-accent font-semibold">{usageData.tier}</span>
            </span>
            <span className="text-slate-300">
              Remaining: <span className="text-accent font-semibold">{usageData.analyses_remaining}</span>
            </span>
          </div>
        </div>
      )}

      {/* Video Upload */}
      <div className="bg-slate-900/50 p-4 rounded-lg">
        <h4 className="text-lg font-semibold text-white mb-3">Upload Game Video</h4>

        <div className="space-y-3">
          <input
            type="file"
            accept="video/*"
            onChange={handleVideoSelect}
            className="block w-full text-sm text-slate-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-accent file:text-white hover:file:bg-accent/80"
            disabled={isProcessing}
          />

          {selectedVideo && (
            <div className="space-y-3">
              <video
                ref={videoRef}
                src={URL.createObjectURL(selectedVideo)}
                controls
                className="w-full max-w-md rounded-lg border border-slate-600"
                preload="metadata"
              />
              <canvas ref={canvasRef} className="hidden" />

              <button
                onClick={handleAnalyze}
                disabled={!canAnalyze}
                className={`px-6 py-2 rounded-lg font-semibold transition-colors ${
                  canAnalyze
                    ? 'bg-accent text-white hover:bg-accent/80'
                    : 'bg-slate-600 text-slate-400 cursor-not-allowed'
                }`}
              >
                {isProcessing ? 'Analyzing...' : 'Analyze Video'}
              </button>
            </div>
          )}
        </div>

        {!canAnalyze && usageData && usageData.analyses_remaining === 0 && (
          <p className="text-amber-400 text-sm mt-2">
            No analyses remaining this month. Upgrade your plan or wait for reset.
          </p>
        )}
      </div>

      {/* Current Analysis Progress */}
      {currentAnalysis && (
        <div className="bg-slate-900/50 p-4 rounded-lg">
          <h4 className="text-lg font-semibold text-white mb-3">Analysis Progress</h4>

          <div className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-slate-300">Status:</span>
              <span className={`font-semibold ${
                currentAnalysis.status === 'completed' ? 'text-green-400' :
                currentAnalysis.status === 'failed' ? 'text-red-400' :
                'text-blue-400'
              }`}>
                {currentAnalysis.status.charAt(0).toUpperCase() + currentAnalysis.status.slice(1)}
              </span>
            </div>

            <div className="w-full bg-slate-700 rounded-full h-2">
              <div
                className="bg-accent h-2 rounded-full transition-all duration-300"
                style={{ width: `${currentAnalysis.progress}%` }}
              />
            </div>

            {currentAnalysis.estimated_remaining_seconds && (
              <p className="text-xs text-slate-400">
                Estimated time remaining: {Math.ceil(currentAnalysis.estimated_remaining_seconds / 60)} minutes
              </p>
            )}
          </div>
        </div>
      )}

      {/* Analysis Results */}
      {currentAnalysis?.status === 'completed' && currentAnalysis.result && (
        <div className="bg-slate-900/50 p-4 rounded-lg">
          <h4 className="text-lg font-semibold text-white mb-3">Analysis Results</h4>

          <div className="space-y-4">
            {currentAnalysis.result.strengths && (
              <div>
                <h5 className="text-green-400 font-semibold mb-2">Strengths</h5>
                <ul className="list-disc list-inside text-slate-300 text-sm space-y-1">
                  {(currentAnalysis.result.strengths as string[]).map((strength, idx) => (
                    <li key={idx}>{strength}</li>
                  ))}
                </ul>
              </div>
            )}

            {currentAnalysis.result.improvements && (
              <div>
                <h5 className="text-yellow-400 font-semibold mb-2">Areas for Improvement</h5>
                <ul className="list-disc list-inside text-slate-300 text-sm space-y-1">
                  {(currentAnalysis.result.improvements as string[]).map((improvement, idx) => (
                    <li key={idx}>{improvement}</li>
                  ))}
                </ul>
              </div>
            )}

            {currentAnalysis.result.overall_score && (
              <div className="text-center p-3 bg-slate-800 rounded-lg">
                <div className="text-2xl font-bold text-accent">
                  {currentAnalysis.result.overall_score}/10
                </div>
                <div className="text-xs text-slate-400">Overall Performance Score</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Recent Analyses */}
      {analysisHistory && analysisHistory.analyses.length > 0 && (
        <div className="bg-slate-900/50 p-4 rounded-lg">
          <h4 className="text-lg font-semibold text-white mb-3">Recent Analyses</h4>

          <div className="space-y-2">
            {analysisHistory.analyses.slice(0, 3).map((analysis) => (
              <div key={analysis.analysis_id} className="flex justify-between items-center p-2 bg-slate-800 rounded">
                <div>
                  <div className="text-sm font-medium text-white">{analysis.title}</div>
                  <div className="text-xs text-slate-400">
                    {new Date(analysis.created_at).toLocaleDateString()}
                  </div>
                </div>
                <div className="text-right">
                  <div className={`text-sm font-semibold ${
                    analysis.status === 'completed' ? 'text-green-400' :
                    analysis.status === 'failed' ? 'text-red-400' :
                    'text-blue-400'
                  }`}>
                    {analysis.status}
                  </div>
                  {analysis.overall_score && (
                    <div className="text-xs text-slate-400">{analysis.overall_score}/10</div>
                  )}
                </div>
              </div>
            ))}
          </div>

          <Link
            to="/ai-coach"
            className="inline-block mt-3 text-sm text-accent hover:underline"
          >
            View all analyses →
          </Link>
        </div>
      )}
    </div>
  )
}

export default function PlayerPerformance() {
  const { user: authUser, isAdmin, isSuperAdmin } = useAuth()
  const currentPlayerName = (authUser?.user ?? '').trim()
  const [selectedPlayer, setSelectedPlayer] = useState<string | null>(null)
  const [selectedAssociation, setSelectedAssociation] = useState<HistoryAssociation>('WPBA')
  const [analyticsWindow, setAnalyticsWindow] = useState<TournamentAnalyticsWindow>('recent_3')
  const [goPublic, setGoPublic] = useState(getGoPublic)
  const [notifyEmail, setNotifyEmail] = useState('')
  const [notifyPlayerName, setNotifyPlayerName] = useState('')
  const [notifySuccess, setNotifySuccess] = useState<string | null>(null)
  const [notifyError, setNotifyError] = useState<string | null>(null)

  // Admin/super_admin can view any player; others only their own
  const canViewAllPlayers = isAdmin

  const { data: playerNamesData } = useQuery({
    queryKey: ['player-names-for-perf'],
    queryFn: () => rankingsApi.getPlayerNames(500),
    enabled: canViewAllPlayers,
  })

  const authHeaders = useMemo((): HeadersInit | undefined => {
    let token = authUser?.token
      || localStorage.getItem('access_token')
      || localStorage.getItem('auth_token')
    if (!token) {
      try {
        const raw = localStorage.getItem('rankings_bot_auth')
        if (raw) {
          const parsed = JSON.parse(raw)
          token = parsed?.token
        }
      } catch (error) {
        logger.warn('Failed to parse rankings_bot_auth in PlayerPerformance', undefined, error as Error)
        token = undefined
      }
    }
    return token ? { Authorization: `Bearer ${token}` } : undefined
  }, [authUser?.token])
  const hasAuth = !!authHeaders?.Authorization

  const { data: myPlayerInfo } = useQuery<{ player_name: string; source: string }>({
    queryKey: ['player-performance-me'],
    queryFn: async () => {
      const response = await fetch('/api/player-performance/me', { headers: authHeaders })
      if (!response.ok) {
        return { player_name: currentPlayerName, source: 'username' }
      }
      return response.json()
    },
    enabled: !!currentPlayerName && hasAuth,
    retry: 1,
    refetchInterval: 30_000, // Live-update
  })

  const effectivePlayerName = (myPlayerInfo?.player_name ?? currentPlayerName).trim()

  const [searchParams] = useSearchParams()
  const playerFromUrl = searchParams.get('player')?.trim() || null
  useEffect(() => {
    if (canViewAllPlayers && playerFromUrl) {
      setSelectedPlayer(playerFromUrl)
    }
  }, [canViewAllPlayers, playerFromUrl])

  // Map selected association to notify API system (WPBA | WPA)
  const notifySystem = selectedAssociation === 'WPBA' ? 'WPBA' : 'WPA'

  const notifySubscribeMutation = useMutation({
    mutationFn: ({ email, playerName, system }: { email: string; playerName: string; system: string }) =>
      rankingsApi.notifySubscribe(email, playerName, system),
    onMutate: () => {
      setNotifyError(null)
      setNotifySuccess("You're subscribed. We'll email you when this player's ranking changes.")
    },
    onSuccess: (data) => {
      setNotifySuccess(data.message || "You're subscribed. We'll email you when this player's ranking changes.")
      setNotifyError(null)
      setNotifyEmail('')
      setNotifyPlayerName('')
    },
    onError: (err: unknown) => {
      setNotifyError(err instanceof Error ? err.message : 'Subscription failed.')
      setNotifySuccess(null)
    },
  })

  useEffect(() => {
    if (!canViewAllPlayers && effectivePlayerName && selectedPlayer !== effectivePlayerName) {
      setSelectedPlayer(effectivePlayerName)
    }
  }, [canViewAllPlayers, effectivePlayerName, selectedPlayer])

  // Fetch player overview data (only this player's info; auth required for access control)
  const { data: overview, isLoading: overviewLoading, error: overviewError, refetch: refetchOverview } = useQuery<PlayerOverview>({
    queryKey: ['player-overview', selectedPlayer],
    queryFn: async () => {
      const response = await fetch(`/api/player-performance/${encodeURIComponent(selectedPlayer!)}/overview`, { headers: authHeaders })
      if (!response.ok) {
        const text = await response.text()
        const msg = response.status === 403 ? 'You can only view your own player performance. Other players\' charts are a paid perk.' : text || 'Failed to fetch player overview'
        throw new Error(msg)
      }
      return response.json()
    },
    enabled: !!selectedPlayer && hasAuth,
    retry: 1,
    refetchInterval: 30_000, // Live-update
  })

  // Fetch ALFa ratings (all systems) to merge with overview — admin/super_admin only
  const { data: alfaData } = useQuery({
    queryKey: ['alfa-overview'],
    queryFn: () => alfaApi.getRatings(),
    enabled: !!selectedPlayer && isAdmin,
    retry: 2,
  })

  // Build map: player_name -> { WPBA_Women, WPA_Women, WPA_Men } -> alfa_rating
  const alfaByPlayerAndSystem = useMemo(() => {
    const map = new Map<string, Record<string, number>>()
    for (const r of alfaData?.rankings ?? []) {
      const name = (r.player_name ?? '').trim()
      const sys = r.ranking_system ?? ''
      if (!name || !sys) continue
      let entry = map.get(name)
      if (!entry) {
        entry = {}
        map.set(name, entry)
      }
      entry[sys] = r.alfa_rating
    }
    return map
  }, [alfaData?.rankings])

  // Merge alfa into overview for display
  const overviewWithAlfa = useMemo(() => {
    if (!overview) return overview
    const name = (overview.player_name ?? '').trim()
    const alfaMap = alfaByPlayerAndSystem.get(name)
    const withAlfa = (d: DivisionStats | null, system: string): DivisionStats | null => {
      if (!d) return d
      const alfa = alfaMap?.[system]
      return { ...d, alfa_rating: alfa ?? d.alfa_rating ?? null }
    }
    return {
      ...overview,
      wpba: withAlfa(overview.wpba, 'WPBA_Women'),
      wpa_women: withAlfa(overview.wpa_women, 'WPA_Women'),
      wpa_men: withAlfa(overview.wpa_men, 'WPA_Men'),
      narrative: overview.narrative,
      narrative_unchanged: overview.narrative_unchanged,
    }
  }, [overview, alfaByPlayerAndSystem])

  const displayOverviewForAlfa = overviewWithAlfa ?? overview ?? null
  const alfaAskRegistration = useMemo(() => {
    if (!hasAuth || !selectedPlayer || !displayOverviewForAlfa?.player_name) return null
    const o = displayOverviewForAlfa
    return {
      page: 'player-performance' as const,
      playerName: o.player_name,
      context: {
        player_name: o.player_name,
        wpba: o.wpba,
        wpa_women: o.wpa_women,
        wpa_men: o.wpa_men,
        tournament_stats: o.tournament_stats,
        narrative: o.narrative,
      } as Record<string, unknown>,
    }
  }, [hasAuth, selectedPlayer, displayOverviewForAlfa])
  useAlfaAskAiRegistration(alfaAskRegistration)

  // Fetch ranking history for chart (one division only)
  const { data: historyData, isLoading: historyLoading, error: historyError, refetch: refetchHistory } = useQuery<{ history: RankingHistory[] }>({
    queryKey: ['player-history', selectedPlayer, selectedAssociation],
    queryFn: async () => {
      const response = await fetch(`/api/player-performance/${encodeURIComponent(selectedPlayer!)}/history?association=${selectedAssociation}`, { headers: authHeaders })
      if (!response.ok) throw new Error(response.status === 403 ? 'You can only view your own performance.' : 'Failed to fetch ranking history')
      return response.json()
    },
    enabled: !!selectedPlayer && hasAuth,
    retry: 1,
  })

  // Fetch tournament results (this player only)
  const { data: tournamentsData, isLoading: tournamentsLoading, error: tournamentsError, refetch: refetchTournaments } = useQuery<{ tournaments: Tournament[] }>({
    queryKey: ['player-tournaments', selectedPlayer],
    queryFn: async () => {
      const response = await fetch(`/api/player-performance/${encodeURIComponent(selectedPlayer!)}/tournaments`, { headers: authHeaders })
      if (!response.ok) throw new Error(response.status === 403 ? 'You can only view your own performance.' : 'Failed to fetch tournaments')
      return response.json()
    },
    enabled: !!selectedPlayer && hasAuth,
    retry: 1,
    refetchInterval: 30_000, // Live-update
  })

  // Fetch historical rating data (Fargo, ALFA, EST over time)
  const { data: historicalRatingsData, isLoading: historicalRatingsLoading, error: historicalRatingsError, refetch: refetchHistoricalRatings } = useQuery<{
    success: boolean
    player_name: string
    player_id: string
    rating_series: {
      fargo: Array<{ date: string; rating: number; confidence: number; source: string }>
      alfa: Array<{ date: string; rating: number; confidence: number; source: string }>
      est: Array<{ date: string; rating: number; confidence: number; source: string }>
    }
    total_entries: number
    filtered_by_type?: string
  }>({
    queryKey: ['player-historical-ratings', selectedPlayer],
    queryFn: async () => {
      const response = await fetch(`/api/player-performance/${encodeURIComponent(selectedPlayer!)}/historical-ratings`, { headers: authHeaders })
      if (!response.ok) {
        const errorText = await response.text().catch(() => 'Unknown error')
        throw new Error(response.status === 403 ? 'You can only view your own performance.' :
                       response.status === 404 ? 'Player not found.' :
                       `Failed to fetch historical ratings: ${errorText}`)
      }
      const data = await response.json()
      if (!data.success) {
        throw new Error(data.message || 'Failed to fetch historical ratings')
      }
      return data
    },
    enabled: !!selectedPlayer && hasAuth,
    retry: (failureCount, error) => {
      // Don't retry on 403/404 errors
      if (error instanceof Error && (error.message.includes('403') || error.message.includes('404'))) {
        return false
      }
      return failureCount < 2
    },
    staleTime: 300_000, // 5 minutes
  })

  // Fetch comprehensive tournament statistics
  const { data: tournamentStatsData, isLoading: tournamentStatsLoading, error: tournamentStatsError, refetch: refetchTournamentStats } = useQuery<{
    success: boolean
    player_name: string
    basic_stats: any
    yearly_breakdown: any
    recent_tournaments: any[]
    performance_trend: any[]
  }>({
    queryKey: ['player-tournament-stats', selectedPlayer],
    queryFn: async () => {
      const response = await fetch(`/api/player-performance/${encodeURIComponent(selectedPlayer!)}/tournament-statistics`, { headers: authHeaders })
      if (!response.ok) {
        const errorText = await response.text().catch(() => 'Unknown error')
        throw new Error(response.status === 403 ? 'You can only view your own performance.' :
                       response.status === 404 ? 'Player not found.' :
                       `Failed to fetch tournament statistics: ${errorText}`)
      }
      const data = await response.json()
      if (!data.success) {
        throw new Error(data.message || 'Failed to fetch tournament statistics')
      }
      return data
    },
    enabled: !!selectedPlayer && hasAuth,
    retry: (failureCount, error) => {
      // Don't retry on 403/404 errors
      if (error instanceof Error && (error.message.includes('403') || error.message.includes('404'))) {
        return false
      }
      return failureCount < 2
    },
    staleTime: 300_000, // 5 minutes
  })

  const {
    data: tournamentAnalytics,
    isLoading: tournamentAnalyticsLoading,
    error: tournamentAnalyticsError,
    refetch: refetchTournamentAnalytics,
  } = useQuery<TournamentAnalyticsResponse>({
    queryKey: ['player-tournament-analytics', selectedPlayer, analyticsWindow],
    queryFn: async () => {
      const response = await fetch(
        `/api/player-performance/${encodeURIComponent(selectedPlayer!)}/tournament-analytics?window=${analyticsWindow}`,
        { headers: authHeaders }
      )
      if (!response.ok) {
        throw new Error(
          response.status === 403
            ? 'You can only view your own performance.'
            : 'Failed to load tournament analytics'
        )
      }
      return response.json()
    },
    enabled: !!selectedPlayer && hasAuth,
    retry: 1,
    staleTime: 60_000,
  })

  const renderOverview = () => {
    if (!selectedPlayer) {
      return (
        <div className="text-center py-12 text-muted-foreground">
          {canViewAllPlayers ? (
            <>
              <p className="text-lg">
                {isSuperAdmin
                  ? 'Choose a player under Browse any player to view their performance'
                  : 'Select a player above to view their performance'}
              </p>
              <p className="text-sm mt-2">Admin/super_admin can view any player&apos;s charts and stats.</p>
            </>
          ) : (
            <>
              <p className="text-lg">Sign in to view your performance profile</p>
              <p className="text-sm mt-2">Your tournament placements, Fargo score, current ranking, and ranking progress will appear here.</p>
            </>
          )}
        </div>
      )
    }

    if (overviewLoading) {
      return (
        <div className="animate-pulse space-y-4">
          <div className="h-32 bg-muted rounded" />
          <div className="h-48 bg-muted rounded" />
        </div>
      )
    }

    if (overviewError) {
      return (
        <div className="rounded-lg border border-amber-800 bg-amber-950/30 p-6 text-center">
          <p className="text-amber-200 mb-2">Could not load this player&apos;s overview.</p>
          <p className="text-sm text-muted-foreground mb-4">{overviewError instanceof Error ? overviewError.message : 'Unknown error'}</p>
          <button type="button" onClick={() => refetchOverview()} className="px-4 py-2 rounded-lg bg-primary text-primary-foreground font-medium hover:opacity-90">Retry</button>
        </div>
      )
    }

    const displayOverview = overviewWithAlfa ?? overview
    if (!displayOverview) return null

    return (
      <div className="space-y-6">
        {/* Player Header Card — only this player's info */}
        <div className="bg-gradient-to-br from-slate-800 to-slate-900 p-6 rounded-xl border border-accent/30 shadow-lg">
          <h2 className="text-3xl font-bold text-white mb-4">{displayOverview.player_name}</h2>
          {displayOverview.narrative && (
            <div className="mb-4 border-l-2 border-slate-500 pl-3 space-y-1">
              {displayOverview.narrative_unchanged && (
                <p className="text-xs text-slate-500 uppercase tracking-wide">Summary unchanged</p>
              )}
              <p
                className={`text-sm ${displayOverview.narrative_unchanged ? 'text-slate-400' : 'text-slate-300/95'}`}
              >
                {displayOverview.narrative}
              </p>
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* WPBA Women */}
            {displayOverview.wpba && (
              <div className="bg-slate-700/30 p-4 rounded-lg border border-accent/20">
                <h3 className="text-lg font-semibold text-accent mb-2">WPBA (Women)</h3>
                <div className="space-y-2 text-sm">
                  <p className="flex justify-between">
                    <span className="text-muted-foreground">Rank:</span>
                    <span className="font-medium text-white">#{displayOverview.wpba.rank}</span>
                  </p>
                  <p className="flex justify-between">
                    <span className="text-muted-foreground">Points:</span>
                    <span className="font-medium text-white">{Number(displayOverview.wpba.rating).toFixed(0)}</span>
                  </p>
                  <p className="flex justify-between gap-4">
                    <span className="text-muted-foreground">Fargo (imported):</span>
                    <span className="font-medium text-white">
                      {displayOverview.wpba.fargo_rating != null ? Number(displayOverview.wpba.fargo_rating).toFixed(0) : '—'}
                    </span>
                  </p>
                  <p className="flex justify-between gap-4">
                    <span className="text-muted-foreground">ALFa (app):</span>
                    <span className="font-medium text-white">
                      {displayOverview.wpba.alfa_rating != null ? Number(displayOverview.wpba.alfa_rating).toFixed(0) : '—'}
                    </span>
                  </p>
                  <p className="flex justify-between">
                    <span className="text-muted-foreground">Country:</span>
                    <span className="font-medium text-white">{displayOverview.wpba.country ?? '—'}</span>
                  </p>
                </div>
              </div>
            )}
            {/* WPA Women only */}
            {displayOverview.wpa_women && (
              <div className="bg-slate-700/30 p-4 rounded-lg border border-accent/20">
                <h3 className="text-lg font-semibold text-accent mb-2">WPA Women</h3>
                <div className="space-y-2 text-sm">
                  <p className="flex justify-between">
                    <span className="text-muted-foreground">Rank:</span>
                    <span className="font-medium text-white">#{displayOverview.wpa_women.rank}</span>
                  </p>
                  <p className="flex justify-between">
                    <span className="text-muted-foreground">Points:</span>
                    <span className="font-medium text-white">{Number(displayOverview.wpa_women.rating).toFixed(0)}</span>
                  </p>
                  <p className="flex justify-between gap-4">
                    <span className="text-muted-foreground">Fargo (imported):</span>
                    <span className="font-medium text-white">
                      {displayOverview.wpa_women.fargo_rating != null ? Number(displayOverview.wpa_women.fargo_rating).toFixed(0) : '—'}
                    </span>
                  </p>
                  <p className="flex justify-between gap-4">
                    <span className="text-muted-foreground">ALFa (app):</span>
                    <span className="font-medium text-white">
                      {displayOverview.wpa_women.alfa_rating != null ? Number(displayOverview.wpa_women.alfa_rating).toFixed(0) : '—'}
                    </span>
                  </p>
                  <p className="flex justify-between">
                    <span className="text-muted-foreground">Country:</span>
                    <span className="font-medium text-white">{displayOverview.wpa_women.country ?? '—'}</span>
                  </p>
                </div>
              </div>
            )}
            {/* WPA Men only */}
            {displayOverview.wpa_men && (
              <div className="bg-slate-700/30 p-4 rounded-lg border border-accent/20">
                <h3 className="text-lg font-semibold text-accent mb-2">WPA Men</h3>
                <div className="space-y-2 text-sm">
                  <p className="flex justify-between">
                    <span className="text-muted-foreground">Rank:</span>
                    <span className="font-medium text-white">#{displayOverview.wpa_men.rank}</span>
                  </p>
                  <p className="flex justify-between">
                    <span className="text-muted-foreground">Points:</span>
                    <span className="font-medium text-white">{Number(displayOverview.wpa_men.rating).toFixed(0)}</span>
                  </p>
                  <p className="flex justify-between gap-4">
                    <span className="text-muted-foreground">Fargo (imported):</span>
                    <span className="font-medium text-white">
                      {displayOverview.wpa_men.fargo_rating != null ? Number(displayOverview.wpa_men.fargo_rating).toFixed(0) : '—'}
                    </span>
                  </p>
                  <p className="flex justify-between gap-4">
                    <span className="text-muted-foreground">ALFa (app):</span>
                    <span className="font-medium text-white">
                      {displayOverview.wpa_men.alfa_rating != null ? Number(displayOverview.wpa_men.alfa_rating).toFixed(0) : '—'}
                    </span>
                  </p>
                  <p className="flex justify-between">
                    <span className="text-muted-foreground">Country:</span>
                    <span className="font-medium text-white">{displayOverview.wpa_men.country ?? '—'}</span>
                  </p>
                </div>
              </div>
            )}
          </div>
          {!displayOverview.wpba && !displayOverview.wpa_women && !displayOverview.wpa_men && (
            <p className="text-muted-foreground text-sm mt-2">No ranking data for this player.</p>
          )}
        </div>

        {/* Tournament Statistics — this player only */}
        {displayOverview.tournament_stats && (
          <div className="bg-slate-800/50 p-6 rounded-xl border border-felt/30">
            <h3 className="text-xl font-bold text-white mb-4">🏆 Tournament Performance</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center p-3 bg-slate-700/30 rounded-lg">
                <div className="text-3xl font-bold text-accent">{displayOverview.tournament_stats.total_tournaments ?? 0}</div>
                <div className="text-sm text-muted-foreground mt-1">Total Tournaments</div>
              </div>
              <div className="text-center p-3 bg-slate-700/30 rounded-lg">
                <div className="text-3xl font-bold text-yellow-400">{displayOverview.tournament_stats.first_place_finishes ?? 0}</div>
                <div className="text-sm text-muted-foreground mt-1">1st Place</div>
              </div>
              <div className="text-center p-3 bg-slate-700/30 rounded-lg">
                <div className="text-3xl font-bold text-blue-400">{displayOverview.tournament_stats.top_3_finishes ?? 0}</div>
                <div className="text-sm text-muted-foreground mt-1">Top 3</div>
              </div>
              <div className="text-center p-3 bg-slate-700/30 rounded-lg">
                <div className="text-3xl font-bold text-green-400">{(displayOverview.tournament_stats.avg_placement ?? 0).toFixed(1)}</div>
                <div className="text-sm text-muted-foreground mt-1">Avg Placement</div>
              </div>
            </div>
          </div>
        )}

        {/* Tournament analytics by period — counts and rates from app data */}
        <div className="bg-slate-800/50 p-6 rounded-xl border border-felt/30">
          <h3 className="text-xl font-bold text-white mb-1">Tournament results by period</h3>
          <p className="text-xs text-muted-foreground mb-4">
            Percentages are shares of your recorded events in that period (not predictions). Match row uses bracket rows with a recorded winner.
          </p>
          <div className="flex flex-wrap gap-2 mb-4">
            {(
              [
                { key: 'recent_3' as const, label: 'Recent 3 events' },
                { key: 'season' as const, label: `This year (${new Date().getFullYear()})` },
                { key: 'all_time' as const, label: 'All time' },
              ] as const
            ).map(({ key, label }) => (
              <button
                key={key}
                type="button"
                onClick={() => setAnalyticsWindow(key)}
                className={`px-4 py-2 rounded-lg text-sm transition-colors ${
                  analyticsWindow === key
                    ? 'bg-accent text-white font-medium'
                    : 'bg-slate-700/50 text-muted-foreground hover:bg-slate-700'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {tournamentAnalyticsError && (
            <div className="rounded border border-amber-800 bg-amber-950/30 p-4 mb-4 flex items-center justify-between gap-2">
              <span className="text-amber-200 text-sm">
                {tournamentAnalyticsError instanceof Error ? tournamentAnalyticsError.message : 'Failed to load analytics'}
              </span>
              <button
                type="button"
                onClick={() => refetchTournamentAnalytics()}
                className="px-3 py-1 rounded bg-primary text-primary-foreground text-sm shrink-0"
              >
                Retry
              </button>
            </div>
          )}
          {tournamentAnalyticsLoading && !tournamentAnalytics ? (
            <div className="h-32 bg-muted/20 rounded animate-pulse" />
          ) : tournamentAnalytics ? (
            <div className="space-y-4">
              <p className="text-sm text-slate-400">{tournamentAnalytics.label}</p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="p-3 bg-slate-700/30 rounded-lg text-center">
                  <div className="text-2xl font-bold text-white">{tournamentAnalytics.counts.events}</div>
                  <div className="text-xs text-muted-foreground mt-1">Events</div>
                </div>
                <div className="p-3 bg-slate-700/30 rounded-lg text-center">
                  <div className="text-2xl font-bold text-yellow-400">{tournamentAnalytics.counts.first_place}</div>
                  <div className="text-xs text-muted-foreground mt-1">1st place</div>
                  {tournamentAnalytics.rates_pct.first_place != null && (
                    <div className="text-xs text-slate-400 mt-0.5">{tournamentAnalytics.rates_pct.first_place}% of events</div>
                  )}
                </div>
                <div className="p-3 bg-slate-700/30 rounded-lg text-center">
                  <div className="text-2xl font-bold text-blue-400">{tournamentAnalytics.counts.top_3}</div>
                  <div className="text-xs text-muted-foreground mt-1">Top 3</div>
                  {tournamentAnalytics.rates_pct.top_3 != null && (
                    <div className="text-xs text-slate-400 mt-0.5">{tournamentAnalytics.rates_pct.top_3}% of events</div>
                  )}
                </div>
                <div className="p-3 bg-slate-700/30 rounded-lg text-center">
                  <div className="text-2xl font-bold text-emerald-400">{tournamentAnalytics.counts.top_8}</div>
                  <div className="text-xs text-muted-foreground mt-1">Top 8</div>
                  {tournamentAnalytics.rates_pct.top_8 != null && (
                    <div className="text-xs text-slate-400 mt-0.5">{tournamentAnalytics.rates_pct.top_8}% of events</div>
                  )}
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
                <div className="p-3 bg-slate-700/20 rounded-lg flex justify-between">
                  <span className="text-muted-foreground">Avg placement</span>
                  <span className="text-white font-medium">
                    {tournamentAnalytics.avg_placement != null ? tournamentAnalytics.avg_placement.toFixed(2) : '—'}
                  </span>
                </div>
                <div className="p-3 bg-slate-700/20 rounded-lg flex justify-between">
                  <span className="text-muted-foreground">Best placement</span>
                  <span className="text-white font-medium">
                    {tournamentAnalytics.best_placement != null ? tournamentAnalytics.best_placement : '—'}
                  </span>
                </div>
                <div className="p-3 bg-slate-700/20 rounded-lg flex justify-between">
                  <span className="text-muted-foreground">Total points (sum)</span>
                  <span className="text-white font-medium">
                    {tournamentAnalytics.total_points != null ? tournamentAnalytics.total_points.toFixed(0) : '—'}
                  </span>
                </div>
              </div>
              {tournamentAnalytics.match_record && tournamentAnalytics.match_record.matches_with_winner > 0 && (
                <div className="p-3 bg-slate-700/20 rounded-lg text-sm">
                  <span className="text-muted-foreground">Matches with winner recorded: </span>
                  <span className="text-white">
                    {tournamentAnalytics.match_record.match_wins}W — {tournamentAnalytics.match_record.match_losses}L
                    {tournamentAnalytics.match_record.match_win_rate_pct != null &&
                      ` (${tournamentAnalytics.match_record.match_win_rate_pct}% win rate)`}
                  </span>
                </div>
              )}
              {tournamentAnalytics.events.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-slate-300 mb-2">Events in this period</h4>
                  <ul className="text-xs text-slate-400 space-y-1 max-h-48 overflow-y-auto">
                    {tournamentAnalytics.events.map((ev, idx) => (
                      <li key={`${ev.tournament_id}-${idx}`} className="flex justify-between gap-2 border-b border-slate-700/50 pb-1">
                        <span className="truncate">{ev.tournament_name ?? ev.tournament_id}</span>
                        <span className="shrink-0 text-slate-300">
                          {ev.tournament_date ? new Date(ev.tournament_date).toLocaleDateString() : '—'} · P
                          {ev.placement ?? '—'}
                          {ev.points != null ? ` · ${Number(ev.points).toFixed(0)} pts` : ''}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : null}
        </div>

        {/* Ranking progress + Fargo over time: two columns */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Ranking History Chart — one division at a time */}
          <div className="bg-slate-800/50 p-6 rounded-xl border border-felt/30">
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
              <h3 className="text-xl font-bold text-white">📈 Ranking progress</h3>
              <div className="flex gap-2">
                {(['WPBA', 'WPA_Women', 'WPA_Men'] as const).map((assoc) => (
                  <button
                    key={assoc}
                    onClick={() => setSelectedAssociation(assoc)}
                    className={`px-4 py-2 rounded-lg transition-colors ${
                      selectedAssociation === assoc
                        ? 'bg-accent text-white font-medium'
                        : 'bg-slate-700/50 text-muted-foreground hover:bg-slate-700'
                    }`}
                  >
                    {assoc === 'WPBA' ? 'WPBA' : assoc === 'WPA_Women' ? 'WPA Women' : 'WPA Men'}
                  </button>
                ))}
              </div>
            </div>
            {historyError && (
              <div className="rounded border border-amber-800 bg-amber-950/30 p-4 mb-4 flex items-center justify-between gap-2">
                <span className="text-amber-200 text-sm">{historyError instanceof Error ? historyError.message : 'Failed to load history'}</span>
                <button type="button" onClick={() => refetchHistory()} className="px-3 py-1 rounded bg-primary text-primary-foreground text-sm">Retry</button>
              </div>
            )}
            {historyLoading ? (
              <div className="h-64 bg-muted/20 rounded animate-pulse" />
            ) : historyData && historyData.history.length > 0 ? (
              <PerformanceCurveChart
                history={historyData.history}
                tournaments={tournamentsData?.tournaments ?? []}
              />
            ) : !historyError ? (
              <div className="text-center py-8 text-muted-foreground">
                No ranking history for this division
              </div>
            ) : null}
          </div>

          {/* Fargo rating over time — from archives + rankings snapshots */}
          <div className="bg-slate-800/50 p-6 rounded-xl border border-felt/30">
            <h3 className="text-xl font-bold text-white mb-2">📊 Fargo rating over time</h3>
            <p className="text-sm text-muted-foreground mb-4">
              Historical Fargo from rating archives and rankings snapshots.
            </p>
            {historicalRatingsLoading ? (
              <div className="h-64 bg-muted/20 rounded animate-pulse" />
            ) : historicalRatingsError ? (
              <div className="text-center py-8 text-muted-foreground">
                <p>Could not load Fargo history</p>
                <p className="text-sm mt-1">{historicalRatingsError instanceof Error ? historicalRatingsError.message : 'Unknown error'}</p>
              </div>
            ) : historicalRatingsData && historicalRatingsData.rating_series.fargo.length > 0 ? (
              <div className="h-64 min-h-[256px] min-w-[200px]">
                <ResponsiveContainer width="100%" height={256} minWidth={200} minHeight={256}>
                  <LineChart
                    data={[...historicalRatingsData.rating_series.fargo]
                      .filter((e) => e?.date != null && typeof e.rating === 'number')
                      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
                      .map((e) => ({ date: e.date, rating: e.rating, source: e.source }))}
                    margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis
                      dataKey="date"
                      stroke="#9CA3AF"
                      fontSize={11}
                      tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', year: '2-digit' })}
                    />
                    <YAxis stroke="#9CA3AF" fontSize={11} domain={['auto', 'auto']} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: '8px' }}
                      labelFormatter={(date) => new Date(date).toLocaleDateString()}
                      formatter={(value: number) => [value?.toFixed(0) ?? '—', 'Fargo']}
                    />
                    <Line
                      type="monotone"
                      dataKey="rating"
                      stroke="#3B82F6"
                      strokeWidth={2}
                      dot={{ fill: '#3B82F6', strokeWidth: 2, r: 3 }}
                      connectNulls={false}
                      name="Fargo"
                    />
                  </LineChart>
                </ResponsiveContainer>
                <p className="text-xs text-muted-foreground mt-2">
                  {historicalRatingsData.rating_series.fargo.length} point{historicalRatingsData.rating_series.fargo.length !== 1 ? 's' : ''}
                  {historicalRatingsData.rating_series.fargo.length > 0 && (
                    <> · Latest: {historicalRatingsData.rating_series.fargo[historicalRatingsData.rating_series.fargo.length - 1]?.rating?.toFixed(0) ?? '—'}</>
                  )}
                </p>
              </div>
            ) : (
              <div className="text-center py-8 text-muted-foreground">
                <p>No Fargo history yet</p>
                <p className="text-sm mt-1">Points will appear as snapshots and archives are collected</p>
              </div>
            )}
          </div>
        </div>

        {/* Historical Ratings Chart */}
        <div className="bg-slate-800/50 p-6 rounded-xl border border-felt/30">
          <h3 className="text-xl font-bold text-white mb-4">📈 Historical Rating Trends</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Track how Fargo, ALFA, and EST ratings have changed over time. This shows the system's learning and accuracy improvements.
          </p>

          {historicalRatingsLoading ? (
            <div className="h-64 bg-muted/20 rounded animate-pulse" />
          ) : historicalRatingsError ? (
            <div className="text-center py-8 text-muted-foreground">
              <p>Could not load historical rating data</p>
              <p className="text-sm mt-1">{historicalRatingsError instanceof Error ? historicalRatingsError.message : 'Unknown error'}</p>
            </div>
          ) : historicalRatingsData && historicalRatingsData.total_entries > 0 ? (
            <div className="space-y-4">
              {/* Rating Trends Chart */}
              <div className="h-80 min-h-[320px] min-w-[200px]">
                <ResponsiveContainer width="100%" height={320} minWidth={200} minHeight={320}>
                  <LineChart data={(() => {
                    try {
                      // Combine all rating series into a unified dataset
                      const allDates = new Set<string>()
                      const ratingMap: Record<string, Record<string, number | null>> = {}

                      // Validate and collect all dates and initialize rating map
                      Object.entries(historicalRatingsData.rating_series).forEach(([ratingType, series]) => {
                        if (Array.isArray(series)) {
                          series.forEach(entry => {
                            if (entry && entry.date && typeof entry.rating === 'number') {
                              allDates.add(entry.date)
                              if (!ratingMap[entry.date]) {
                                ratingMap[entry.date] = { date: entry.date, fargo: null, alfa: null, est: null }
                              }
                              ratingMap[entry.date][ratingType] = entry.rating
                            }
                          })
                        }
                      })

                      // Convert to array and sort by date
                      const chartData = Array.from(allDates)
                        .map(date => ratingMap[date])
                        .filter(item => item && item.date) // Filter out invalid entries
                        .sort((a, b) => {
                          try {
                            return new Date(a.date).getTime() - new Date(b.date).getTime()
                          } catch (e) {
                            return 0 // Fallback for invalid dates
                          }
                        })

                      return chartData.length > 0 ? chartData : []
                    } catch (error) {
                      console.error('Error processing historical ratings chart data:', error)
                      return []
                    }
                  })()}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                    <XAxis
                      dataKey="date"
                      stroke="#9CA3AF"
                      fontSize={12}
                      tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', year: '2-digit' })}
                    />
                    <YAxis stroke="#9CA3AF" fontSize={12} domain={[100, 1000]} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#1F2937',
                        border: '1px solid #374151',
                        borderRadius: '8px'
                      }}
                      labelFormatter={(date) => new Date(date).toLocaleDateString()}
                      formatter={(value: number, name: string) => [
                        value?.toFixed(0) ?? 'N/A',
                        name === 'fargo' ? 'Fargo' : name === 'alfa' ? 'ALFA' : 'EST'
                      ]}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="fargo"
                      stroke="#3B82F6"
                      strokeWidth={2}
                      dot={{ fill: '#3B82F6', strokeWidth: 2, r: 4 }}
                      connectNulls={false}
                      name="Fargo Rating"
                    />
                    <Line
                      type="monotone"
                      dataKey="alfa"
                      stroke="#10B981"
                      strokeWidth={2}
                      dot={{ fill: '#10B981', strokeWidth: 2, r: 4 }}
                      connectNulls={false}
                      name="ALFA Rating"
                    />
                    <Line
                      type="monotone"
                      dataKey="est"
                      stroke="#F59E0B"
                      strokeWidth={2}
                      dot={{ fill: '#F59E0B', strokeWidth: 2, r: 4 }}
                      connectNulls={false}
                      name="EST Rating"
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Rating Statistics Summary */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                <div className="bg-slate-700/30 p-3 rounded-lg">
                  <div className="text-blue-400 font-semibold">Fargo Ratings</div>
                  <div className="text-white">
                    {historicalRatingsData.rating_series.fargo.length} data points
                  </div>
                  {historicalRatingsData.rating_series.fargo.length > 0 && (
                    <div className="text-muted-foreground text-xs">
                      Latest: {historicalRatingsData.rating_series.fargo[historicalRatingsData.rating_series.fargo.length - 1]?.rating?.toFixed(0) ?? 'N/A'}
                    </div>
                  )}
                </div>
                <div className="bg-slate-700/30 p-3 rounded-lg">
                  <div className="text-green-400 font-semibold">ALFA Ratings</div>
                  <div className="text-white">
                    {historicalRatingsData.rating_series.alfa.length} data points
                  </div>
                  {historicalRatingsData.rating_series.alfa.length > 0 && (
                    <div className="text-muted-foreground text-xs">
                      Latest: {historicalRatingsData.rating_series.alfa[historicalRatingsData.rating_series.alfa.length - 1]?.rating?.toFixed(0) ?? 'N/A'}
                    </div>
                  )}
                </div>
                <div className="bg-slate-700/30 p-3 rounded-lg">
                  <div className="text-yellow-400 font-semibold">EST Ratings</div>
                  <div className="text-white">
                    {historicalRatingsData.rating_series.est.length} data points
                  </div>
                  {historicalRatingsData.rating_series.est.length > 0 && (
                    <div className="text-muted-foreground text-xs">
                      Latest: {historicalRatingsData.rating_series.est[historicalRatingsData.rating_series.est.length - 1]?.rating?.toFixed(0) ?? 'N/A'}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <p>No historical rating data available</p>
              <p className="text-sm mt-1">Rating history will appear here as the player participates in tournaments</p>
            </div>
          )}
        </div>

        {/* Tournament Performance Chart */}
        <div className="bg-slate-800/50 p-6 rounded-xl border border-felt/30">
          <h3 className="text-xl font-bold text-white mb-4">🏆 Tournament Performance History</h3>

          {tournamentStatsLoading ? (
            <div className="h-64 bg-muted/20 rounded animate-pulse" />
          ) : tournamentStatsError ? (
            <div className="text-center py-8 text-muted-foreground">
              <p>Could not load tournament statistics</p>
              <p className="text-sm mt-1">{tournamentStatsError instanceof Error ? tournamentStatsError.message : 'Unknown error'}</p>
            </div>
          ) : tournamentStatsData ? (
            <div className="space-y-6">
              {/* Tournament Statistics Overview */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-slate-700/30 p-4 rounded-lg text-center">
                  <div className="text-2xl font-bold text-blue-400">
                    {tournamentStatsData.basic_stats?.total_tournaments ?? 0}
                  </div>
                  <div className="text-sm text-muted-foreground">Total Tournaments</div>
                </div>
                <div className="bg-slate-700/30 p-4 rounded-lg text-center">
                  <div className="text-2xl font-bold text-green-400">
                    {tournamentStatsData.basic_stats?.first_place_finishes ?? 0}
                  </div>
                  <div className="text-sm text-muted-foreground">1st Place Finishes</div>
                </div>
                <div className="bg-slate-700/30 p-4 rounded-lg text-center">
                  <div className="text-2xl font-bold text-yellow-400">
                    {tournamentStatsData.basic_stats?.top_3_finishes ?? 0}
                  </div>
                  <div className="text-sm text-muted-foreground">Top 3 Finishes</div>
                </div>
                <div className="bg-slate-700/30 p-4 rounded-lg text-center">
                  <div className="text-2xl font-bold text-purple-400">
                    {tournamentStatsData.basic_stats?.average_placement?.toFixed(1) ?? 'N/A'}
                  </div>
                  <div className="text-sm text-muted-foreground">Avg Placement</div>
                </div>
              </div>

              {/* Performance Trend Chart */}
              {tournamentStatsData.performance_trend && tournamentStatsData.performance_trend.length > 0 && (
                <div className="space-y-4">
                  <h4 className="text-lg font-semibold text-white">Performance Trend Over Time</h4>
                  <div className="h-64 min-h-[256px] min-w-[200px]">
                    <ResponsiveContainer width="100%" height={256} minWidth={200} minHeight={256}>
                      <LineChart data={tournamentStatsData.performance_trend}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                        <XAxis
                          dataKey="year"
                          stroke="#9CA3AF"
                          fontSize={12}
                        />
                        <YAxis
                          stroke="#9CA3AF"
                          fontSize={12}
                          domain={['dataMin - 1', 'dataMax + 1']}
                          reversed
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#1F2937',
                            border: '1px solid #374151',
                            borderRadius: '8px'
                          }}
                          formatter={(value: number, name: string) => [
                            value?.toFixed(2) ?? 'N/A',
                            name === 'avg_placement' ? 'Avg Placement' :
                            name === 'win_rate' ? 'Win Rate (%)' :
                            name === 'top3_rate' ? 'Top 3 Rate (%)' : name
                          ]}
                        />
                        <Legend />
                        <Line
                          type="monotone"
                          dataKey="avg_placement"
                          stroke="#3B82F6"
                          strokeWidth={3}
                          dot={{ fill: '#3B82F6', strokeWidth: 2, r: 5 }}
                          name="Avg Placement"
                        />
                        <Line
                          type="monotone"
                          dataKey="win_rate"
                          stroke="#10B981"
                          strokeWidth={2}
                          dot={{ fill: '#10B981', strokeWidth: 2, r: 4 }}
                          name="Win Rate (%)"
                        />
                        <Line
                          type="monotone"
                          dataKey="top3_rate"
                          stroke="#F59E0B"
                          strokeWidth={2}
                          dot={{ fill: '#F59E0B', strokeWidth: 2, r: 4 }}
                          name="Top 3 Rate (%)"
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}

              {/* Recent Tournament Results */}
              {tournamentStatsData.recent_tournaments && tournamentStatsData.recent_tournaments.length > 0 && (
                <div className="space-y-4">
                  <h4 className="text-lg font-semibold text-white">Recent Tournament Results</h4>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {tournamentStatsData.recent_tournaments.map((tournament: any, index: number) => (
                      <div key={index} className="bg-slate-700/20 p-3 rounded-lg flex items-center justify-between">
                        <div className="flex-1">
                          <div className="font-medium text-white">{tournament.tournament_name}</div>
                          <div className="text-sm text-muted-foreground">
                            {tournament.date ? new Date(tournament.date).getFullYear() : 'N/A'} • {tournament.association}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`font-bold ${
                            tournament.placement === 1 ? 'text-yellow-400' :
                            tournament.placement === 2 ? 'text-gray-400' :
                            tournament.placement === 3 ? 'text-amber-600' :
                            'text-white'
                          }`}>
                            #{tournament.placement}
                          </div>
                          {tournament.points && (
                            <div className="text-sm text-muted-foreground">
                              {tournament.points} pts
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <p>No tournament data available</p>
              <p className="text-sm mt-1">Tournament statistics will appear here as results are recorded</p>
            </div>
          )}
        </div>

        {/* Performance Analytics */}
        <div className="bg-slate-800/50 p-6 rounded-xl border border-felt/30">
          <h3 className="text-xl font-bold text-white mb-4">📊 Performance Analytics</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {(() => {
              const stats = displayOverview.tournament_stats
              const tournaments = tournamentsData?.tournaments ?? []
              const metrics = []

              if (stats && tournaments.length > 0) {
                // Performance trend
                const sortedTournaments = [...tournaments].sort((a, b) =>
                  new Date(a.tournament_date ?? a.start_date ?? 0).getTime() - new Date(b.tournament_date ?? b.start_date ?? 0).getTime()
                )
                const firstHalf = sortedTournaments.slice(0, Math.floor(sortedTournaments.length / 2))
                const secondHalf = sortedTournaments.slice(Math.floor(sortedTournaments.length / 2))

                const firstHalfAvg = firstHalf.length > 0
                  ? firstHalf.reduce((sum, t) => sum + t.placement, 0) / firstHalf.length
                  : 0
                const secondHalfAvg = secondHalf.length > 0
                  ? secondHalf.reduce((sum, t) => sum + t.placement, 0) / secondHalf.length
                  : 0

                const trend = secondHalfAvg < firstHalfAvg ? 'improving' : secondHalfAvg > firstHalfAvg ? 'declining' : 'stable'
                const trendIcon = trend === 'improving' ? '📈' : trend === 'declining' ? '📉' : '➡️'
                const trendColor = trend === 'improving' ? 'text-green-400' : trend === 'declining' ? 'text-red-400' : 'text-blue-400'

                metrics.push({
                  title: 'Performance Trend',
                  value: `${trendIcon} ${trend.charAt(0).toUpperCase() + trend.slice(1)}`,
                  subtitle: `Recent avg: ${secondHalfAvg.toFixed(1)} vs Overall: ${(stats.avg_placement ?? 0).toFixed(1)}`,
                  color: trendColor
                })

                // Best streak analysis
                let currentStreak = 0
                let bestStreak = 0
                let tempStreak = 0

                for (const tournament of sortedTournaments) {
                  if (tournament.placement <= 3) {
                    tempStreak++
                    bestStreak = Math.max(bestStreak, tempStreak)
                  } else {
                    tempStreak = 0
                  }
                }

                // Current streak (from most recent)
                for (let i = sortedTournaments.length - 1; i >= 0; i--) {
                  if (sortedTournaments[i].placement <= 3) {
                    currentStreak++
                  } else {
                    break
                  }
                }

                metrics.push({
                  title: 'Top 3 Streaks',
                  value: `Best: ${bestStreak}`,
                  subtitle: `Current: ${currentStreak}`,
                  color: bestStreak > 2 ? 'text-green-400' : 'text-blue-400'
                })

                // Points per tournament
                const totalPoints = tournaments.reduce((sum, t) => sum + t.points, 0)
                const avgPoints = tournaments.length > 0 ? totalPoints / tournaments.length : 0

                metrics.push({
                  title: 'Avg Points/Tournament',
                  value: avgPoints.toFixed(1),
                  subtitle: `Total: ${totalPoints} pts`,
                  color: avgPoints > 50 ? 'text-green-400' : avgPoints > 25 ? 'text-blue-400' : 'text-yellow-400'
                })

                // Association distribution
                const associations = tournaments.reduce((acc, t) => {
                  acc[t.association] = (acc[t.association] || 0) + 1
                  return acc
                }, {} as Record<string, number>)

                const primaryAssociation = Object.entries(associations).sort(([,a], [,b]) => b - a)[0]?.[0] || 'N/A'

                metrics.push({
                  title: 'Primary Association',
                  value: primaryAssociation,
                  subtitle: `${Object.keys(associations).length} associations played`,
                  color: 'text-purple-400'
                })
              }

              return metrics.map((metric, idx) => (
                <div key={idx} className="bg-slate-900/50 p-4 rounded-lg border border-slate-700">
                  <div className="flex justify-between items-start mb-2">
                    <h4 className="text-sm font-medium text-slate-400">{metric.title}</h4>
                    <span className={`text-lg font-bold ${metric.color}`}>{metric.value}</span>
                  </div>
                  <p className="text-xs text-slate-500">{metric.subtitle}</p>
                </div>
              ))
            })()}
          </div>
        </div>

        {/* Go public with stats */}
        <div className="bg-slate-800/50 p-4 rounded-xl border border-felt/30">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={goPublic}
              onChange={(e) => {
                const v = e.target.checked
                setGoPublic(v)
                try {
                  localStorage.setItem(GO_PUBLIC_KEY, String(v))
                } catch (error) {
                  logger.warn('Failed to persist go-public preference', { value: v }, error as Error)
                }
              }}
              className="w-4 h-4 rounded border-slate-600 text-accent focus:ring-accent"
            />
            <span className="text-sm text-slate-200">Go public with stats — let other players see my ranking, Fargo rating, and chart</span>
          </label>
        </div>

        {/* Tournament Results */}
        <div className="bg-slate-800/50 p-6 rounded-xl border border-felt/30">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xl font-bold text-white">🎯 Tournament Results</h3>
            <Link
              to="/tournaments/history"
              className="text-sm font-medium text-accent hover:underline"
            >
              View tournament history →
            </Link>
          </div>
          {tournamentsLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-20 bg-muted/20 rounded animate-pulse" />
              ))}
            </div>
          ) : tournamentsData && tournamentsData.tournaments.length > 0 ? (
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {tournamentsData.tournaments.map((tournament, idx) => (
                <div key={idx} className="bg-slate-900/50 p-4 rounded-lg border border-slate-700 hover:border-accent/50 transition-colors">
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <h4 className="font-semibold text-white">{tournament.tournament_name}</h4>
                      <p className="text-sm text-muted-foreground">
                        {tournament.location} • {tournament.tournament_date ? new Date(tournament.tournament_date).toLocaleDateString() : '—'}
                      </p>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                      tournament.placement === 1 ? 'bg-yellow-500/20 text-yellow-400' :
                      tournament.placement <= 3 ? 'bg-blue-500/20 text-blue-400' :
                      tournament.placement <= 8 ? 'bg-green-500/20 text-green-400' :
                      'bg-slate-700 text-muted-foreground'
                    }`}>
                      {tournament.placement === 1 ? '🥇' : tournament.placement === 2 ? '🥈' : tournament.placement === 3 ? '🥉' : `#${tournament.placement}`}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-4 text-sm">
                    <span className="text-muted-foreground">
                      <span className="text-accent font-medium">{tournament.points}</span> pts
                    </span>
                    {tournament.fargo_rating_at_scrape != null && (
                      <span className="text-muted-foreground">
                        Fargo: <span className="font-medium text-white">{Number(tournament.fargo_rating_at_scrape).toFixed(0)}</span>
                      </span>
                    )}
                    <span className="text-muted-foreground">{tournament.association}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : tournamentsError ? (
            <div className="rounded border border-amber-800 bg-amber-950/30 p-4 flex items-center justify-between gap-2">
              <span className="text-amber-200 text-sm">{tournamentsError instanceof Error ? tournamentsError.message : 'Failed to load tournaments'}</span>
              <button type="button" onClick={() => refetchTournaments()} className="px-3 py-1 rounded bg-primary text-primary-foreground text-sm">Retry</button>
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              No tournament results available
            </div>
          )}
        </div>

        {/* AI Coach Insights */}
        <div className="bg-slate-800/50 p-6 rounded-xl border border-felt/30">
          <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
            <span>🤖</span> AI Coach Insights
          </h3>
          <div className="space-y-4">
            {(() => {
              const stats = displayOverview.tournament_stats
              const tournaments = tournamentsData?.tournaments ?? []
              const recentTournaments = tournaments.slice(0, 5)
              const insights: string[] = []

              if (stats) {
                const winRate = stats.total_tournaments > 0 ? (stats.first_place_finishes / stats.total_tournaments) * 100 : 0
                const top3Rate = stats.total_tournaments > 0 ? (stats.top_3_finishes / stats.total_tournaments) * 100 : 0

                if (winRate > 30) {
                  insights.push("🎯 Excellent consistency! Your win rate suggests strong fundamentals. Focus on maintaining this level while challenging tougher competition.")
                } else if (winRate > 15) {
                  insights.push("📈 Good progress! Your win rate shows solid improvement. Keep working on shot accuracy and position play.")
                } else if (stats.total_tournaments > 5) {
                  insights.push("🎯 Focus on fundamentals. Work on break shots, safety play, and bank shots to improve your win percentage.")
                }

                if (top3Rate > 50) {
                  insights.push("⭐ Top performer! You're consistently in the money. Consider studying professional matches to fine-tune your game.")
                }

                const avgPlacement = stats.avg_placement ?? 0
                if (avgPlacement < 4 && stats.total_tournaments > 3) {
                  insights.push("💪 Strong competitor! Your average placement is impressive. Keep practicing to maintain this level.")
                } else if (avgPlacement > 8) {
                  insights.push("🎯 Room for improvement. Focus on shot selection and reading the table layout better.")
                }

                // Recent performance analysis
                if (recentTournaments.length >= 3) {
                  const recentAvg = recentTournaments.reduce((sum, t) => sum + t.placement, 0) / recentTournaments.length
                  const overallAvg = avgPlacement

                  if (recentAvg < overallAvg - 1) {
                    insights.push("📈 Improving trend! Your recent performances are better than your historical average. Keep this momentum!")
                  } else if (recentAvg > overallAvg + 1) {
                    insights.push("📊 Recent results below average. Review your recent matches - focus on consistency and mental preparation.")
                  }
                }

                // Tournament frequency
                if (stats.total_tournaments < 5) {
                  insights.push("🎮 Play more tournaments! Regular competition is key to improving your ranking and gaining experience.")
                }
              }

              if (insights.length === 0) {
                insights.push("🎯 Start playing tournaments to get personalized coaching insights!")
              }

              return insights.map((insight, idx) => (
                <div key={idx} className="bg-slate-900/50 p-4 rounded-lg border border-slate-700">
                  <p className="text-slate-200 text-sm leading-relaxed">{insight}</p>
                </div>
              ))
            })()}
          </div>
        </div>

        {/* AI Video Analysis Section */}
        <div className="bg-slate-800/50 p-6 rounded-xl border border-felt/30">
          <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
            <span>🎥</span> AI Video Analysis
          </h3>

          <VideoAnalysisSection selectedPlayer={selectedPlayer} />
        </div>

      </div>
    )
  }

  // Unique names (API can repeat; super_admin would also see the same list twice if dropdown + browse both rendered)
  const playerNames = useMemo(() => {
    const raw = playerNamesData?.names ?? []
    const byKey = new Map<string, string>()
    for (const n of raw) {
      const t = n.trim()
      if (!t) continue
      const key = t.toLowerCase()
      if (!byKey.has(key)) byKey.set(key, t)
    }
    return [...byKey.values()].sort((a, b) =>
      a.localeCompare(b, undefined, { sensitivity: 'base' })
    )
  }, [playerNamesData?.names])
  // Super admin: browse-only UI. Regular admin: dropdown only (no duplicate list).
  const showPlayerSelector = canViewAllPlayers && !isSuperAdmin && playerNames.length > 0
  const showAllPlayersButtons = isSuperAdmin && playerNames.length > 0
  const [playerFilter, setPlayerFilter] = useState('')
  const filteredPlayerNames = useMemo(() => {
    if (!playerFilter.trim()) return playerNames
    const q = playerFilter.trim().toLowerCase()
    return playerNames.filter((n) => n.toLowerCase().includes(q))
  }, [playerNames, playerFilter])

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-4xl font-bold text-white mb-2">
          <span className="text-accent">{canViewAllPlayers ? 'Player' : 'Your'}</span> Performance
        </h1>
        <p className="text-muted-foreground mb-4">
          Finishes, Fargo rating, current rank, and how rank has changed over time.
        </p>

        {showPlayerSelector && (
          <div className="mb-6">
            <label className="block text-sm font-medium text-slate-300 mb-2">View player</label>
            <select
              value={selectedPlayer ?? ''}
              onChange={(e) => setSelectedPlayer(e.target.value || null)}
              className="bg-slate-800 border border-slate-600 rounded-lg px-4 py-2 text-white min-w-[200px] focus:ring-2 focus:ring-accent focus:border-accent"
            >
              <option value="">Select a player…</option>
              {playerNames.map((name) => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>
          </div>
        )}

        {showAllPlayersButtons && (
          <div className="mb-6 p-4 rounded-xl border border-felt/30 bg-slate-800/50">
            <h2 className="text-lg font-semibold text-white mb-2">Browse any player</h2>
            <input
              type="text"
              placeholder="Filter by name…"
              value={playerFilter}
              onChange={(e) => setPlayerFilter(e.target.value)}
              className="mb-3 w-full max-w-xs px-3 py-2 rounded-lg bg-background border border-slate-600 text-white placeholder:text-slate-400 focus:ring-2 focus:ring-accent"
            />
            <div className="flex flex-wrap gap-2 max-h-48 overflow-y-auto">
              {filteredPlayerNames.map((name) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => setSelectedPlayer(name)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    selectedPlayer === name
                      ? 'bg-accent text-white ring-2 ring-accent ring-offset-2 ring-offset-background'
                      : 'bg-slate-700/80 text-slate-200 hover:bg-slate-600 border border-slate-600'
                  }`}
                >
                  {name}
                </button>
              ))}
            </div>
            {filteredPlayerNames.length === 0 && <p className="text-sm text-muted-foreground">No players match the filter.</p>}
          </div>
        )}

        {/* Get notified when a player's ranking changes */}
        <div className="rounded-xl border border-border bg-card p-4 shadow-sm mb-6" role="region" aria-label="Email notifications">
          <div className="flex items-center justify-between gap-2 mb-2">
            <p className="font-medium text-foreground">Get notified when a player&apos;s ranking changes</p>
            <a
              href={`${API_BASE_URL}/docs/notifications-email`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-primary hover:underline shrink-0"
            >
              Learn more
            </a>
          </div>
          <p className="text-sm text-muted-foreground mb-3">
            Enter your email and the player name. We&apos;ll email you when that player&apos;s rank or points change ({notifySystem}).
          </p>
          {notifySuccess && (
            <p className="text-sm text-green-600 dark:text-green-400 mb-3" role="alert">{notifySuccess}</p>
          )}
          {notifyError && (
            <p className="text-sm text-destructive mb-3" role="alert">{notifyError}</p>
          )}
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-0 w-full sm:w-auto sm:min-w-[12rem]">
              <label htmlFor="notify-email-pp" className="block text-xs font-medium text-muted-foreground mb-1">Email</label>
              <input
                id="notify-email-pp"
                type="email"
                value={notifyEmail}
                onChange={(e) => { setNotifyEmail(e.target.value); setNotifyError(null); setNotifySuccess(null); }}
                placeholder="you@example.com"
                className="w-full min-w-0 px-3 py-2.5 rounded-lg bg-background border border-input text-foreground text-sm"
              />
            </div>
            <div className="min-w-0 w-full sm:w-auto sm:min-w-[12rem]">
              <label htmlFor="notify-player-pp" className="block text-xs font-medium text-muted-foreground mb-1">Player name</label>
              <input
                id="notify-player-pp"
                type="text"
                value={notifyPlayerName}
                onChange={(e) => { setNotifyPlayerName(e.target.value); setNotifyError(null); setNotifySuccess(null); }}
                placeholder="Player name"
                className="w-full min-w-0 px-3 py-2.5 rounded-lg bg-background border border-input text-foreground text-sm"
              />
            </div>
            <button
              type="button"
              onClick={() => {
                if (!notifyEmail.trim() || !notifyPlayerName.trim()) {
                  setNotifyError('Email and player name are required.')
                  return
                }
                notifySubscribeMutation.mutate({
                  email: notifyEmail.trim(),
                  playerName: notifyPlayerName.trim(),
                  system: notifySystem,
                })
              }}
              disabled={notifySubscribeMutation.isPending}
              className="min-h-[44px] shrink-0 px-4 py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {notifySubscribeMutation.isPending ? '…' : 'Notify me'}
            </button>
          </div>
        </div>

        {renderOverview()}
      </div>
    </div>
  )
}
