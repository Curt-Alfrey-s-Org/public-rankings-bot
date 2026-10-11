/**
 * Settings > Admin > Edit Splash
 * Configure the login splash screen. Admin only.
 * Splash config (title, media) + capabilities list.
 */

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/contexts/AuthContext'
import { splashConfigApi, type SplashConfig } from '@/api/splashConfig'
import { loginFeaturesApi, type FeatureItem } from '@/api/loginFeatures'
import { toast } from '@/lib/toast'

function FeatureRow({
  item,
  onChange,
  onRemove,
  disabled,
}: {
  item: FeatureItem
  onChange: (title: string, description: string) => void
  onRemove: () => void
  disabled?: boolean
}) {
  return (
    <div className="flex gap-2 items-start flex-wrap">
      <input
        type="text"
        value={item.title}
        onChange={(e) => onChange(e.target.value, item.description)}
        placeholder="Title"
        className="flex-1 min-w-[120px] px-2 py-1.5 rounded border border-border bg-background text-sm"
        disabled={disabled}
      />
      <input
        type="text"
        value={item.description}
        onChange={(e) => onChange(item.title, e.target.value)}
        placeholder="Description"
        className="flex-[2] min-w-[160px] px-2 py-1.5 rounded border border-border bg-background text-sm"
        disabled={disabled}
      />
      <button
        type="button"
        onClick={onRemove}
        disabled={disabled}
        className="px-2 py-1.5 text-destructive hover:bg-destructive/10 rounded text-sm"
        aria-label="Remove"
      >
        Remove
      </button>
    </div>
  )
}

export default function SettingsEditSplashPage() {
  const queryClient = useQueryClient()
  const { isSuperAdmin } = useAuth()
  const [splash, setSplash] = useState<SplashConfig>({
    splash_url: '',
    splash_type: 'video',
    splash_use_scraped_media: false,
    title: 'Pro Billiards Software',
  })
  const [fullList, setFullList] = useState<FeatureItem[]>([])

  const { data: splashData, isLoading: loadingSplash } = useQuery({
    queryKey: ['splash-config'],
    queryFn: () => splashConfigApi.get(),
    staleTime: 60_000,
  })
  const { data: featuresData } = useQuery({
    queryKey: ['login-features', 'admin'],
    queryFn: () => loginFeaturesApi.get(),
    staleTime: 60_000,
    enabled: isSuperAdmin,
  })

  useEffect(() => {
    if (splashData) setSplash(splashData)
  }, [splashData])
  useEffect(() => {
    if (featuresData?.full?.length) setFullList(featuresData.full)
  }, [featuresData])

  const splashMutation = useMutation({
    mutationFn: (body: Partial<SplashConfig>) => splashConfigApi.update(body),
    onSuccess: (result) => {
      setSplash(result)
      queryClient.invalidateQueries({ queryKey: ['splash-config'] })
      toast.success('Splash config saved.')
    },
    onError: (e: Error) => toast.error(e?.message ?? 'Save failed'),
  })
  const featuresMutation = useMutation({
    mutationFn: (payload: { full: FeatureItem[] }) => loginFeaturesApi.update(payload),
    onSuccess: (result) => {
      if (result.full) setFullList(result.full)
      queryClient.invalidateQueries({ queryKey: ['login-features'] })
      toast.success('Capabilities list saved.')
    },
    onError: (e: Error) => toast.error(e?.message ?? 'Save failed'),
  })

  const updateFull = (index: number, title: string, description: string) => {
    setFullList((prev) => {
      const next = [...prev]
      next[index] = { title, description }
      return next
    })
  }
  const removeFull = (index: number) => setFullList((prev) => prev.filter((_, i) => i !== index))
  const addFull = () => setFullList((prev) => [...prev, { title: '', description: '' }])

  const handleSaveSplash = () => splashMutation.mutate(splash)
  const handleSaveFeatures = () => featuresMutation.mutate({ full: fullList })

  const isLoading = loadingSplash && !splashData

  if (isLoading) return <p className="p-6 text-muted-foreground">Loading…</p>

  return (
    <div className="p-6 max-w-4xl space-y-8">
      <header>
        <h1 className="text-2xl font-bold">Edit Splash</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Customize the login splash screen. Changes apply to all visitors.
        </p>
      </header>

      {/* Splash config */}
      <section className="border border-border rounded-lg p-6 space-y-4">
        <h2 className="text-lg font-semibold">Splash screen</h2>
        <p className="text-sm text-muted-foreground">
          Title, background media, and type. Media must be uploaded in Settings → Admin → Appearance.
        </p>

        <div>
          <label className="block text-sm font-medium mb-1">Title</label>
          <input
            type="text"
            value={splash.title}
            onChange={(e) => setSplash((s) => ({ ...s, title: e.target.value }))}
            placeholder="Pro Billiards Software"
            className="w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Background URL</label>
          <input
            type="text"
            value={splash.splash_url}
            onChange={(e) => setSplash((s) => ({ ...s, splash_url: e.target.value }))}
            placeholder="/assets/video/... or /assets/..."
            className="w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground"
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-2">Background type</label>
          <div className="flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="radio"
                name="splashType"
                checked={splash.splash_type === 'video'}
                onChange={() => setSplash((s) => ({ ...s, splash_type: 'video' }))}
                className="rounded border-border"
              />
              Video
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="radio"
                name="splashType"
                checked={splash.splash_type === 'image'}
                onChange={() => setSplash((s) => ({ ...s, splash_type: 'image' }))}
                className="rounded border-border"
              />
              Image
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="radio"
                name="splashType"
                checked={splash.splash_type === 'none'}
                onChange={() => setSplash((s) => ({ ...s, splash_type: 'none' }))}
                className="rounded border-border"
              />
              None
            </label>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="splashScraped"
            checked={splash.splash_use_scraped_media}
            onChange={(e) => setSplash((s) => ({ ...s, splash_use_scraped_media: e.target.checked }))}
            className="w-4 h-4 rounded border-border"
          />
          <label htmlFor="splashScraped" className="text-sm cursor-pointer">
            Use scraped media for splash (random WPBA/WPA pics slideshow)
          </label>
        </div>

        <button
          type="button"
          onClick={handleSaveSplash}
          disabled={splashMutation.isPending}
          className="min-h-[44px] px-4 py-2.5 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 disabled:opacity-50"
        >
          {splashMutation.isPending ? 'Saving…' : 'Save splash config'}
        </button>
      </section>

      {/* Capabilities list (super_admin only) */}
      {isSuperAdmin && (
      <section className="border border-border rounded-lg p-6 space-y-4">
        <h2 className="text-lg font-semibold">Capabilities list</h2>
        <p className="text-sm text-muted-foreground">
          Shown on splash (half on each side of the login form) and Full Software Capabilities page.
        </p>

        <div className="space-y-2 max-h-64 overflow-y-auto">
          {fullList.map((item, i) => (
            <FeatureRow
              key={`full-${i}`}
              item={item}
              onChange={(title, desc) => updateFull(i, title, desc)}
              onRemove={() => removeFull(i)}
              disabled={featuresMutation.isPending}
            />
          ))}
          <button
            type="button"
            onClick={addFull}
            disabled={featuresMutation.isPending}
            className="text-sm text-primary hover:underline"
          >
            + Add item
          </button>
        </div>

        <button
          type="button"
          onClick={handleSaveFeatures}
          disabled={featuresMutation.isPending}
          className="min-h-[44px] px-4 py-2.5 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 disabled:opacity-50"
        >
          {featuresMutation.isPending ? 'Saving…' : 'Save capabilities list'}
        </button>
      </section>
      )}
    </div>
  )
}
