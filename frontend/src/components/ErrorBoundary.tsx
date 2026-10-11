import React, { Component, ErrorInfo, ReactNode } from 'react'
import { AlertTriangle, RefreshCw, Home } from 'lucide-react'
import { logger } from '@/lib/logger'

interface Props {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
  showDetails?: boolean
}

interface State {
  hasError: boolean
  error?: Error
  errorInfo?: ErrorInfo
  errorId?: string
}

/**
 * Comprehensive error boundary that catches JavaScript errors anywhere in the component tree
 * Provides user-friendly error messages and recovery options
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(error: Error): State {
    // Generate unique error ID for tracking
    const errorId = `error_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    return {
      hasError: true,
      error,
      errorId
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo)

    this.setState({ errorInfo })

    if (this.props.onError) {
      this.props.onError(error, errorInfo)
    }

    this.reportError(error, errorInfo)

    const isChunk =
      error.message?.includes('Failed to fetch dynamically imported module') ||
      error.message?.includes('Loading chunk') ||
      error.message?.includes('ChunkLoadError')
    if (isChunk) {
      const key = '__eb_chunk_reload__'
      const last = Number(sessionStorage.getItem(key) || '0')
      if (Date.now() - last > 10_000) {
        sessionStorage.setItem(key, String(Date.now()))
        window.location.reload()
        return
      }
    }
  }

  private reportError(error: Error, errorInfo: ErrorInfo) {
    try {
      // Create error report
      const errorReport = {
        message: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
        url: window.location.href,
        errorId: this.state.errorId,
        // Additional context
        viewport: {
          width: window.innerWidth,
          height: window.innerHeight
        },
        online: navigator.onLine,
        localStorage: this.checkLocalStorage()
      }

      // Log to console in development
      if (import.meta.env.DEV) {
        console.group('🚨 Error Report')
        console.error('Error Details:', errorReport)
        console.groupEnd()
      }

      const sentry = (window as any).Sentry
      if (sentry?.captureException) {
        sentry.captureException(error, {
          extra: errorReport,
          contexts: { react: { componentStack: errorInfo.componentStack } },
        })
      }
      logger.error('React error boundary captured exception', error, {
        errorId: this.state.errorId,
        componentStack: errorInfo.componentStack,
      })

    } catch (reportingError) {
      console.error('Failed to report error:', reportingError)
    }
  }

  private checkLocalStorage(): boolean {
    try {
      const test = '__error_boundary_test__'
      localStorage.setItem(test, 'test')
      localStorage.removeItem(test)
      return true
    } catch (error) {
      logger.warn('ErrorBoundary localStorage availability check failed', undefined, error as Error)
      return false
    }
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: undefined, errorInfo: undefined, errorId: undefined })
  }

  private handleReload = () => {
    window.location.reload()
  }

  private handleGoHome = () => {
    window.location.href = '/'
  }

  render() {
    if (this.state.hasError) {
      // Custom fallback UI — inject onRetry so fallback can offer "Try again"
      if (this.props.fallback) {
        if (React.isValidElement(this.props.fallback)) {
          const isChunkLoadError =
            this.state.error?.message?.includes('Failed to fetch dynamically imported module') ||
            this.state.error?.message?.includes('Loading chunk') ||
            this.state.error?.message?.includes('ChunkLoadError')
          return React.cloneElement(
            this.props.fallback as React.ReactElement<{
              onRetry?: () => void
              error?: Error
              isChunkLoadError?: boolean
            }>,
            {
              onRetry: this.handleRetry,
              error: this.state.error,
              isChunkLoadError,
            },
          )
        }
        return this.props.fallback
      }

      // Chunk load / dynamic import failure (often when network or dev server is flaky)
      const isChunkLoadError =
        this.state.error?.message?.includes('Failed to fetch dynamically imported module') ||
        this.state.error?.message?.includes('Loading chunk') ||
        this.state.error?.message?.includes('ChunkLoadError')

      // Default error UI
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
          <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-6 text-center">
            <div className="flex justify-center mb-4">
              <AlertTriangle className="h-12 w-12 text-red-500" />
            </div>

            <h1 className="text-xl font-semibold text-gray-900 mb-2">
              {isChunkLoadError ? 'Page failed to load' : 'Something went wrong'}
            </h1>

            <p className="text-gray-600 mb-6">
              {isChunkLoadError
                ? 'A required part of the app could not be loaded. This can happen when the connection is slow or the server is busy. Try refreshing the page.'
                : "We encountered an unexpected error. This has been reported and we're working to fix it."}
            </p>

            <div className="space-y-3">
              <button
                onClick={this.handleRetry}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Try Again
              </button>

              <button
                onClick={this.handleReload}
                className="w-full px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors flex items-center justify-center"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Reload Page
              </button>

              <button
                onClick={this.handleGoHome}
                className="w-full px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors flex items-center justify-center"
              >
                <Home className="h-4 w-4 mr-2" />
                Go Home
              </button>
            </div>

            {this.props.showDetails && this.state.error && (
              <details className="mt-6 text-left">
                <summary className="cursor-pointer text-sm text-gray-500 hover:text-gray-700">
                  Technical Details
                </summary>
                <div className="mt-2 p-3 bg-gray-pool_opt_in rounded text-xs font-mono text-gray-800 overflow-auto max-h-40">
                  <div className="mb-2">
                    <strong>Error:</strong> {this.state.error.message}
                  </div>
                  {this.state.errorId && (
                    <div className="mb-2">
                      <strong>Error ID:</strong> {this.state.errorId}
                    </div>
                  )}
                  {this.state.error.stack && (
                    <pre className="whitespace-pre-wrap text-xs">
                      {this.state.error.stack}
                    </pre>
                  )}
                </div>
              </details>
            )}
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

/**
 * Higher-order component to wrap components with error boundary
 */
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  errorBoundaryProps?: Omit<Props, 'children'>
) {
  const WrappedComponent = (props: P) => (
    <ErrorBoundary {...errorBoundaryProps}>
      <Component {...props} />
    </ErrorBoundary>
  )

  WrappedComponent.displayName = `withErrorBoundary(${Component.displayName || Component.name})`

  return WrappedComponent
}

/**
 * Hook to manually trigger error boundary (for testing)
 */
export const useErrorBoundary = () => {
  const [, setState] = React.useState()

  return React.useCallback((error: Error) => {
    setState(() => {
      throw error
    })
  }, [])
}

export default ErrorBoundary