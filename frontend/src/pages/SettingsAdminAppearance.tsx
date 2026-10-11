/**
 * Settings > Admin > Appearance: avatar, background, splash; default for users without access;
 * edit player avatars. Single admin appearance page.
 */

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi, type DefaultAppearance } from '@/api/admin'
import { tournamentsApi, type Player } from '@/api/tournaments'
import { settingsApi, type Settings } from '@/api/settings'
import SettingsSection from '@/components/SettingsSection'
import { toast } from '@/lib/toast'

export default function SettingsAdminAppearancePage() {
  const queryClient = useQueryClient()
  const [defaultAvatar, setDefaultAvatar] = useState('')
  const [defaultBackground, setDefaultBackground] = useState('')

  const { data: settings } = useQuery<Settings>({
    queryKey: ['settings'],
    queryFn: settingsApi.getSettings,
  })

  const { data: defaultAppearance, isLoading: loadingDefault } = useQuery({
    queryKey: ['admin', 'appearance', 'default'],
    queryFn: adminApi.getDefaultAppearance,
  })

  useEffect(() => {
    if (defaultAppearance) {
      setDefaultAvatar(defaultAppearance.default_avatar_url ?? '')
      setDefaultBackground(defaultAppearance.default_background_url ?? '')
    }
  }, [defaultAppearance])

  const updateDefaultMutation = useMutation({
    mutationFn: (body: Partial<DefaultAppearance>) => adminApi.updateDefaultAppearance(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'appearance', 'default'] })
      toast.success('Default appearance saved.')
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed to save'),
  })

  const handleSaveDefault = () => {
    updateDefaultMutation.mutate({
      default_avatar_url: defaultAvatar.trim(),
      default_background_url: defaultBackground.trim(),
    })
  }

  const { data: players = [], isLoading: loadingPlayers } = useQuery({
    queryKey: ['tournaments', 'players'],
    queryFn: () => tournamentsApi.getPlayers(false),
  })

  return (
    <div className="p-6 max-w-4xl space-y-8">
      <header>
        <h1 className="text-2xl font-bold">Admin — Appearance</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Avatar, background, splash; default for users without access; edit player avatars.
        </p>
      </header>

      {/* Your appearance (avatar, background, splash) */}
      {settings && (
        <section className="border border-border rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-3">Avatar, background & splash</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Your app appearance (sidebar avatar, dashboard background, splash screen). Stored in browser.
          </p>
          <SettingsSection
            category="appearance"
            settings={settings}
            onSave={() => {}}
            isSaving={false}
          />
        </section>
      )}

      {/* Default for users without access */}
      <section className="border border-border rounded-lg p-4">
        <h2 className="text-lg font-semibold mb-3">Default for users without access</h2>
        <p className="text-sm text-muted-foreground mb-4">
          These URLs are used when a user has not set their own avatar or background.
        </p>
        {loadingDefault ? (
          <p className="text-muted-foreground">Loading…</p>
        ) : (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Default avatar URL</label>
              <input
                type="url"
                value={defaultAvatar}
                onChange={(e) => setDefaultAvatar(e.target.value)}
                placeholder="https://… or /assets/…"
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-foreground"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Default background URL</label>
              <input
                type="url"
                value={defaultBackground}
                onChange={(e) => setDefaultBackground(e.target.value)}
                placeholder="https://… or /assets/…"
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-foreground"
              />
            </div>
            <button
              type="button"
              onClick={handleSaveDefault}
              disabled={updateDefaultMutation.isPending}
              className="rounded-lg bg-primary px-4 py-2 text-primary-foreground font-medium hover:bg-primary/90 disabled:opacity-50"
            >
              {updateDefaultMutation.isPending ? 'Saving…' : 'Save default'}
            </button>
          </div>
        )}
      </section>

      {/* Players: avatar edit/delete */}
      <section className="border border-border rounded-lg p-4">
        <h2 className="text-lg font-semibold mb-3">Players — avatars</h2>
        <p className="text-sm text-muted-foreground mb-4">
          Edit or clear each player&apos;s avatar URL.
        </p>
        {loadingPlayers ? (
          <p className="text-muted-foreground">Loading players…</p>
        ) : players.length === 0 ? (
          <p className="text-muted-foreground">No players found.</p>
        ) : (
          <ul className="space-y-3">
            {players.map((player) => (
              <PlayerAvatarRow key={player.player_id} player={player} />
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

function PlayerAvatarRow({ player }: { player: Player }) {
  const queryClient = useQueryClient()
  const [editUrl, setEditUrl] = useState(player.avatar_url ?? '')
  const [saving, setSaving] = useState(false)

  const updateMutation = useMutation({
    mutationFn: (avatarUrl: string) =>
      tournamentsApi.updatePlayer(player.player_id, { avatar_url: avatarUrl || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tournaments', 'players'] })
      toast.success('Avatar updated.')
      setSaving(false)
    },
    onError: () => {
      toast.error('Failed to update avatar.')
      setSaving(false)
    },
  })

  const handleSave = () => {
    setSaving(true)
    updateMutation.mutate(editUrl.trim())
  }

  const handleClear = () => {
    setEditUrl('')
    setSaving(true)
    updateMutation.mutate('')
  }

  const displayName = [player.first_name, player.last_name].filter(Boolean).join(' ') || player.player_id

  return (
    <li className="flex flex-wrap items-center gap-3 p-3 rounded-lg bg-card/50 border border-border">
      <div className="w-10 h-10 rounded-full bg-muted overflow-hidden flex-shrink-0">
        {player.avatar_url ? (
          <img src={player.avatar_url} alt="" className="w-full h-full object-cover" />
        ) : (
          <span className="w-full h-full flex items-center justify-center text-muted-foreground text-sm">
            —
          </span>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="font-medium truncate">{displayName}</div>
        <input
          type="url"
          value={editUrl}
          onChange={(e) => setEditUrl(e.target.value)}
          placeholder="Avatar URL"
          className="mt-1 w-full max-w-md rounded border border-border bg-background px-2 py-1 text-sm"
        />
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="rounded px-3 py-1.5 text-sm bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button
          type="button"
          onClick={handleClear}
          disabled={saving}
          className="rounded px-3 py-1.5 text-sm border border-border hover:bg-accent disabled:opacity-50"
        >
          Clear
        </button>
      </div>
    </li>
  )
}
