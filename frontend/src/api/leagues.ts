/**
 * API Client for League Management
 */

import { apiClient } from './client'

export interface League {
  league_id: string
  name: string
  org_code?: string | null
  season_start?: string | null
  season_end?: string | null
}

export interface LeagueTeam {
  id: number
  team_name: string
  captain_player_id?: string | null
}

const BASE = '/leagues'

export const leaguesApi = {
  list: async (): Promise<League[]> => {
    const { data } = await apiClient.get<League[]>(BASE)
    return data
  },

  create: async (payload: { name: string; org_code?: string; season_start?: string; season_end?: string }) => {
    const { data } = await apiClient.post<{ league_id: string; message: string }>(BASE, payload)
    return data
  },

  listTeams: async (leagueId: string): Promise<LeagueTeam[]> => {
    const { data } = await apiClient.get<LeagueTeam[]>(`${BASE}/${leagueId}/teams`)
    return data
  },

  createTeam: async (
    leagueId: string,
    payload: { team_name: string; captain_player_id?: string }
  ) => {
    const { data } = await apiClient.post<{ message: string }>(`${BASE}/${leagueId}/teams`, payload)
    return data
  },
}
