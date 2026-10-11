/**
 * Director API: table clock settings (shot clock, game clock, match clock, table time alert).
 */

import apiClient from './client'

export interface DirectorClockSettings {
  shot_clock_enabled: boolean
  shot_clock_seconds: number
  game_clock_minutes: number
  match_clock_minutes: number
  table_time_alert_minutes: number
}

export const directorApi = {
  getClockSettings: () =>
    apiClient.get<DirectorClockSettings>('/director/clock-settings').then((r) => r.data),

  updateClockSettings: (body: Partial<DirectorClockSettings>) =>
    apiClient.patch<DirectorClockSettings>('/director/clock-settings', body).then((r) => r.data),
}
