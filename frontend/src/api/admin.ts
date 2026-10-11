import { apiClient, API_BASE_URL } from './client'
import type { LiveLogStarted } from './liveLogStream'

export interface RebuildWebsiteResponse {
  status: string
  message: string
  configured: boolean
  /** Command run by the rebuild button (e.g. "bash scripts/full_deploy.sh") */
  command?: string | null
}

export interface DefaultAppearance {
  default_avatar_url: string
  default_background_url: string
}

export interface SecurityMetricsResponse {
  failed_attempts_24h: number
  successful_attempts_24h: number
  unique_ips_24h: number
  locked_accounts_count: number
}

/**
 * Headers for fetch() — mirror apiClient (localStorage + legacy keys).
 * Prefer `explicitToken` (e.g. AuthContext user.token); storage can be missing/out of sync and caused 401 on the log stream.
 */
function getAuthHeaders(explicitToken?: string | null): Record<string, string> {
  const headers: Record<string, string> = {}
  const apiKey =
    typeof import.meta.env.VITE_API_KEY === 'string' && import.meta.env.VITE_API_KEY
      ? import.meta.env.VITE_API_KEY
      : ''
  if (apiKey) {
    headers['X-API-Key'] = apiKey
  }
  let token = (explicitToken && explicitToken.trim()) || null
  if (!token) token = localStorage.getItem('access_token')
  if (!token) token = localStorage.getItem('auth_token')
  if (!token) {
    try {
      const authData = localStorage.getItem('rankings_bot_auth')
      if (authData) {
        const parsed = JSON.parse(authData) as { token?: string; access_token?: string }
        token = parsed?.token ?? parsed?.access_token ?? null
      }
    } catch {
      /* ignore */
    }
  }
  if (!token) {
    token = sessionStorage.getItem('access_token') || sessionStorage.getItem('auth_token')
  }
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

/**
 * Stream rebuild-website log (live output). Call after POST rebuild-website.
 * Invokes onChunk with each decoded text chunk; resolves when stream ends or errors.
 */
export async function streamRebuildWebsiteLog(
  onChunk: (text: string) => void,
  signal?: AbortSignal,
  /** Prefer AuthContext `user.token` so fetch matches the session axios uses. */
  authToken?: string | null
): Promise<void> {
  const url = `${API_BASE_URL}/admin/rebuild-website/log`
  const res = await fetch(url, { headers: getAuthHeaders(authToken), signal })
  if (!res.ok) throw new Error(res.statusText || 'Failed to stream log')
  const reader = res.body?.getReader()
  if (!reader) throw new Error('No response body')
  const dec = new TextDecoder()
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      if (value) onChunk(dec.decode(value, { stream: true }))
    }
    const tail = dec.decode()
    if (tail) onChunk(tail)
  } finally {
    reader.releaseLock()
  }
}

