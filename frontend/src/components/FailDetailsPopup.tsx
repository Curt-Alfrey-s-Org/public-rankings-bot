import { useQueryClient } from '@tanstack/react-query'
import type { RunTestsResponse } from '@/api/system'

interface FailDetailsPopupProps {
  isOpen: boolean
  onClose: () => void
}

export default function FailDetailsPopup({ isOpen, onClose }: FailDetailsPopupProps) {
  const queryClient = useQueryClient()
  const lastResult = queryClient.getQueryData<RunTestsResponse>(['last-test-result'])
  const failedTests = lastResult?.failed_tests ?? []
  const hasFails = failedTests.length > 0

  if (!isOpen) return null

  const copyToClipboard = () => {
    const text = failedTests
      .map((t) => `✗ ${t.name}${t.error ? `\n  ${t.error}` : ''}`)
      .join('\n\n')
    navigator.clipboard.writeText(text)
  }

  return (
    <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-lg w-full max-w-2xl max-h-[85vh] overflow-hidden shadow-xl mx-4">
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-lg font-bold">Self-check fail details</h2>
          <div className="flex items-center gap-2">
            {hasFails && (
              <button
                onClick={copyToClipboard}
                className="px-3 py-1.5 text-sm bg-muted hover:bg-muted/80 rounded transition-colors"
              >
                Copy all
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1 hover:bg-accent rounded transition-colors"
              aria-label="Close"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <div className="p-4 overflow-y-auto max-h-[70vh]">
          {!lastResult ? (
            <p className="text-muted-foreground text-sm">
              No self-check data yet. Wait for system health to load, then open this again.
            </p>
          ) : !hasFails ? (
            <p className="text-green-500 text-sm">Last self-check had no failures.</p>
          ) : (
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">
                Last run: {lastResult.passed}/{lastResult.total} passed, {lastResult.failed} failed
                {lastResult.duration_s != null && ` • ${lastResult.duration_s}s`}
              </p>
              <div className="space-y-3">
                {failedTests.map((test, index) => (
                  <div
                    key={index}
                    className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-left"
                  >
                    <div className="font-medium text-red-400 mb-1">✗ {test.name}</div>
                    {test.error && (
                      <pre className="mt-2 text-sm text-muted-foreground whitespace-pre-wrap break-words font-mono bg-muted/30 p-3 rounded">
                        {test.error}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="p-4 border-t border-border flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-muted text-muted-foreground rounded-lg hover:bg-muted/80 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
