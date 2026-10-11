/**
 * Creator & business attribution — visible to all users (guests and logged-in).
 * Attract more business: Example Example, alfaqd.com, GitHub, X, self-hosted messaging.
 */

const CREATOR_NAME = 'Example Example'
const BUSINESS_URL = 'https://alfaqd.com'
const GITHUB_URL = 'https://github.com/example-owner-s-Org'
const X_URL = 'https://x.com/example'

export default function CreatorFooter() {
  return (
    <footer
      className="flex-shrink-0 border-t border-border bg-card/90 backdrop-blur-sm px-3 sm:px-4 py-3 text-center text-xs text-muted-foreground"
      role="contentinfo"
      aria-label="Creator and business"
    >
      <p className="mb-1">
        Built by{' '}
        <a
          href={BUSINESS_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline focus:outline-none focus:ring-2 focus:ring-ring rounded"
        >
          {CREATOR_NAME}
        </a>
        {' · '}
        <a
          href={BUSINESS_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline focus:outline-none focus:ring-2 focus:ring-ring rounded"
        >
          alfaqd.com
        </a>
        {' · '}
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline focus:outline-none focus:ring-2 focus:ring-ring rounded"
          title="GitHub"
        >
          GitHub
        </a>
        {' · '}
        <a
          href={X_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline focus:outline-none focus:ring-2 focus:ring-ring rounded"
          title="@example"
        >
          X
        </a>
      </p>
      <p className="text-muted-foreground/90">
        WPBA & WPA rankings · self-hosted by alfaqd.com. Built for the sport by {CREATOR_NAME}.
      </p>
    </footer>
  )
}
