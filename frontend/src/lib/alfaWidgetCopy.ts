import type { AskAIPageId } from '@alfa-ai/chat-widget'

/** ALFa avatar with ?v=build_hash so CDN/PWA do not serve a stale PNG after deploy. */
export function alfaAvatarSrc(): string {
  const base = '/branding/alfa-ai-avatar.png'
  const buildHash = (import.meta.env.VITE_API_BUILD_HASH as string | undefined)?.trim()
  if (buildHash && buildHash !== 'unknown') {
    return `${base}?v=${encodeURIComponent(buildHash)}`
  }
  return base
}

export function rankingsPageHint(page: AskAIPageId): string {
  switch (page) {
    case 'player-performance':
      return 'Questions about this player, rankings, and performance stats'
    case 'head-to-head':
      return 'Questions about head-to-head matchups and comparisons'
    case 'tournament-history':
      return 'Questions about tournament results and placement history'
    default:
      return 'App help, tiers and deals - or name a player (e.g. show stats for …)'
  }
}

export function rankingsPlaceholder(page: AskAIPageId): string {
  switch (page) {
    case 'player-performance':
      return 'Ask about this player, ratings, placements, or trends...'
    case 'head-to-head':
      return 'Ask about these two players or their matchup history...'
    case 'tournament-history':
      return 'Ask about tournaments, finishes, or career history...'
    default:
      return 'Ask ALFa - features, tiers, or “stats for Player Name”...'
  }
}

export function rankingsEmptyStateHint(page: AskAIPageId): string {
  switch (page) {
    case 'player-performance':
      return 'Ask about rankings, ALFa rating, placements, or what the stats mean.'
    case 'head-to-head':
      return 'Ask who has the edge, recent form, or how to read the comparison.'
    case 'tournament-history':
      return 'Ask about finishes, trends, or what stands out in this history.'
    default:
      return 'Tip: name a player in your question, or open Player Performance / Head-to-Head / Tournament History.'
  }
}
