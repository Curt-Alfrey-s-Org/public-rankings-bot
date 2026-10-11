import { useState, useEffect } from 'react'
import { AlertCircle, Check } from 'lucide-react'

interface UserProfile {
  username: string
  nickname: string | null
  email: string | null
  role: string
}

export function ProfilePage() {
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const [nickname, setNickname] = useState('')
  const [email, setEmail] = useState('')
  const [savingNickname, setSavingNickname] = useState(false)
  const [savingEmail, setSavingEmail] = useState(false)

  useEffect(() => {
    fetchProfile()
  }, [])

  const fetchProfile = async () => {
    try {
      const response = await fetch('/api/me', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
      })

      if (!response.ok) {
        throw new Error('Failed to fetch profile')
      }

      const data: UserProfile = await response.json()
      setProfile(data)
      setNickname(data.nickname || '')
      setEmail(data.email || '')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const saveNickname = async () => {
    if (!nickname.trim()) {
      setError('Nickname cannot be empty')
      return
    }

    setSavingNickname(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await fetch('/api/profile/nickname', {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ nickname: nickname.trim() }),
      })

      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to update nickname')
      }

      await fetchProfile()
      setSuccess('Nickname updated successfully!')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setSavingNickname(false)
    }
  }

  const saveEmail = async () => {
    if (!email.trim()) {
      setError('Email cannot be empty')
      return
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError('Please enter a valid email address')
      return
    }

    setSavingEmail(true)
    setError(null)
    setSuccess(null)

    try {
      const response = await fetch('/api/profile/email', {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email: email.trim() }),
      })

      if (!response.ok) {
        const err = await response.json()
        throw new Error(err.detail || 'Failed to update email')
      }

      await fetchProfile()
      setSuccess('Email updated successfully!')
      setTimeout(() => setSuccess(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setSavingEmail(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-screen text-slate-400">
        <div>Loading profile...</div>
      </div>
    )
  }

  if (!profile) {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <div className="bg-red-900/30 border border-red-700 text-red-200 px-4 py-3 rounded flex gap-2">
          <AlertCircle className="h-5 w-5 flex-shrink-0" />
          <span>Failed to load profile</span>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h1 className="text-3xl font-bold text-white mb-8">User Profile</h1>

      {error && (
        <div className="bg-red-900/30 border border-red-700 text-red-200 px-4 py-3 rounded mb-6 flex gap-2">
          <AlertCircle className="h-5 w-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="bg-green-900/30 border border-green-700 text-green-200 px-4 py-3 rounded mb-6 flex gap-2">
          <Check className="h-5 w-5 flex-shrink-0" />
          <span>{success}</span>
        </div>
      )}

      {/* Username Section */}
      <div className="bg-slate-800 rounded-lg p-6 mb-6 border border-slate-700">
        <h2 className="text-lg font-semibold text-white mb-4">Account Information</h2>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Username</label>
            <div className="bg-slate-900 text-slate-300 px-4 py-3 rounded border border-slate-600 font-mono">
              {profile.username}
            </div>
            <p className="text-xs text-slate-400 mt-1">Username cannot be changed</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Role</label>
            <div className="bg-slate-900 text-slate-300 px-4 py-3 rounded border border-slate-600">
              <span className={`inline-block px-3 py-1 rounded text-sm font-semibold ${
                profile.role === 'super_admin'
                  ? 'bg-red-900/30 text-red-300 border border-red-700/30'
                  : profile.role === 'admin'
                  ? 'bg-amber-900/30 text-amber-300 border border-amber-700/30'
                  : 'bg-slate-700 text-slate-300'
              }`}>
                {profile.role}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Profile Customization */}
      <div className="bg-slate-800 rounded-lg p-6 mb-6 border border-slate-700">
        <h2 className="text-lg font-semibold text-white mb-4">Profile Customization</h2>

        <div className="space-y-4">
          {/* Nickname */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Display Name (Nickname)
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={nickname}
                onChange={(e) => setNickname(e.target.value)}
                placeholder="Leave empty to use your username"
                className="flex-1 bg-slate-900 text-white px-4 py-2 rounded border border-slate-600 focus:border-sky-500 focus:outline-none"
              />
              <button
                onClick={saveNickname}
                disabled={savingNickname || nickname === profile.nickname}
                className="bg-sky-600 hover:bg-sky-700 disabled:bg-slate-600 px-4 py-2 rounded text-white font-semibold disabled:opacity-50"
              >
                {savingNickname ? '...' : 'Save'}
              </button>
            </div>
            <p className="text-xs text-slate-400 mt-2">
              This is how other players will see you in the rankings
            </p>
            {profile.nickname && (
              <p className="text-xs text-sky-300 mt-1">
                Currently: <strong>{profile.nickname}</strong>
              </p>
            )}
          </div>

          {/* Email */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Email Address
            </label>
            <div className="flex gap-2">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your.email@example.com"
                className="flex-1 bg-slate-900 text-white px-4 py-2 rounded border border-slate-600 focus:border-sky-500 focus:outline-none"
              />
              <button
                onClick={saveEmail}
                disabled={savingEmail || email === profile.email}
                className="bg-sky-600 hover:bg-sky-700 disabled:bg-slate-600 px-4 py-2 rounded text-white font-semibold disabled:opacity-50"
              >
                {savingEmail ? '...' : 'Save'}
              </button>
            </div>
            <p className="text-xs text-slate-400 mt-2">
              Required for password reset and account recovery
            </p>
            {profile.email ? (
              <p className="text-xs text-green-300 mt-1 flex items-center gap-1">
                <Check className="h-3 w-3" /> {profile.email}
              </p>
            ) : (
              <p className="text-xs text-amber-300 mt-1 flex items-center gap-1">
                <AlertCircle className="h-3 w-3" /> Email not set - some features may be unavailable
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Security Section */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <h2 className="text-lg font-semibold text-white mb-4">Security</h2>

        <div className="space-y-3">
          <button className="w-full bg-amber-600 hover:bg-amber-700 px-4 py-3 rounded text-white text-sm font-semibold">
            Change Password
          </button>
          <p className="text-xs text-slate-400">
            Email address must be set before you can reset your password
          </p>
        </div>
      </div>
    </div>
  )
}
