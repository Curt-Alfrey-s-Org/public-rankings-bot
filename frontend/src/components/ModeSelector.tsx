import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/api/client'
import { toast } from '@/lib/toast'
import ConfirmDialog from './ConfirmDialog'

type BotMode = 'sandbox' | 'live' | 'yfinance' | 'dryrun-live'

interface ModeSelectorProps {
  currentMode?: string
  botRunning?: boolean
}

export default function ModeSelector({ currentMode, botRunning = false }: ModeSelectorProps) {
  const queryClient = useQueryClient()
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [pendingMode, setPendingMode] = useState<BotMode | null>(null)

  const modeMutation = useMutation({
    mutationFn: async (mode: BotMode) => {
      try {
        const response = await apiClient.post('/bot/mode', { mode }, {
          timeout: 5000, // 5 second timeout
        })
        return response.data
      } catch (error: any) {
        // Re-throw with better error message
        if (!error.response) {
          if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
            throw new Error('Connection timeout. Please check if the API server is running.')
          } else if (error.message?.includes('Network')) {
            throw new Error('Cannot connect to API server. Please start the API with ./start_api.sh')
          }
        }
        throw error
      }
    },
    onSuccess: (_data, mode) => {
      queryClient.invalidateQueries({ queryKey: ['bot-status'] })
      toast.success(`Mode set to ${mode}. This mode will be used when you start the bot.`)
      setPendingMode(null)
    },
    onError: (error: any) => {
      // Silent error handling - no user-facing error messages
      const errorMessage = error.response?.data?.detail || error.message || 'Unknown error'
      
      // Only show toast for user action errors (bot running), not system errors
      if (error.response?.status === 400 && errorMessage.includes('running')) {
        toast.error('Cannot change mode while bot is running. Please stop the bot first.')
      } else {
        // For network/system errors, just reset state silently
        // The ConnectionStatus component will show the connection state
        if (import.meta.env.DEV) {
          console.debug('Mode change error (silent):', errorMessage)
        }
      }
      
      // Reset pending mode on error
      setPendingMode(null)
    },
  })

  const modes: { value: BotMode; label: string; icon: string; description: string }[] = [
    { value: 'sandbox', label: 'Sandbox', icon: '🧪', description: 'Paper trading mode' },
    { value: 'live', label: 'Live', icon: '⚡', description: 'Live trading mode' },
    { value: 'yfinance', label: 'YFinance', icon: '📊', description: 'Yahoo Finance data' },
    { value: 'dryrun-live', label: 'Dry Run Live', icon: '🔍', description: 'Test with live data' },
  ]

  const handleModeChange = (mode: BotMode) => {
    // Prevent mode change when bot is running
    if (botRunning) {
      toast.error('Cannot change mode while bot is running. Please stop the bot first.')
      return
    }
    
    if (mode === currentMode) {
      toast.info('Already in this mode')
      return
    }
    
    // Store the pending mode and show confirmation dialog
    setPendingMode(mode)
    setShowConfirmDialog(true)
  }

  const handleConfirmModeChange = () => {
    if (pendingMode && !modeMutation.isPending) {
      // Close dialog first to prevent multiple clicks
      setShowConfirmDialog(false)
      // Then trigger mutation
      modeMutation.mutate(pendingMode)
    }
  }

  const handleCancelModeChange = () => {
    setPendingMode(null)
    setShowConfirmDialog(false)
  }

  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <h3 className="text-sm font-semibold mb-3">Trading Mode</h3>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {modes.map((mode) => {
          const isActive = currentMode === mode.value
          const isPending = pendingMode === mode.value && modeMutation.isPending
          
          return (
            <button
              key={mode.value}
              onClick={() => handleModeChange(mode.value)}
              disabled={isPending || modeMutation.isPending || botRunning}
              className={`p-3 rounded-lg border-2 transition-all ${
                isActive
                  ? 'border-primary bg-primary/20 text-primary'
                  : 'border-border hover:border-primary/50 hover:bg-accent/50'
              } ${isPending || botRunning ? 'opacity-50 cursor-not-allowed' : ''}`}
              title={botRunning ? 'Stop the bot before changing mode' : ''}
            >
              <div className="flex flex-col items-center gap-2">
                <span className="text-2xl">{mode.icon}</span>
                <span className="text-sm font-medium">{mode.label}</span>
                <span className="text-xs text-muted-foreground">{mode.description}</span>
                {isActive && (
                  <span className="text-xs font-semibold text-primary">Active</span>
                )}
                {isPending && (
                  <span className="text-xs">Changing...</span>
                )}
              </div>
            </button>
          )
        })}
      </div>

      {currentMode && (
        <div className="mt-3 text-sm text-muted-foreground text-center space-y-0.5">
          <div>Current mode: <span className="font-semibold capitalize">{currentMode}</span></div>
          <div className="text-xs">Saved to .env — used when you Start the bot.</div>
        </div>
      )}
      
      {botRunning && (
        <div className="mt-3 p-2 bg-red-500/20 border border-red-500/50 rounded text-xs text-red-600 dark:text-red-400 text-center">
          ⚠️ Bot is running. Stop the bot before changing modes.
        </div>
      )}

      {/* Confirmation Dialog */}
      <ConfirmDialog
        isOpen={showConfirmDialog}
        title="Change Trading Mode"
        message={
          pendingMode
            ? `Are you sure you want to change mode to ${pendingMode}? This mode will be used when you start the bot.`
            : ''
        }
        confirmText="Change Mode"
        onConfirm={handleConfirmModeChange}
        onCancel={handleCancelModeChange}
      />
    </div>
  )
}
