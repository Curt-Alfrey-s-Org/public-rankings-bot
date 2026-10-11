/**
 * Error boundary for the Rankings page only.
 * Logs the error (signal trail for debugging) and shows fallback with buttons
 * that use reload/href so they work even if React state is broken.
 */

import { Component, ErrorInfo, ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
}

/** Log to console for debugging; in dev also show component stack */
function logRankingsError(error: Error, errorInfo: ErrorInfo | null) {
  const payload = {
    message: error?.message,
    stack: error?.stack,
    componentStack: errorInfo?.componentStack ?? null,
    timestamp: new Date().toISOString(),
  }
  console.error('[Rankings] Error boundary caught:', payload)
  if (typeof window !== 'undefined') {
    (window as any).__rankingsLastError = payload
  }
}

export default class RankingsErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error, errorInfo: null }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    logRankingsError(error, errorInfo)
    this.setState((s) => (s.errorInfo ? s : { ...s, errorInfo }))
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
  }

  render() {
    if (this.state.hasError && this.state.error) {
      const err = this.state.error
      const msg = err?.message ?? 'Unknown error'
      return (
        <div
          className="flex flex-col items-center justify-center min-h-[50vh] px-4 bg-slate-950 text-slate-50"
          role="alert"
        >
          <div className="bg-card border border-destructive rounded-lg p-6 max-w-lg w-full">
            <h2 className="text-lg font-bold text-red-400 mb-2">Rankings: something went wrong</h2>
            <p className="text-sm text-slate-400 mb-2 break-words">{msg}</p>
            {import.meta.env.DEV && this.state.errorInfo?.componentStack && (
              <details className="mb-4">
                <summary className="cursor-pointer text-xs text-slate-500">Component stack</summary>
                <pre className="mt-1 text-xs bg-slate-900 p-2 rounded overflow-auto max-h-32 text-slate-300">
                  {this.state.errorInfo.componentStack}
                </pre>
              </details>
            )}
            <div className="flex flex-wrap gap-3">
              <button
                type="button"
                onClick={this.handleRetry}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
                aria-label="Try again"
              >
                Try again
              </button>
              <button
                type="button"
                onClick={() => { window.location.href = '/rankings' }}
                className="px-4 py-2 bg-muted text-muted-foreground rounded-lg hover:bg-muted/80 transition-colors"
                aria-label="Go to rankings"
              >
                Go to Rankings
              </button>
              <button
                type="button"
                onClick={() => {
                  const t = err?.message + '\n' + (err?.stack ?? '') + (this.state.errorInfo?.componentStack ?? '')
                  navigator.clipboard?.writeText(t).catch(() => {})
                }}
                className="px-4 py-2 border border-border rounded-lg text-muted-foreground hover:bg-muted/50 transition-colors text-sm"
                aria-label="Copy error"
              >
                Copy error
              </button>
            </div>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
