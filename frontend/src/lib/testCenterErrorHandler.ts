/**
 * Error handling utilities for TestCenter component
 * Provides retry logic, error recovery, and user-friendly error messages
 */

import { testCenterLogger } from './testCenterLogger'
import { toast } from '@/lib/toast'

export interface TestCenterError {
  type: 'network' | 'auth' | 'validation' | 'server' | 'timeout' | 'unknown'
  message: string
  originalError?: any
  retryable: boolean
  userMessage: string
  suggestions: string[]
  recoveryActions?: string[]
}

export interface RetryOptions {
  maxRetries: number
  baseDelay: number
  maxDelay: number
  backoffFactor: number
  retryCondition?: (error: any) => boolean
}

const DEFAULT_RETRY_OPTIONS: RetryOptions = {
  maxRetries: 3,
  baseDelay: 1000,
  maxDelay: 10000,
  backoffFactor: 2,
  retryCondition: (error) => {
    // Retry on network errors, timeouts, and 5xx server errors
    if (!error.response) return true // Network error
    if (error.code === 'ECONNABORTED') return true // Timeout
    if (error.response.status >= 500) return true // Server error
    return false
  }
}

class TestCenterErrorHandler {
  /**
   * Categorize and enhance error information
   */
  categorizeError(error: any, context?: any): TestCenterError {
    let type: TestCenterError['type'] = 'unknown'
    let userMessage = 'An unexpected error occurred'
    let suggestions: string[] = []
    let recoveryActions: string[] = []
    let retryable = false

    // Network/Connection errors
    if (!error.response || error.isNetworkError || error.isConnectionError) {
      type = error.code === 'ECONNABORTED' || error.message?.includes('timeout') ? 'timeout' : 'network'
      userMessage = type === 'timeout'
        ? 'Request timed out. The server may be busy.'
        : 'Unable to connect to the server. Please check your internet connection.'

      suggestions = [
        'Check your internet connection',
        'Try again in a few moments',
        'Contact support if the problem persists'
      ]
      recoveryActions = ['retry', 'check_connection']
      retryable = true
    }
    // Authentication errors
    else if (error.response?.status === 401 || error.response?.status === 403) {
      type = 'auth'
      userMessage = 'Authentication required. Please log in again.'

      suggestions = [
        'Log out and log back in',
        'Clear your browser cache',
        'Contact an administrator for access'
      ]
      recoveryActions = ['relogin', 'clear_cache']
      retryable = false
    }
    // Validation errors
    else if (error.response?.status === 400 || error.response?.status === 422) {
      type = 'validation'
      userMessage = 'Invalid data provided. Please check your input.'

      const validationErrors = error.response?.data?.detail || error.response?.data?.errors || []
      if (Array.isArray(validationErrors)) {
        suggestions = validationErrors.map((err: any) => err.message || err.msg || err)
      } else if (typeof validationErrors === 'string') {
        suggestions = [validationErrors]
      }

      suggestions.unshift('Please review and correct the form data')
      recoveryActions = ['fix_input']
      retryable = false
    }
    // Server errors
    else if (error.response?.status >= 500) {
      type = 'server'
      userMessage = 'Server error occurred. Our team has been notified.'

      suggestions = [
        'Try again later',
        'Refresh the page',
        'Contact support with the error details'
      ]
      recoveryActions = ['retry', 'refresh_page']
      retryable = true
    }
    // Other client errors
    else if (error.response?.status >= 400) {
      type = 'unknown'
      userMessage = `Request failed: ${error.response?.statusText || 'Unknown error'}`

      suggestions = [
        'Try again',
        'Check your input data',
        'Contact support if the issue persists'
      ]
      recoveryActions = ['retry']
      retryable = false
    }

    return {
      type,
      message: error.message || 'Unknown error',
      originalError: error,
      retryable,
      userMessage,
      suggestions,
      recoveryActions
    }
  }

  /**
   * Execute operation with retry logic
   */
  async withRetry<T>(
    operation: () => Promise<T>,
    operationId: string,
    options: Partial<RetryOptions> = {},
    context?: any
  ): Promise<T> {
    const config = { ...DEFAULT_RETRY_OPTIONS, ...options }
    let lastError: any

    for (let attempt = 1; attempt <= config.maxRetries + 1; attempt++) {
      try {
        testCenterLogger.startOperation(`${operationId}_attempt_${attempt}`, {
          tab: context?.tab,
          operation: operationId,
          retryCount: attempt > 1 ? attempt - 1 : undefined
        })

        const result = await operation()

        testCenterLogger.endOperation(`${operationId}_attempt_${attempt}`, true, {
          tab: context?.tab,
          operation: operationId
        })

        return result
      } catch (error) {
        lastError = error
        const categorizedError = this.categorizeError(error, context)

        testCenterLogger.endOperation(`${operationId}_attempt_${attempt}`, false, {
          tab: context?.tab,
          operation: operationId,
          errorType: categorizedError.type
        })

        // Check if we should retry
        const shouldRetry = attempt <= config.maxRetries &&
                           config.retryCondition?.(error) &&
                           categorizedError.retryable

        if (!shouldRetry) {
          break
        }

        // Calculate delay with exponential backoff
        const delay = Math.min(
          config.baseDelay * Math.pow(config.backoffFactor, attempt - 1),
          config.maxDelay
        )

        testCenterLogger.retryAttempt(operationId, attempt, config.maxRetries, {
          tab: context?.tab,
          operation: operationId,
          errorType: categorizedError.type
        })

        await new Promise(resolve => setTimeout(resolve, delay))
      }
    }

    // All retries exhausted
    throw lastError
  }

