import { useState, useEffect } from 'react'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { apiClient } from '@/api/client'

interface LoginAttempt {
  id: number
  username: string
  ip_address: string
  success: boolean
  failure_reason: string | null
  timestamp: string
}

interface LoginAttemptsData {
  total: number
  attempts: LoginAttempt[]
}

export function LoginAttemptsMonitor() {
  const [attempts, setAttempts] = useState<LoginAttempt[]>([])
  const [loading, setLoading] = useState(false)
  const [hours, setHours] = useState(24)
  const [failedOnly, setFailedOnly] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchAttempts = async () => {
    setLoading(true)
    setError(null)
    try {
      const { data } = await apiClient.get<LoginAttemptsData>('/admin/login-attempts', {
        params: {
          hours,
          failed_only: failedOnly,
          limit: 100,
        },
      })
      setAttempts(data.attempts)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAttempts()
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchAttempts, 30000)
    return () => clearInterval(interval)
  }, [hours, failedOnly])

  const failedCount = attempts.filter(a => !a.success).length
  const successCount = attempts.filter(a => a.success).length
  const uniqueIps = new Set(attempts.map(a => a.ip_address)).size

  return (
    <div className="space-y-6 p-6 bg-slate-900 text-slate-pool_opt_in rounded-lg border border-slate-700">
      <div>
        <h3 className="text-lg font-semibold text-white mb-4">🔐 Login Attempt Monitoring</h3>
        
        {error && (
          <div className="bg-red-900/30 border border-red-700 text-red-200 px-4 py-3 rounded mb-4 flex gap-2">
            <AlertCircle className="h-5 w-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Controls */}
        <div className="flex flex-wrap gap-4 mb-4">
          <div className="flex items-center gap-2">
            <label className="text-sm text-slate-400">Last:</label>
            <select
              value={hours}
              onChange={(e) => setHours(Number(e.target.value))}
              className="bg-slate-800 text-white px-3 py-2 rounded border border-slate-600 text-sm"
            >
              <option value={1}>1 hour</option>
              <option value={6}>6 hours</option>
              <option value={24}>24 hours</option>
              <option value={48}>48 hours</option>
              <option value={168}>7 days</option>
            </select>
          </div>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={failedOnly}
              onChange={(e) => setFailedOnly(e.target.checked)}
              className="rounded border-slate-600"
            />
            <span className="text-slate-400">Failed only</span>
          </label>

          <button
            onClick={fetchAttempts}
            disabled={loading}
            className="flex items-center gap-2 bg-sky-600 hover:bg-sky-700 px-3 py-2 rounded text-sm text-white disabled:opacity-50"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <div className="bg-slate-800 p-3 rounded border border-slate-600">
            <div className="text-xs text-slate-400">Total Attempts</div>
            <div className="text-2xl font-bold text-white">{attempts.length}</div>
          </div>
          <div className="bg-green-900/20 p-3 rounded border border-green-700/30">
            <div className="text-xs text-green-300">Successful</div>
            <div className="text-2xl font-bold text-green-400">{successCount}</div>
          </div>
          <div className="bg-red-900/20 p-3 rounded border border-red-700/30">
            <div className="text-xs text-red-300">Failed</div>
            <div className="text-2xl font-bold text-red-400">{failedCount}</div>
          </div>
          <div className="bg-amber-900/20 p-3 rounded border border-amber-700/30">
            <div className="text-xs text-amber-300">Unique IPs</div>
            <div className="text-2xl font-bold text-amber-400">{uniqueIps}</div>
          </div>
        </div>

        {/* Attempts Table */}
        {loading ? (
          <div className="text-center py-8 text-slate-400">Loading...</div>
        ) : attempts.length === 0 ? (
          <div className="text-center py-8 text-slate-400">No login attempts</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-600">
                  <th className="text-left py-3 px-4 text-slate-300 font-semibold">Username</th>
                  <th className="text-left py-3 px-4 text-slate-300 font-semibold">IP Address</th>
                  <th className="text-left py-3 px-4 text-slate-300 font-semibold">Status</th>
                  <th className="text-left py-3 px-4 text-slate-300 font-semibold">Reason</th>
                  <th className="text-left py-3 px-4 text-slate-300 font-semibold">Time</th>
                </tr>
              </thead>
              <tbody>
                {attempts.map((attempt) => (
                  <tr key={attempt.id} className="border-b border-slate-700 hover:bg-slate-800">
                    <td className="py-3 px-4 font-mono text-blue-300">{attempt.username}</td>
                    <td className="py-3 px-4 font-mono text-amber-300 text-xs break-all">{attempt.ip_address}</td>
                    <td className="py-3 px-4">
                      <span className={`inline-block px-2 py-1 rounded text-xs font-semibold ${
                        attempt.success
                          ? 'bg-green-900/30 text-green-400 border border-green-700/30'
                          : 'bg-red-900/30 text-red-400 border border-red-700/30'
                      }`}>
                        {attempt.success ? '✓ Success' : '✗ Failed'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-400 text-xs">{attempt.failure_reason || '—'}</td>
                    <td className="py-3 px-4 text-slate-400 text-xs">
                      {new Date(attempt.timestamp).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
