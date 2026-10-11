/**
 * RankingsTable Component
 * Reusable table component for displaying rankings data
 * Uses virtualization for smooth scrolling when 100+ rows (via @tanstack/react-virtual)
 */

import { useState, useRef, useMemo } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'
import { Ranking } from '@/api/rankings'

/** Minimum rows before virtualization kicks in (avoids overhead for small lists) */
const VIRTUALIZE_THRESHOLD = 100

/** Overall ranking views (WPA Men overall, WPBA, WPA Women, etc.) show Fargo and ALFA; per-column views do not. */
export const OVERALL_RANKING_TYPES = [
  'WPBA_Women', 'WPA_Women', 'WPA_Men', 'WPA_Heyball_Men', 'WPA_Heyball_Women', 'WPA_Artistic',
] as const

export interface RankingsTableProps {
  rankings: Ranking[]
  isLoading?: boolean
  onPlayerClick?: (player: string) => void
  /** When rankings are empty: 'no-data' = no rankings in system; 'search' = filtered to none */
  emptyReason?: 'no-data' | 'search'
  association?: string
  /** Ranking type (e.g. WPA_Men, WPA_Men_Yalin_8Ball). Fargo and ALFA columns shown only for overall types. */
  rankingType?: string | null
  /** Admin only: show Edit button per row; callback receives full row (with id) for editing. */
  onEditRow?: (row: Ranking) => void
  showEditButton?: boolean
  /** Whether the current user is admin+. Edit button and export. */
  isAdmin?: boolean
  /** Super admin only: show est confidence, est robustness, est rating (with trend), alfa rating. */
  isSuperAdmin?: boolean
}

/** Known columns in display order; any extra keys from API (source_data) appear after these */
const KNOWN_COLUMNS = [
  'rank',
  'name',
  'country',
  'license_number',
  'stops_played',
  'insidesp_rating',
  'matches_rated',
  'insidesp_nationality',
  'fargo_rating',
  'fargo_robustness',
  'est_rating',
  'est_rating_confidence',
  'est_rating_robustness',
  'alfa_rating',
  'position_pts',
  'score_pts',
  'discipline_pts',
  'raw_total',
  'pct_applied',
  'points',
  'date',
] as const
type SortField = (typeof KNOWN_COLUMNS)[number] | string
type SortDirection = 'asc' | 'desc'
const WPA_OVERALL_STRICT_COLUMNS = ['rank', 'name', 'country', 'license_number', 'fargo_rating', 'fargo_robustness', 'est_rating', 'est_rating_confidence', 'est_rating_robustness', 'alfa_rating', 'points'] as const

/** Columns visible only to super admin (est confidence, robustness, live est + trend, alfa). */
const SUPER_ADMIN_ONLY_COLUMNS = ['est_rating_confidence', 'est_rating_robustness', 'est_rating', 'alfa_rating'] as const

