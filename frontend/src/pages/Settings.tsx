import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { settingsApi, Settings } from '@/api/settings'
import SettingsSection from '@/components/SettingsSection'
import { toast } from '@/lib/toast'

interface SettingsProps {
  sidebarOpen?: boolean
  onSidebarToggle?: () => void
}

export default function SettingsPage({ sidebarOpen: _sidebarOpen, onSidebarToggle }: SettingsProps) {
  const queryClient = useQueryClient()
  const [activeCategory, setActiveCategory] = useState<string>('appearance')

  const { data: settings, isLoading, isError, error } = useQuery<Settings>({
    queryKey: ['settings'],
    queryFn: settingsApi.getSettings,
    retry: 2,
    retryDelay: 1000,
    staleTime: 0,
    gcTime: 0,
    refetchOnMount: true,
    refetchOnWindowFocus: true,
  })

  const updateMutation = useMutation({
    mutationFn: (updatedSettings: Partial<Settings>) =>
      settingsApi.updateSettings(updatedSettings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      queryClient.invalidateQueries({ queryKey: ['stats'] })
      toast.success('Settings saved successfully!')
    },
    onError: (error: any) => {
      // Silent error handling - no user-facing error messages
      if (import.meta.env.DEV) {
        console.debug('Settings save error (silent):', error.message || 'Unknown error')
      }
    },
  })

  const handleSave = (_category: string, categorySettings: Partial<Settings>) => {
    updateMutation.mutate(categorySettings)
  }

  const isPresetSaving = updateMutation.isPending

  const categories = [
    { id: 'appearance', label: 'Appearance', icon: '🎨' },
    { id: 'advanced', label: 'Advanced', icon: '⚙️' },
  ]

  if (isLoading) {
    return (
      <div className="flex flex-col h-screen bg-black/90 text-foreground">
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto">
            <div className="animate-pulse space-y-4">
              <div className="h-8 bg-muted rounded w-1/4"></div>
              <div className="h-64 bg-muted rounded"></div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Show error state
  if (isError) {
    return (
      <div className="flex flex-col h-screen bg-black/90 text-foreground">
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto">
            <div className="bg-destructive/10 border border-destructive rounded-lg p-6">
              <h2 className="text-xl font-semibold text-destructive mb-2">Error Loading Settings</h2>
              <p className="text-muted-foreground mb-4">
                {error instanceof Error ? (error as Error).message : 'Failed to load settings from API'}
              </p>
              <button
                onClick={() => queryClient.invalidateQueries({ queryKey: ['settings'] })}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90"
              >
                Retry
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Show loading state
  if (isLoading || !settings) {
    return (
      <div className="flex flex-col h-screen bg-black/90 text-foreground">
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto">
            <div className="animate-pulse space-y-4">
              <div className="h-8 bg-muted rounded w-1/4"></div>
              <div className="h-64 bg-muted rounded"></div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen bg-black/90 text-foreground overflow-hidden">
      {/* Header */}
      <header className="bg-card/50 backdrop-blur-sm border-b border-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          {onSidebarToggle && (
            <button
              onClick={onSidebarToggle}
              className="p-2 hover:bg-accent rounded-lg transition-colors"
              aria-label="Toggle menu"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          )}
          <div>
            <h1 className="text-2xl font-bold">Settings</h1>
            <p className="text-sm text-muted-foreground">
              Configure bot parameters and preferences
            </p>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-y-auto p-6">
        <div className="max-w-7xl mx-auto">
          {/* Global Presets Bar */}
          <div className="mb-6 bg-card border border-border rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">Presets</h2>
                <p className="text-sm text-muted-foreground">Quickly switch between tested configurations</p>
              </div>
              <div className="flex gap-2">
                <button
                  className={`px-3 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 ${isPresetSaving ? 'opacity-60 cursor-not-allowed' : ''}`}
                  disabled={isPresetSaving}
                  aria-busy={isPresetSaving}
                  onClick={() => {
                    const preset: Partial<Settings> = {
                      ENABLE_ML_SIGNAL_FILTER: 'false',
                      ML_SIGNAL_FILTER_MIN_CONFIDENCE: 0.3,
                      ML_SIGNAL_FILTER_MIN_WIN_PROB: 0.3,
                      STRATEGY_MIN_BARS: 10,
                      TRADING_FREQUENCY: 1,
                      MAX_DISCOVERED_STOCKS: 200,
                      BOT_MAX_OPEN_POSITIONS: 50,
                      BOT_MAX_ALLOCATION: 5000,
                    }
                    updateMutation.mutate(preset)
                    toast.success('Applied Testing Mode preset')
                  }}
                >
                  {isPresetSaving ? (
                    <span className="inline-flex items-center">
                      <svg className="w-4 h-4 mr-2 animate-spin" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path>
                      </svg>
                      Applying...
                    </span>
                  ) : (
                    'Apply Testing Mode'
                  )}
                </button>
                <button
                  className={`px-3 py-2 rounded-lg bg-accent text-foreground hover:bg-accent/80 border border-border ${isPresetSaving ? 'opacity-60 cursor-not-allowed' : ''}`}
                  disabled={isPresetSaving}
                  aria-busy={isPresetSaving}
                  onClick={() => {
                    const preset: Partial<Settings> = {
                      ENABLE_ML_SIGNAL_FILTER: 'true',
                      ML_SIGNAL_FILTER_MIN_CONFIDENCE: 0.5,
                      ML_SIGNAL_FILTER_MIN_WIN_PROB: 0.55,
                      STRATEGY_MIN_BARS: 30,
                      TRADING_FREQUENCY: 3,
                    }
                    updateMutation.mutate(preset)
                    toast.success('Applied Moderate ML preset')
                  }}
                >
                  {isPresetSaving ? (
                    <span className="inline-flex items-center">
                      <svg className="w-4 h-4 mr-2 animate-spin" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path>
                      </svg>
                      Applying...
                    </span>
                  ) : (
                    'Apply Moderate ML'
                  )}
                </button>
              </div>
            </div>
          </div>
          <div className="flex gap-6">
          {/* Category Sidebar */}
          <aside className="w-64 flex-shrink-0">
            <div className="bg-card border border-border rounded-lg p-4 space-y-2">
              {categories.map((category) => (
                <button
                  key={category.id}
                  onClick={() => setActiveCategory(category.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                    activeCategory === category.id
                      ? 'bg-primary text-primary-foreground'
                      : 'hover:bg-accent text-foreground'
                  }`}
                >
                  <span className="text-xl">{category.icon}</span>
                  <span className="font-medium">{category.label}</span>
                </button>
              ))}
            </div>
          </aside>

          {/* Settings Content */}
          <main className="flex-1">
            <SettingsSection
              category={activeCategory}
              settings={settings}
              onSave={handleSave}
              isSaving={updateMutation.isPending}
            />
          </main>
          </div>
        </div>
      </main>
    </div>
  )
}
