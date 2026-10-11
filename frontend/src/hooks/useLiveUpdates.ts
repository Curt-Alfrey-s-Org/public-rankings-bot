/**
 * Live updates via WebSocket + SSE.
 *
 * Error handling:
 * - WebSocket: useWebSocket manages connect/disconnect; ConnectionStatus shows reconnect state.
 *   On close (e.g. 1006): exponential backoff reconnect; app falls back to React Query polling.
 * - SSE (/api/live/updates): EventSource onerror logs disconnect; ERR_QUIC_PROTOCOL_ERROR is
 *   a transport issue (QUIC/HTTP3). App continues with WebSocket + polling if SSE fails.
 * See docs/DEBUG_CONSOLE_ERRORS.md for troubleshooting.
 */
import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useWebSocket, LiveUpdateMessage, TournamentUpdateData, MatchScoreUpdateData, PlayerRegistrationData } from './useWebSocket'
import { logger } from '@/lib/logger'
import { toast } from '@/lib/toast'

export function useLiveUpdates() {
  const { isConnected, lastMessage } = useWebSocket()
  const queryClient = useQueryClient()

  // WebSocket Live Updates
  useEffect(() => {
    if (!lastMessage) return

    const { event, data } = lastMessage

    switch (event) {
      case 'ui_customization_updated':
        handleUICustomizationUpdate(data)
        break

      case 'ui_customization_reset':
        handleUICustomizationReset(data)
        break

      case 'tournament_created':
        handleTournamentCreated(data)
        break

      case 'tournament_score_updated':
        handleTournamentScoreUpdate(data)
        break

      case 'match_score_updated':
        handleMatchScoreUpdate(data)
        break

      case 'player_registered':
        handlePlayerRegistration(data)
        break

      case 'player_unregistered':
        handlePlayerUnregistration(data)
        break

      case 'ranking_updated':
        handleRankingUpdate(data)
        break

      case 'rack_completed':
        handleRackCompleted(data)
        break

      case 'rating_updated':
        handleRatingUpdated(data)
        break

      case 'cache_invalidated':
        handleCacheInvalidation(data)
        break

      default:
        logger.debug('Unknown live update event received', { event, data })
    }
  }, [lastMessage, queryClient])

  // Server-Sent Events for Scraper Updates
  useEffect(() => {
    let eventSource: EventSource | null = null

    try {
      const apiBase = import.meta.env.VITE_API_URL || '/api'
      const streamUrl = typeof window !== 'undefined' && !apiBase.startsWith('http')
        ? `${window.location.origin}${apiBase}/live/updates`
        : `${apiBase}/live/updates`

      eventSource = new EventSource(streamUrl)

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          logger.debug('SSE Scraper event received', { data })

          if (data.type === 'connected') return

          // It's a ScraperEvent
          if (data.status === 'success') {
            toast.success(`Data update completed: ${data.scraper_type}`)

            const topic: string = data.scraper_type || ''

            // Invalidate every query whose first key element either equals `topic`
            // (nested-array convention: ['tournament-history','details', id])
            // or starts with `${topic}-` (legacy hyphenated convention:
            // ['tournament-history-details', id]). One predicate covers both —
            // see TanStack Query "Query Invalidation" docs.
            const invalidateByTopic = (t: string) => {
              if (!t) return
              queryClient.invalidateQueries({
                predicate: (query) => {
                  const k0 = query.queryKey?.[0]
                  return typeof k0 === 'string' && (k0 === t || k0.startsWith(`${t}-`))
                },
              })
            }

            // Map server-side topic -> frontend query key prefixes.
            // Keep the legacy scheduler topics working (rankings_*, fargo, tournament,
            // upcoming) and route new operator-write topics (tournament-history,
            // upcoming-events, calibration, backups, settings, players, scores,
            // uploads) via the same predicate.
            if (topic.startsWith('rankings_') || topic === 'fargo' || topic === 'rankings') {
              invalidateByTopic('rankings')
              queryClient.invalidateQueries({ queryKey: ['leaderboard_rankings'] })
            } else if (topic === 'tournament' || topic === 'upcoming') {
              queryClient.invalidateQueries({ queryKey: ['leaderboard_tournament_history'] })
              queryClient.invalidateQueries({ queryKey: ['leaderboard_tournament_history_by_association'] })
              queryClient.invalidateQueries({ queryKey: ['leaderboard_completed_tournaments'] })
              queryClient.invalidateQueries({ queryKey: ['tournaments'] })
            } else if (topic === 'tournament-history' || topic === 'upcoming-events') {
              invalidateByTopic('tournament-history')
              invalidateByTopic('upcoming-events')
              queryClient.invalidateQueries({ queryKey: ['leaderboard_tournament_history'] })
              queryClient.invalidateQueries({ queryKey: ['leaderboard_tournament_history_by_association'] })
              queryClient.invalidateQueries({ queryKey: ['leaderboard_completed_tournaments'] })
              queryClient.invalidateQueries({ queryKey: ['tournaments'] })
            } else if (topic === 'calibration') {
              invalidateByTopic('calibration')
              invalidateByTopic('rankings')
              invalidateByTopic('self-calibration')
            } else if (topic === 'backups') {
              invalidateByTopic('backups')
            } else if (topic === 'settings') {
              invalidateByTopic('settings')
            } else if (topic === 'players') {
              invalidateByTopic('players')
              invalidateByTopic('player')
              invalidateByTopic('fargo')
            } else if (topic === 'scores') {
              invalidateByTopic('scores')
              invalidateByTopic('tournaments')
              invalidateByTopic('tournament-history')
              queryClient.invalidateQueries({ queryKey: ['leaderboard_rankings'] })
            } else if (topic === 'uploads') {
              invalidateByTopic('uploads')
              invalidateByTopic('media')
              invalidateByTopic('photos')
            } else if (topic === 'leaderboard') {
              queryClient.invalidateQueries({ queryKey: ['leaderboard_rankings'] })
              queryClient.invalidateQueries({ queryKey: ['leaderboard_tournament_history'] })
              queryClient.invalidateQueries({ queryKey: ['leaderboard_tournament_history_by_association'] })
              queryClient.invalidateQueries({ queryKey: ['leaderboard_completed_tournaments'] })
            } else {
              // Unknown topic: be conservative — invalidate by the topic literally
              // (covers any future topic added on the backend before frontend updates)
              // and the broad leaderboard set.
              invalidateByTopic(topic)
              queryClient.invalidateQueries({ queryKey: ['leaderboard_rankings'] })
              queryClient.invalidateQueries({ queryKey: ['leaderboard_tournament_history'] })
              queryClient.invalidateQueries({ queryKey: ['tournaments'] })
              queryClient.invalidateQueries({ queryKey: ['rankings'] })
            }
          }
        } catch (err) {
          logger.error('Error parsing SSE message', err)
        }
      }

      eventSource.onerror = (err) => {
        logger.debug('SSE Scraper stream error/disconnect', err)
      }
    } catch (err) {
      logger.error('Failed to initialize SSE EventSource', err)
    }

    return () => {
      if (eventSource) {
        eventSource.close()
      }
    }
  }, [queryClient])

  const handleUICustomizationUpdate = (data: any) => {
    // UI customizations are handled by the specific component
    // This is just for logging/notification
    logger.debug('UI customization updated live', { data })
  }

  const handleUICustomizationReset = (data: any) => {
    logger.debug('UI customization reset live', { data })
    // Force a page reload for UI customization resets
    window.location.reload()
  }

  const handleTournamentCreated = (data: TournamentUpdateData) => {
    logger.debug('Tournament created via live update', { tournamentId: data.tournament_id, data })

    // Invalidate tournaments list
    queryClient.invalidateQueries({ queryKey: ['tournaments'] })
    queryClient.invalidateQueries({ queryKey: ['leaderboard_in_progress'] })
    queryClient.invalidateQueries({ queryKey: ['leaderboard_completed_tournaments'] })

    // Show notification
    toast.success(`New tournament created: ${data.name || data.tournament_id}`)
  }

  const handleTournamentScoreUpdate = (data: TournamentUpdateData) => {
    logger.debug('Tournament score updated via live update', { data })

    // Invalidate tournament-specific queries
    if (data.tournament_id) {
      queryClient.invalidateQueries({ queryKey: ['tournaments', data.tournament_id] })
      queryClient.invalidateQueries({ queryKey: ['tournament-bracket', data.tournament_id] })
      queryClient.invalidateQueries({ queryKey: ['tournament-matches', data.tournament_id] })
    }
    
    // Invalidate leaderboard since points might have changed
    queryClient.invalidateQueries({ queryKey: ['leaderboard_rankings'] })
    queryClient.invalidateQueries({ queryKey: ['leaderboard_completed_tournaments'] })
    queryClient.invalidateQueries({ queryKey: ['leaderboard_in_progress'] })
  }

  const handleMatchScoreUpdate = (data: MatchScoreUpdateData) => {
    logger.debug('Match score updated via live update', { data })

    // Invalidate tournament and match data
    if (data.tournament_id) {
      queryClient.invalidateQueries({ queryKey: ['tournaments', data.tournament_id] })
      queryClient.invalidateQueries({ queryKey: ['tournament-bracket', data.tournament_id] })
      queryClient.invalidateQueries({ queryKey: ['tournament-matches', data.tournament_id] })
      queryClient.invalidateQueries({ queryKey: ['match', data.match_id] })
    }

    // Match completion might affect leaderboard rankings
    if (data.winner_id) {
      queryClient.invalidateQueries({ queryKey: ['leaderboard_rankings'] })
    }

    // Show notification for score updates
    const winner = data.winner_id
    if (winner) {
      toast.info(`Match completed - ${data.operator_id || 'Player 1'} vs ${data.player2_id || 'Player 2'}`)
    } else {
      toast.info(`Match score updated - ${data.operator_score || 0} : ${data.player2_score || 0}`)
    }
  }

  const handlePlayerRegistration = (data: PlayerRegistrationData) => {
    logger.debug('Player registered via live update', { data })

    // Invalidate tournament player lists
    if (data.tournament_id) {
      queryClient.invalidateQueries({ queryKey: ['tournaments', data.tournament_id, 'players'] })
      queryClient.invalidateQueries({ queryKey: ['tournament-players', data.tournament_id] })
    }

    // Show notification
    toast.success(`${data.player_name} registered for tournament`)
  }

  const handlePlayerUnregistration = (data: PlayerRegistrationData) => {
    logger.debug('Player unregistered via live update', { data })

    // Invalidate tournament player lists
    if (data.tournament_id) {
      queryClient.invalidateQueries({ queryKey: ['tournaments', data.tournament_id, 'players'] })
      queryClient.invalidateQueries({ queryKey: ['tournament-players', data.tournament_id] })
    }

    // Show notification
    toast.info(`${data.player_name} unregistered from tournament`)
  }

  const handleRankingUpdate = (data: any) => {
    logger.debug('Ranking updated via live update', { data })

    // Invalidate ranking queries
    queryClient.invalidateQueries({ queryKey: ['rankings'] })
    queryClient.invalidateQueries({ queryKey: ['rankings', data.ranking_system] })
    queryClient.invalidateQueries({ queryKey: ['player-performance', data.player_name] })
    queryClient.invalidateQueries({ queryKey: ['leaderboard_rankings'] })

    // Show notification
    toast.info(`${data.player_name} ranking updated`)
  }

  const handleRackCompleted = (data: any) => {
    logger.debug('Rack completed via live update', { data })

    if (data.tournament_id) {
      queryClient.invalidateQueries({ queryKey: ['tournament-matches', data.tournament_id] })
      queryClient.invalidateQueries({ queryKey: ['tournament-progress', data.tournament_id] })
      queryClient.invalidateQueries({ queryKey: ['tournament-detail', data.tournament_id] })
      queryClient.invalidateQueries({ queryKey: ['tournaments', data.tournament_id] })
    }
    if (data.match_id) {
      queryClient.invalidateQueries({ queryKey: ['match', data.match_id] })
    }

    const ratingUpdates = data.rating_updates
    if (ratingUpdates && typeof ratingUpdates === 'object' && Object.keys(ratingUpdates).length > 0) {
      queryClient.invalidateQueries({ queryKey: ['rankings'] })
      queryClient.invalidateQueries({ queryKey: ['leaderboard_rankings'] })
      queryClient.invalidateQueries({ queryKey: ['live-ratings'] })
    }
  }

  const handleRatingUpdated = (data: any) => {
    logger.debug('Live est_rating updated via WebSocket', { data })

    queryClient.invalidateQueries({ queryKey: ['rankings'] })
    queryClient.invalidateQueries({ queryKey: ['leaderboard_rankings'] })
    queryClient.invalidateQueries({ queryKey: ['live-ratings'] })
    if (data.player_id) {
      queryClient.invalidateQueries({ queryKey: ['live-ratings', data.player_id] })
      queryClient.invalidateQueries({ queryKey: ['player-performance'] })
    }
  }

  const handleCacheInvalidation = (data: any) => {
    logger.debug('Cache invalidation received', { reason: data.reason, data })

    // Invalidate all cached data to force fresh fetches from API
    queryClient.invalidateQueries()

    // Show user-friendly notification
    const reason = data.reason || 'data update'
    const message = `Data updated (${reason}) - refreshing...`
    toast.info(message, {
      duration: 3000,
      description: 'Your rankings data has been refreshed'
    })
  }

  return {
    isConnected,
    lastUpdate: lastMessage
  }
}