function columnLabel(key: string): string {
  const labels: Record<string, string> = {
    rank: 'Rank',
    name: 'Player Name',
    country: 'Country',
    license_number: 'License',
    stops_played: 'Stops',
    fargo_rating: 'Fargo',
    fargo_robustness: 'Robustness',
    est_rating: 'Live Est. Rating',
    est_rating_confidence: 'Est. Confidence',
    est_rating_robustness: 'Est. Robustness',
    alfa_rating: 'ALFa Rating',
    insidesp_rating: 'IS Display Rating',
    matches_rated: 'Matches rated',
    insidesp_nationality: 'IS Nationality',
    points: 'Points',
    date: 'Date',
    ranking_system: 'System',
    position_pts: 'Position Pts',
    score_pts: 'Score Pts',
    discipline_pts: 'Discipline Pts',
    raw_total: 'Raw Total',
    pct_applied: '% Applied',
    '2019_cao_pts': '2019 CAO',
    '2019_wc_pts': '2019 WC',
    '2021_nc_pts': '2021 NC',
    '2022_nc_pts': '2022 NC',
    '2022_wc_pts': '2022 WC',
    '2023_mc_pts': '2023 MC',
    '2023_sao_pts': '2023 SAO',
  }
  return labels[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

const ROW_HEIGHT_DESKTOP = 56
const ROW_HEIGHT_MOBILE = 80

export default function RankingsTable({ rankings, isLoading = false, onPlayerClick, emptyReason = 'search', association = 'WPBA', rankingType = null, onEditRow, showEditButton = false, isAdmin = false, isSuperAdmin = false }: RankingsTableProps) {
  /** Stops column only for WPBA; hidden for WPA, Heyball, Artistic, CP */
  const showStopsColumn = association === 'WPBA'

  /** Fargo and ALFA only on overall views (WPA Men overall, WPBA, WPA Women, Heyball, Artistic); hidden on per-column buttons */
  const showFargoAlfa = rankingType != null && OVERALL_RANKING_TYPES.includes(rankingType as (typeof OVERALL_RANKING_TYPES)[number])
  /** Overall buttons show only core columns (no per-tournament columns); tournaments have their own buttons */
  const useStrictOverallColumns =
    rankingType === 'WPA_Men' ||
    rankingType === 'WPA_Women' ||
    rankingType === 'WPBA_Women' ||
    rankingType === 'WPA_Heyball_Men' ||
    rankingType === 'WPA_Heyball_Women' ||
    rankingType === 'WPA_Artistic'

  /** Column list: known order first, then extra from source_data. Exclude Date and System. Exclude Fargo/ALFA for non-overall. Hide columns where every row is null/empty. Super-admin-only columns hidden for non-super-admin. */
  const displayColumns = useMemo(() => {
    // Overall buttons: only core columns; tournaments are separate buttons, not columns.
    if (useStrictOverallColumns) {
      const cols = [...WPA_OVERALL_STRICT_COLUMNS]
      if (!isSuperAdmin) {
        return cols.filter((c) => !SUPER_ADMIN_ONLY_COLUMNS.includes(c))
      }
      return cols
    }

    const first = rankings[0] as Ranking | undefined
    const known = [...KNOWN_COLUMNS]
    const extra = first ? Object.keys(first).filter((k) => !known.includes(k)) : []
    const all = [...known, ...extra.sort()]
    let filtered = all.filter((c) => c !== 'date' && c !== 'ranking_system' && c !== 'id' && c !== 'player_name')
    if (!showFargoAlfa) {
      filtered = filtered.filter((c) => c !== 'fargo_rating' && c !== 'fargo_robustness' && c !== 'est_rating' && c !== 'est_rating_confidence' && c !== 'est_rating_robustness' && c !== 'alfa_rating')
    }
    if (!showStopsColumn) {
      filtered = filtered.filter((c) => c !== 'stops_played')
    }
    if (!isSuperAdmin) {
      filtered = filtered.filter((c) => !SUPER_ADMIN_ONLY_COLUMNS.includes(c as (typeof SUPER_ADMIN_ONLY_COLUMNS)[number]))
    }
    const isInsideSpin = Boolean(rankingType?.startsWith('InsideSpin_'))
    const alwaysShow = new Set(
      isInsideSpin
        ? ['rank', 'name', 'insidesp_rating', 'matches_rated']
        : ['rank', 'name', 'points']
    )
    filtered = filtered.filter((col) => {
      if (alwaysShow.has(col)) return true
      // Hide empty points column for Inside Spin rank-position systems
      if (isInsideSpin && col === 'points') {
        return rankings.some((r) => {
          const v = r.points
          return v != null && Number(v) !== 0
        })
      }
      return rankings.some((r) => {
        const v = r[col]
        return v != null && v !== '' && v !== 'Unknown'
      })
    })
    // Prefer IS rating columns near front for Inside Spin
    if (isInsideSpin) {
      const preferred = ['rank', 'name', 'insidesp_rating', 'matches_rated', 'insidesp_nationality', 'country']
      filtered = [
        ...preferred.filter((c) => filtered.includes(c)),
        ...filtered.filter((c) => !preferred.includes(c)),
      ]
    }
    return filtered
  }, [rankings, showStopsColumn, showFargoAlfa, useStrictOverallColumns, isAdmin, isSuperAdmin, rankingType])

  const [sortField, setSortField] = useState<SortField>(
    rankingType?.startsWith('InsideSpin_') ? 'insidesp_rating' : 'rank'
  )
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc')

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('asc')
    }
  }

  const sortedRankings = useMemo(() => {
    return [...rankings].sort((a, b) => {
      const aVal: string | number = a[sortField] != null ? (typeof a[sortField] === 'string' ? (a[sortField] as string).toLowerCase() : (a[sortField] as number)) : ''
      const bVal: string | number = b[sortField] != null ? (typeof b[sortField] === 'string' ? (b[sortField] as string).toLowerCase() : (b[sortField] as number)) : ''
      if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1
      if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1
      return 0
    })
  }, [rankings, sortField, sortDirection])

  // All hooks must run before any early return (Rules of Hooks)
  const useVirtual = rankings.length >= VIRTUALIZE_THRESHOLD
  const mobileScrollRef = useRef<HTMLDivElement>(null)
  const rowVirtualizer = useVirtualizer({
    count: sortedRankings.length,
    getScrollElement: () => mobileScrollRef.current,
    estimateSize: () => ROW_HEIGHT_MOBILE,
    overscan: 10,
  })
  const virtualItems = useVirtual ? rowVirtualizer.getVirtualItems() : null

  if (isLoading) {
    return (
      <div className="bg-card border border-border rounded-xl overflow-hidden shadow-sm">
        <div className="animate-pulse p-8 text-center text-muted-foreground">
          Loading rankings...
        </div>
      </div>
    )
  }

  if (rankings.length === 0) {
    const noDataMessage = emptyReason === 'no-data'
      ? `No rankings yet for ${association}. Admins can add data via Data Input or refresh from WPBA/WPA sources.`
      : 'No rankings found matching your search.'
    return (
      <div className="bg-card border border-border rounded-xl overflow-hidden shadow-sm">
        <div className="p-8 text-center text-muted-foreground">
          {noDataMessage}
        </div>
      </div>
    )
  }

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <span className="opacity-50">⇅</span>
    return sortDirection === 'asc' ? <span>↑</span> : <span>↓</span>
  }

  const MedalBadge = ({ rank }: { rank: number }) => {
    if (rank === 1) return <span className="text-xl tracking-wide">🥇</span>
    if (rank === 2) return <span className="text-xl tracking-wide">🥈</span>
    if (rank === 3) return <span className="text-xl tracking-wide">🥉</span>
    return null
  }

  const isNumericColumn = (key: string) =>
    ['rank', 'points', 'stops_played', 'fargo_rating', 'fargo_robustness', 'alfa_rating', 'est_rating', 'est_rating_confidence', 'est_rating_robustness'].includes(key) ||
    /^col_\d+$/.test(key) || /points|rank|rating|stops|robustness|confidence/i.test(key)

  const Th = ({ field, align }: { field: SortField; align?: 'left' | 'right' | 'center' }) => {
    const a = align ?? 'center'
    const textAlign = a === 'right' ? 'text-right' : a === 'center' ? 'text-center' : 'text-left'
    const justify = a === 'right' ? 'justify-end' : a === 'center' ? 'justify-center' : 'justify-start'
    return (
      <th
        className={`px-6 py-4 ${textAlign} text-xs font-bold uppercase tracking-wider cursor-pointer hover:bg-white/10 transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-inset`}
        onClick={() => handleSort(field)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleSort(field) } }}
        tabIndex={0}
        role="button"
        aria-label={`Sort by ${columnLabel(String(field))}. Current: ${sortField === field ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none'}`}
      >
        <div className={`flex items-center gap-2 ${justify}`}>
          {columnLabel(String(field))} <SortIcon field={field} />
        </div>
      </th>
    )
  }

  const renderCell = (ranking: Ranking, col: string, isFeatured: boolean) => {
    const val = ranking[col]
    if (val == null || val === '') return <span className="text-muted-foreground">—</span>
    if (col === 'rank') {
      return (
        <div className="flex items-center gap-2">
          <span className={`font-bold text-lg ${isFeatured ? 'text-felt' : 'text-foreground'}`}>{String(val)}</span>
          {isFeatured && typeof val === 'number' && val <= 3 && <MedalBadge rank={val} />}
        </div>
      )
    }
    if (col === 'name') {
      return <span className={`${isFeatured ? 'font-semibold text-base' : ''} text-foreground`}>{String(val)}</span>
    }
    if (col === 'points' && typeof val === 'number') {
      return <div className={`font-mono ${isFeatured ? 'font-bold text-lg' : ''} text-foreground`}>{val.toFixed(2)}</div>
    }
    if (col === 'fargo_rating' && typeof val === 'number') {
      return <span className="font-mono text-foreground">{String(val)}</span>
    }
    if (col === 'alfa_rating' && typeof val === 'number') {
      return <span className="font-mono italic text-amber-400" title="Estimated from tournament placements">{val.toFixed(0)}*</span>
    }
    if (col === 'est_rating' && typeof val === 'number') {
      const trend = ranking.est_rating_trend
      const trendArrow = trend === 1 ? <span className="text-emerald-400 ml-0.5" title="Trending up">▲</span> : trend === -1 ? <span className="text-amber-400 ml-0.5" title="Trending down">▼</span> : <span className="text-slate-500 ml-0.5" title="Stable">−</span>
      return <span className="font-mono italic text-blue-400" title="Live rating updated during tournaments">{val.toFixed(0)}†{trendArrow}</span>
    }
    if (col === 'est_rating_confidence' && typeof val === 'number') {
      return <span className="font-mono text-muted-foreground">{(val * 100).toFixed(1)}%</span>
    }
    if (col === 'est_rating_robustness' && typeof val === 'number') {
      return <span className="font-mono text-muted-foreground">{val.toLocaleString()}</span>
    }
    if (col === 'fargo_robustness' && typeof val === 'number') {
      return <span className="font-mono text-foreground">{val.toLocaleString()}</span>
    }
    if (col === 'pct_applied' && typeof val === 'number') {
      return <span className="font-mono text-foreground">{val}%</span>
    }
    if (typeof val === 'number') return <span className="font-mono text-foreground">{val}</span>
    return <span className="text-muted-foreground">{String(val)}</span>
  }

  const renderDesktopRow = (ranking: Ranking, index: number) => {
    const isFeatured = ranking.rank <= 3
    return (
      <tr
        key={`${ranking.rank}-${ranking.name}-${index}`}
        className={`border-b border-border/50 last:border-b-0 transition-colors ${
          isFeatured ? 'bg-felt/5 hover:bg-felt/10' : ''
        } ${onPlayerClick ? 'cursor-pointer hover:bg-accent/30 focus-within:bg-accent/20' : ''}`}
        onClick={() => onPlayerClick?.(ranking.name)}
        onKeyDown={(e) => {
          if (onPlayerClick && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault()
            onPlayerClick(ranking.name)
          }
        }}
        tabIndex={onPlayerClick ? 0 : undefined}
        role={onPlayerClick ? 'button' : undefined}
        aria-label={onPlayerClick ? `View details for ${ranking.name}` : undefined}
      >
        {displayColumns.map((col) => (
          <td
            key={col}
            className={`px-6 py-4 ${col === 'name' ? 'text-left' : 'text-center'}`}
          >
            {renderCell(ranking, col, isFeatured)}
          </td>
        ))}
        {showEditButton && onEditRow && (
          <td className="px-2 py-4 text-center" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              onClick={() => onEditRow(ranking)}
              className="px-2 py-1 text-xs font-medium rounded bg-muted hover:bg-muted/80 text-foreground"
              aria-label={`Edit ${ranking.name}`}
            >
              Edit
            </button>
          </td>
        )}
      </tr>
    )
  }

  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden shadow-sm">
      {/* Desktop table: single table so header and body columns stay aligned */}
      <div className="hidden md:block overflow-x-auto -mx-1 px-1">
        <div className="overflow-auto" style={{ maxHeight: '60vh' }}>
          <table className="w-full min-w-[32rem] border-collapse">
            <thead className="border-b-2 border-felt bg-gradient-to-r from-slate-900 to-slate-800 text-white sticky top-0 z-10 shadow-sm">
              <tr>
                {displayColumns.map((col) => (
                  <Th key={col} field={col} align={col === 'name' ? 'left' : 'center'} />
                ))}
                {showEditButton && onEditRow && (
                  <th className="px-2 py-4 text-center text-xs font-bold uppercase tracking-wider w-16">Edit</th>
                )}
              </tr>
            </thead>
            <tbody>
              {sortedRankings.map((ranking, index) => renderDesktopRow(ranking, index))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Mobile: virtualized card stack when 100+ rows */}
      <div
        ref={mobileScrollRef}
        className="md:hidden overflow-auto"
        style={{ maxHeight: '60vh' }}
      >
        {useVirtual && virtualItems ? (
          <div
            style={{ height: `${rowVirtualizer.getTotalSize()}px`, position: 'relative' }}
            className="divide-y divide-border"
          >
            {virtualItems.map((virtualRow) => {
              const ranking = sortedRankings[virtualRow.index]
              const isFeatured = ranking.rank <= 3
              return (
                <div
                  key={virtualRow.key}
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    transform: `translateY(${virtualRow.start}px)`,
                    height: virtualRow.size,
                  }}
                  className={`p-4 flex flex-col justify-center transition-colors ${
                    isFeatured ? 'bg-felt/5' : ''
                  } ${onPlayerClick ? 'cursor-pointer hover:bg-accent/30 active:bg-accent/50' : ''}`}
                  onClick={() => onPlayerClick?.(ranking.name)}
                >
                  <div className="flex items-start justify-between mb-1">
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-1">
                        <span className={`text-2xl font-bold ${isFeatured ? 'text-felt' : 'text-foreground'}`}>
                          {ranking.rank}
                        </span>
                        {isFeatured && <MedalBadge rank={ranking.rank} />}
                      </div>
                      <div>
                        <div className={`${isFeatured ? 'font-semibold text-base' : ''} text-foreground`}>
                          {ranking.name}
                        </div>
                        <div className="text-sm text-muted-foreground">{ranking.country || '—'}</div>
                      </div>
                    </div>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-muted-foreground">{ranking.date || '—'}</span>
                    <div className="flex items-center gap-2">
                      {showEditButton && onEditRow && (
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); onEditRow(ranking) }}
                          className="px-2 py-1 text-xs font-medium rounded bg-muted hover:bg-muted/80 text-foreground"
                        >
                          Edit
                        </button>
                      )}
                      <span className={`font-mono ${isFeatured ? 'font-bold text-base' : ''} text-foreground`}>
                        {ranking.points.toFixed(2)}
                      </span>
                      <span className="text-sm text-muted-foreground">pts</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="divide-y divide-border">
            {sortedRankings.map((ranking, index) => {
            const isFeatured = ranking.rank <= 3
            return (
              <div
                key={`${ranking.rank}-${ranking.name}-${index}`}
                className={`p-4 min-h-[64px] flex flex-col justify-center transition-colors ${
                  isFeatured ? 'bg-felt/5' : ''
                } ${onPlayerClick ? 'cursor-pointer hover:bg-accent/30 active:bg-accent/50' : ''}`}
                onClick={() => onPlayerClick?.(ranking.name)}
              >
                <div className="flex items-start justify-between mb-1">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1">
                      <span className={`text-2xl font-bold ${isFeatured ? 'text-felt' : 'text-foreground'}`}>
                        {ranking.rank}
                      </span>
                      {isFeatured && <MedalBadge rank={ranking.rank} />}
                    </div>
                    <div>
                      <div className={`${isFeatured ? 'font-semibold text-base' : ''} text-foreground`}>
                        {ranking.name}
                      </div>
                      <div className="text-sm text-muted-foreground">{ranking.country || '—'}</div>
                    </div>
                  </div>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-muted-foreground">{ranking.date || '—'}</span>
                  <div className="flex items-center gap-2">
                    {showEditButton && onEditRow && (
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); onEditRow(ranking) }}
                        className="px-2 py-1 text-xs font-medium rounded bg-muted hover:bg-muted/80 text-foreground"
                      >
                        Edit
                      </button>
                    )}
                    <span className={`font-mono ${isFeatured ? 'font-bold text-base' : ''} text-foreground`}>
                      {ranking.points.toFixed(2)}
                    </span>
                    <span className="text-sm text-muted-foreground ml-2">pts</span>
                  </div>
                </div>
              </div>
            )
          })}
          </div>
        )}
      </div>
    </div>
  )
}