export const adminApi = {
  /** Check if rebuild-website is configured on the server. */
  getRebuildStatus: () =>
    apiClient.get<RebuildWebsiteResponse>('/admin/rebuild-website/status'),

  /** Trigger rebuild and restart (build frontend, restart API/containers). */
  rebuildWebsite: () =>
    apiClient.post<RebuildWebsiteResponse>('/admin/rebuild-website', {}, { timeout: 15000 }),

  /** Check if full deploy is configured on the server. */
  getRebuildAllStatus: () =>
    apiClient.get<RebuildWebsiteResponse>('/admin/rebuild-all-images/status'),

  /** Full deploy: rebuild all Docker images and restart containers (admin/super_admin). */
  rebuildAllImages: () =>
    apiClient.post<RebuildWebsiteResponse>('/admin/rebuild-all-images', {}, { timeout: 60000 }),

  /** Admin: get default avatar/background for users without custom. */
  getDefaultAppearance: () =>
    apiClient.get<DefaultAppearance>('/admin/appearance/default').then((r) => r.data),

  /** Admin: set default avatar/background. */
  updateDefaultAppearance: (body: Partial<DefaultAppearance>) =>
    apiClient.patch<DefaultAppearance>('/admin/appearance/default', body).then((r) => r.data),

  /** Admin: last N lines of probilliards.log (for debugging after Update website). */
  getLogsTail: (lines = 200) =>
    apiClient.get<{ lines: string[]; message?: string }>('/admin/logs/tail', { params: { lines } }).then((r) => r.data),

  /** Admin: AI Coach tier config (Freebie, Rookie, etc.). Super admin can edit. */
  getTierConfig: () =>
    apiClient.get<{ tiers: Record<string, { name?: string; monthly_limit?: number | null; lifetime_limit?: number | null; max_video_duration?: number; price_monthly?: number; features?: string[] }> }>('/admin/tier-config').then((r) => r.data),

  /** Super Admin: save tier config (prices, limits, features). */
  putTierConfig: (tiers: Record<string, { name?: string; monthly_limit?: number | null; lifetime_limit?: number | null; max_video_duration?: number; price_monthly?: number; features?: string[] }>) =>
    apiClient.put<{ tiers: Record<string, unknown> }>('/admin/tier-config', { tiers }).then((r) => r.data),

  /** Admin: role capability matrix. Super admin can edit. */
  getRoleCapabilities: () =>
    apiClient.get<{ capabilities: Array<{ id: string; label: string; roles: [boolean, boolean, boolean, boolean] }> }>('/admin/role-capabilities').then((r) => r.data),

  /** Super Admin: save role capabilities. */
  putRoleCapabilities: (capabilities: Array<{ id: string; label: string; roles: [boolean, boolean, boolean, boolean] }>) =>
    apiClient.put<{ capabilities: Array<{ id: string; label: string; roles: boolean[] }> }>('/admin/role-capabilities', { capabilities }).then((r) => r.data),

  /** Admin: get list of player names with unresolved conflicts (for Player link filter). */
  getConflictingPlayerNames: () =>
    apiClient.get<{ conflictingNames: string[] }>('/admin/conflicting-player-names').then((r) => r.data),

  /** Super Admin: get data quality issues (conflicting player data, missing fields). */
  getDataQualityIssues: () =>
    apiClient.get<DataQualityIssuesResponse>('/admin/data-quality-issues').then((r) => r.data),

  /** Super Admin: mark a conflict as resolved. */
  resolveDataQualityConflict: (conflictId: number, resolutionNotes: string) =>
    apiClient.post<{ status: string; message: string }>(`/admin/data-quality-issues/${conflictId}/resolve`, { resolution_notes: resolutionNotes }).then((r) => r.data),

  /** Super Admin: fix missing Fargo ratings by running Tier 1 + Tier 2 matching. */
  fixMissingFargoData: () =>
    apiClient.post<{ status: string; message: string; playersProcessed: number; tier1Matches: number; tier2Matches: number; totalMatched: number }>('/admin/data-quality/fix-missing-fargo').then((r) => r.data),

  /** Admin: aggregated login security metrics (24h), from audit log. */
  getSecurityMetrics: () =>
    apiClient.get<SecurityMetricsResponse>('/admin/security-metrics').then((r) => r.data),

  /**
   * Admin: trigger a database backup. Fire-and-forget (the API spawns
   * `scripts/backup_postgres.sh` in a background thread and writes its combined
   * stdout/stderr into `logs/system_backup.log`); watch progress by streaming
   * `/backups/create/log` via `streamLog(...)` from `@/api/liveLogStream`.
   *
   * NOTE: The endpoint lives at `/api/backups/create` (not the legacy
   * `/api/admin/system/backup`, which never existed on the backend).
   */
  createSystemBackup: () =>
    apiClient.post<LiveLogStarted>('/backups/create').then((r) => r.data),
}

export interface DataQualityConflict {
  id: number
  playerName: string
  conflictType: 'COUNTRY' | 'LICENSE' | 'FARGO' | 'FARGO_MISMATCH'
  system1: string
  value1: string
  system2: string
  value2: string
  detectedAt: string
  notes?: string
}

export interface PlayerMissingData {
  playerName: string
  systems: Record<string, string[]> // ranking_system -> array of missing fields
}

export interface DataQualityStats {
  totalConflicts: number
  totalPlayersWithMissingData: number
  countryConflicts: number
  licenseConflicts: number
  fargoConflicts: number
}

export interface DataQualityIssuesResponse {
  conflicts: DataQualityConflict[]
  missingData: PlayerMissingData[]
  stats: DataQualityStats
}
