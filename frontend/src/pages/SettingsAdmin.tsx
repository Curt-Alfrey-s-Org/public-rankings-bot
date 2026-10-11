/**
 * Settings > Admin: grouped sections (data, billing, deploy, users, Fargo, diagnostics).
 * Admin-only; linked from Settings layout.
 */

import { useState, useEffect, useCallback, useMemo, useRef, type ReactNode } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { rankingsApi, streamScraperLog, type ScraperName } from '@/api/rankings'
import { tournamentHistoryApi } from '@/api/tournamentHistory'
import { adminApi, streamRebuildWebsiteLog } from '@/api/admin'
import { selfCalibrationApi, type CalibrationRatingType } from '@/api/selfCalibration'
import { apiClient } from '@/api/client'
import { usersApi, type CreateUserBody } from '@/api/users'
import { toast } from '@/lib/toast'
import { useAuth } from '@/contexts/AuthContext'
import { alfaDashboardApi } from '@/api/alfaDashboard'
import { PaymentMethod } from '@/features/admin/components/PaymentMethod'
import { ChangePasswordSettings } from '@/features/admin/components/ChangePasswordSettings'
import { LoginAttemptsMonitor } from '@/features/admin/components/LoginAttemptsMonitor'
import StatsSummary from '@/components/StatsSummary'
import MetricsDetailModal from '@/features/metrics/MetricsDetailModal'
import { LiveLogModal } from '@/components/LiveLogModal'
import { useLiveLogStream, type LiveLogStatus } from '@/hooks/useLiveLogStream'
import { jobOutcomeToStreamStatus, liveLogStatusClass, liveLogStatusLabel, parseLiveLogJobOutcome } from '@/utils/liveLogOutcome'
import { BarChart3, TrendingUp, Target, Brain, Zap } from 'lucide-react'
/** Fargo sync is rate-limited; can take 1–2 min (missing only) or 5–10 min (full refresh). */
const FARGO_SYNC_TIMEOUT_MS = 120_000
const FARGO_FULL_REFRESH_TIMEOUT_MS = 600_000

const ROLE_LABELS = ['Player', 'Director', 'Admin', 'Super admin'] as const

type CrosswalkReviewRow = {
  id: number
  tournament_id: string
  source: string
  source_event_id: string
  source_url: string | null
  match_method: string
  match_score: number | null
  tournament_name: string | null
  tournament_date: string | null
}

type FargoSyncResponse = {
  updated: number
  org_code: string
  players_processed: number
  error?: string | null
  started?: boolean
  message?: string
  failed_players?: string[]
  failed_count?: number
}

async function triggerFargoSync(
  orgCode: string = 'WPBA',
  wait: boolean = true,
  fullRefresh: boolean = false
): Promise<FargoSyncResponse> {
  const timeout = fullRefresh ? FARGO_FULL_REFRESH_TIMEOUT_MS : FARGO_SYNC_TIMEOUT_MS
  const { data } = await apiClient.post<FargoSyncResponse>(
    '/fargo/sync',
    null,
    {
      params: {
        org_code: orgCode,
        wait: wait ? 'true' : 'false',
        full_refresh: fullRefresh ? 'true' : 'false',
      },
      timeout,
    }
  )
  return data
}

function AdminPageSection({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children: ReactNode
}) {
  return (
    <section className="bg-card border border-border rounded-lg p-6 space-y-4">
      <div className="border-b border-border pb-3">
        <h2 className="text-lg font-semibold tracking-tight text-foreground">{title}</h2>
        {description ? <p className="text-sm text-muted-foreground mt-1.5">{description}</p> : null}
      </div>
      <div className="space-y-4">{children}</div>
    </section>
  )
}

