import type { UpcomingEvent, UpcomingEnrichmentHint } from '@/api/tournamentHistory'

export type PrefillSource = {
  field: string
  label: string
  source: string
  sourceUrl?: string
}

export type UpcomingPrefillResult = {
  tournament_name: string
  tournament_date: string
  tournament_end_date: string
  location: string
  max_players?: number
  elimination_type?: 'single' | 'double' | 'round_robin' | 'group_stage'
  notes: string
  association?: string
  sources: PrefillSource[]
}

function isoDate(value?: string | null): string | undefined {
  if (!value) return undefined
  const d = value.slice(0, 10)
  return /^\d{4}-\d{2}-\d{2}$/.test(d) ? d : undefined
}

function hintLabel(field: string): string {
  switch (field) {
    case 'max_players':
      return 'Player count'
    case 'elimination_type':
      return 'Format'
    case 'location':
      return 'Location'
    default:
      return field
  }
}

function eliminationFromHint(value: unknown): UpcomingPrefillResult['elimination_type'] | undefined {
  const v = String(value || '').toLowerCase()
  if (v === 'double') return 'double'
  if (v === 'single') return 'single'
  if (v === 'round_robin') return 'round_robin'
  if (v === 'group_stage') return 'group_stage'
  return undefined
}

/** Build editable wizard defaults from an upcoming / future-tournament row. */
export function buildPrefillFromUpcomingEvent(event: UpcomingEvent): UpcomingPrefillResult {
  const start = isoDate(event.start_date) ?? isoDate(event.date) ?? new Date().toISOString().slice(0, 10)
  const end = isoDate(event.end_date) ?? start
  const sources: PrefillSource[] = []

  const hints = event.enrichment?.hints ?? []
  for (const h of hints as UpcomingEnrichmentHint[]) {
    sources.push({
      field: h.field,
      label: hintLabel(h.field),
      source: h.source,
      sourceUrl: h.source_url,
    })
  }

  let maxPlayers = event.max_players
  let eliminationType: UpcomingPrefillResult['elimination_type']

  for (const h of hints as UpcomingEnrichmentHint[]) {
    if (h.field === 'max_players' && typeof h.value === 'number') {
      maxPlayers = h.value
    }
    if (h.field === 'elimination_type') {
      eliminationType = eliminationFromHint(h.value)
    }
  }

  const noteParts: string[] = []
  if (event.prize_pool) noteParts.push(`Prize pool (listing): ${event.prize_pool}`)
  if (event.format) noteParts.push(`Format (listing): ${event.format}`)
  if (event.url) noteParts.push(`Source: ${event.url}`)
  const matched = event.enrichment?.matched_articles ?? []
  if (matched.length > 0) {
    noteParts.push(
      `News: ${matched.slice(0, 2).map((a) => a.title).join('; ')}`,
    )
  }

  return {
    tournament_name: event.name || '',
    tournament_date: start,
    tournament_end_date: end,
    location: event.location || event.venue_address || '',
    max_players: maxPlayers,
    elimination_type: eliminationType,
    notes: noteParts.join('\n'),
    association: event.association,
    sources,
  }
}

export function upcomingEventKey(event: UpcomingEvent): string {
  return String(event.event_id ?? event.id ?? event.name)
}
