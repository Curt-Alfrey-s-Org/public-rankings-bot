/**
 * Error display component for TestCenter with recovery options
 */

import React from 'react'
import { TestCenterError } from '@/lib/testCenterErrorHandler'
import { testCenterLog } from '@/lib/testCenterLogger'

interface TestCenterErrorDisplayProps {
  error: TestCenterError
  onRetry?: () => void
  onRecoveryAction?: (action: string) => void
  onDismiss?: () => void
  className?: string
}

export default function TestCenterErrorDisplay({
  error,
  onRetry,
  onRecoveryAction,
  onDismiss,
  className = ''
}: TestCenterErrorDisplayProps) {
  const handleRecoveryClick = (action: string) => {
    testCenterLog.userInteraction('error_recovery_attempted', {
      errorType: error.type,
      recoveryAction: action
    })
    onRecoveryAction?.(action)
  }

  const getErrorIcon = (type: TestCenterError['type']) => {
    switch (type) {
      case 'network': return '🌐'
      case 'auth': return '🔐'
      case 'validation': return '⚠️'
      case 'server': return '🔧'
      case 'timeout': return '⏱️'
      default: return '❌'
    }
  }

  const getSeverityColor = (type: TestCenterError['type']) => {
    switch (type) {
      case 'network': return 'text-yellow-600 border-yellow-200 bg-yellow-50'
      case 'auth': return 'text-red-600 border-red-200 bg-red-50'
      case 'validation': return 'text-orange-600 border-orange-200 bg-orange-50'
      case 'server': return 'text-purple-600 border-purple-200 bg-purple-50'
      case 'timeout': return 'text-blue-600 border-blue-200 bg-blue-50'
      default: return 'text-gray-600 border-gray-200 bg-gray-50'
    }
  }

  return (
    <div className={`test-center-error-display ${getSeverityColor(error.type)} border rounded-lg p-4 mb-4 ${className}`}>
      <div className="flex items-start space-x-3">
        <div className="text-2xl">{getErrorIcon(error.type)}</div>
        <div className="flex-1">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold text-lg">{error.type.charAt(0).toUpperCase() + error.type.slice(1)} Error</h3>
            {onDismiss && (
              <button
                onClick={() => {
                  testCenterLog.userInteraction('error_dismissed', { errorType: error.type })
                  onDismiss()
                }}
                className="text-gray-400 hover:text-gray-600 text-xl"
                aria-label="Dismiss error"
              >
                ×
              </button>
            )}
          </div>

          <p className="text-sm mt-1 font-medium">{error.userMessage}</p>

          {error.suggestions.length > 0 && (
            <div className="mt-3">
              <h4 className="font-medium text-sm mb-2">💡 Suggestions:</h4>
              <ul className="text-sm space-y-1">
                {error.suggestions.map((suggestion, index) => (
                  <li key={index} className="flex items-start">
                    <span className="text-xs mr-2 mt-0.5">•</span>
                    <span>{suggestion}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(error.recoveryActions || error.retryable) && (
            <div className="mt-4 flex flex-wrap gap-2">
              {error.retryable && onRetry && (
                <button
                  onClick={() => {
                    testCenterLog.userInteraction('error_retry_clicked', { errorType: error.type })
                    onRetry()
                  }}
                  className="px-3 py-1 bg-blue-500 text-white text-sm rounded hover:bg-blue-600 transition-colors"
                >
                  🔄 Retry
                </button>
              )}

              {error.recoveryActions?.map(action => {
                const getActionLabel = (action: string) => {
                  switch (action) {
                    case 'relogin': return '🔐 Re-login'
                    case 'refresh_page': return '🔄 Refresh Page'
                    case 'clear_cache': return '🗑️ Clear Cache'
                    case 'check_connection': return '🌐 Check Connection'
                    case 'fix_input': return '✏️ Fix Input'
                    default: return action.charAt(0).toUpperCase() + action.slice(1)
                  }
                }

                return (
                  <button
                    key={action}
                    onClick={() => handleRecoveryClick(action)}
                    className="px-3 py-1 bg-gray-500 text-white text-sm rounded hover:bg-gray-600 transition-colors"
                  >
                    {getActionLabel(action)}
                  </button>
                )
              })}
            </div>
          )}

          {import.meta.env.DEV && (
            <details className="mt-3">
              <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">
                🔍 Technical Details
              </summary>
              <div className="mt-2 p-2 bg-gray-pool_opt_in rounded text-xs font-mono">
                <div><strong>Type:</strong> {error.type}</div>
                <div><strong>Message:</strong> {error.message}</div>
                <div><strong>Retryable:</strong> {error.retryable ? 'Yes' : 'No'}</div>
                {error.originalError?.response && (
                  <div><strong>Status:</strong> {error.originalError.response.status}</div>
                )}
              </div>
            </details>
          )}
        </div>
      </div>
    </div>
  )
}