export default function SettingsAdminPage() {
  const queryClient = useQueryClient()
  const [exportSystem, setExportSystem] = useState<'WPBA_Women' | 'WPA_Women' | 'WPA_Men'>('WPBA_Women')
  const [exporting, setExporting] = useState(false)
  const [fargoMessage, setFargoMessage] = useState<string | null>(null)
  const [rebuildMessage, setRebuildMessage] = useState<string | null>(null)
  const [rebuildDone, setRebuildDone] = useState(false)
  const [fargoDone, setFargoDone] = useState(false)
  const [fargoImportText, setFargoImportText] = useState('')
  const [fargoImportSystem, setFargoImportSystem] = useState<'WPBA' | 'WPA'>('WPBA')
  const [fargoModalOpen, setFargoModalOpen] = useState(false)
  const [fargoResult, setFargoResult] = useState<FargoSyncResponse | null>(null)
  const [fargoFullRefresh, setFargoFullRefresh] = useState(true)
  const [exportDone, setExportDone] = useState(false)
  const [createUserOpen, setCreateUserOpen] = useState(false)
  const [createUserForm, setCreateUserForm] = useState<CreateUserBody>({ username: '', email: '', password: '', role: 'user', tier: '' })
  const [createUserAssociations, setCreateUserAssociations] = useState('')
  const [editUserOpen, setEditUserOpen] = useState(false)
  const [editUserUsername, setEditUserUsername] = useState<string | null>(null)
  const [editUserNewUsername, setEditUserNewUsername] = useState<string>('')
  const [editUserRole, setEditUserRole] = useState<string>('user')
  const [editUserAssociationsText, setEditUserAssociationsText] = useState('')
  const [editUserNewPassword, setEditUserNewPassword] = useState('')
  const [editUserPasswordError, setEditUserPasswordError] = useState<string | null>(null)
  const [tournamentScrapeMessage, setTournamentScrapeMessage] = useState<string | null>(null)
  const [scraperRunMessage, setScraperRunMessage] = useState<string | null>(null)
  const [dataQualityLoading, setDataQualityLoading] = useState(false)
  const [dataQualitySummary, setDataQualitySummary] = useState<string | null>(null)
  const [crosswalkReviewLoading, setCrosswalkReviewLoading] = useState(false)
  const [crosswalkReviewRows, setCrosswalkReviewRows] = useState<CrosswalkReviewRow[] | null>(null)
  const [crosswalkReviewMessage, setCrosswalkReviewMessage] = useState<string | null>(null)
  const [crosswalkRowPending, setCrosswalkRowPending] = useState<number | null>(null)

  const loadCrosswalkReview = async () => {
    setCrosswalkReviewLoading(true)
    setCrosswalkReviewMessage(null)
    try {
      const res = await apiClient.get('/admin/data-quality/crosswalk/review')
      setCrosswalkReviewRows(res.data?.rows ?? [])
    } catch (e: unknown) {
      setCrosswalkReviewMessage(e instanceof Error ? e.message : 'Failed to load crosswalk review')
    } finally {
      setCrosswalkReviewLoading(false)
    }
  }

  const actOnCrosswalkRow = async (rowId: number, action: 'confirm' | 'reject') => {
    if (crosswalkRowPending !== null) return
    setCrosswalkRowPending(rowId)
    setCrosswalkReviewMessage(null)
    try {
      if (action === 'confirm') {
        await apiClient.post(`/admin/data-quality/crosswalk/${rowId}/confirm`)
      } else {
        const res = await apiClient.delete(`/admin/data-quality/crosswalk/${rowId}`)
        const n = res.data?.local_results_count
        if (typeof n === 'number' && n > 0) {
          setCrosswalkReviewMessage(
            `Rejected. The linked tournament still holds ${n} result rows — verify they belong to it before re-ingesting.`
          )
        }
      }
      setCrosswalkReviewRows((rows) => (rows ?? []).filter((r) => r.id !== rowId))
    } catch (e: unknown) {
      setCrosswalkReviewMessage(e instanceof Error ? e.message : `Failed to ${action} row ${rowId}`)
    } finally {
      setCrosswalkRowPending(null)
    }
  }

  const isHttpUrl = (url: string | null): url is string => {
    if (!url) return false
    try {
      const u = new URL(url, window.location.origin)
      return u.protocol === 'http:' || u.protocol === 'https:'
    } catch {
      return false
    }
  }
  const [scraperRunLoading, setScraperRunLoading] = useState<string | null>(null)
  const [wpbaPdfMessage, setWpbaPdfMessage] = useState<string | null>(null)
  const [wpbaPdfError, setWpbaPdfError] = useState<string | null>(null)
  const [fullDeployMessage, setFullDeployMessage] = useState<string | null>(null)
  const [backupMessage, setBackupMessage] = useState<string | null>(null)
  const [backupDone, setBackupDone] = useState(false)
  const [rebuildModalOpen, setRebuildModalOpen] = useState(false)
  /** Live rebuild log stream status (Update website / View rebuild log). */
  const [rebuildStreamStatus, setRebuildStreamStatus] = useState<LiveLogStatus>('idle')
  const [rebuildLogContent, setRebuildLogContent] = useState('')
  const [rebuildLogLoading, setRebuildLogLoading] = useState(false)
  const rebuildLogEndRef = useRef<HTMLDivElement>(null)
  const rebuildCompleteToastSentRef = useRef(false)
  const rebuildStreamAbortRef = useRef<AbortController | null>(null)

  // Scraper live log modal — same UX as Update website (POST kicks off background
  // run, GET streams logs/scraper_<name>.log via fetch). Reused for WPBA, WPA, CP.
  const [scraperLogModalOpen, setScraperLogModalOpen] = useState(false)
  const [scraperLogScraper, setScraperLogScraper] = useState<ScraperName | null>(null)
  const [scraperLogStatus, setScraperLogStatus] = useState<LiveLogStatus>('idle')
  const [scraperLogContent, setScraperLogContent] = useState('')
  const [scraperLogLoading, setScraperLogLoading] = useState(false)
  const scraperLogEndRef = useRef<HTMLDivElement>(null)
  const scraperLogStreamAbortRef = useRef<AbortController | null>(null)
  const scraperCompleteToastSentRef = useRef(false)
  
  // Data quality state
  const [dataQualityTab, setDataQualityTab] = useState<'conflicts' | 'missing'>('conflicts')
  const [resolvingConflictId, setResolvingConflictId] = useState<number | null>(null)
  const [editableCapabilities, setEditableCapabilities] = useState<Array<{ id: string; label: string; roles: [boolean, boolean, boolean, boolean] }>>([])
  const [editableTierConfig, setEditableTierConfig] = useState<Record<string, { name?: string; monthly_limit?: number | null; lifetime_limit?: number | null; max_video_duration?: number; price_monthly?: number; features?: string[] }>>({})
  const [resolutionNote, setResolutionNote] = useState('')

  // Metrics detail modal state
  const [metricsModalOpen, setMetricsModalOpen] = useState(false)
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null)
  const [metricsModalDetails, setMetricsModalDetails] = useState<Array<{ label: string; value: string | number; secondary?: string }>>([])


  useEffect(() => {
    if (!rebuildDone) return
    const t = setTimeout(() => setRebuildDone(false), 1000)
    return () => clearTimeout(t)
  }, [rebuildDone])
  useEffect(() => {
    if (!fargoDone) return
    const t = setTimeout(() => setFargoDone(false), 1000)
    return () => clearTimeout(t)
  }, [fargoDone])
  useEffect(() => {
    if (!exportDone) return
    const t = setTimeout(() => setExportDone(false), 1000)
    return () => clearTimeout(t)
  }, [exportDone])

  const { isAdmin, isSuperAdmin, user: authUser } = useAuth()
  const canAdmin = isAdmin || isSuperAdmin
  
  // Metrics queries (moved from Dashboard)
  const { data: alfaStats } = useQuery({
    queryKey: ['dashboard-alfa-stats'],
    queryFn: async () => {
      try {
        return await alfaDashboardApi.getDashboardStats()
      } catch (error) {
        console.error('Failed to fetch Alfa dashboard stats:', error)
        return null
      }
    },
    retry: 1,
    staleTime: 180_000,
  })

  const { data: tournamentStats } = useQuery({
    queryKey: ['dashboard-tournament-stats'],
    queryFn: async () => {
      try {
        const res = await tournamentHistoryApi.getTournamentStatistics()
        return res?.statistics ?? null
      } catch (error) {
        console.error('Failed to fetch tournament stats:', error)
        return null
      }
    },
    retry: 1,
    staleTime: 300_000,
  })

  // Rating accuracy dashboard
  const { data: accuracyStats, refetch: refetchAccuracy } = useQuery({
    queryKey: ['rating-accuracy-dashboard'],
    queryFn: async () => {
      try {
        const response = await fetch('/api/rating-accuracy/dashboard')
        if (!response.ok) throw new Error('Failed to fetch accuracy data')
        const result = await response.json()
        return result.success ? result.data : null
      } catch (error) {
        console.error('Failed to fetch rating accuracy stats:', error)
        return null
      }
    },
    retry: 1,
    staleTime: 300_000,
  })

  // Self-calibration independence progress
  const { data: independenceStats, refetch: refetchIndependence } = useQuery({
    queryKey: ['self-calibration-independence'],
    queryFn: async () => {
      try {
        const response = await fetch('/api/self-calibration/independence-progress')
        if (!response.ok) throw new Error('Failed to fetch independence data')
        const result = await response.json()
        return result.success ? result.data : null
      } catch (error) {
        console.error('Failed to fetch independence stats:', error)
        return null
      }
    },
    retry: 1,
    staleTime: 300_000,
  })

  const { data: securityMetrics } = useQuery({
    queryKey: ['admin', 'security-metrics'],
    queryFn: () => adminApi.getSecurityMetrics(),
    enabled: canAdmin,
    retry: 1,
    staleTime: 60_000,
    refetchInterval: canAdmin ? 60_000 : false,
    refetchOnWindowFocus: true,
  })
  
  const { data: usersList } = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => usersApi.listUsers(),
    enabled: canAdmin,
  })
  const { data: rebuildStatus } = useQuery({
    queryKey: ['admin', 'rebuild-status'],
    queryFn: () => adminApi.getRebuildStatus().then((r) => r.data),
    enabled: canAdmin,
  })
  const { data: rebuildAllStatus } = useQuery({
    queryKey: ['admin', 'rebuild-all-status'],
    queryFn: () => adminApi.getRebuildAllStatus().then((r) => r.data),
    enabled: isSuperAdmin,
  })
  const { data: tierConfigData } = useQuery({
    queryKey: ['admin', 'tier-config'],
    queryFn: () => adminApi.getTierConfig(),
    enabled: canAdmin,
  })
  const tierConfig = tierConfigData?.tiers ?? {}

  const { data: roleCapabilitiesData } = useQuery({
    queryKey: ['admin', 'role-capabilities'],
    queryFn: () => adminApi.getRoleCapabilities(),
    enabled: canAdmin,
  })
  const roleCapabilities = roleCapabilitiesData?.capabilities ?? []
  
  // Data quality issues query (super admin only)
  const { data: dataQualityData } = useQuery({
    queryKey: ['admin', 'data-quality-issues'],
    queryFn: () => adminApi.getDataQualityIssues(),
    enabled: isSuperAdmin,
    refetchOnWindowFocus: true,
  })

  // Sync editable capabilities when fetched
  useEffect(() => {
    if (roleCapabilities.length > 0) {
      setEditableCapabilities(roleCapabilities.map((c) => ({ ...c, roles: [...c.roles] })))
    }
  }, [roleCapabilities])

  // Sync editable tier config when fetched
  useEffect(() => {
    if (Object.keys(tierConfig).length > 0) {
      setEditableTierConfig(
        Object.fromEntries(
          Object.entries(tierConfig).map(([k, v]) => [
            k,
            {
              name: (v as { name?: string }).name ?? k,
              monthly_limit: (v as { monthly_limit?: number | null }).monthly_limit ?? null,
              lifetime_limit: (v as { lifetime_limit?: number | null }).lifetime_limit ?? null,
              max_video_duration: (v as { max_video_duration?: number }).max_video_duration ?? 30,
              price_monthly: (v as { price_monthly?: number }).price_monthly ?? 0,
              features: [...((v as { features?: string[] }).features ?? [])],
            },
          ])
        )
      )
    }
  }, [tierConfig])

  const saveRoleCapabilitiesMutation = useMutation({
    mutationFn: (caps: Array<{ id: string; label: string; roles: [boolean, boolean, boolean, boolean] }>) =>
      adminApi.putRoleCapabilities(caps),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'role-capabilities'] })
      toast.success('Role capabilities saved')
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed to save'),
  })

  const saveTierConfigMutation = useMutation({
    mutationFn: (tiers: Record<string, { name?: string; monthly_limit?: number | null; lifetime_limit?: number | null; max_video_duration?: number; price_monthly?: number; features?: string[] }>) =>
      adminApi.putTierConfig(tiers),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'tier-config'] })
      toast.success('Tier config saved')
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed to save'),
  })
  
  const parseAssociationsInput = (raw: string): string[] =>
    raw
      .split(/[,\n]/)
      .map((s) => s.trim())
      .filter(Boolean)

  const createUserMutation = useMutation({
    mutationFn: (body: CreateUserBody) => usersApi.createUser(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      setCreateUserOpen(false)
      setCreateUserForm({ username: '', email: '', password: '', role: 'user', tier: '' })
      setCreateUserAssociations('')
      toast.success('User created')
    },
    onError: (err: Error) => toast.error(err?.message ?? 'Create user failed'),
  })
  const updateUserMutation = useMutation({
    mutationFn: ({
      username,
      newUsername,
      role,
      associations,
    }: {
      username: string
      newUsername?: string
      role: string
      associations: string[]
    }) =>
      usersApi.updateUser(username, {
        role,
        associations,
        ...(newUsername && newUsername.trim() !== username ? { username: newUsername.trim() } : {}),
      }),
    onSuccess: (_, { username, newUsername }) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      setEditUserOpen(false)
      setEditUserUsername(null)
      setEditUserNewUsername('')
      const display = newUsername?.trim() || username
      toast.success(newUsername?.trim() ? `User updated: ${username} → ${display}` : `Role updated for ${display}`)
    },
    onError: (err: Error) => toast.error(err?.message ?? 'Update role failed'),
  })
  const setUserPasswordMutation = useMutation({
    mutationFn: ({ username, newPassword }: { username: string; newPassword: string }) => usersApi.setUserPassword(username, newPassword),
    onSuccess: (_, { username }) => {
      setEditUserNewPassword('')
      setEditUserPasswordError(null)
      toast.success(`Password updated for ${username}. They must change it on next login.`)
    },
    onError: (err: Error) => {
      setEditUserPasswordError(err?.message ?? 'Set password failed')
      toast.error(err?.message ?? 'Set password failed')
    },
  })
  const resetUserPasswordMutation = useMutation({
    mutationFn: (username: string) => usersApi.resetUserPassword(username),
    onSuccess: (data, username) => {
      setEditUserPasswordError(null)
      const temp = data?.temporary_password
      toast.success(
        temp
          ? `Password reset for ${username}. Temporary password: ${temp}. User must change on next login.`
          : `Password reset for ${username}. User must change on next login.`
      )
    },
    onError: (err: Error) => {
      setEditUserPasswordError(err?.message ?? 'Reset password failed')
      toast.error(err?.message ?? 'Reset password failed')
    },
  })
  const deleteUserMutation = useMutation({
    mutationFn: (username: string) => usersApi.deleteUser(username),
    onSuccess: (_, username) => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
      setEditUserOpen(false)
      setEditUserUsername(null)
      toast.success(`User ${username} deleted`)
    },
    onError: (err: Error) => toast.error(err?.message ?? 'Delete user failed'),
  })
  const validateEditUserPassword = (pw: string): string | null => {
    if (pw.length < 8) return 'At least 8 characters'
    if (!/[A-Z]/.test(pw) || !/[a-z]/.test(pw) || !/[0-9]/.test(pw) || !/[!@#$%^&*()\-_=+[\]{};':"|,.<>?]/.test(pw)) return 'Need uppercase, lowercase, number, and special character'
    return null
  }

  const startRebuildLogStream = useCallback(() => {
    rebuildStreamAbortRef.current?.abort()
    const ac = new AbortController()
    rebuildStreamAbortRef.current = ac
    setRebuildLogContent('')
    setRebuildStreamStatus('running')
    setRebuildLogLoading(true)
    streamRebuildWebsiteLog(
      (chunk) => {
        setRebuildLogContent((prev) => {
          const next = prev + chunk
          if (next.includes('Done in')) {
            setRebuildStreamStatus(jobOutcomeToStreamStatus(parseLiveLogJobOutcome(next)))
          }
          return next
        })
      },
      ac.signal,
      authUser?.token
    )
      .then(() => {
        setRebuildLogLoading(false)
        setRebuildStreamStatus((p) =>
          p === 'complete' || p === 'complete_warning' || p === 'complete_failed' || p === 'error'
            ? p
            : 'stream_ended',
        )
      })
      .catch((e: unknown) => {
        setRebuildLogLoading(false)
        const err = e as { name?: string; message?: string }
        if (err?.name === 'AbortError') {
          setRebuildStreamStatus((p) => (p === 'running' ? 'stream_ended' : p))
          return
        }
        setRebuildStreamStatus('error')
        setRebuildLogContent((prev) => prev + `\n[Error streaming log: ${err?.message ?? 'unknown'}]`)
      })
  }, [authUser?.token])

  const closeRebuildModal = useCallback(() => {
    rebuildStreamAbortRef.current?.abort()
    rebuildStreamAbortRef.current = null
    setRebuildModalOpen(false)
    setRebuildStreamStatus('idle')
    setRebuildLogLoading(false)
    rebuildCompleteToastSentRef.current = false
  }, [])

  useEffect(() => {
    if (!rebuildModalOpen || rebuildStreamStatus !== 'complete') return
    if (rebuildCompleteToastSentRef.current) return
    rebuildCompleteToastSentRef.current = true
    toast.success('Rebuild finished. Hard refresh (Ctrl+Shift+R) or use a private window to load updates.')
  }, [rebuildModalOpen, rebuildStreamStatus])

  useEffect(() => {
    if (!rebuildModalOpen) return
    rebuildLogEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [rebuildLogContent, rebuildModalOpen])

  // ---- Scraper live log (mirrors rebuild stream UX) ----
  const startScraperLogStream = useCallback((name: ScraperName) => {
    scraperLogStreamAbortRef.current?.abort()
    const ac = new AbortController()
    scraperLogStreamAbortRef.current = ac
    setScraperLogContent('')
    setScraperLogStatus('running')
    setScraperLogLoading(true)
    streamScraperLog(
      name,
      (chunk) => {
        setScraperLogContent((prev) => {
          const next = prev + chunk
          if (next.includes('Done in')) {
            setScraperLogStatus(jobOutcomeToStreamStatus(parseLiveLogJobOutcome(next)))
          }
          return next
        })
      },
      ac.signal,
      authUser?.token,
    )
      .then(() => {
        setScraperLogLoading(false)
        setScraperLogStatus((p) =>
          p === 'complete' || p === 'complete_warning' || p === 'complete_failed' || p === 'error'
            ? p
            : 'stream_ended',
        )
      })
      .catch((e: unknown) => {
        setScraperLogLoading(false)
        const err = e as { name?: string; message?: string }
        if (err?.name === 'AbortError') {
          setScraperLogStatus((p) => (p === 'running' ? 'stream_ended' : p))
          return
        }
        setScraperLogStatus('error')
        setScraperLogContent((prev) => prev + `\n[Error streaming log: ${err?.message ?? 'unknown'}]`)
      })
  }, [authUser?.token])

  const closeScraperLogModal = useCallback(() => {
    scraperLogStreamAbortRef.current?.abort()
    scraperLogStreamAbortRef.current = null
    setScraperLogModalOpen(false)
    setScraperLogStatus('idle')
    setScraperLogLoading(false)
    scraperCompleteToastSentRef.current = false
    setScraperLogScraper(null)
  }, [])

  useEffect(() => {
    if (!scraperLogModalOpen) return
    if (
      scraperLogStatus !== 'complete' &&
      scraperLogStatus !== 'complete_warning' &&
      scraperLogStatus !== 'complete_failed'
    ) {
      return
    }
    if (scraperCompleteToastSentRef.current) return
    scraperCompleteToastSentRef.current = true
    if (scraperLogStatus === 'complete_failed') {
      toast.error('Scraper finished with errors — no data was saved. Review the log.')
    } else if (scraperLogStatus === 'complete_warning') {
      toast.warning('Scraper finished with warnings — some divisions were not saved. Review the log.')
    } else {
      toast.success('Scraper finished. Tables will refresh automatically.')
    }
    queryClient.invalidateQueries({ queryKey: ['rankings'] })
    queryClient.invalidateQueries({ queryKey: ['rankings-last-update'] })
    queryClient.invalidateQueries({ queryKey: ['data-quality'] })
    queryClient.invalidateQueries({ queryKey: ['background-task-status'] })
  }, [scraperLogModalOpen, scraperLogStatus, queryClient])

  useEffect(() => {
    if (!scraperLogModalOpen) return
    scraperLogEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [scraperLogContent, scraperLogModalOpen])

  // ---- Shared live log (used by every long-running admin button except the
  // pre-existing rebuild-website + scraper-run flows above, which keep their
  // dedicated modals for now to minimize churn). All new buttons follow the
  // same UX: POST kicks off background work, then the GET .../log endpoint
  // streams progress into this single modal.
  const sharedLiveLog = useLiveLogStream({ authToken: authUser?.token })
  const [sharedLiveLogTitle, setSharedLiveLogTitle] = useState<string>('')
  const [sharedLiveLogLogPath, setSharedLiveLogLogPath] = useState<string>('')
  /**
   * Open the shared live-log modal pointed at the given streaming GET URL.
   * `logPath` is purely for the modal subtitle (e.g. `logs/load_wpba_pdf.log`).
   */
  const openSharedLiveLog = useCallback(
    (opts: { title: string; logPath: string; streamUrl: string; onComplete?: () => void }) => {
      setSharedLiveLogTitle(opts.title)
      setSharedLiveLogLogPath(opts.logPath)
      sharedLiveLog.start(opts.streamUrl, { onComplete: opts.onComplete })
    },
    [sharedLiveLog],
  )
  // Stable subtitle node so the modal doesn't re-render its DOM each tick.
  const sharedLiveLogSubtitle = useMemo(
    () =>
      sharedLiveLogLogPath ? (
        <>
          Output from{' '}
          <code className="text-sky-400 bg-slate-800 px-1 rounded">{sharedLiveLogLogPath}</code>{' '}
          on the server.
        </>
      ) : null,
    [sharedLiveLogLogPath],
  )

  const rebuildMutation = useMutation({
    mutationFn: () => adminApi.rebuildWebsite().then((r) => r.data),
    onSuccess: (data) => {
      if (data?.configured === false || data?.status === 'not_configured') {
        toast.error(data?.message ?? 'Not configured')
        return
      }
      setRebuildDone(true)
      rebuildCompleteToastSentRef.current = false
      setRebuildModalOpen(true)
      startRebuildLogStream()
      toast.success('Rebuild started — watch the progress window.')
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((e: any) => e?.msg ?? e).join(', ') : err?.message ?? 'Rebuild request failed'
      toast.error(msg)
    },
  })
  const fullDeployMutation = useMutation({
    mutationFn: () => adminApi.rebuildAllImages().then((r) => r.data),
    onSuccess: (data) => {
      const msg = data?.message ?? 'Full deploy started in background.'
      setFullDeployMessage(msg)
      if (data?.configured === false || data?.status === 'not_configured') {
        toast.error(msg)
        queryClient.invalidateQueries({ queryKey: ['admin', 'rebuild-all-status'] })
        return
      }
      toast.success(msg)
      // Open the shared live-log window pointed at full_deploy.log so the
      // operator can watch the long-running rebuild in real time. The pre-existing
      // _run_backfill_in_background thread on the server is unaffected.
      openSharedLiveLog({
        title: 'Full deploy',
        logPath: 'logs/full_deploy.log',
        streamUrl: '/admin/rebuild-all-images/log',
        onComplete: () => {
          toast.success('Full deploy finished. Hard refresh (Ctrl+Shift+R) to load updated assets.')
          queryClient.invalidateQueries({ queryKey: ['admin', 'rebuild-all-status'] })
        },
      })
    },
    onError: (err: Error) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      setFullDeployMessage(typeof detail === 'string' ? detail : err?.message ?? 'Failed')
      toast.error(err?.message ?? 'Full deploy failed')
    },
  })
  const fargoMutation = useMutation({
    mutationFn: () => triggerFargoSync('WPBA', false, fargoFullRefresh),
    onSuccess: (res) => {
      setFargoDone(true)
      setFargoResult(res)
      const started = res.started === true
      const msg = res.message ?? (started
        ? 'Fargo sync started in background. Watch logs for progress.'
        : `Updated ${res.updated} ratings (${res.players_processed} players). ${res.error ?? ''}`.trim())
      setFargoMessage(msg)
      queryClient.invalidateQueries({ queryKey: ['rankings'] })
      queryClient.invalidateQueries({ queryKey: ['rankings-last-update'] })
      queryClient.invalidateQueries({ queryKey: ['health-detailed'] })
      queryClient.invalidateQueries({ queryKey: ['admin', 'data-quality-issues'] })
      toast.success(started ? 'Fargo sync started in background' : res.updated > 0 ? `Fargo: ${res.updated} ratings updated` : 'Fargo sync finished')
    },
    onError: (err: Error) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      const msg = detail || err.message || 'Fargo sync disabled. Use the Import Fargo (CSV) section below.'
      setFargoMessage(msg)
      setFargoResult({ updated: 0, org_code: 'WPBA', players_processed: 0, error: msg, started: false })
      toast.error(msg)
    },
  })
  const fargoImportMutation = useMutation({
    mutationFn: () => {
      const lines = fargoImportText.trim().split(/\n/).filter(Boolean)
      const ratings: { player_name: string; fargo_rating: number }[] = []
      for (const line of lines) {
        const parts = line.split(/[,;\t]/).map((p) => p.trim())
        if (parts.length >= 2) {
          const name = parts[0].replace(/^["']|["']$/g, '')
          const rating = parseFloat(parts[1])
          if (name && !Number.isNaN(rating)) ratings.push({ player_name: name, fargo_rating: rating })
        }
      }
      if (ratings.length === 0) throw new Error('No valid rows. Use format: player_name,fargo_rating (one per line).')
      return rankingsApi.importFargo(fargoImportSystem as 'WPBA' | 'WPA', ratings)
    },
    onSuccess: (data: { message: string }) => {
      queryClient.invalidateQueries({ queryKey: ['rankings'] })
      toast.success(data.message)
      setFargoImportText('')
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Import failed')
    },
  })
  const tournamentScrapeMutation = useMutation({
    mutationFn: () => tournamentHistoryApi.triggerScrape(),
    onSuccess: (data) => {
      const msg =
        data?.message ??
        (data?.status === 'already_running'
          ? 'Scrape already in progress — watch the live log.'
          : 'Tournament history scrape started — watch the live log.')
      setTournamentScrapeMessage(msg)
      toast.success(msg)
      openSharedLiveLog({
        title: 'Tournament history sync (from rankings)',
        logPath: 'logs/refresh_past_tournaments.log',
        streamUrl: '/tournament-history/refresh-past/log',
        onComplete: () => {
          queryClient.invalidateQueries({ queryKey: ['tournament-history-scrape-status'] })
          queryClient.invalidateQueries({ queryKey: ['tournament-history'] })
          queryClient.invalidateQueries({ queryKey: ['tournament-history-years'] })
        },
      })
    },
    onError: (err: Error) => {
      setTournamentScrapeMessage(err.message)
      toast.error(err.message ?? 'Scrape failed')
    },
  })

  const runScraperMutation = useMutation({
    mutationFn: (name: ScraperName) => rankingsApi.runScraper(name),
    onSuccess: (data, name) => {
      setScraperRunLoading(null)
      setScraperRunMessage(data.message ?? `${name} scraper started.`)
      // Open the live-log modal so the user sees the same progress UX as Update website.
      scraperCompleteToastSentRef.current = false
      setScraperLogScraper(name)
      setScraperLogModalOpen(true)
      startScraperLogStream(name)
      toast.success(
        data.status === 'already_running'
          ? `${name} scraper already running — watch the live log.`
          : `${name} scraper started — watch the progress window.`,
      )
      // Pre-invalidate so the UI is ready when the run finishes; final invalidation
      // also fires on stream completion (see useEffect on scraperLogStatus).
      queryClient.invalidateQueries({ queryKey: ['rankings'] })
      queryClient.invalidateQueries({ queryKey: ['rankings-last-update'] })
      queryClient.invalidateQueries({ queryKey: ['data-quality'] })
      queryClient.invalidateQueries({ queryKey: ['background-task-status'] })
      if (name === 'wpa') {
        queryClient.invalidateQueries({ queryKey: ['rankings', 'wpa-men-tournament-systems'] })
        queryClient.invalidateQueries({ queryKey: ['rankings', 'wpa-women-tournament-systems'] })
        queryClient.invalidateQueries({ queryKey: ['leaderboard_rankings'] })
      }
      if (name === 'wpba') {
        queryClient.invalidateQueries({ queryKey: ['rankings', 'wpba-tournament-systems'] })
        queryClient.invalidateQueries({ queryKey: ['leaderboard_rankings'] })
      }
    },
    onError: (err: any) => {
      setScraperRunLoading(null)
      const detail = err?.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : err?.message ?? 'Scraper failed to start'
      setScraperRunMessage(msg)
      toast.error(msg)
    },
  })

  const wpbaPdfLoadMutation = useMutation({
    mutationFn: () => rankingsApi.refreshWpba(),
    onSuccess: (data) => {
      const msg =
        data.message ??
        (data.status === 'already_running'
          ? 'WPBA PDF load already in progress — watch the live log.'
          : 'WPBA PDF load started — watch the live log.')
      setWpbaPdfMessage(msg)
      setWpbaPdfError(null)
      toast.success(msg)
      // Invalidations move to onComplete so the UI refreshes when the run actually
      // finishes (writes "Done in Xs"), not the moment the POST returns 200.
      openSharedLiveLog({
        title: 'Load WPBA PDF',
        logPath: 'logs/load_wpba_pdf.log',
        streamUrl: '/rankings/refresh-wpba/log',
        onComplete: () => {
          queryClient.invalidateQueries({ queryKey: ['rankings'] })
          queryClient.invalidateQueries({ queryKey: ['rankings', 'wpba-tournament-systems'] })
          queryClient.invalidateQueries({ queryKey: ['rankings-last-update'] })
          queryClient.invalidateQueries({ queryKey: ['data-quality'] })
          queryClient.invalidateQueries({ queryKey: ['audit-log'] })
          queryClient.invalidateQueries({ queryKey: ['hot_streak_players'] })
          queryClient.invalidateQueries({ queryKey: ['tournament-history-years'] })
          queryClient.invalidateQueries({ queryKey: ['tournament-history'] })
          queryClient.invalidateQueries({ queryKey: ['tournament-history-details'] })
          queryClient.invalidateQueries({ queryKey: ['leaderboard_tournament_history_by_association'] })
        },
      })
    },
    onError: (err: Error) => {
      setWpbaPdfError(err.message ?? 'Load failed')
      setWpbaPdfMessage(null)
      toast.error(err.message ?? 'WPBA PDF load failed')
    },
  })

  const refreshUpcomingMutation = useMutation({
    mutationFn: () => tournamentHistoryApi.refreshUpcomingEvents(),
    onSuccess: (result) => {
      const msg =
        result.message ??
        (result.status === 'already_running'
          ? 'Refresh already in progress — watch the live log.'
          : 'Refresh started — watch the live log.')
      toast.success(msg)
      openSharedLiveLog({
        title: 'Refresh future tournaments',
        logPath: 'logs/refresh_upcoming_events.log',
        streamUrl: '/tournament-history/refresh-upcoming/log',
        onComplete: () => {
          queryClient.invalidateQueries({ queryKey: ['future-tournaments'] })
          queryClient.invalidateQueries({ queryKey: ['dashboard-upcoming-events'] })
        },
      })
    },
    onError: (err) => {
      toast.error(`Refresh failed: ${err instanceof Error ? err.message : 'Unknown error'}`)
    },
  })
  
  // Data quality resolve mutation
  const resolveConflictMutation = useMutation({
    mutationFn: ({ conflictId, notes }: { conflictId: number; notes: string }) =>
      adminApi.resolveDataQualityConflict(conflictId, notes),
    onSuccess: () => {
      toast.success('Conflict marked as resolved')
      queryClient.invalidateQueries({ queryKey: ['admin', 'data-quality-issues'] })
      setResolvingConflictId(null)
      setResolutionNote('')
    },
    onError: (err: Error) => {
      toast.error(`Failed to resolve: ${err.message || 'Unknown error'}`)
    },
  })

  // Data quality fix missing Fargo mutation
  const fixMissingFargoMutation = useMutation({
    mutationFn: () => adminApi.fixMissingFargoData(),
    onSuccess: (data) => {
      const matched = data?.totalMatched ?? 0
      const t1 = data?.tier1Matches ?? 0
      const t2 = data?.tier2Matches ?? 0
      toast.success(`✓ Fixed ${matched} players${t1 || t2 ? ` (Tier1: ${t1}, Tier2: ${t2})` : ''}`)
      queryClient.invalidateQueries({ queryKey: ['admin', 'data-quality-issues'] })
      queryClient.invalidateQueries({ queryKey: ['rankings'] })
      queryClient.invalidateQueries({ queryKey: ['rankings-last-update'] })
    },
    onError: (err: Error & { response?: { data?: { detail?: string } } }) => {
      const detail = err?.response?.data?.detail
      toast.error(`Fargo repair disabled: ${typeof detail === 'string' ? detail : 'Use CSV import instead.'}`)
    },
  })

  // System maintenance mutations
  const backupMutation = useMutation({
    mutationFn: () => adminApi.createSystemBackup(),
    onSuccess: (result) => {
      setBackupDone(true)
      const msg =
        result.message ??
        (result.status === 'already_running'
          ? 'A backup is already running — watch the live log.'
          : 'System backup started — watch the live log.')
      setBackupMessage(msg)
      toast.success(msg)
      openSharedLiveLog({
        title: 'Create system backup',
        logPath: 'logs/system_backup.log',
        streamUrl: '/backups/create/log',
        onComplete: () => {
          // Backup file landed; refresh the listing so a future Restore page sees it.
          queryClient.invalidateQueries({ queryKey: ['admin', 'backups'] })
          queryClient.invalidateQueries({ queryKey: ['backups'] })
        },
      })
    },
    onError: (err: Error) => {
      const msg = err.message || 'System backup failed'
      setBackupMessage(msg)
      toast.error(msg)
    },
  })

  // ---- Self-calibration mutations (replace inline `fetch('/api/self-calibration/...')`
  // calls in the JSX below; those calls had no auth headers and would 401 against the
  // hardened backend that now requires `Depends(require_admin)`).
  const runFullCalibrationMutation = useMutation({
    mutationFn: () => selfCalibrationApi.runCalibrationCycle(),
    onSuccess: (data) => {
      toast.success(
        data.message ??
          (data.status === 'already_running'
            ? 'Calibration cycle already running — watch the live log.'
            : 'Self-calibration cycle started — watch the live log.'),
      )
      openSharedLiveLog({
        title: 'Run full self-calibration',
        logPath: 'logs/calibration_cycle.log',
        streamUrl: '/self-calibration/run-calibration-cycle/log',
        onComplete: () => {
          queryClient.invalidateQueries({ queryKey: ['rating-accuracy'] })
          queryClient.invalidateQueries({ queryKey: ['independence-progress'] })
        },
      })
    },
    onError: (err: Error) => {
      toast.error(err.message ?? 'Failed to start calibration cycle')
    },
  })

  const compareEstFargoMutation = useMutation({
    mutationFn: () => selfCalibrationApi.compareEstFargo(),
    onSuccess: (data) => {
      toast.success(
        `EST vs Fargo: recorded ${data.recorded ?? 0} of ${data.candidates ?? 0}` +
          (data.mae != null ? ` · MAE ${data.mae}` : '') +
          (data.rmse != null ? ` · RMSE ${data.rmse}` : '')
      )
      queryClient.invalidateQueries({ queryKey: ['rating-accuracy'] })
      queryClient.invalidateQueries({ queryKey: ['independence-progress'] })
    },
    onError: (err: Error) => {
      toast.error(err.message ?? 'EST vs Fargo comparison failed')
    },
  })

  const applyRecommendationsMutation = useMutation({
    mutationFn: (ratingType: CalibrationRatingType) =>
      selfCalibrationApi.applyRecommendations(ratingType),
    onSuccess: (data, ratingType) => {
      toast.success(
        data.message ??
          (data.status === 'already_running'
            ? `Recommendations for ${ratingType} already applying — watch the live log.`
            : `Applying ${ratingType} recommendations — watch the live log.`),
      )
      openSharedLiveLog({
        title: `Apply AI recommendations (${ratingType.toUpperCase()})`,
        logPath: `logs/apply_recommendations_${ratingType}.log`,
        streamUrl: `/self-calibration/apply-recommendations/${ratingType}/log`,
        onComplete: () => {
          queryClient.invalidateQueries({ queryKey: ['rating-accuracy'] })
          queryClient.invalidateQueries({ queryKey: ['independence-progress'] })
        },
      })
    },
    onError: (err: Error, ratingType) => {
      toast.error(err.message ?? `Failed to apply ${ratingType} recommendations`)
    },
  })

  const { data: scrapeStatus } = useQuery({
    queryKey: ['tournament-history-scrape-status'],
    queryFn: () => tournamentHistoryApi.getScrapeStatus(),
    refetchInterval: (q) => (q.state.data?.running ? 3000 : false),
    enabled: !!tournamentScrapeMessage || tournamentScrapeMutation.isSuccess,
  })

  // Metrics detail handlers
  const handleFailedLoginsClick = () => {
    if (!securityMetrics) return
    setSelectedMetric('Failed Logins (24h)')
    setMetricsModalDetails([
      { label: 'Failed Attempts (24h)', value: securityMetrics.failed_attempts_24h },
      { label: 'Successful Logins (24h)', value: securityMetrics.successful_attempts_24h },
      { label: 'Total Login Activity (24h)', value: (securityMetrics.failed_attempts_24h + securityMetrics.successful_attempts_24h) },
    ])
    setMetricsModalOpen(true)
  }

  const handleUniqueIPsClick = () => {
    if (!securityMetrics) return
    setSelectedMetric('Unique IPs (24h)')
    setMetricsModalDetails([
      { label: 'Unique IP Addresses (24h)', value: securityMetrics.unique_ips_24h },
      { label: 'Failed Logins from Unique IPs', value: securityMetrics.failed_attempts_24h },
      { label: 'Active Login Sources', value: securityMetrics.unique_ips_24h, secondary: 'Different IP addresses attempting login' },
    ])
    setMetricsModalOpen(true)
  }

  const handleLockedAccountsClick = () => {
    if (!securityMetrics) return
    setSelectedMetric('Locked Accounts')
    setMetricsModalDetails([
      { label: 'Currently Locked Accounts', value: securityMetrics.locked_accounts_count },
      { label: 'Lock Duration', value: '30 minutes', secondary: 'Accounts lock after 5 failed attempts' },
      { label: 'Reason', value: 'Security', secondary: 'Protecting against brute force attacks' },
    ])
    setMetricsModalOpen(true)
  }

  const handleExportCSV = async () => {
    setExporting(true)
    try {
      const limit = 2000
      const data =
        exportSystem === 'WPBA_Women'
          ? await rankingsApi.getWPBAWomen(limit, 0)
          : exportSystem === 'WPA_Women'
            ? await rankingsApi.getWPAWomen(limit, 0)
            : await rankingsApi.getWPAMen(limit, 0)
      const rankings = data?.rankings ?? []
      if (!rankings.length) {
        toast.error('No rankings to export')
        return
      }
      const headers = ['Rank', 'Player Name', 'Fargo', 'Country', 'Points']
      const rows = rankings.map((r) =>
        [r.rank, `"${(r.name || '').replace(/"/g, '""')}"`, r.fargo_rating != null ? r.fargo_rating : 'none', r.country ?? '', r.points].join(',')
      )
      const csvContent = [headers.join(','), ...rows].join('\n')
      const blob = new Blob([csvContent], { type: 'text/csv' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${exportSystem.replace('_', '-')}_rankings_${new Date().toISOString().split('T')[0]}.csv`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      window.URL.revokeObjectURL(url)
      toast.success('CSV downloaded')
      setExportDone(true)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="p-6 space-y-8 max-w-6xl mx-auto">
      <header>
        <h2 className="text-lg font-semibold">Admin</h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          Operational tools first; overview and rating diagnostics below. Use scrapers and deploy actions sparingly.
        </p>
      </header>

      <AdminPageSection
        title="Rankings & data sources"
        description="Super-admin live scrapers call POST /rankings/scrapers/…/run. The API does not schedule these; avoid cron or daemons hitting refresh endpoints if you want updates only from here."
      >

          {isSuperAdmin && (
            <div className="rounded-lg border border-border bg-muted/20 overflow-hidden mb-4">
              <div className="px-3 py-2 border-b border-border bg-muted/40">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Live rankings scrapers
                </span>
              </div>
              <div className="divide-y divide-border">
                <div className="flex flex-wrap items-center gap-2 px-3 py-3">
                  <span className="text-sm font-medium w-44 shrink-0">WPBA Women</span>
                  <button
                    type="button"
                    onClick={() => {
                      setScraperRunMessage(null)
                      setScraperRunLoading('wpba')
                      runScraperMutation.mutate('wpba')
                    }}
                    disabled={!!scraperRunLoading}
                    className="min-h-[40px] px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
                  >
                    {scraperRunLoading === 'wpba' ? 'Running…' : 'Run'}
                  </button>
                </div>
                <div className="flex flex-wrap items-center gap-2 px-3 py-3">
                  <span className="text-sm font-medium w-44 shrink-0">WPA (all divisions)</span>
                  <button
                    type="button"
                    onClick={() => {
                      setScraperRunMessage(null)
                      setScraperRunLoading('wpa')
                      runScraperMutation.mutate('wpa')
                    }}
                    disabled={!!scraperRunLoading}
                    className="min-h-[40px] px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
                  >
                    {scraperRunLoading === 'wpa' ? 'Running…' : 'Run'}
                  </button>
                </div>
                <div className="flex flex-wrap items-center gap-2 px-3 py-3">
                  <span className="text-sm font-medium w-44 shrink-0">CP</span>
                  <button
                    type="button"
                    onClick={() => {
                      setScraperRunMessage(null)
                      setScraperRunLoading('externalpool')
                      runScraperMutation.mutate('externalpool')
                    }}
                    disabled={!!scraperRunLoading}
                    className="min-h-[40px] px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
                  >
                    {scraperRunLoading === 'externalpool' ? 'Running…' : 'Run'}
                  </button>
                </div>
                <div className="flex flex-wrap items-center gap-2 px-3 py-3">
                  <span className="text-sm font-medium w-44 shrink-0">Inside Spin (ratings + events)</span>
                  <button
                    type="button"
                    onClick={() => {
                      setScraperRunMessage(null)
                      setScraperRunLoading('insidesp')
                      runScraperMutation.mutate('insidesp')
                    }}
                    disabled={!!scraperRunLoading}
                    className="min-h-[40px] px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
                  >
                    {scraperRunLoading === 'insidesp' ? 'Running…' : 'Run'}
                  </button>
                </div>
                <div className="flex flex-wrap items-center gap-2 px-3 py-3">
                  <span className="text-sm font-medium w-44 shrink-0">Inside Spin Tier-2 (history)</span>
                  <button
                    type="button"
                    onClick={() => {
                      setScraperRunMessage(null)
                      setScraperRunLoading('insidesp_tier2')
                      runScraperMutation.mutate('insidesp_tier2')
                    }}
                    disabled={!!scraperRunLoading}
                    className="min-h-[40px] px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
                  >
                    {scraperRunLoading === 'insidesp_tier2' ? 'Running…' : 'Run'}
                  </button>
                </div>
              </div>
              {scraperRunMessage && (
                <p className="px-3 py-2 text-sm text-muted-foreground border-t border-border bg-background/50">{scraperRunMessage}</p>
              )}
            </div>
          )}

          <div className="rounded-lg border border-border overflow-hidden">
            <div className="px-3 py-2 border-b border-border bg-muted/30">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Data quality (Phase 5)
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2 px-3 py-3">
              <span className="text-sm font-medium w-44 shrink-0">Crosswalk &amp; drift</span>
              <button
                type="button"
                disabled={dataQualityLoading}
                onClick={async () => {
                  setDataQualityLoading(true)
                  setDataQualitySummary(null)
                  try {
                    const res = await apiClient.get('/admin/data-quality/summary')
                    const cw = res.data?.crosswalk?.total_rows ?? '?'
                    const drift = res.data?.insidesp_drift
                    const line = drift?.error
                      ? `Drift check error: ${drift.error}`
                      : `Crosswalk rows: ${cw}; IS API ${drift?.api_catalog_count} vs local crosswalk ${drift?.local_insidesp_crosswalk}; Fargo ${res.data?.fargo_coverage?.with_fargo_score}/${res.data?.fargo_coverage?.players_total}`
                    setDataQualitySummary(line)
                  } catch (e: unknown) {
                    setDataQualitySummary(e instanceof Error ? e.message : 'Data quality summary failed')
                  } finally {
                    setDataQualityLoading(false)
                  }
                }}
                className="min-h-[40px] px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
              >
                {dataQualityLoading ? 'Loading…' : 'Run report'}
              </button>
            </div>
            {dataQualitySummary && (
              <p className="px-3 py-2 text-sm text-muted-foreground border-t border-border bg-background/50">{dataQualitySummary}</p>
            )}
            <div className="flex flex-wrap items-center gap-2 px-3 py-3 border-t border-border">
              <span className="text-sm font-medium w-44 shrink-0">Crosswalk review</span>
              <button
                type="button"
                disabled={crosswalkReviewLoading}
                onClick={loadCrosswalkReview}
                className="min-h-[40px] px-3 py-1.5 rounded-lg bg-card border border-border text-sm font-medium hover:bg-accent disabled:opacity-50"
              >
                {crosswalkReviewLoading ? 'Loading…' : 'Load fuzzy matches'}
              </button>
              {crosswalkReviewRows !== null && (
                <span className="text-xs text-muted-foreground">
                  {crosswalkReviewRows.length} pending
                </span>
              )}
            </div>
            {crosswalkReviewMessage && (
              <p className="px-3 py-2 text-sm text-destructive border-t border-border bg-background/50">{crosswalkReviewMessage}</p>
            )}
            {crosswalkReviewRows !== null && crosswalkReviewRows.length > 0 && (
              <div className="border-t border-border overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-muted/30 text-left text-muted-foreground">
                      <th className="px-3 py-2 font-medium">Source event</th>
                      <th className="px-3 py-2 font-medium">Matched tournament</th>
                      <th className="px-3 py-2 font-medium">Score</th>
                      <th className="px-3 py-2 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {crosswalkReviewRows.map((row) => (
                      <tr key={row.id}>
                        <td className="px-3 py-2">
                          <span className="text-muted-foreground">{row.source}:</span>{' '}
                          {isHttpUrl(row.source_url) ? (
                            <a href={row.source_url} target="_blank" rel="noopener noreferrer" className="text-sky-500 hover:underline">
                              {row.source_event_id}
                            </a>
                          ) : (
                            row.source_event_id
                          )}
                        </td>
                        <td className="px-3 py-2">
                          {row.tournament_name ?? row.tournament_id}
                          {row.tournament_date && (
                            <span className="text-muted-foreground"> ({row.tournament_date})</span>
                          )}
                        </td>
                        <td className="px-3 py-2">{row.match_score != null ? row.match_score.toFixed(3) : '—'}</td>
                        <td className="px-3 py-2">
                          <div className="flex gap-2">
                            <button
                              type="button"
                              disabled={crosswalkRowPending !== null}
                              onClick={() => actOnCrosswalkRow(row.id, 'confirm')}
                              className="px-2 py-1 rounded bg-green-700/80 text-white hover:bg-green-600 disabled:opacity-50"
                            >
                              {crosswalkRowPending === row.id ? '…' : 'Confirm'}
                            </button>
                            <button
                              type="button"
                              disabled={crosswalkRowPending !== null}
                              onClick={() => actOnCrosswalkRow(row.id, 'reject')}
                              className="px-2 py-1 rounded bg-red-800/80 text-white hover:bg-red-700 disabled:opacity-50"
                            >
                              {crosswalkRowPending === row.id ? '…' : 'Reject'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="rounded-lg border border-border overflow-hidden">
            <div className="px-3 py-2 border-b border-border bg-muted/30">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                WPBA PDF &amp; tournament feeds
              </span>
            </div>
            <div className="divide-y divide-border">
              <div className="flex flex-wrap items-start gap-3 px-3 py-3">
                <span className="text-sm font-medium w-44 shrink-0 pt-2">WPBA PDF</span>
                <div className="flex flex-col gap-2 min-w-0">
                  <p className="text-xs text-muted-foreground max-w-xl">
                    Official PDF import (wpba.com). Saves rankings, splits per-tournament rows, tournament history, views.
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setWpbaPdfMessage(null)
                        setWpbaPdfError(null)
                        wpbaPdfLoadMutation.mutate()
                      }}
                      disabled={wpbaPdfLoadMutation.isPending}
                      className="min-h-[40px] px-4 py-2 rounded-lg bg-amber-600 text-white text-sm font-medium hover:bg-amber-500 disabled:opacity-50"
                    >
                      {wpbaPdfLoadMutation.isPending ? 'Loading PDF & saving…' : 'Load WPBA PDF'}
                    </button>
                    {wpbaPdfMessage && (
                      <span className="text-sm text-green-600 dark:text-green-400">{wpbaPdfMessage}</span>
                    )}
                    {wpbaPdfError && <span className="text-sm text-destructive">{wpbaPdfError}</span>}
                  </div>
                </div>
              </div>
              <div className="flex flex-wrap items-start gap-3 px-3 py-3">
                <span className="text-sm font-medium w-44 shrink-0 pt-2">Tournament history</span>
                <div className="flex flex-col gap-2 min-w-0">
                  <p className="text-xs text-muted-foreground max-w-xl">
                    <strong className="text-foreground/90">Super admin only.</strong> Does not call external sites. It rebuilds{' '}
                    <code className="bg-muted px-1 rounded text-[11px]">tournament_history</code> /{' '}
                    <code className="bg-muted px-1 rounded text-[11px]">tournament_results</code> from data the live scrapers
                    have already written: (1) every <code className="bg-muted px-1 rounded text-[11px]">rankings</code> snapshot
                    becomes a snapshot-style event; (2) WPBA Women per-event rows are filled from the latest PDF snapshot columns.
                    Run the scrapers above (or Load WPBA PDF) first so <code className="bg-muted px-1 rounded text-[11px]">rankings</code> is current.
                    To ingest CP / ExternalPool JSON from disk, use <code className="bg-muted px-1 rounded text-[11px]">POST /api/tournament-history/fill-from-cp-archives</code> separately — that path is not part of this sync.
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      setTournamentScrapeMessage(null)
                      tournamentScrapeMutation.mutate(undefined)
                    }}
                    disabled={tournamentScrapeMutation.isPending || scrapeStatus?.running}
                    className="min-h-[40px] w-fit px-4 py-2 rounded-lg bg-card border border-border text-sm font-medium hover:bg-accent disabled:opacity-50 flex items-center gap-2"
                  >
                    {(tournamentScrapeMutation.isPending || scrapeStatus?.running) ? (
                      <><span className="animate-spin">⟳</span> Syncing…</>
                    ) : (
                      <><span>📜</span> Sync tournament history</>
                    )}
                  </button>
                  {tournamentScrapeMessage && (
                    <p className="text-sm text-muted-foreground">{tournamentScrapeMessage}</p>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap items-start gap-3 px-3 py-3">
                <span className="text-sm font-medium w-44 shrink-0 pt-2">Future tournaments</span>
                <div className="flex flex-col gap-2 min-w-0">
                  <p className="text-xs text-muted-foreground max-w-xl">
                    Upcoming WPBA/WPA events for the Future Tournaments page.
                  </p>
                  <button
                    type="button"
                    onClick={() => refreshUpcomingMutation.mutate()}
                    disabled={refreshUpcomingMutation.isPending}
                    className="min-h-[40px] w-fit px-4 py-2 rounded-lg bg-card border border-border text-sm font-medium hover:bg-accent disabled:opacity-50 flex items-center gap-2"
                    title="Scrape latest upcoming events from WPBA and WPA"
                  >
                    {refreshUpcomingMutation.isPending ? (
                      <><span className="animate-spin">⟳</span> Refreshing…</>
                    ) : (
                      <><span>📅</span> Refresh future tournaments</>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>

        <div className="rounded-lg border border-border p-4 bg-muted/10">
          <h3 className="text-sm font-semibold mb-2">Export rankings to CSV</h3>
          <p className="text-xs text-muted-foreground mb-3">
            Download current rankings (including Fargo rating when available) as a CSV file for the selected system.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={exportSystem}
              onChange={(e) => setExportSystem(e.target.value as 'WPBA_Women' | 'WPA_Women' | 'WPA_Men')}
              className="px-3 py-2 rounded-lg bg-background border border-input text-foreground text-sm"
            >
              <option value="WPBA_Women">WPBA Women</option>
              <option value="WPA_Women">WPA Women</option>
              <option value="WPA_Men">WPA Men</option>
            </select>
            <button
              type="button"
              onClick={handleExportCSV}
              disabled={exporting}
              className="min-h-[44px] px-4 py-2.5 rounded-lg bg-card border border-border font-medium hover:bg-accent disabled:opacity-50 flex items-center gap-2"
            >
              {exporting ? (
                <><span className="animate-spin">⟳</span> Updating...</>
              ) : exportDone ? (
                'Done'
              ) : (
                <><span>📥</span> Export CSV</>
              )}
            </button>
          </div>
        </div>
      </AdminPageSection>

      <AdminPageSection title="Billing">
        <PaymentMethod />
      </AdminPageSection>

      <AdminPageSection title="Your account">
        <ChangePasswordSettings />
      </AdminPageSection>

      <AdminPageSection title="Deploy & backups" description="Backup, frontend rebuild, full deploy, and ALFa chat widget UI refresh. Does not refresh rankings or Fargo scrape data.">
        <div>
          <h3 className="text-sm font-semibold mb-2">System maintenance</h3>
          <div className="space-y-4">
            <div>
              <p className="text-xs text-muted-foreground mb-2">
                Create a comprehensive backup of database, source code, and documentation.
              </p>
              <button
                type="button"
                onClick={() => {
                  setBackupMessage(null)
                  backupMutation.mutate()
                }}
                disabled={backupMutation.isPending}
                className="min-h-[44px] px-4 py-2.5 rounded-lg bg-card border border-border font-medium hover:bg-accent disabled:opacity-50 flex items-center gap-2"
              >
                {backupMutation.isPending ? (
                  <><span className="animate-spin">⟳</span> Creating backup...</>
                ) : backupDone ? (
                  'Backup completed'
                ) : (
                  <><span>💾</span> Create system backup</>
                )}
              </button>
              {backupMessage && (
                <p className="mt-2 text-sm text-muted-foreground">{backupMessage}</p>
              )}
            </div>

          </div>
        </div>

        <div className="border-t border-border pt-4">
          <h3 className="text-sm font-semibold mb-1">ALFa chat widget — refresh UI</h3>
          <p className="text-xs text-muted-foreground mb-3">
            The floating Ask ALFa dock matches <span className="font-medium">contracts-bot</span> via{' '}
            <code className="text-xs bg-muted px-1 rounded">@alfa-ai/chat-widget</code>. After{' '}
            <code className="text-xs bg-muted px-1 rounded">git pull</code> on this server (widget integration or package bump),
            run <span className="font-medium">Refresh app UI</span> below so the browser serves a new{' '}
            <code className="text-xs bg-muted px-1 rounded">frontend/dist</code>. Hard-refresh the site (Ctrl+Shift+R) when done.
            Super admin: use <span className="font-medium">Full deploy</span> for API + nginx + tunnel parity.
          </p>
          {rebuildStatus?.configured === true && (
            <button
              type="button"
              onClick={() => {
                setRebuildMessage(null)
                rebuildMutation.mutate()
              }}
              disabled={rebuildMutation.isPending}
              className="min-h-[44px] px-4 py-2.5 rounded-lg bg-sky-600 text-white font-medium hover:bg-sky-500 disabled:opacity-50 flex items-center gap-2"
            >
              {rebuildMutation.isPending ? (
                <><span className="animate-spin">⟳</span> Rebuilding frontend…</>
              ) : (
                <><span>💬</span> Refresh app UI (rebuild frontend)</>
              )}
            </button>
          )}
        </div>

        <div className="border-t border-border pt-4">
          <h3 className="text-sm font-semibold mb-1">Update website</h3>
          <p className="text-xs text-muted-foreground mb-3">
            Rebuilds the frontend (npm/vite on the server), then optionally rebuilds Docker images. Code must already be on the server (git pull / deploy). If nothing changes, use <span className="font-medium">View rebuild log</span> — common fixes: production API container needs the full <code className="text-xs bg-muted px-1 rounded">frontend/</code> mount and Node in the image (see <code className="text-xs bg-muted px-1 rounded">docs/PRODUCTION_DEPLOYMENT.md</code> §5). For Python/API-only changes, run <code className="text-xs bg-muted px-1 rounded">./scripts/full_deploy.sh</code> on the host. Does not refresh rankings/Fargo.
          </p>

          {rebuildStatus === undefined && (
            <p className="text-xs text-muted-foreground mb-3">Checking if rebuild is available…</p>
          )}
          {rebuildStatus?.configured === false && (
            <div className="mb-3 p-3 rounded-lg bg-muted/50 border border-border">
              <p className="text-sm font-medium text-foreground mb-1">Update website not available on this server</p>
              <p className="text-xs text-muted-foreground">On the server, ensure Docker Compose is configured with the rebuild script environment variables. Use <code className="bg-muted px-1 rounded">./scripts/rebuild_website_now.sh</code> for manual rebuilds.</p>
            </div>
          )}
          {rebuildStatus?.configured === true && (
            <>
              <button
                type="button"
                onClick={() => {
                  setRebuildMessage(null)
                  rebuildMutation.mutate()
                }}
                disabled={rebuildMutation.isPending}
                className="min-h-[44px] px-4 py-2.5 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 disabled:opacity-50 flex items-center gap-2"
              >
                {rebuildMutation.isPending ? (
                  <><span className="animate-spin">⟳</span> Starting…</>
                ) : rebuildDone ? (
                  <><span className="text-green-400">✓</span> Started</>
                ) : (
                  <><span>🌐</span> Update website</>
                )}
              </button>
              {rebuildMessage && !rebuildMutation.isPending && (
                <p className={`mt-2 text-sm ${rebuildMutation.isError ? 'text-amber-500' : 'text-muted-foreground'}`}>{rebuildMessage}</p>
              )}
              <p className="mt-2 text-xs text-muted-foreground">
                If errors occur: check Settings → Health &amp; logs for API errors, or on the server run{' '}
                <code className="bg-muted px-1 rounded">tail -f logs/rebuild_website.log</code> (repo <code className="bg-muted px-1 rounded">./logs/</code>).
              </p>
              <button
                type="button"
                onClick={() => {
                  rebuildCompleteToastSentRef.current = false
                  setRebuildModalOpen(true)
                  startRebuildLogStream()
                }}
                className="mt-2 text-xs text-muted-foreground hover:text-foreground underline"
              >
                View rebuild log (live)
              </button>
            </>
          )}
        </div>

        {rebuildModalOpen && (
          <div
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4"
            onClick={() => closeRebuildModal()}
            role="presentation"
          >
            <div
              className="w-full max-w-4xl max-h-[90vh] flex flex-col rounded-xl border border-border bg-slate-900 text-slate-pool_opt_in shadow-xl"
              onClick={(e) => e.stopPropagation()}
              role="dialog"
              aria-modal="true"
              aria-labelledby="rebuild-modal-title"
            >
              <div className="flex items-start justify-between gap-3 border-b border-slate-700 px-4 py-3 shrink-0">
                <div>
                  <h2 id="rebuild-modal-title" className="text-lg font-semibold text-white">
                    Website rebuild
                  </h2>
                  <p className="text-xs text-slate-400 mt-1">
                    Output from <code className="text-sky-400 bg-slate-800 px-1 rounded">logs/rebuild_website.log</code> on the server.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => closeRebuildModal()}
                  className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-300 hover:bg-slate-800 hover:text-white"
                >
                  Close
                </button>
              </div>
              <div className="px-4 py-2 border-b border-slate-700 shrink-0 flex flex-wrap items-center gap-2">
                {rebuildStreamStatus === 'running' && (
                  <span className="inline-flex items-center gap-2 text-sm text-sky-400">
                    <span className="inline-block h-2 w-2 rounded-full bg-sky-400 animate-pulse" aria-hidden />
                    {liveLogStatusLabel(rebuildStreamStatus)}
                  </span>
                )}
                {(rebuildStreamStatus === 'complete' ||
                  rebuildStreamStatus === 'complete_warning' ||
                  rebuildStreamStatus === 'complete_failed') && (
                  <span className={`text-sm font-medium ${liveLogStatusClass(rebuildStreamStatus)}`}>
                    {liveLogStatusLabel(rebuildStreamStatus)}
                  </span>
                )}
                {rebuildStreamStatus === 'stream_ended' && (
                  <span className={`text-sm font-medium ${liveLogStatusClass(rebuildStreamStatus)}`}>
                    Live stream ended — if the log does not show &quot;Done in …&quot;, the rebuild may still be running on the server.
                  </span>
                )}
                {rebuildStreamStatus === 'error' && (
                  <span className={`text-sm font-medium ${liveLogStatusClass(rebuildStreamStatus)}`}>
                    {liveLogStatusLabel(rebuildStreamStatus)}
                  </span>
                )}
                {rebuildLogLoading && <span className="text-xs text-slate-500">Receiving…</span>}
              </div>
              <div className="flex-1 min-h-[200px] overflow-auto px-4 py-3">
                <pre className="text-xs font-mono whitespace-pre-wrap break-words text-slate-200">
                  {rebuildLogContent || (rebuildLogLoading ? 'Connecting to log…' : '[Waiting for log…]')}
                  <div ref={rebuildLogEndRef} />
                </pre>
              </div>
              <div className="border-t border-slate-700 px-4 py-2 flex justify-end gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => {
                    rebuildCompleteToastSentRef.current = false
                    startRebuildLogStream()
                  }}
                  className="rounded-lg px-3 py-1.5 text-sm font-medium bg-slate-800 text-slate-200 hover:bg-slate-700"
                >
                  Refresh log
                </button>
                <button
                  type="button"
                  onClick={() => closeRebuildModal()}
                  className="rounded-lg px-3 py-1.5 text-sm font-medium bg-sky-600 text-white hover:bg-sky-500"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        )}

        {scraperLogModalOpen && scraperLogScraper && (
          <div
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4"
            onClick={() => closeScraperLogModal()}
            role="presentation"
          >
            <div
              className="w-full max-w-4xl max-h-[90vh] flex flex-col rounded-xl border border-border bg-slate-900 text-slate-pool_opt_in shadow-xl"
              onClick={(e) => e.stopPropagation()}
              role="dialog"
              aria-modal="true"
              aria-labelledby="scraper-log-modal-title"
            >
              <div className="flex items-start justify-between gap-3 border-b border-slate-700 px-4 py-3 shrink-0">
                <div>
                  <h2 id="scraper-log-modal-title" className="text-lg font-semibold text-white">
                    {scraperLogScraper === 'wpba'
                      ? 'WPBA Women scraper'
                      : scraperLogScraper === 'wpa'
                        ? 'WPA scraper (all divisions)'
                        : scraperLogScraper === 'insidesp'
                          ? 'Inside Spin scraper (ratings + events)'
                          : scraperLogScraper === 'insidesp_tier2'
                            ? 'Inside Spin Tier-2 (historical events + placements)'
                            : 'CP (External Pool) scraper'}
                  </h2>
                  <p className="text-xs text-slate-400 mt-1">
                    Output from{' '}
                    <code className="text-sky-400 bg-slate-800 px-1 rounded">
                      logs/scraper_{scraperLogScraper}.log
                    </code>{' '}
                    on the server.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => closeScraperLogModal()}
                  className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-300 hover:bg-slate-800 hover:text-white"
                >
                  Close
                </button>
              </div>
              <div className="px-4 py-2 border-b border-slate-700 shrink-0 flex flex-wrap items-center gap-2">
                {scraperLogStatus === 'running' && (
                  <span className="inline-flex items-center gap-2 text-sm text-sky-400">
                    <span className="inline-block h-2 w-2 rounded-full bg-sky-400 animate-pulse" aria-hidden />
                    {liveLogStatusLabel(scraperLogStatus)}
                  </span>
                )}
                {(scraperLogStatus === 'complete' ||
                  scraperLogStatus === 'complete_warning' ||
                  scraperLogStatus === 'complete_failed') && (
                  <span className={`text-sm font-medium ${liveLogStatusClass(scraperLogStatus)}`}>
                    {liveLogStatusLabel(scraperLogStatus)}
                  </span>
                )}
                {scraperLogStatus === 'stream_ended' && (
                  <span className={`text-sm font-medium ${liveLogStatusClass(scraperLogStatus)}`}>
                    Live stream ended — if the log does not show &quot;Done in …&quot;, the scraper may still be running on the server.
                  </span>
                )}
                {scraperLogStatus === 'error' && (
                  <span className={`text-sm font-medium ${liveLogStatusClass(scraperLogStatus)}`}>
                    {liveLogStatusLabel(scraperLogStatus)}
                  </span>
                )}
                {scraperLogLoading && <span className="text-xs text-slate-500">Receiving…</span>}
              </div>
              <div className="flex-1 min-h-[200px] overflow-auto px-4 py-3">
                <pre className="text-xs font-mono whitespace-pre-wrap break-words text-slate-200">
                  {scraperLogContent || (scraperLogLoading ? 'Connecting to log…' : '[Waiting for log…]')}
                  <div ref={scraperLogEndRef} />
                </pre>
              </div>
              <div className="border-t border-slate-700 px-4 py-2 flex justify-end gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => {
                    scraperCompleteToastSentRef.current = false
                    if (scraperLogScraper) startScraperLogStream(scraperLogScraper)
                  }}
                  className="rounded-lg px-3 py-1.5 text-sm font-medium bg-slate-800 text-slate-200 hover:bg-slate-700"
                >
                  Refresh log
                </button>
                <button
                  type="button"
                  onClick={() => closeScraperLogModal()}
                  className="rounded-lg px-3 py-1.5 text-sm font-medium bg-sky-600 text-white hover:bg-sky-500"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Shared live-log modal — rendered once, reused by every long-running
            admin button (Load WPBA PDF, Refresh future tournaments, Tournament
            scrape, Full deploy, Self-calibration cycle, Apply AI recommendations,
            Create system backup). The pre-existing rebuild-website + scraper
            modals above keep their dedicated state for now to minimize churn. */}
        <LiveLogModal
          open={sharedLiveLog.open}
          status={sharedLiveLog.status}
          loading={sharedLiveLog.loading}
          content={sharedLiveLog.content}
          refresh={sharedLiveLog.refresh}
          close={sharedLiveLog.close}
          title={sharedLiveLogTitle || 'Live log'}
          subtitle={sharedLiveLogSubtitle}
          titleId="shared-live-log-modal-title"
        />

        {isSuperAdmin && (
          <div className="border-t border-border pt-4">
            <h3 className="text-sm font-semibold mb-2">Server controls (Super admin)</h3>
            <p className="text-xs text-muted-foreground mb-3">
              Full deploy from the web app. Runs scripts on the server.
            </p>
            {rebuildAllStatus?.configured === false && (
              <div className="mb-3 p-3 rounded-lg bg-muted/50 border border-border">
                <p className="text-sm font-medium text-amber-600 dark:text-amber-500 mb-1">Full deploy not available on this server</p>
                <p className="text-xs text-muted-foreground">On the server, ensure Docker Compose is configured with the rebuild script environment variables. Use <code className="bg-muted px-1 rounded">./scripts/rebuild_website_now.sh</code> for manual rebuilds.</p>
              </div>
            )}
            <div className="flex flex-wrap gap-2 mb-3">
              <button
                type="button"
                onClick={() => { setFullDeployMessage(null); fullDeployMutation.mutate() }}
                disabled={fullDeployMutation.isPending || rebuildAllStatus?.configured === false}
                className="min-h-[40px] px-4 py-2 rounded-lg bg-amber-600 text-white text-sm font-medium hover:bg-amber-500 disabled:opacity-50 flex items-center gap-2"
                title={rebuildAllStatus?.configured === false ? 'Full deploy script not found on server' : undefined}
              >
                {fullDeployMutation.isPending ? <><span className="animate-spin">⟳</span> Starting…</> : <>Full deploy</>}
              </button>
            </div>
            {fullDeployMessage && <p className="text-xs text-muted-foreground mb-1">{fullDeployMessage}</p>}
          </div>
        )}

      </AdminPageSection>

      <AdminPageSection title="Users & permissions" description="Accounts, role matrix, and AI Coach tiers. Super-admin edits persist to JSON config files.">
        <div className="space-y-6">
          <div>
          <h3 className="text-sm font-semibold mb-2">User management</h3>
          <p className="text-xs text-muted-foreground mb-3">
            List accounts and create new users. Super admin can create any role including other super admins.
          </p>
          <div className="overflow-x-auto">
            {usersList?.users?.length ? (
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 pr-4">Username</th>
                    <th className="text-left py-2 pr-4">Email</th>
                    <th className="text-left py-2">Role</th>
                    <th className="text-right py-2 w-20">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {usersList.users.map((u) => (
                    <tr key={u.id} className="border-b border-border/50">
                      <td className="py-1.5 pr-4 font-medium">{u.username}</td>
                      <td className="py-1.5 pr-4 text-muted-foreground">{u.email}</td>
                      <td className="py-1.5">{u.role}</td>
                      <td className="py-1.5 text-right">
                        <button
                          type="button"
                          onClick={async () => {
                            setEditUserUsername(u.username)
                            setEditUserNewUsername(u.username)
                            setEditUserRole(u.role)
                            setEditUserNewPassword('')
                            setEditUserPasswordError(null)
                            setEditUserOpen(true)
                            setEditUserAssociationsText('')
                            try {
                              const r = await usersApi.getUserAssociations(u.username)
                              setEditUserAssociationsText(r.associations.join(', '))
                            } catch {
                              setEditUserAssociationsText('')
                            }
                          }}
                          className="text-primary hover:underline text-xs font-medium"
                        >
                          Edit role
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-sm text-muted-foreground">No users or loading…</p>
            )}
          </div>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => setCreateUserOpen(true)}
              className="min-h-[36px] px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90"
            >
              Create user
            </button>
            <button
              type="button"
              onClick={async () => {
                try {
                  const blob = await usersApi.downloadFargoAccountsCSV()
                  const url = window.URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = `fargo_accounts_${new Date().toISOString().split('T')[0]}.csv`
                  document.body.appendChild(a)
                  a.click()
                  window.URL.revokeObjectURL(url)
                  document.body.removeChild(a)
                  toast.success('Fargo accounts CSV downloaded')
                } catch (err) {
                  toast.error(err instanceof Error ? err.message : 'Failed to download CSV')
                }
              }}
              className="min-h-[36px] px-3 py-1.5 rounded-lg bg-card border border-border text-sm font-medium hover:bg-accent"
            >
              Download Fargo Accounts CSV
            </button>
          </div>
          {createUserOpen && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setCreateUserOpen(false)}>
              <div className="bg-card border border-border rounded-lg p-4 w-full max-w-sm shadow-lg" onClick={(e) => e.stopPropagation()}>
                <h4 className="font-semibold mb-3">Create user</h4>
                <div className="space-y-2">
                  <input
                    type="text"
                    placeholder="Username"
                    value={createUserForm.username}
                    onChange={(e) => setCreateUserForm((f) => ({ ...f, username: e.target.value }))}
                    className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm"
                  />
                  <input
                    type="email"
                    placeholder="Email"
                    value={createUserForm.email}
                    onChange={(e) => setCreateUserForm((f) => ({ ...f, email: e.target.value }))}
                    className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm"
                  />
                  <input
                    type="password"
                    placeholder="Password"
                    value={createUserForm.password}
                    onChange={(e) => setCreateUserForm((f) => ({ ...f, password: e.target.value }))}
                    className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm"
                  />
                  <select
                    value={createUserForm.role}
                    onChange={(e) => setCreateUserForm((f) => ({ ...f, role: e.target.value }))}
                    className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm"
                  >
                    <option value="user">User</option>
                    <option value="admin">Admin</option>
                    <option value="director">Director</option>
                    <option value="moderator">Moderator</option>
                    {isSuperAdmin && <option value="super_admin">Super admin</option>}
                  </select>
                  <div>
                    <label className="block text-xs text-muted-foreground mb-1">AI Coach tier</label>
                    <select
                      value={createUserForm.tier ?? ''}
                      onChange={(e) => setCreateUserForm((f) => ({ ...f, tier: e.target.value }))}
                      className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm"
                    >
                      <option value="">Select tier…</option>
                      {Object.entries(tierConfig).map(([key, t]) => (
                        <option key={key} value={key}>
                          {(t as { name?: string }).name ?? key}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-muted-foreground mb-1">
                      Ranking associations (director required)
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. WPA_Women, WPBA_Women"
                      value={createUserAssociations}
                      onChange={(e) => setCreateUserAssociations(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm"
                    />
                    <p className="text-[10px] text-muted-foreground mt-1">Comma-separated. Controls which ranking systems the director may import.</p>
                  </div>
                </div>
                <div className="mt-4 flex gap-2 justify-end">
                  <button type="button" onClick={() => setCreateUserOpen(false)} className="px-3 py-1.5 rounded-lg border border-border hover:bg-accent text-sm">Cancel</button>
                  <button
                    type="button"
                    onClick={() => {
                      const assoc = parseAssociationsInput(createUserAssociations)
                      createUserMutation.mutate({
                        ...createUserForm,
                        tier: createUserForm.tier || undefined,
                        associations: assoc.length ? assoc : undefined,
                      })
                    }}
                    disabled={
                      createUserMutation.isPending
                      || !createUserForm.username.trim()
                      || !createUserForm.email.trim()
                      || !createUserForm.password
                      || !createUserForm.tier?.trim()
                      || (createUserForm.role === 'director' && parseAssociationsInput(createUserAssociations).length === 0)
                    }
                    className="px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
                  >
                    {createUserMutation.isPending ? 'Creating…' : 'Create'}
                  </button>
                </div>
              </div>
            </div>
          )}
          {editUserOpen && editUserUsername && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setEditUserOpen(false)}>
              <div className="bg-card border border-border rounded-lg p-4 w-full max-w-sm shadow-lg" onClick={(e) => e.stopPropagation()}>
                <h4 className="font-semibold mb-3">Edit user: {editUserUsername}</h4>
                {isSuperAdmin && (
                  <>
                    <p className="text-xs text-muted-foreground mb-2">Username</p>
                    <input
                      type="text"
                      value={editUserNewUsername}
                      onChange={(e) => setEditUserNewUsername(e.target.value)}
                      placeholder="Username (3-20 chars)"
                      className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm mb-4"
                    />
                  </>
                )}
                <p className="text-xs text-muted-foreground mb-2">Role</p>
                <select
                  value={editUserRole}
                  onChange={(e) => setEditUserRole(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm mb-2"
                >
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                  <option value="director">Director</option>
                  <option value="moderator">Moderator</option>
                  {isSuperAdmin && <option value="super_admin">Super admin</option>}
                </select>
                <label className="block text-xs text-muted-foreground mb-1">Ranking associations</label>
                <input
                  type="text"
                  placeholder="e.g. WPA_Women, WPBA_Women"
                  value={editUserAssociationsText}
                  onChange={(e) => setEditUserAssociationsText(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm mb-4"
                />
                <p className="text-[10px] text-muted-foreground mb-4">Comma-separated. Saved with role. Directors must have at least one.</p>
                <div className="flex gap-2 justify-end mb-4">
                  <button type="button" onClick={() => setEditUserOpen(false)} className="px-3 py-1.5 rounded-lg border border-border hover:bg-accent text-sm">Cancel</button>
                  <button
                    type="button"
                    onClick={() =>
                      updateUserMutation.mutate({
                        username: editUserUsername,
                        newUsername: isSuperAdmin ? editUserNewUsername : undefined,
                        role: editUserRole,
                        associations: parseAssociationsInput(editUserAssociationsText),
                      })
                    }
                    disabled={
                      updateUserMutation.isPending
                      || (isSuperAdmin && editUserNewUsername.trim().length > 0 && (editUserNewUsername.trim().length < 3 || editUserNewUsername.trim().length > 20))
                      || (editUserRole === 'director' && parseAssociationsInput(editUserAssociationsText).length === 0)
                    }
                    className="px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
                  >
                    {updateUserMutation.isPending ? 'Saving…' : 'Save role & associations'}
                  </button>
                </div>
                <div className="border-t border-border pt-3 mt-3">
                  <p className="text-xs font-medium text-muted-foreground mb-2">Password</p>
                  <button
                    type="button"
                    onClick={() => resetUserPasswordMutation.mutate(editUserUsername)}
                    disabled={resetUserPasswordMutation.isPending}
                    className="w-full px-3 py-1.5 rounded-lg bg-amber-600/20 text-amber-600 border border-amber-600/40 text-sm font-medium hover:bg-amber-600/30 disabled:opacity-50 mb-3"
                  >
                    {resetUserPasswordMutation.isPending ? 'Resetting…' : 'Reset to default password'}
                  </button>
                  <p className="text-xs text-muted-foreground mb-2">Sets temp password; user must change on next login. Or set a custom password below:</p>
                  <input
                    type="password"
                    placeholder="New password (optional)"
                    value={editUserNewPassword}
                    onChange={(e) => { setEditUserNewPassword(e.target.value); setEditUserPasswordError(null) }}
                    className="w-full px-3 py-2 rounded-lg border border-input bg-background text-sm mb-2"
                  />
                  {editUserPasswordError && <p className="text-xs text-amber-500 mb-2">{editUserPasswordError}</p>}
                  <button
                    type="button"
                    onClick={() => {
                      const err = validateEditUserPassword(editUserNewPassword)
                      if (err) { setEditUserPasswordError(err); return }
                      setUserPasswordMutation.mutate({ username: editUserUsername, newPassword: editUserNewPassword })
                    }}
                    disabled={setUserPasswordMutation.isPending || !editUserNewPassword}
                    className="w-full px-3 py-1.5 rounded-lg bg-muted text-muted-foreground text-sm font-medium hover:bg-muted/80 disabled:opacity-50"
                  >
                    {setUserPasswordMutation.isPending ? 'Setting…' : 'Set custom password'}
                  </button>
                  <p className="text-xs text-muted-foreground mt-2">8+ chars, upper, lower, number, special character. User must change on next login.</p>
                </div>
                <div className="border-t border-border pt-3 mt-3">
                  <p className="text-xs font-medium text-muted-foreground mb-2">Delete user</p>
                  <button
                    type="button"
                    onClick={() => {
                      if (confirm(`Are you sure you want to delete user "${editUserUsername}"? This action cannot be undone.`)) {
                        deleteUserMutation.mutate(editUserUsername)
                      }
                    }}
                    disabled={deleteUserMutation.isPending}
                    className="w-full px-3 py-1.5 rounded-lg bg-red-600/20 text-red-600 border border-red-600/40 text-sm font-medium hover:bg-red-600/30 disabled:opacity-50"
                  >
                    {deleteUserMutation.isPending ? 'Deleting…' : 'Delete this user'}
                  </button>
                  <p className="text-xs text-muted-foreground mt-2">Permanently removes the user account and all associated data.</p>
                </div>
              </div>
            </div>
          )}
          </div>

        {canAdmin && (
          <>
            <div className="border-t border-border pt-4">
              <h3 className="text-sm font-semibold mb-2">Role capabilities</h3>
              <p className="text-xs text-muted-foreground mb-3">
                {isSuperAdmin
                  ? 'Super admin can edit. Changes saved to config/role_capabilities.json.'
                  : "What each role can do. To change a user's capabilities, use Edit role in the User management table above."}
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-2 pr-4 font-medium">Capability</th>
                      {ROLE_LABELS.map((r) => (
                        <th key={r} className="text-center py-2 px-2 font-medium">{r}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(editableCapabilities.length > 0 ? editableCapabilities : roleCapabilities).map((row, rowIdx) => (
                      <tr key={row.id} className="border-b border-border/50">
                        <td className="py-1.5 pr-4">{row.label}</td>
                        {row.roles.map((checked, i) => (
                          <td key={i} className="text-center py-1.5 px-2">
                            {isSuperAdmin ? (
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => {
                                  const next = [...(editableCapabilities.length > 0 ? editableCapabilities : roleCapabilities)]
                                  const r = next[rowIdx]
                                  if (r) {
                                    const roles = [...r.roles] as [boolean, boolean, boolean, boolean]
                                    roles[i] = !roles[i]
                                    next[rowIdx] = { ...r, roles }
                                    setEditableCapabilities(next)
                                  }
                                }}
                                className="rounded border-border"
                              />
                            ) : (
                              <input type="checkbox" checked={checked} readOnly className="rounded border-border" />
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {isSuperAdmin && (editableCapabilities.length > 0 || roleCapabilities.length > 0) && (
                <button
                  type="button"
                  onClick={() => saveRoleCapabilitiesMutation.mutate(editableCapabilities.length > 0 ? editableCapabilities : roleCapabilities)}
                  disabled={saveRoleCapabilitiesMutation.isPending}
                  className="mt-3 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
                >
                  {saveRoleCapabilitiesMutation.isPending ? 'Saving…' : 'Save capabilities'}
                </button>
              )}
            </div>

            <div className="border-t border-border pt-4">
              <h3 className="text-sm font-semibold mb-2">Price level / tier (AI Coach)</h3>
              <p className="text-xs text-muted-foreground mb-3">
                {isSuperAdmin
                  ? 'Super admin can edit. Changes saved to config/tier_config.json.'
                  : 'What each tier includes.'}
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="text-left py-2 pr-4 font-medium">Feature / Tier</th>
                      {Object.entries(Object.keys(editableTierConfig).length > 0 ? editableTierConfig : tierConfig).map(([key, t]) => (
                        <th key={key} className="text-center py-2 px-2 font-medium">
                          {isSuperAdmin ? (
                            <input
                              type="text"
                              value={(t as { name?: string }).name ?? key}
                              onChange={(e) => setEditableTierConfig((prev) => ({ ...prev, [key]: { ...prev[key], name: e.target.value } }))}
                              className="w-24 px-1 py-0.5 rounded bg-background border border-input text-center text-xs"
                            />
                          ) : (
                            (t as { name?: string }).name ?? key
                          )}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-border/50">
                      <td className="py-1.5 pr-4">Price $/mo</td>
                      {Object.entries(Object.keys(editableTierConfig).length > 0 ? editableTierConfig : tierConfig).map(([key, t]) => (
                        <td key={key} className="text-center py-1.5 px-2">
                          {isSuperAdmin ? (
                            <input
                              type="number"
                              min="0"
                              step="0.01"
                              value={(t as { price_monthly?: number }).price_monthly ?? 0}
                              onChange={(e) => setEditableTierConfig((prev) => ({ ...prev, [key]: { ...prev[key], price_monthly: parseFloat(e.target.value) || 0 } }))}
                              className="w-16 px-1 py-0.5 rounded bg-background border border-input text-center text-xs"
                            />
                          ) : (
                            (t as { price_monthly?: number }).price_monthly ?? '—'
                          )}
                        </td>
                      ))}
                    </tr>
                    <tr className="border-b border-border/50">
                      <td className="py-1.5 pr-4">Monthly analyses</td>
                      {Object.entries(Object.keys(editableTierConfig).length > 0 ? editableTierConfig : tierConfig).map(([key, t]) => {
                        const v = (t as { monthly_limit?: number | null }).monthly_limit
                        return (
                          <td key={key} className="text-center py-1.5 px-2">
                            {isSuperAdmin ? (
                              <input
                                type="text"
                                placeholder="— or number"
                                value={v == null ? '' : (v > 900000 ? 'Unlimited' : String(v))}
                                onChange={(e) => {
                                  const val = e.target.value.trim()
                                  setEditableTierConfig((prev) => ({
                                    ...prev,
                                    [key]: { ...prev[key], monthly_limit: val === '' ? null : val.toLowerCase() === 'unlimited' ? 999999 : parseInt(val, 10) || null },
                                  }))
                                }}
                                className="w-20 px-1 py-0.5 rounded bg-background border border-input text-center text-xs"
                              />
                            ) : (
                              v == null ? '—' : (v > 900000 ? 'Unlimited' : String(v))
                            )}
                          </td>
                        )
                      })}
                    </tr>
                    <tr className="border-b border-border/50">
                      <td className="py-1.5 pr-4">Lifetime analyses</td>
                      {Object.entries(Object.keys(editableTierConfig).length > 0 ? editableTierConfig : tierConfig).map(([key, t]) => {
                        const v = (t as { lifetime_limit?: number | null }).lifetime_limit
                        return (
                          <td key={key} className="text-center py-1.5 px-2">
                            {isSuperAdmin ? (
                              <input
                                type="text"
                                placeholder="—"
                                value={v == null ? '' : String(v)}
                                onChange={(e) => {
                                  const val = e.target.value.trim()
                                  setEditableTierConfig((prev) => ({ ...prev, [key]: { ...prev[key], lifetime_limit: val === '' ? null : parseInt(val, 10) || null } }))
                                }}
                                className="w-16 px-1 py-0.5 rounded bg-background border border-input text-center text-xs"
                              />
                            ) : (
                              v == null ? '—' : String(v)
                            )}
                          </td>
                        )
                      })}
                    </tr>
                    <tr className="border-b border-border/50">
                      <td className="py-1.5 pr-4">Max video (sec)</td>
                      {Object.entries(Object.keys(editableTierConfig).length > 0 ? editableTierConfig : tierConfig).map(([key, t]) => (
                        <td key={key} className="text-center py-1.5 px-2">
                          {isSuperAdmin ? (
                            <input
                              type="number"
                              min="0"
                              value={(t as { max_video_duration?: number }).max_video_duration ?? 30}
                              onChange={(e) => setEditableTierConfig((prev) => ({ ...prev, [key]: { ...prev[key], max_video_duration: parseInt(e.target.value, 10) || 30 } }))}
                              className="w-16 px-1 py-0.5 rounded bg-background border border-input text-center text-xs"
                            />
                          ) : (
                            (t as { max_video_duration?: number }).max_video_duration ?? '—'
                          )}
                        </td>
                      ))}
                    </tr>
                    {(() => {
                      const tiers = Object.keys(editableTierConfig).length > 0 ? editableTierConfig : tierConfig
                      const allFeatures = new Set<string>()
                      Object.values(tiers).forEach((t) => ((t as { features?: string[] }).features ?? []).forEach((f) => allFeatures.add(f)))
                      return Array.from(allFeatures).sort().map((feat) => (
                        <tr key={feat} className="border-b border-border/50">
                          <td className="py-1.5 pr-4">{feat}</td>
                          {Object.entries(tiers).map(([key, t]) => {
                            const has = ((t as { features?: string[] }).features ?? []).includes(feat)
                            return (
                              <td key={key} className="text-center py-1.5 px-2">
                                {isSuperAdmin ? (
                                  <input
                                    type="checkbox"
                                    checked={has}
                                    onChange={(e) => {
                                      const features = ((t as { features?: string[] }).features ?? [])
                                      const next = e.target.checked ? [...features, feat] : features.filter((f) => f !== feat)
                                      setEditableTierConfig((prev) => ({ ...prev, [key]: { ...prev[key], features: next } }))
                                    }}
                                    className="rounded border-border"
                                  />
                                ) : (
                                  <input type="checkbox" checked={has} readOnly className="rounded border-border" />
                                )}
                              </td>
                            )
                          })}
                        </tr>
                      ))
                    })()}
                  </tbody>
                </table>
              </div>
              {isSuperAdmin && Object.keys(editableTierConfig).length > 0 && (
                <button
                  type="button"
                  onClick={() => saveTierConfigMutation.mutate(editableTierConfig)}
                  disabled={saveTierConfigMutation.isPending}
                  className="mt-3 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
                >
                  {saveTierConfigMutation.isPending ? 'Saving…' : 'Save tier config'}
                </button>
              )}
            </div>
          </>
        )}
        </div>

      </AdminPageSection>

      <AdminPageSection title="Fargo" description="Manual CSV import only. External scraping (FairMatch / dashboard) is disabled. Obtain ratings via FargoRate LMS exports, the unofficial 'fargo' CLI tool, CSI lookup pages, or tournament lists, then import below.">
        <div className="space-y-6">
          <div>
          <h3 className="text-sm font-semibold mb-2">Update Fargo Rating (disabled)</h3>
          <p className="text-xs text-muted-foreground mb-3">
            Direct sync/scrape is disabled. Use CSV import below. Failed attempts are logged; see{' '}
            <a href="/settings/admin/system-messages" className="text-primary hover:underline">System & messages</a>.
          </p>
          <div className="flex flex-wrap items-center gap-3 mb-2">
            <span className="text-xs text-amber-600">Scraping disabled — button kept for compatibility. It will return a clear disabled message.</span>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => {
                setFargoMessage(null)
                setFargoResult(null)
                setFargoModalOpen(true)
                fargoMutation.mutate()
              }}
              disabled={fargoMutation.isPending}
              className="min-h-[44px] px-4 py-2.5 rounded-lg bg-muted text-muted-foreground font-medium hover:bg-muted/80 disabled:opacity-50 flex items-center gap-2"
            >
              {fargoMutation.isPending ? (
                <><span className="animate-spin">⟳</span> Checking…</>
              ) : fargoDone ? (
                'Done'
              ) : (
                'Try Sync (will show disabled)'
              )}
            </button>
            {fargoMessage && (
              <span className={`text-sm ${fargoMutation.isError ? 'text-amber-500' : 'text-muted-foreground'}`}>{fargoMessage}</span>
            )}
          </div>
          {fargoModalOpen && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => { if (!fargoMutation.isPending) setFargoModalOpen(false) }}>
              <div className="bg-card border border-border rounded-lg p-5 shadow-lg max-w-md w-full mx-4" onClick={(e) => e.stopPropagation()}>
                <h4 className="text-sm font-semibold mb-3">Fargo rating sync</h4>
                {fargoMutation.isPending ? (
                  <div className="flex flex-col gap-3">
                    <p className="text-sm text-muted-foreground">
                      External Fargo scraping is disabled. This will return a clear message directing you to use CSV import.
                    </p>
                    <div className="flex items-center gap-2 text-primary">
                      <span className="animate-spin">⟳</span>
                      <span className="text-sm font-medium">Contacting API…</span>
                    </div>
                  </div>
                ) : fargoResult ? (
                  <div className="space-y-3">
                    <div className="text-sm">
                      <p className="font-medium text-muted-foreground">Results</p>
                      <ul className="mt-2 space-y-1">
                        <li><strong>Ratings updated:</strong> {fargoResult.updated}</li>
                        <li><strong>Players processed:</strong> {fargoResult.players_processed}</li>
                        {(fargoResult.failed_count ?? 0) > 0 && (
                          <li className="text-amber-600"><strong>Failed:</strong> {fargoResult.failed_count} player(s)</li>
                        )}
                        {fargoResult.error && (
                          <li className="text-amber-600"><strong>Note:</strong> {fargoResult.error}</li>
                        )}
                        {fargoResult.failed_players && fargoResult.failed_players.length > 0 && (
                          <li className="text-xs text-muted-foreground mt-1">
                            {fargoResult.failed_players.slice(0, 10).join(', ')}
                            {(fargoResult.failed_count ?? 0) > 10 && ' …'}
                          </li>
                        )}
                      </ul>
                    </div>
                    <button
                      type="button"
                      onClick={() => setFargoModalOpen(false)}
                      className="w-full min-h-[40px] px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90"
                    >
                      Close
                    </button>
                  </div>
                ) : (
                  <div className="flex justify-end">
                    <button type="button" onClick={() => setFargoModalOpen(false)} className="px-4 py-2 rounded-lg bg-muted text-sm hover:bg-muted/80">Close</button>
                  </div>
                )}
              </div>
            </div>
          )}
          </div>

        <div>
          <h3 className="text-sm font-semibold mb-2">Import Fargo (CSV)</h3>
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <button
              type="button"
              onClick={() => {
                // Trigger export of players missing Fargo (opens download); user then pastes the list into the textarea below for import.
                rankingsApi.exportPlayersWithoutFargo().then((blob) => {
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = 'players_without_fargo.txt'
                  document.body.appendChild(a)
                  a.click()
                  a.remove()
                  URL.revokeObjectURL(url)
                  toast.success('Downloaded list of players missing Fargo. Paste lines into the box below and Import.')
                }).catch(() => toast.error('Could not export missing list'))
              }}
              disabled={!isSuperAdmin}
              className="min-h-[44px] px-4 py-2.5 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
            >
              📋 List players missing Fargo
            </button>
            <span className="text-xs text-muted-foreground">
              Downloads names of players without stored Fargo. Paste into the box (name,rating format) and use Import below. No scraping.
            </span>
          </div>
          <p className="text-xs text-muted-foreground mb-2">
            Paste CSV lines: one per player, <code className="bg-muted px-1 rounded">player_name,fargo_rating</code> (or name, rating, robustness). Use the button above to get candidates. Official sources: FargoRate LMS exports, fargo CLI (unofficial), or tournament-provided lists.
          </p>
          <select
            value={fargoImportSystem}
            onChange={(e) => setFargoImportSystem(e.target.value as 'WPBA' | 'WPA')}
            className="mb-2 rounded border border-border bg-background px-2 py-1.5 text-sm"
          >
            <option value="WPBA">WPBA</option>
            <option value="WPA">WPA</option>
          </select>
          <textarea
            value={fargoImportText}
            onChange={(e) => setFargoImportText(e.target.value)}
            placeholder={'Alice Smith,650\nBob Jones,620'}
            rows={5}
            className="w-full rounded border border-border bg-background px-3 py-2 text-sm font-mono mb-2"
          />
          <button
            type="button"
            onClick={() => fargoImportMutation.mutate()}
            disabled={fargoImportMutation.isPending || !fargoImportText.trim()}
            className="min-h-[44px] px-4 py-2.5 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 disabled:opacity-50"
          >
            {fargoImportMutation.isPending ? 'Importing...' : 'Import Fargo CSV'}
          </button>
        </div>
        </div>
      </AdminPageSection>

      {isSuperAdmin ? (
        <AdminPageSection
          title="Data quality"
          description="Conflicts and missing fields across ranking systems."
        >
            <p className="text-xs text-muted-foreground mb-3">
              Review conflicting player data and players with missing information.
            </p>

            {dataQualityData && (
              <>
                {/* Stats */}
                <div className="grid grid-cols-2 gap-2 mb-4">
                  <div className="bg-red-950/30 border border-red-500/30 rounded p-2">
                    <div className="text-xs text-muted-foreground">Conflicts</div>
                    <div className="text-xl font-bold text-red-400">{dataQualityData.stats.totalConflicts}</div>
                    <div className="text-[10px] text-muted-foreground">
                      {dataQualityData.stats.countryConflicts} country • {dataQualityData.stats.fargoConflicts} fargo
                    </div>
                  </div>
                  <div className="bg-amber-950/30 border border-amber-500/30 rounded p-2">
                    <div className="text-xs text-muted-foreground">Missing Data</div>
                    <div className="text-xl font-bold text-amber-400">{dataQualityData.stats.totalPlayersWithMissingData}</div>
                    <div className="text-[10px] text-muted-foreground">Players incomplete</div>
                  </div>
                </div>

                {/* Tabs */}
                <div className="flex gap-2 mb-3 border-b border-border">
                  <button
                    onClick={() => setDataQualityTab('conflicts')}
                    className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                      dataQualityTab === 'conflicts'
                        ? 'text-primary border-b-2 border-primary'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    Conflicts ({dataQualityData.conflicts.length})
                  </button>
                  <button
                    onClick={() => setDataQualityTab('missing')}
                    className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                      dataQualityTab === 'missing'
                        ? 'text-primary border-b-2 border-primary'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    Missing ({dataQualityData.missingData.length})
                  </button>
                </div>

                {/* Conflicts Tab */}
                {dataQualityTab === 'conflicts' && (
                  <div className="space-y-2 max-h-[400px] overflow-y-auto">
                    {dataQualityData.conflicts.length === 0 ? (
                      <p className="text-xs text-muted-foreground py-2">✅ No unresolved conflicts</p>
                    ) : (
                      dataQualityData.conflicts.map((conflict) => (
                        <div key={conflict.id} className="bg-card/50 border border-border rounded p-2 text-xs">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <div className="font-semibold truncate">{conflict.playerName}</div>
                              <div className="text-[10px] text-amber-400 mb-1">{conflict.conflictType}</div>
                              <div className="grid grid-cols-2 gap-2 text-[10px]">
                                <div>
                                  <span className="text-muted-foreground">{conflict.system1}:</span>
                                  <span className="ml-1 font-mono">{conflict.value1}</span>
                                </div>
                                <div>
                                  <span className="text-muted-foreground">{conflict.system2}:</span>
                                  <span className="ml-1 font-mono">{conflict.value2}</span>
                                </div>
                              </div>
                            </div>
                            {resolvingConflictId === conflict.id ? (
                              <div className="flex flex-col gap-1">
                                <input
                                  type="text"
                                  placeholder="Notes (optional)"
                                  value={resolutionNote}
                                  onChange={(e) => setResolutionNote(e.target.value)}
                                  className="px-2 py-1 bg-background border border-border rounded text-[10px] w-32"
                                />
                                <div className="flex gap-1">
                                  <button
                                    onClick={() => resolveConflictMutation.mutate({ conflictId: conflict.id, notes: resolutionNote })}
                                    className="px-2 py-1 bg-green-600 text-white rounded text-[10px] hover:bg-green-700"
                                  >
                                    ✓
                                  </button>
                                  <button
                                    onClick={() => {
                                      setResolvingConflictId(null)
                                      setResolutionNote('')
                                    }}
                                    className="px-2 py-1 bg-slate-700 text-white rounded text-[10px] hover:bg-slate-600"
                                  >
                                    ✕
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <button
                                onClick={() => setResolvingConflictId(conflict.id)}
                                className="px-2 py-1 bg-primary text-primary-foreground rounded text-[10px] hover:bg-primary/90 whitespace-nowrap"
                              >
                                Resolve
                              </button>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                )}

                {/* Missing Data Tab */}
                {dataQualityTab === 'missing' && (
                  <>
                    {/* Missing data list */}
                    <div className="space-y-2 max-h-[400px] overflow-y-auto">
                      {dataQualityData.missingData.length === 0 ? (
                        <p className="text-xs text-muted-foreground py-2">✅ No missing data</p>
                      ) : (
                        dataQualityData.missingData.slice(0, 20).map((player, idx) => (
                          <div key={idx} className="bg-card/50 border border-border rounded p-2 text-xs">
                            <div className="font-semibold mb-1">{player.playerName}</div>
                            <div className="space-y-0.5">
                              {Object.entries(player.systems).map(([system, fields]) => (
                                <div key={system} className="flex items-center gap-2 text-[10px]">
                                  <span className="text-muted-foreground w-32 truncate">{system}</span>
                                  <div className="flex gap-1">
                                    {(fields as string[]).map((field) => (
                                      <span
                                        key={field}
                                        className="px-1.5 py-0.5 bg-amber-500/20 text-amber-400 rounded"
                                      >
                                        {field}
                                      </span>
                                    ))}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))
                      )}
                      {dataQualityData.missingData.length > 20 && (
                        <p className="text-[10px] text-muted-foreground text-center py-1">
                          Showing first 20 of {dataQualityData.missingData.length} players
                        </p>
                      )}
                    </div>
                  </>
                )}
              </>
            )}
        </AdminPageSection>
      ) : null}

      <AdminPageSection
        title="Overview"
        description="High-level stats and login security. Click a metric to see detail."
      >
        <StatsSummary stats={[
          {
            label: 'Total Players',
            value: alfaStats?.total_players ?? 0,
            unit: 'players',
            icon: '👥',
            trend: 12.5,
            trendDirection: 'up' as const,
          },
          {
            label: 'Tournaments',
            value: tournamentStats?.total_tournaments ?? 0,
            unit: 'events',
            icon: '🏆',
            trend: 5.2,
            trendDirection: 'up' as const,
          },
          {
            label: 'Recent Matches',
            value: alfaStats?.predictions_today ?? 0,
            unit: 'matches',
            icon: '🎱',
            trend: -3.1,
            trendDirection: 'down' as const,
          },
          {
            label: 'System Status',
            value: 'Healthy',
            unit: 'status',
            icon: '✓',
            trend: 0,
            trendDirection: 'neutral' as const,
          },
          {
            label: 'Failed Logins (24h)',
            value: securityMetrics?.failed_attempts_24h ?? 0,
            unit: 'attempts',
            icon: '🔒',
            trend: 0,
            trendDirection: 'neutral' as const,
            onClick: handleFailedLoginsClick,
          },
          {
            label: 'Unique IPs (24h)',
            value: securityMetrics?.unique_ips_24h ?? 0,
            unit: 'IPs',
            icon: '🌐',
            trend: 0,
            trendDirection: 'neutral' as const,
            onClick: handleUniqueIPsClick,
          },
          {
            label: 'Locked Accounts',
            value: securityMetrics?.locked_accounts_count ?? 0,
            unit: 'accounts',
            icon: '⛔',
            trend: 0,
            trendDirection: 'neutral' as const,
            onClick: handleLockedAccountsClick,
          },
        ]} />
      </AdminPageSection>

      {canAdmin ? (
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <div className="px-6 pt-6 pb-2">
            <h2 className="text-lg font-semibold text-white">Login activity & IP addresses</h2>
            <p className="text-sm text-muted-foreground mt-1">
              Live list from the auth audit log (same source as the metrics above). Refreshes every 30s.
            </p>
          </div>
          <LoginAttemptsMonitor />
        </div>
      ) : null}

      <AdminPageSection
        title="Rating accuracy"
        description="Prediction accuracy vs tournament results."
      >
        <div className="flex justify-end mb-2">
          <button
            type="button"
            onClick={() => refetchAccuracy()}
            className="px-3 py-1 bg-primary text-primary-foreground rounded text-sm hover:bg-primary/90"
          >
            Refresh
          </button>
        </div>
        {accuracyStats ? (
          <div className="space-y-6">
            <div className="bg-card/50 border border-border rounded p-4">
              <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-blue-500" />
                Overall System Accuracy
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-400">
                    {accuracyStats.overall_accuracy?.system_accuracy_percentage?.toFixed(1) ?? 'N/A'}%
                  </div>
                  <div className="text-xs text-muted-foreground">System Accuracy</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-400">
                    {new Date(accuracyStats.overall_accuracy?.last_updated ?? '').toLocaleDateString()}
                  </div>
                  <div className="text-xs text-muted-foreground">Last Updated</div>
                </div>
                <div className="text-center">
                  <div className="text-lg font-semibold text-yellow-400">
                    {accuracyStats.overall_accuracy?.data_freshness ?? 'Unknown'}
                  </div>
                  <div className="text-xs text-muted-foreground">Data Freshness</div>
                </div>
                <div className="text-center">
                  <div className="text-lg font-semibold text-purple-400">Self-Calibrating</div>
                  <div className="text-xs text-muted-foreground">System Status</div>
                </div>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {['fargo', 'alfa', 'est'].map((ratingType) => {
                const typeData = accuracyStats.rating_type_breakdown?.[ratingType]
                const trendData = accuracyStats.recent_trends?.[ratingType]
                return (
                  <div key={ratingType} className="bg-card/50 border border-border rounded p-4">
                    <h4 className="text-md font-semibold text-white mb-2 capitalize">
                      {ratingType === 'fargo' ? 'Fargo' : ratingType === 'alfa' ? 'ALFA' : 'EST'} Ratings
                    </h4>
                    <div className="space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-muted-foreground">Accuracy:</span>
                        <span className={`font-semibold ${typeData?.accuracy_percentage >= 90 ? 'text-green-400' :
                          typeData?.accuracy_percentage >= 75 ? 'text-yellow-400' : 'text-red-400'}`}>
                          {typeData?.accuracy_percentage?.toFixed(1) ?? 'N/A'}%
                        </span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-muted-foreground">Predictions:</span>
                        <span className="font-semibold text-white">{typeData?.total_predictions ?? 0}</span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-muted-foreground">Avg Error:</span>
                        <span className="font-semibold text-orange-400">
                          {typeData?.mean_absolute_error?.toFixed(1) ?? 'N/A'}
                        </span>
                      </div>
                      {trendData && (
                        <div className="flex justify-between items-center pt-1 border-t border-border">
                          <span className="text-sm text-muted-foreground">Trend:</span>
                          <span className={`font-semibold ${
                            trendData.trend_direction === 'improving' ? 'text-green-400' :
                            trendData.trend_direction === 'declining' ? 'text-red-400' :
                            'text-yellow-400'
                          }`}>
                            {trendData.trend_direction === 'improving' ? '↗' :
                             trendData.trend_direction === 'declining' ? '↘' : '→'}
                            {Math.abs(trendData.trend).toFixed(1)}%
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="bg-gradient-to-r from-blue-500/10 to-green-500/10 border border-blue-500/20 rounded p-4">
              <h4 className="text-md font-semibold text-white mb-2 flex items-center gap-2">
                <Target className="w-5 h-5 text-blue-400" />
                FargoRate Independence Progress
              </h4>
              <div className="text-sm text-muted-foreground mb-3">
                System is learning to calculate ratings independently of FargoRate data through continuous accuracy comparison and self-calibration.
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center">
                <div>
                  <div className="text-xl font-bold text-green-400">
                    {((accuracyStats.overall_accuracy?.system_accuracy_percentage ?? 0) / 100 * 100).toFixed(0)}%
                  </div>
                  <div className="text-xs text-muted-foreground">Current Accuracy</div>
                </div>
                <div>
                  <div className="text-xl font-bold text-blue-400">
                    {(accuracyStats.rating_type_breakdown?.alfa?.accuracy_percentage ?? 0) > 75 ? 'High' :
                     (accuracyStats.rating_type_breakdown?.alfa?.accuracy_percentage ?? 0) > 60 ? 'Medium' : 'Learning'}
                  </div>
                  <div className="text-xs text-muted-foreground">AI Confidence</div>
                </div>
                <div>
                  <div className="text-xl font-bold text-purple-400">
                    {(accuracyStats.rating_type_breakdown?.est?.accuracy_percentage ?? 0) > 80 ? 'Stable' : 'Calibrating'}
                  </div>
                  <div className="text-xs text-muted-foreground">Live Rating Status</div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-8">
            <Target className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">Loading rating accuracy data...</p>
            <button
              type="button"
              onClick={() => refetchAccuracy()}
              className="mt-2 px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/90"
            >
              Retry
            </button>
          </div>
        )}
      </AdminPageSection>

      <AdminPageSection
        title="Self-calibration & independence"
        description="Fargo independence metrics and calibration actions."
      >
        <div className="flex justify-end mb-2">
          <button
            type="button"
            onClick={() => {
              void refetchIndependence()
              void refetchAccuracy()
            }}
            className="px-3 py-1 bg-primary text-primary-foreground rounded text-sm hover:bg-primary/90"
          >
            Refresh all
          </button>
        </div>
        {independenceStats ? (
          <div className="space-y-6">
            <div className="bg-gradient-to-r from-purple-500/10 to-blue-500/10 border border-purple-500/20 rounded p-4">
              <h3 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
                <Zap className="w-5 h-5 text-purple-400" />
                System Independence Progress
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div className="text-center">
                  <div className="text-3xl font-bold text-purple-400">
                    {(independenceStats.overall_independence * 100).toFixed(0)}%
                  </div>
                  <div className="text-sm text-muted-foreground">Current Independence</div>
                  <div className="w-full bg-slate-700 rounded-full h-2 mt-2">
                    <div
                      className="bg-purple-500 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${independenceStats.overall_independence * 100}%` }}
                    />
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-400">
                    {independenceStats.estimated_full_independence_date
                      ? new Date(independenceStats.estimated_full_independence_date).toLocaleDateString('en-US', {
                          year: 'numeric',
                          month: 'short',
                        })
                      : 'TBD'}
                  </div>
                  <div className="text-sm text-muted-foreground">Est. Full Independence</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-400">
                    {independenceStats.rating_type_independence
                      ? Object.keys(independenceStats.rating_type_independence).length
                      : 0}
                  </div>
                  <div className="text-sm text-muted-foreground">Rating Systems</div>
                </div>
              </div>
              <div className="text-sm text-muted-foreground">
                The system continuously learns from tournament results to improve rating accuracy, gradually reducing dependence on FargoRate data for validation.
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {independenceStats.rating_type_independence &&
                Object.entries(independenceStats.rating_type_independence).map(([ratingType, data]: [string, any]) => (
                  <div key={ratingType} className="bg-slate-700/30 p-4 rounded-lg">
                    <h4 className="text-md font-semibold text-white mb-2 capitalize">
                      {ratingType === 'fargo' ? 'Fargo' : ratingType === 'alfa' ? 'ALFA' : 'EST'} Independence
                    </h4>
                    <div className="space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-muted-foreground">Independence:</span>
                        <span
                          className={`font-semibold ${
                            data.independence_score > 0.8
                              ? 'text-green-400'
                              : data.independence_score > 0.6
                                ? 'text-yellow-400'
                                : 'text-red-400'
                          }`}
                        >
                          {(data.independence_score * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-muted-foreground">Accuracy:</span>
                        <span className="font-semibold text-blue-400">
                          {data.accuracy_percentage?.toFixed(1) ?? 'N/A'}%
                        </span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-muted-foreground">Confidence:</span>
                        <span className="font-semibold text-purple-400">
                          {(data.accuracy_contribution * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="w-full bg-slate-600 rounded-full h-1.5 mt-2">
                        <div
                          className={`h-1.5 rounded-full transition-all duration-300 ${
                            data.independence_score > 0.8
                              ? 'bg-green-500'
                              : data.independence_score > 0.6
                                ? 'bg-yellow-500'
                                : 'bg-red-500'
                          }`}
                          style={{ width: `${data.independence_score * 100}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
            </div>
            <div className="bg-slate-700/30 p-4 rounded-lg">
              <h4 className="text-md font-semibold text-white mb-3 flex items-center gap-2">
                <Brain className="w-5 h-5 text-purple-400" />
                Self-Calibration Actions
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => runFullCalibrationMutation.mutate()}
                  disabled={runFullCalibrationMutation.isPending}
                  className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 transition-colors flex items-center gap-2 disabled:opacity-50"
                >
                  <Brain className="w-4 h-4" />
                  {runFullCalibrationMutation.isPending ? 'Starting…' : 'Run Full Calibration'}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    // Apply recommendations for each rating type sequentially. The
                    // backend serializes runs anyway via per-job locks, so back-to-back
                    // POSTs from one click are safe; each one streams into its own log.
                    const ratingTypes: CalibrationRatingType[] = ['fargo', 'alfa', 'est']
                    ratingTypes.forEach((rt) => applyRecommendationsMutation.mutate(rt))
                  }}
                  disabled={applyRecommendationsMutation.isPending}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors flex items-center gap-2 disabled:opacity-50"
                >
                  <TrendingUp className="w-4 h-4" />
                  {applyRecommendationsMutation.isPending ? 'Applying…' : 'Apply AI Recommendations'}
                </button>
                <button
                  type="button"
                  onClick={() => compareEstFargoMutation.mutate()}
                  disabled={compareEstFargoMutation.isPending}
                  className="px-4 py-2 bg-emerald-700 text-white rounded hover:bg-emerald-600 transition-colors flex items-center gap-2 disabled:opacity-50"
                >
                  <TrendingUp className="w-4 h-4" />
                  {compareEstFargoMutation.isPending ? 'Comparing…' : 'Compare EST vs Fargo'}
                </button>
              </div>
              <div className="text-xs text-muted-foreground mt-3">
                Self-calibration adjusts rating algorithms from accuracy trends and tournament validation.
                Run <strong>Compare EST vs Fargo</strong> first so accuracy tables have samples (Phase 4).
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-8">
            <Brain className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">Loading self-calibration data...</p>
            <button
              type="button"
              onClick={() => refetchIndependence()}
              className="mt-2 px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-primary/90"
            >
              Retry
            </button>
          </div>
        )}
      </AdminPageSection>

      <MetricsDetailModal
        isOpen={metricsModalOpen}
        onClose={() => setMetricsModalOpen(false)}
        metricName={selectedMetric ?? ''}
        icon={
          selectedMetric?.includes('Failed')
            ? '🔒'
            : selectedMetric?.includes('IPs')
              ? '🌐'
              : selectedMetric?.includes('Locked')
                ? '⛔'
                : '📊'
        }
        loading={false}
        error={undefined}
        details={metricsModalDetails}
      />
    </div>
  )
}

