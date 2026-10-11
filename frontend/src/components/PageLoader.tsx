/**
 * Centered loading spinner for Suspense fallback (lazy route loading).
 * Used during code-split route transitions.
 */
export default function PageLoader() {
  return (
    <div
      className="flex flex-col items-center justify-center min-h-[40vh] gap-4"
      role="status"
      aria-label="Loading page"
    >
      <div
        className="w-10 h-10 border-2 border-primary border-t-transparent rounded-full animate-spin"
        aria-hidden
      />
      <p className="text-sm text-muted-foreground">Loading…</p>
    </div>
  )
}
