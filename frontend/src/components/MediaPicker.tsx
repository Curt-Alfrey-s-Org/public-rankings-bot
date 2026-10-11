/**
 * Search & upload pics/videos from folder. Use selection for avatar, background, or splash.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getAssets, uploadAssets, type AssetEntry } from '@/api/assets'

export type MediaUse = 'avatar' | 'background' | 'splash'

export interface MediaPickerProps {
  onSelect: (url: string, use: MediaUse) => void
  /** Optional: filter to images only (e.g. for avatar) */
  imagesOnly?: boolean
}

export default function MediaPicker({ onSelect, imagesOnly }: MediaPickerProps) {
  const [list, setList] = useState<AssetEntry[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const fetchList = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const files = await getAssets()
      setList(files)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load assets')
      setList([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchList()
  }, [fetchList])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return list
    return list.filter((f) => f.name.toLowerCase().includes(q))
  }, [list, search])

  const displayList = imagesOnly ? filtered.filter((f) => f.type === 'image') : filtered

  const handleUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files
      if (!files?.length) return
      setUploading(true)
      setError(null)
      try {
        const urls = await uploadAssets(Array.from(files))
        if (urls.length) await fetchList()
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Upload failed')
      } finally {
        setUploading(false)
        e.target.value = ''
      }
    },
    [fetchList]
  )

  const handleUse = useCallback(
    (path: string, use: MediaUse) => {
      const url = path.startsWith('http') || path.startsWith('/') ? path : `/${path.replace(/^\/+/, '')}`
      onSelect(url, use)
    },
    [onSelect]
  )

  return (
    <div className="space-y-3 rounded-lg border border-border bg-card/30 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          placeholder="Search pics & videos..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 min-w-[180px] px-3 py-2 bg-background border border-input rounded-lg text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,video/*"
          multiple
          className="hidden"
          onChange={handleUpload}
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
        >
          {uploading ? 'Uploading…' : 'Upload from folder'}
        </button>
      </div>
      {error && (
        <p className="text-sm text-destructive">{error}</p>
      )}
      {loading ? (
        <p className="text-sm text-muted-foreground py-4">Loading…</p>
      ) : displayList.length === 0 ? (
        <p className="text-sm text-muted-foreground py-4">
          {list.length === 0 ? 'No pics or videos yet. Upload from folder or add files to public/assets.' : 'No matches.'}
        </p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 max-h-[320px] overflow-y-auto">
          {displayList.map((f) => (
            <div
              key={f.path}
              className="rounded-lg border border-border bg-background/80 overflow-hidden flex flex-col"
            >
              <div className="aspect-square bg-muted flex items-center justify-center relative">
                {f.type === 'image' ? (
                  <img
                    src={f.path}
                    alt={f.name}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = 'none'
                    }}
                  />
                ) : (
                  <span className="text-4xl text-muted-foreground">🎬</span>
                )}
              </div>
              <div className="p-2 flex flex-col gap-1">
                <p className="text-xs text-muted-foreground truncate" title={f.name}>
                  {f.name}
                </p>
                <div className="flex flex-wrap gap-1">
                  {f.type === 'image' && (
                    <button
                      type="button"
                      onClick={() => handleUse(f.path, 'avatar')}
                      className="px-2 py-1 text-xs rounded bg-muted hover:bg-muted/80"
                    >
                      Avatar
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => handleUse(f.path, 'background')}
                    className="px-2 py-1 text-xs rounded bg-muted hover:bg-muted/80"
                  >
                    BG
                  </button>
                  <button
                    type="button"
                    onClick={() => handleUse(f.path, 'splash')}
                    className="px-2 py-1 text-xs rounded bg-muted hover:bg-muted/80"
                  >
                    Splash
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