  /**
   * Show user-friendly error message
   */
  showErrorToast(error: TestCenterError, showSuggestions: boolean = true) {
    const title = this.getErrorTitle(error.type)
    const message = showSuggestions && error.suggestions.length > 0
      ? `${error.userMessage}\n\nSuggestions:\n• ${error.suggestions.join('\n• ')}`
      : error.userMessage

    toast.error(`${title}: ${message}`)

    // Log the user-visible error
    testCenterLogger.userInteraction('error_displayed', {
      errorType: error.type,
      userMessage: error.userMessage,
      suggestionsCount: error.suggestions.length
    })
  }

  /**
   * Get error title based on type
   */
  private getErrorTitle(type: TestCenterError['type']): string {
    const titles = {
      network: 'Connection Error',
      auth: 'Authentication Error',
      validation: 'Validation Error',
      server: 'Server Error',
      timeout: 'Timeout Error',
      unknown: 'Error'
    }
    return titles[type] || 'Error'
  }

  /**
   * Attempt recovery action
   */
  async attemptRecovery(error: TestCenterError, action: string, context?: any): Promise<boolean> {
    testCenterLogger.errorRecovery(error.type, action, false, {
      tab: context?.tab,
      operation: 'error_recovery_attempt'
    })

    try {
      switch (action) {
        case 'retry':
          // Retry logic is handled by withRetry method
          return true

        case 'refresh_page':
          if (typeof window !== 'undefined') {
            window.location.reload()
            return true
          }
          return false

        case 'clear_cache':
          if (typeof localStorage !== 'undefined') {
            // Clear TestCenter-specific cache
            const keysToRemove = []
            for (let i = 0; i < localStorage.length; i++) {
              const key = localStorage.key(i)
              if (key && (key.includes('test') || key.includes('TestCenter'))) {
                keysToRemove.push(key)
              }
            }
            keysToRemove.forEach(key => localStorage.removeItem(key))
            toast.success('Cache cleared. Please refresh the page.')
            return true
          }
          return false

        case 'relogin':
          // Trigger logout
          if (typeof window !== 'undefined') {
            localStorage.removeItem('rankings_bot_auth')
            localStorage.removeItem('access_token')
            window.dispatchEvent(new CustomEvent('auth:session-expired'))
            return true
          }
          return false

        default:
          return false
      }
    } catch (recoveryError) {
      testCenterLogger.criticalError(recoveryError as Error, {
        tab: context?.tab,
        operation: 'recovery_failed',
        recoveryAction: action
      })
      return false
    }
  }

  /**
   * Handle API errors with comprehensive logging and user feedback
   */
  async handleApiError(
    error: any,
    operationId: string,
    context?: any,
    showToast: boolean = true
  ): Promise<TestCenterError> {
    const categorizedError = this.categorizeError(error, context)

    // Log the error
    testCenterLogger.criticalError(new Error(categorizedError.message), {
      tab: context?.tab,
      operation: operationId,
      errorType: categorizedError.type,
      retryable: categorizedError.retryable
    })

    // Show user-friendly error message
    if (showToast) {
      this.showErrorToast(categorizedError)
    }

    return categorizedError
  }

  /**
   * Create error boundary for React components
   */
  createErrorBoundary() {
    return class TestCenterErrorBoundary extends Error {
      constructor(message: string, context?: any) {
        super(message)
        this.name = 'TestCenterErrorBoundary'

        testCenterLogger.criticalError(this, {
          tab: context?.tab,
          operation: 'error_boundary',
          component: 'TestCenter'
        })
      }
    }
  }
}

// Create singleton instance
export const testCenterErrorHandler = new TestCenterErrorHandler()

// Export convenience functions
export const errorHandler = {
  categorizeError: testCenterErrorHandler.categorizeError.bind(testCenterErrorHandler),
  withRetry: testCenterErrorHandler.withRetry.bind(testCenterErrorHandler),
  showErrorToast: testCenterErrorHandler.showErrorToast.bind(testCenterErrorHandler),
  attemptRecovery: testCenterErrorHandler.attemptRecovery.bind(testCenterErrorHandler),
  handleApiError: testCenterErrorHandler.handleApiError.bind(testCenterErrorHandler),
  createErrorBoundary: testCenterErrorHandler.createErrorBoundary.bind(testCenterErrorHandler)
}

export default testCenterErrorHandler