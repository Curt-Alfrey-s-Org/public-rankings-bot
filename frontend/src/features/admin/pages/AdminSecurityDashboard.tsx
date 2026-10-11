import { useState } from 'react'
import { Lock, Users, Activity } from 'lucide-react'
import { LoginAttemptsMonitor } from '../components/LoginAttemptsMonitor'
import { BulkUserCreator } from '../components/BulkUserCreator'
import { UserSecurityStatus } from '../components/UserSecurityStatus'

export function AdminSecurityDashboard() {
  const [activeTab, setActiveTab] = useState<'bulk' | 'monitor' | 'user-status'>('bulk')
  const [selectedUsername, setSelectedUsername] = useState('')

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 to-slate-900 text-slate-pool_opt_in p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-white mb-2 flex items-center gap-3">
            <Lock className="h-8 w-8 text-sky-500" />
            Admin Security Dashboard
          </h1>
          <p className="text-slate-400">Manage users, monitor login attempts, and enforce security policies</p>
        </div>

        {/* Tabs */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <button
            onClick={() => setActiveTab('bulk')}
            className={`p-4 rounded-lg border-2 transition ${
              activeTab === 'bulk'
                ? 'border-sky-500 bg-sky-900/20'
                : 'border-slate-600 bg-slate-800/50 hover:border-slate-500'
            }`}
          >
            <Users className="h-6 w-6 mb-2 text-sky-400" />
            <div className="font-semibold">Bulk User Import</div>
            <div className="text-xs text-slate-400">Create users from Fargo</div>
          </button>

          <button
            onClick={() => setActiveTab('monitor')}
            className={`p-4 rounded-lg border-2 transition ${
              activeTab === 'monitor'
                ? 'border-sky-500 bg-sky-900/20'
                : 'border-slate-600 bg-slate-800/50 hover:border-slate-500'
            }`}
          >
            <Activity className="h-6 w-6 mb-2 text-amber-400" />
            <div className="font-semibold">Login Monitoring</div>
            <div className="text-xs text-slate-400">View failed attempts</div>
          </button>

          <button
            onClick={() => setActiveTab('user-status')}
            className={`p-4 rounded-lg border-2 transition ${
              activeTab === 'user-status'
                ? 'border-sky-500 bg-sky-900/20'
                : 'border-slate-600 bg-slate-800/50 hover:border-slate-500'
            }`}
          >
            <Lock className="h-6 w-6 mb-2 text-red-400" />
            <div className="font-semibold">User Security</div>
            <div className="text-xs text-slate-400">Check locks & unlock</div>
          </button>
        </div>

        {/* Content Area */}
        <div className="bg-slate-800/30 rounded-lg border border-slate-700 min-h-96">
          {activeTab === 'bulk' && (
            <BulkUserCreator />
          )}

          {activeTab === 'monitor' && (
            <LoginAttemptsMonitor />
          )}

          {activeTab === 'user-status' && (
            <div className="p-6">
              <h3 className="text-lg font-semibold text-white mb-4">🔒 User Security Status</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Search User by Username
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={selectedUsername}
                      onChange={(e) => setSelectedUsername(e.target.value.toLowerCase())}
                      placeholder="Enter username..."
                      className="flex-1 bg-slate-900 text-white px-4 py-2 rounded border border-slate-600 focus:border-sky-500 focus:outline-none"
                    />
                    <button
                      disabled={!selectedUsername.trim()}
                      className="bg-sky-600 hover:bg-sky-700 disabled:bg-slate-600 px-4 py-2 rounded text-white font-semibold disabled:opacity-50"
                    >
                      Load
                    </button>
                  </div>
                </div>

                {selectedUsername.trim() && (
                  <UserSecurityStatus username={selectedUsername.trim()} />
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer Info */}
        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-blue-900/20 border border-blue-700/30 p-4 rounded-lg">
            <h4 className="font-semibold text-blue-300 mb-2">💡 Bulk Import</h4>
            <p className="text-sm text-blue-200">
              Paste player data (name, rating, state, ID) to create accounts with auto-generated usernames and secure passwords. Export CSV for distribution.
            </p>
          </div>

          <div className="bg-amber-900/20 border border-amber-700/30 p-4 rounded-lg">
            <h4 className="font-semibold text-amber-300 mb-2">📊 Monitor</h4>
            <p className="text-sm text-amber-200">
              Real-time login attempt tracking with IP addresses. Filter by time range and success/failure status. Auto-refreshes every 30 seconds.
            </p>
          </div>

          <div className="bg-red-900/20 border border-red-700/30 p-4 rounded-lg">
            <h4 className="font-semibold text-red-300 mb-2">🔐 Security</h4>
            <p className="text-sm text-red-200">
              Account lockout after 5 failed attempts (30 min). View recent IPs, unlock accounts, and see attempt history per user.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
