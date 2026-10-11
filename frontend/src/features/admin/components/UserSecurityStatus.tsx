import { useState } from 'react'
import { AlertCircle, Lock, Unlock } from 'lucide-react'

interface SecurityStatusData {
  username: string
  failed_attempts: number
  is_locked: boolean
  locked_until: string | null
  minutes_remaining: number | null
  recent_ips: string[]
  recent_attempts: Array<{
    ip_address: string
    success: boolean
    timestamp: string
    failure_reason?: string
  }>
}

interface Props {
  username: string
}

export function UserSecurityStatus({ username }: Props) {
  const [data, setData] = useState<SecurityStatusData | null>(null)
  const [_loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [unlocking, setUnlocking] = useState(false)

  const fetchSecurityStatus = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`/api/admin/users/${username}/security`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })

      if (!response.ok) {
        throw new Error(`Failed to fetch: ${response.statusText}`)
      }

      const result: SecurityStatusData = await response.json()
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const handleUnlock = async () => {
    setUnlocking(true)
    setError(null)
    try {
      const response = await fetch(`/api/admin/users/${username}/unlock`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        throw new Error(`Failed to unlock: ${response.statusText}`)
      }

      // Refresh the status
      await fetchSecurityStatus()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setUnlocking(false)
    }
  }

  if (!data) {
    return (
      <div className="space-y-2" onClick={fetchSecurityStatus}>
        <button className="bg-sky-600 hover:bg-sky-700 px-3 py-2 rounded text-sm text-white">
          Load Security Status
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-4 p-4 bg-slate-800 rounded border border-slate-600">
      <div className="flex justify-between items-start">
        <div>
          <h4 className="font-semibold text-white mb-2">{username}</h4>
        </div>
        {data.is_locked && (
          <button
            onClick={handleUnlock}
            disabled={unlocking}
            className="flex items-center gap-2 bg-amber-600 hover:bg-amber-700 px-3 py-2 rounded text-sm text-white disabled:opacity-50"
          >
            <Unlock className="h-4 w-4" />
            Unlock
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-900/30 border border-red-700 text-red-200 px-3 py-2 rounded text-sm flex gap-2">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Status Summary */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-slate-700 p-3 rounded">
          <div className="text-xs text-slate-400 mb-1">Failed Attempts</div>
          <div className={`text-2xl font-bold ${data.failed_attempts > 0 ? 'text-red-400' : 'text-green-400'}`}>
            {data.failed_attempts}
          </div>
        </div>

        <div className={`p-3 rounded ${
          data.is_locked
            ? 'bg-red-900/20 border border-red-700/30'
            : 'bg-green-900/20 border border-green-700/30'
        }`}>
          <div className={`text-xs mb-1 ${data.is_locked ? 'text-red-300' : 'text-green-300'}`}>
            Account Status
          </div>
          <div className={`font-bold flex items-center gap-1 ${data.is_locked ? 'text-red-400' : 'text-green-400'}`}>
            {data.is_locked ? (
              <>
                <Lock className="h-4 w-4" /> LOCKED
              </>
            ) : (
              '✓ ACTIVE'
            )}
          </div>
        </div>
      </div>

      {data.is_locked && data.minutes_remaining !== null && (
        <div className="bg-amber-900/20 border border-amber-700/30 p-3 rounded text-sm text-amber-300">
          Account unlocks in {Math.max(0, data.minutes_remaining)} minute{data.minutes_remaining !== 1 ? 's' : ''}
        </div>
      )}

      {/* Recent IPs */}
      {data.recent_ips.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-slate-300 mb-2">Recent IP Addresses</div>
          <div className="space-y-1">
            {data.recent_ips.map((ip, idx) => (
              <div key={idx} className="bg-slate-700 px-3 py-2 rounded text-sm font-mono text-amber-300">
                {ip}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Attempts */}
      {data.recent_attempts.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-slate-300 mb-2">Recent Attempts (Last 24h)</div>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {data.recent_attempts.map((attempt, idx) => (
              <div key={idx} className="bg-slate-700 px-3 py-2 rounded text-xs">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono text-amber-300">{attempt.ip_address}</span>
                  <span className={`px-2 py-1 rounded ${
                    attempt.success
                      ? 'bg-green-900/30 text-green-300'
                      : 'bg-red-900/30 text-red-300'
                  }`}>
                    {attempt.success ? '✓ Success' : '✗ Failed'}
                  </span>
                </div>
                <div className="text-slate-400">
                  {new Date(attempt.timestamp).toLocaleString()}
                </div>
                {attempt.failure_reason && (
                  <div className="text-slate-400 mt-1">{attempt.failure_reason}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
