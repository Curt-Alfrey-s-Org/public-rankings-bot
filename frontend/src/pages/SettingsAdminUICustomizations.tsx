/**
 * Settings > Admin > UI Customizations: Manage dashboard UI elements, text, buttons, layouts
 * Full customization of all UI components with live preview and updates
 */

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useLiveUpdates } from '@/hooks/useLiveUpdates'
import SettingsSection from '@/components/SettingsSection'
import { toast } from '@/lib/toast'

// API functions for UI customizations
const uiApi = {
  getCustomizations: async () => {
    const response = await fetch('/api/ui-customizations')
    if (!response.ok) throw new Error('Failed to fetch customizations')
    return response.json()
  },

  getCustomization: async (scope: string) => {
    const response = await fetch(`/api/ui-customizations/${scope}`)
    if (!response.ok) throw new Error('Failed to fetch customization')
    return response.json()
  },

  updateCustomization: async (scope: string, data: any) => {
    const response = await fetch(`/api/ui-customizations/${scope}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scope, data })
    })
    if (!response.ok) throw new Error('Failed to update customization')
    return response.json()
  },

  resetCustomization: async (scope: string) => {
    const response = await fetch(`/api/ui-customizations/reset/${scope}`, {
      method: 'POST'
    })
    if (!response.ok) throw new Error('Failed to reset customization')
    return response.json()
  },

  getDefaults: async (scope: string) => {
    const response = await fetch(`/api/ui-customizations/defaults/${scope}`)
    if (!response.ok) throw new Error('Failed to fetch defaults')
    return response.json()
  }
}

type UICustomization = {
  scope: string
  data: {
    text?: Record<string, string>
    buttons?: Record<string, string>
    layouts?: Record<string, boolean>
    version?: number
  }
  created_at: string
  updated_at: string
}

export default function SettingsAdminUICustomizationsPage() {
  const queryClient = useQueryClient()
  const [selectedScope, setSelectedScope] = useState('global')
  const [customizationData, setCustomizationData] = useState<any>({})
  const { isConnected, lastUpdate } = useLiveUpdates()

  const { data: customizations, isLoading } = useQuery({
    queryKey: ['ui-customizations'],
    queryFn: uiApi.getCustomizations
  })

  const { data: defaults } = useQuery({
    queryKey: ['ui-customization-defaults', selectedScope],
    queryFn: () => uiApi.getDefaults(selectedScope),
    enabled: !!selectedScope
  })

  useEffect(() => {
    if (customizations?.customizations) {
      const global = customizations.customizations.find((c: UICustomization) => c.scope === 'global')
      if (global) {
        setCustomizationData(global.data)
      }
    }
  }, [customizations])

  // Handle live updates from WebSocket
  useEffect(() => {
    if (lastUpdate && lastUpdate.event === 'ui_customization_updated') {
      const { scope, data } = lastUpdate.data
      if (scope === selectedScope) {
        setCustomizationData(data)
        queryClient.invalidateQueries({ queryKey: ['ui-customizations'] })
        toast.success('UI customization updated live!')
      }
    } else if (lastUpdate && lastUpdate.event === 'ui_customization_reset') {
      const { scope } = lastUpdate.data
      if (scope === selectedScope) {
        queryClient.invalidateQueries({ queryKey: ['ui-customizations'] })
        toast.success('UI customization reset live!')
      }
    }
  }, [lastUpdate, selectedScope, queryClient])

  const updateMutation = useMutation({
    mutationFn: (data: any) => uiApi.updateCustomization(selectedScope, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ui-customizations'] })
      toast.success('UI customization updated successfully!')
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed to update customization')
  })

  const resetMutation = useMutation({
    mutationFn: () => uiApi.resetCustomization(selectedScope),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ui-customizations'] })
      toast.success('UI customization reset to defaults')
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Failed to reset customization')
  })

  const handleTextChange = (key: string, value: string) => {
    const newData = {
      ...customizationData,
      text: {
        ...customizationData.text,
        [key]: value
      }
    }
    setCustomizationData(newData)
  }

  const handleButtonChange = (key: string, value: string) => {
    const newData = {
      ...customizationData,
      buttons: {
        ...customizationData.buttons,
        [key]: value
      }
    }
    setCustomizationData(newData)
  }

  const handleLayoutChange = (key: string, value: boolean) => {
    const newData = {
      ...customizationData,
      layouts: {
        ...customizationData.layouts,
        [key]: value
      }
    }
    setCustomizationData(newData)
  }

  const handleSave = () => {
    updateMutation.mutate(customizationData)
  }

  const handleReset = () => {
    resetMutation.mutate()
  }

  if (isLoading) {
    return <div className="p-6">Loading UI customizations...</div>
  }

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">UI Customizations</h1>
          <p className="text-muted-foreground">
            Customize all dashboard UI elements, text, buttons, and layouts
          </p>
        </div>
        <div className="flex gap-2">
          <span className={`px-2 py-1 rounded text-xs ${isConnected ? 'bg-green-pool_opt_in text-green-800' : 'bg-red-pool_opt_in text-red-800'}`}>
            {isConnected ? '🟢 Live Updates Active' : '🔴 Live Updates Offline'}
          </span>
          {lastUpdate && (
            <span className="px-2 py-1 rounded text-xs border">
              Last update: {new Date(lastUpdate.timestamp).toLocaleTimeString()}
            </span>
          )}
        </div>
      </div>

      <div className="rounded-lg border border-border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
        <h3 className="font-semibold text-foreground mb-2">How to use UI Customizations</h3>
        <ul className="list-disc list-inside space-y-1">
          <li>This page controls dashboard titles, button labels, and layout options (e.g. breadcrumbs) for the whole app. Changes apply everywhere after you click <strong>Save Changes</strong>.</li>
          <li>Edit the fields in <strong>Text Elements</strong>, <strong>Button Labels</strong>, and <strong>Layout Options</strong>; use <strong>Live Preview</strong> below to see the effect before saving.</li>
          <li>Use <strong>Reset to Defaults</strong> to restore built-in defaults for the selected scope.</li>
          <li><strong>Tip:</strong> For quick edits to text on a specific page (e.g. Home or Dashboard), use the <strong>Edit UI</strong> button (bottom-right) on that page; for changing all labels and options in one place, use this page.</li>
        </ul>
      </div>

      <div className="space-y-6">
        <div className="flex gap-4">
          <button
            onClick={handleSave}
            disabled={updateMutation.isPending}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
          </button>
          <button
            onClick={handleReset}
            disabled={resetMutation.isPending}
            className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            {resetMutation.isPending ? 'Resetting...' : 'Reset to Defaults'}
          </button>
        </div>

          <div className="grid gap-6 md:grid-cols-2">
            {/* Text Customizations */}
            <div className="border border-border rounded-lg p-4">
              <h3 className="text-lg font-semibold mb-4">Text Elements</h3>
              <div className="space-y-4">
                {Object.entries(customizationData.text || {}).map(([key, value]) => (
                  <div key={key}>
                    <label htmlFor={`text-${key}`} className="block text-sm font-medium mb-1 capitalize">
                      {key.replace(/_/g, ' ')}
                    </label>
                    <input
                      id={`text-${key}`}
                      type="text"
                      value={value as string}
                      onChange={(e) => handleTextChange(key, e.target.value)}
                      className="w-full rounded-lg border border-border bg-card px-3 py-2 text-foreground"
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* Button Labels */}
            <div className="border border-border rounded-lg p-4">
              <h3 className="text-lg font-semibold mb-4">Button Labels</h3>
              <div className="space-y-4">
                {Object.entries(customizationData.buttons || {}).map(([key, value]) => (
                  <div key={key}>
                    <label htmlFor={`button-${key}`} className="block text-sm font-medium mb-1 capitalize">
                      {key.replace(/_/g, ' ')} Button
                    </label>
                    <input
                      id={`button-${key}`}
                      type="text"
                      value={value as string}
                      onChange={(e) => handleButtonChange(key, e.target.value)}
                      className="w-full rounded-lg border border-border bg-card px-3 py-2 text-foreground"
                    />
                  </div>
                ))}
              </div>
            </div>

            {/* Layout Options */}
            <div className="border border-border rounded-lg p-4 md:col-span-2">
              <h3 className="text-lg font-semibold mb-4">Layout Options</h3>
              <div className="grid gap-4 md:grid-cols-2">
                {Object.entries(customizationData.layouts || {}).map(([key, value]) => (
                  <div key={key} className="flex items-center space-x-2">
                    <input
                      id={`layout-${key}`}
                      type="checkbox"
                      checked={value as boolean}
                      onChange={(e) => handleLayoutChange(key, e.target.checked)}
                      className="rounded border-border"
                    />
                    <label htmlFor={`layout-${key}`} className="text-sm font-medium capitalize">
                      {key.replace(/_/g, ' ')}
                    </label>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Preview Section */}
          <div className="border border-border rounded-lg p-4">
            <h3 className="text-lg font-semibold mb-4">Live Preview</h3>
            <div className="space-y-4 p-4 border rounded-lg bg-slate-50 dark:bg-slate-900">
              <div className="text-center">
                <h2 className="text-xl font-bold">{customizationData.text?.dashboard_title || 'Dashboard Title'}</h2>
                <p className="text-muted-foreground">{customizationData.text?.dashboard_subtitle || 'Dashboard Subtitle'}</p>
              </div>

              <div className="flex gap-2 justify-center">
                <button className="px-3 py-1 border border-gray-300 rounded text-sm hover:bg-gray-50">
                  {customizationData.buttons?.refresh || 'Refresh'}
                </button>
                <button className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">
                  {customizationData.buttons?.save || 'Save'}
                </button>
                <button className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700">
                  {customizationData.buttons?.cancel || 'Cancel'}
                </button>
              </div>

              {customizationData.layouts?.show_breadcrumbs && (
                <div className="text-xs text-muted-foreground border-t pt-2">
                  Home / Dashboard / Settings
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
  )
}