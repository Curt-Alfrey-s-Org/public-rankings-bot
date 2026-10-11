import { Link } from 'react-router-dom'

interface PageErrorFallbackProps {
  onRetry?: () => void
  /** Set by ErrorBoundary when cloning this fallback */
  error?: Error
  isChunkLoadError?: boolean
}

async function clearSiteCachesAndReload(): Promise<void> {
  try {
    if ('serviceWorker' in navigator) {
      const regs = await navigator.serviceWorker.getRegistrations()
      await Promise.all(regs.map((r) => r.unregister()))
    }
  } catch {
    /* ignore */
  }
  try {
    const keys = await caches.keys()
    await Promise.all(keys.map((k) => caches.delete(k)))
  } catch {
    /* ignore */
  }
  window.location.reload()
}

/**
 * Route-level error fallback. "Try again" resets the boundary; "Go to Dashboard" navigates away.
 * ErrorBoundary injects onRetry, error, and isChunkLoadError when using this as fallback.
 */
export default function PageErrorFallback({
  onRetry,
  error,
  isChunkLoadError,
}: PageErrorFallbackProps) {
  const chunk = Boolean(isChunkLoadError)

  return (
    <div
      className="flex flex-col items-center justify-center min-h-[40vh] px-4"
      role="alert"
      aria-live="assertive"
    >
      <div className="bg-card border border-destructive rounded-lg p-6 max-w-md w-full">
        <h2 className="text-lg font-bold text-destructive mb-2">
          {chunk ? 'App update needed' : 'Something went wrong'}
        </h2>
        <p className="text-sm text-muted-foreground mb-4">
          {chunk ? (
            <>
              A part of the site failed to download (often right after we publish an update, or if a
              deploy did not finish). Try a full reload. If it keeps happening, use &quot;Clear saved site
              data &amp; reload&quot; once.
            </>
          ) : (
            <>This page encountered an error. Try again or go back to the dashboard.</>
          )}
        </p>
        {chunk && error?.message && (
          <p className="text-xs text-muted-foreground/80 mb-4 font-mono break-all">{error.message}</p>
        )}
        <div className="flex flex-col gap-2">
          {chunk && (
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="w-full px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
              aria-label="Reload the page"
            >
              Reload page
            </button>
          )}
          {chunk && (
            <button
              type="button"
              onClick={() => void clearSiteCachesAndReload()}
              className="w-full px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors"
              aria-label="Clear caches and reload"
            >
              Clear saved site data &amp; reload
            </button>
          )}
          <div className="flex gap-3 flex-wrap">
            {onRetry && (
              <button
                onClick={onRetry}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
                aria-label="Try loading this page again"
              >
                Try again
              </button>
            )}
            <Link
              to="/"
              className="px-4 py-2 bg-muted text-muted-foreground rounded-lg hover:bg-muted/80 transition-colors inline-flex items-center"
              aria-label="Go to dashboard"
            >
              Go to Dashboard
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
