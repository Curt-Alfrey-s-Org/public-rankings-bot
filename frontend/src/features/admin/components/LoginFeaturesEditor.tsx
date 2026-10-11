/**
 * Capabilities list editor. Super_admin only.
 * Full list = splash screen (half on each side) and Full Software Capabilities page.
 */

import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
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

export function LoginFeaturesEditor() {
  const queryClient = useQueryClient()
  const [fullList, setFullList] = useState<FeatureItem[]>([])

  const initialized = useRef(false)
  const { data, isLoading } = useQuery({
    queryKey: ['login-features', 'admin'],
    queryFn: () => loginFeaturesApi.get(),
    staleTime: 60_000,
  })
  useEffect(() => {
    if (data && !initialized.current) {
      initialized.current = true
      if (data.full?.length) setFullList(data.full)
    }
  }, [data])

  const updateMutation = useMutation({
    mutationFn: (payload: { full?: FeatureItem[] }) => loginFeaturesApi.update(payload),
    onSuccess: (result) => {
      if (result.full) setFullList(result.full)
      queryClient.invalidateQueries({ queryKey: ['login-features'] })
      toast.success('Capabilities list saved.')
    },
    onError: (e: Error) => toast.error(e?.message ?? 'Save failed'),
  })

  const handleSave = () => {
    updateMutation.mutate({ full: fullList })
  }

  const updateFull = (index: number, title: string, description: string) => {
    setFullList((prev) => {
      const next = [...prev]
      next[index] = { title, description }
      return next
    })
  }
  const removeFull = (index: number) => setFullList((prev) => prev.filter((_, i) => i !== index))
  const addFull = () => setFullList((prev) => [...prev, { title: '', description: '' }])

  if (isLoading && !data) return <p className="text-sm text-muted-foreground">Loading…</p>

  return (
    <div className="border-t border-border pt-4 space-y-4">
      <h3 className="text-sm font-semibold">Capabilities list (super_admin)</h3>
      <p className="text-xs text-muted-foreground">
        Shown on splash (half on each side) and Full Software Capabilities page.
      </p>
      <div className="space-y-4">
        <div>
          <h4 className="text-xs font-medium text-muted-foreground mb-2">Capabilities list</h4>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {fullList.map((item, i) => (
              <FeatureRow
                key={`full-${i}`}
                item={item}
                onChange={(title, desc) => updateFull(i, title, desc)}
                onRemove={() => removeFull(i)}
                disabled={updateMutation.isPending}
              />
            ))}
            <button
              type="button"
              onClick={addFull}
              disabled={updateMutation.isPending}
              className="text-xs text-primary hover:underline"
            >
              + Add item
            </button>
          </div>
        </div>
        <button
          type="button"
          onClick={handleSave}
          disabled={updateMutation.isPending}
          className="min-h-[44px] px-4 py-2.5 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 disabled:opacity-50"
        >
          {updateMutation.isPending ? 'Saving…' : 'Save list'}
        </button>
      </div>
    </div>
  )
}
