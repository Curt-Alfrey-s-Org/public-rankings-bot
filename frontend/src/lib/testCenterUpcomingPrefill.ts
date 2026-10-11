import type { UpcomingEvent } from '@/api/tournamentHistory'
import type { TournamentState } from '@/lib/tournamentPersistence'
import { buildPrefillFromUpcomingEvent } from '@/lib/upcomingEventPrefill'

function mapEliminationToTestFormat(
  elim?: 'single' | 'double' | 'round_robin' | 'group_stage',
): TournamentState['format'] {
  if (elim === 'double') return 'double_elimination'
  if (elim === 'single') return 'single_elimination'
  return ''
}

function parsePrizePool(value?: string | null): number {
  if (!value) return 0
  const digits = value.replace(/[^\d.]/g, '')
  const n = parseInt(digits, 10)
  return Number.isFinite(n) ? n : 0
}

/** Map an upcoming_events row into Test Center setup fields (editable). */
export function buildTestSetupFromUpcomingEvent(
  event: UpcomingEvent,
  prev: TournamentState,
): Partial<TournamentState> {
  const prefill = buildPrefillFromUpcomingEvent(event)
  const prizeFromEvent = parsePrizePool(event.prize_pool)
  return {
    ...prev,
    name: prefill.tournament_name || prev.name,
    location: prefill.location || prev.location,
    startDate: prefill.tournament_date || prev.startDate,
    endDate: prefill.tournament_end_date || prev.endDate,
    maxPlayers: prefill.max_players ?? prev.maxPlayers,
    format: mapEliminationToTestFormat(prefill.elimination_type) || prev.format,
    association: prefill.association || prev.association,
    prizePool: prizeFromEvent > 0 ? prizeFromEvent : prev.prizePool,
    rankingSystem: prefill.association?.toUpperCase().includes('WPBA')
      ? 'WPBA Women'
      : prev.rankingSystem,
    gameType: prefill.association?.toUpperCase().includes('WPBA') ? '9-ball' : prev.gameType,
  }
}
