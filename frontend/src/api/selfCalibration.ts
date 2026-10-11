/**
 * API client for the self-calibration admin endpoints.
 *
 * Both POSTs are fire-and-forget (the backend spawns a daemon thread, returns
 * immediately, and writes progress into `logs/calibration_cycle.log` /
 * `logs/apply_recommendations_<rating>.log`). Callers should pair the POST with
 * a live-log stream via `streamLog(...)` from `@/api/liveLogStream`.
 *
 * Both endpoints require admin auth, so we use the shared axios `apiClient`
 * (which carries the bearer token + `X-API-Key`). The previous inline
 * `fetch('/api/self-calibration/...')` call sites in SettingsAdmin.tsx had
 * **no** auth headers and would now return 401 against the hardened backend.
 */

import { apiClient } from './client'
import type { LiveLogStarted } from './liveLogStream'

export type CalibrationRatingType = 'fargo' | 'alfa' | 'est'

export const selfCalibrationApi = {
  /** Trigger a full self-calibration cycle for all rating systems (admin only). */
  runCalibrationCycle: async (): Promise<LiveLogStarted> => {
    const response = await apiClient.post('/self-calibration/run-calibration-cycle')
    return response.data as LiveLogStarted
  },

  /** Apply AI-generated calibration recommendations for one rating type (admin only). */
  applyRecommendations: async (
    ratingType: CalibrationRatingType,
  ): Promise<LiveLogStarted> => {
    const response = await apiClient.post(
      `/self-calibration/apply-recommendations/${ratingType}`,
    )
    return response.data as LiveLogStarted
  },

  /** Phase 4: snapshot EST vs published Fargo into accuracy tables. */
  compareEstFargo: async (): Promise<{
    success: boolean
    recorded?: number
    mae?: number | null
    rmse?: number | null
    candidates?: number
  }> => {
    const response = await apiClient.post('/rating-accuracy/compare-est-fargo')
    return response.data
  },
}
