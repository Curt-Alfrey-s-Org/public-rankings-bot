/**
 * Profile settings - user details, country, state, home pool room.
 * Avatar is admin-only (Settings > Admin > Appearance).
 */

import { useState, useEffect } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { usersApi } from '@/api/users'
import { toast } from '@/lib/toast'

export function ProfileSettings() {
  const { user } = useAuth()
  const [country, setCountry] = useState('')
  const [state, setState] = useState('')
  const [homePoolRoom, setHomePoolRoom] = useState('')
  const [profileDirty, setProfileDirty] = useState(false)
  const [profileLoading, setProfileLoading] = useState(true)

  useEffect(() => {
    usersApi.getProfile()
      .then((p) => {
        setCountry(p.country ?? '')
        setState(p.state ?? '')
        setHomePoolRoom(p.home_pool_room ?? '')
      })
      .catch(() => {})
      .finally(() => setProfileLoading(false))
  }, [])

  const handleCountryChange = (v: string) => { setCountry(v); setProfileDirty(true) }
  const handleStateChange = (v: string) => { setState(v); setProfileDirty(true) }
  const handleHomePoolRoomChange = (v: string) => { setHomePoolRoom(v); setProfileDirty(true) }
  const handleSaveProfile = () => {
    usersApi.updateProfile({ country: country.trim() || undefined, state: state.trim() || undefined, home_pool_room: homePoolRoom.trim() || undefined })
      .then(() => {
        setProfileDirty(false)
        toast.success('Profile updated')
      })
      .catch(() => toast.error('Failed to update profile'))
  }

  const role = user && typeof user === 'object' && 'role' in user ? (user as { role: string }).role : 'User'
  const username = user && typeof user === 'object' && 'user' in user ? (user as { user: string }).user : '—'

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/50 p-4" title="Your account details and profile. Role determines which features you can access.">
      <h3 className="text-lg font-semibold text-white mb-4">Profile</h3>

      {/* User details */}
      <div className="space-y-3 mb-6">
        <div>
          <label className="text-xs font-medium text-slate-500 uppercase tracking-wider">Username</label>
          <p className="text-slate-200 mt-0.5">{username}</p>
        </div>
        <div>
          <label className="text-xs font-medium text-slate-500 uppercase tracking-wider">Role</label>
          <p className="text-slate-200 mt-0.5 capitalize">{role}</p>
        </div>
        {!profileLoading && (
          <>
            <div>
              <label className="text-xs font-medium text-slate-500 uppercase tracking-wider">Country</label>
              <input
                type="text"
                value={country}
                onChange={(e) => handleCountryChange(e.target.value)}
                placeholder="e.g. USA"
                className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500 uppercase tracking-wider">State / Region</label>
              <input
                type="text"
                value={state}
                onChange={(e) => handleStateChange(e.target.value)}
                placeholder="e.g. California"
                className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500 uppercase tracking-wider">Home pool room</label>
              <input
                type="text"
                value={homePoolRoom}
                onChange={(e) => handleHomePoolRoomChange(e.target.value)}
                placeholder="e.g. Billiards Cafe"
                className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
            {profileDirty && (
              <button
                type="button"
                onClick={handleSaveProfile}
                className="px-3 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90"
              >
                Save profile
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )
}
