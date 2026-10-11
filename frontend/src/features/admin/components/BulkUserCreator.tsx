import { useState } from 'react'
import { AlertCircle, Download, Loader } from 'lucide-react'

interface UserCreationResult {
  username: string
  password: string
  name: string
  fargo_rating: number | null
  state: string | null
  fargo_id: number | null
}

interface BulkCreateResponse {
  created_count: number
  error_count: number
  users: UserCreationResult[]
  errors: Array<{ player: any; error: string }>
  csv_data: string
}

export function BulkUserCreator() {
  const [csvInput, setCsvInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<BulkCreateResponse | null>(null)

  const handleCreateUsers = async () => {
    if (!csvInput.trim()) {
      setError('Please paste CSV data first')
      return
    }

    setLoading(true)
    setError(null)

    try {
      // Parse CSV input
      const lines = csvInput.trim().split('\n')
      const players = lines.map((line) => {
        const [name, fargo_rating, state, fargo_id] = line.split(',').map(v => v.trim())
        return {
          name,
          fargo_rating: fargo_rating ? parseInt(fargo_rating) : null,
          state: state || null,
          fargo_id: fargo_id ? parseInt(fargo_id) : null,
        }
      })

      const response = await fetch('/api/admin/users/bulk-create', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ players }),
      })

      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || `Failed to create users: ${response.statusText}`)
      }

      const data: BulkCreateResponse = await response.json()
      setResult(data)
      setCsvInput('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const downloadCsv = () => {
    if (!result?.csv_data) return

    const blob = new Blob([result.csv_data], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `users_${new Date().toISOString().split('T')[0]}.csv`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  }

  const resetForm = () => {
    setResult(null)
    setCsvInput('')
    setError(null)
  }

  return (
    <div className="space-y-6 p-6 bg-slate-900 text-slate-pool_opt_in rounded-lg border border-slate-700">
      <div>
        <h3 className="text-lg font-semibold text-white mb-2">📥 Bulk User Creation</h3>
        <p className="text-sm text-slate-400 mb-4">
          Import players from Fargo and generate unique usernames with secure passwords
        </p>

        {error && (
          <div className="bg-red-900/30 border border-red-700 text-red-200 px-4 py-3 rounded mb-4 flex gap-2">
            <AlertCircle className="h-5 w-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!result ? (
          <div className="space-y-4">
            {/* Input Instructions */}
            <div className="bg-slate-800 p-4 rounded border border-slate-600 text-sm text-slate-300">
              <p className="font-semibold text-slate-200 mb-2">CSV Format (name, fargo_rating, state, fargo_id):</p>
              <div className="bg-slate-900 p-2 rounded font-mono text-xs mb-2 overflow-x-auto">
                John Smith,800,CA,12345<br />
                Jane Doe,750,NY,12346<br />
                Bob Johnson,900,TX,12347
              </div>
              <p className="text-xs text-slate-400">One player per line. Fargo rating, state, and ID are optional.</p>
            </div>

            {/* Textarea */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Paste Player Data</label>
              <textarea
                value={csvInput}
                onChange={(e) => setCsvInput(e.target.value)}
                placeholder="Name, Rating, State, FargoID"
                className="w-full h-48 bg-slate-800 text-white px-4 py-3 rounded border border-slate-600 focus:border-sky-500 focus:outline-none font-mono text-sm"
              />
            </div>

            {/* Button */}
            <button
              onClick={handleCreateUsers}
              disabled={loading || !csvInput.trim()}
              className="w-full flex items-center justify-center gap-2 bg-sky-600 hover:bg-sky-700 disabled:bg-slate-600 px-4 py-3 rounded text-white font-semibold disabled:opacity-50"
            >
              {loading && <Loader className="h-5 w-5 animate-spin" />}
              {loading ? 'Creating Users...' : 'Create Users'}
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Summary */}
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div className="bg-green-900/20 border border-green-700/30 p-4 rounded">
                <div className="text-xs text-green-300 mb-1">Created</div>
                <div className="text-3xl font-bold text-green-400">{result.created_count}</div>
              </div>
              {result.error_count > 0 && (
                <div className="bg-red-900/20 border border-red-700/30 p-4 rounded">
                  <div className="text-xs text-red-300 mb-1">Errors</div>
                  <div className="text-3xl font-bold text-red-400">{result.error_count}</div>
                </div>
              )}
            </div>

            {/* Users Table */}
            {result.users.length > 0 && (
              <div className="mb-4">
                <h4 className="font-semibold text-slate-200 mb-2 text-sm">Created Users (Username • Password)</h4>
                <div className="bg-slate-800 rounded border border-slate-600 overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-slate-600">
                        <th className="text-left px-3 py-2 text-slate-300">Username</th>
                        <th className="text-left px-3 py-2 text-slate-300">Password</th>
                        <th className="text-left px-3 py-2 text-slate-300">Name</th>
                        <th className="text-left px-3 py-2 text-slate-300">Rating</th>
                        <th className="text-left px-3 py-2 text-slate-300">State</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.users.map((user, idx) => (
                        <tr key={idx} className="border-b border-slate-700 hover:bg-slate-700/50">
                          <td className="px-3 py-2 font-mono text-blue-300">{user.username}</td>
                          <td className="px-3 py-2 font-mono text-amber-300">{user.password}</td>
                          <td className="px-3 py-2 text-slate-300">{user.name}</td>
                          <td className="px-3 py-2 text-slate-400">{user.fargo_rating || '—'}</td>
                          <td className="px-3 py-2 text-slate-400">{user.state || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Errors */}
            {result.errors.length > 0 && (
              <div className="bg-red-900/20 border border-red-700/30 p-4 rounded">
                <h4 className="font-semibold text-red-300 mb-2 text-sm">Creation Errors</h4>
                <div className="space-y-2 text-xs text-red-200">
                  {result.errors.map((err, idx) => (
                    <div key={idx}>
                      <strong>{err.player.name}:</strong> {err.error}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* CSV Download */}
            <div className="bg-green-900/20 border border-green-700/30 p-4 rounded">
              <p className="text-xs text-green-300 mb-3">
                ✓ Ready to export! Download the CSV file and distribute to WPA/WPBA presidents.
              </p>
              <button
                onClick={downloadCsv}
                className="flex items-center justify-center gap-2 bg-green-600 hover:bg-green-700 w-full px-4 py-2 rounded text-white font-semibold"
              >
                <Download className="h-4 w-4" />
                Download CSV ({result.created_count} users)
              </button>
            </div>

            {/* Action Buttons */}
            <button
              onClick={resetForm}
              className="w-full bg-slate-700 hover:bg-slate-600 px-4 py-2 rounded text-slate-pool_opt_in text-sm"
            >
              Import Another Batch
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
