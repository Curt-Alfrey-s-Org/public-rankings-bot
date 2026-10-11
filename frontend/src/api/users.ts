/**
 * User profile API (current user) and admin user management (list/create).
 */

import { apiClient } from './client'

const BASE = '/users'

export interface UserProfile {
  id: number
  username: string
  email: string
  role: string
  email_verified: boolean
  created_at: string
  last_login: string | null
  country: string | null
  state: string | null
  home_pool_room: string | null
}

export interface ProfileUpdate {
  country?: string
  state?: string
  home_pool_room?: string
}

/** Admin/super_admin: list all users */
export interface UserListItem {
  id: number
  username: string
  email: string
  role: string
  email_verified: boolean
  created_at: string
  last_login: string | null
}

export interface CreateUserBody {
  username: string
  email: string
  password: string
  role: string
  tier?: string  // AI Coach tier: FREEBIE, ROOKIE, etc. No default; super admin must choose.
  /** Ranking association tags (e.g. WPA_Women, WPBA_Women). Required when role is director. */
  associations?: string[]
}

export interface PlayerLink {
  user_id: number
  username: string
  player_name: string
  player_id?: string | null
  license_number?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface PlayerLinkUpsertBody {
  username: string
  player_name: string
  player_id?: string | null
  license_number?: string | null
}

export const usersApi = {
  /** Authenticated: associations for tournament wizard (director tags or full list for admin). */
  getMyAssociations: async (): Promise<{ associations: string[] }> => {
    const { data } = await apiClient.get<{ associations: string[] }>(`${BASE}/profile/me/associations`)
    return data
  },
  getProfile: async (): Promise<UserProfile> => {
    const { data } = await apiClient.get<UserProfile>(`${BASE}/profile/me`)
    return data
  },
  updateProfile: async (body: ProfileUpdate): Promise<UserProfile> => {
    const { data } = await apiClient.patch<UserProfile>(`${BASE}/profile/me`, body)
    return data
  },
  /** Admin/super_admin: list users */
  listUsers: () =>
    apiClient.get<{ users: UserListItem[] }>(BASE).then((r) => r.data),
  /** Admin/super_admin: create user */
  createUser: (body: CreateUserBody) =>
    apiClient.post<UserListItem>(BASE, body).then((r) => r.data),
  /** Admin/super_admin: update user role; super_admin can also change username */
  updateUser: (username: string, body: { role: string; username?: string; associations?: string[] }) =>
    apiClient.put<{ message: string }>(`${BASE}/${encodeURIComponent(username)}`, body).then((r) => r.data),
  /** Admin/super_admin: list user_associations for Data input scoping */
  getUserAssociations: (username: string) =>
    apiClient
      .get<{ associations: string[] }>(`${BASE}/${encodeURIComponent(username)}/associations`)
      .then((r) => r.data),
  /** Admin/super_admin: set another user's password (user must change on next login) */
  setUserPassword: (username: string, newPassword: string) =>
    apiClient.post<{ message: string }>(`${BASE}/${encodeURIComponent(username)}/set-password`, { new_password: newPassword }).then((r) => r.data),
  /** Admin/super_admin: reset user's password to default temp password (user must change on next login) */
  resetUserPassword: (username: string) =>
    apiClient.post<{ message: string; temporary_password: string }>(`${BASE}/${encodeURIComponent(username)}/reset-password`).then((r) => r.data),
  /** Admin/super_admin: delete user */
  deleteUser: (username: string) =>
    apiClient.delete<{ message: string }>(`${BASE}/${encodeURIComponent(username)}`).then((r) => r.data),
  /** Admin/super_admin: list user-to-player links */
  listPlayerLinks: () =>
    apiClient.get<{ links: PlayerLink[] }>(`${BASE}/player-links`).then((r) => r.data),
  /** Admin/super_admin: upsert user-to-player link */
  upsertPlayerLink: (body: PlayerLinkUpsertBody) =>
    apiClient.post<PlayerLink>(`${BASE}/player-links`, body).then((r) => r.data),
  /** Admin/super_admin: delete user-to-player link */
  deletePlayerLink: (username: string) =>
    apiClient.delete<{ message: string }>(`${BASE}/player-links/${encodeURIComponent(username)}`).then((r) => r.data),
  /** Admin/super_admin: download Fargo accounts CSV */
  downloadFargoAccountsCSV: async (): Promise<Blob> => {
    const response = await apiClient.get(`${BASE}/fargo-accounts-csv`, {
      responseType: 'blob',
    } as any)
    return response.data as Blob
  },
}
