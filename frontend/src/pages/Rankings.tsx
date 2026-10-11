/**
 * Rankings Page Component
 * Main page for displaying WPBA Women, WPA Women, and WPA Men rankings
 *
 * Doc refs (AI / maintainers): docs/RANKINGS_DATA_DOC_HOOKS.md; docs/WPA_RANKINGS_DATA_FLOW.md;
 *   docs/WPBA_DATA_FLOW.md
 */

import { useState, useMemo } from 'react'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import RankingsTable from '@/components/RankingsTable'
import PlayerDetailModal from '@/components/PlayerDetailModal'
import { useAuth } from '@/contexts/AuthContext'
import { type Ranking } from '@/api/rankings'
import { useRankingsApi, useApiPathPrefixes } from '@/contexts/ApiPathContext'
import { useUiCustomization } from '@/contexts/UiCustomizationContext'
import { logger } from '@/lib/logger'
import { toast } from '@/lib/toast'

interface RankingsPageProps {
  sidebarOpen?: boolean
  onSidebarToggle?: () => void
}

/** TypeScript type guards for per-tournament ranking_system strings.
 *  Menu rendering is driven by the API (wpba-tournament-systems, wpa-men/wpa-women-tournament-systems, etc.),
 *  which return the 10 most recent active tournaments sorted newest-first — NOT by these arrays.
 *  They exist only so TypeScript accepts dynamic system strings. */
const WPA_MEN_COLUMN_TYPES = [
  'WPA_Men_10B_Polish',
  'WPA_Men_Maldives',
  'WPA_Men_HCM',
  'WPA_Men_9B_IntlOpen',
  'WPA_Men_10B_Qatar',
  'WPA_Men_Yalin_8Ball',
  'WPA_Men_Predator_10B',
  'WPA_Men_JPBA_JapanOpen',
  'WPA_Men_9B_ChinaOpen',
  'WPA_Men_9B_WorldChamp',
  'WPA_Men_10B_Indonesia',
  'WPA_Men_Kamui_LasVegas',
] as const

/** WPA Women per-column systems (one button per event column) */
const WPA_WOMEN_COLUMN_TYPES = [
  'WPA_Women_9B_WorldChamp',
  'WPA_Women_LittleMonster',
  'WPA_Women_AllJapan57',
  'WPA_Women_DRPoolTour',
  'WPA_Women_10B_Predator',
  'WPA_Women_9Ball',
  'WPA_Women_JapanOpen',
  'WPA_Women_ChinaOpen',
  'WPA_Women_WPBA_Colorado',
  'WPA_Women_10B_Indonesia',
  'WPA_Women_8Ball',
  'WPA_Women_WPBA_SEMasters',
  'WPA_Women_WPBA_RaxxMezz',
  'WPA_Women_Kamui_LasVegas',
  'WPA_Women_WPBA_IronCity',
] as const

/** WPA Heyball Men per-column systems (one button per event column) */
const WPA_HEYBALL_MEN_COLUMN_TYPES = [
  'WPA_Heyball_Men_WorldChamp',
  'WPA_Heyball_Men_10Ball',
  'WPA_Heyball_Men_Asian',
  'WPA_Heyball_Men_European',
  'WPA_Heyball_Men_NorthAmerican',
  'WPA_Heyball_Men_Oceania',
  'WPA_Heyball_Men_PanAmerican',
  'WPA_Heyball_Men_Champions',
] as const

/** WPA Heyball Women per-column systems (one button per event column) */
const WPA_HEYBALL_WOMEN_COLUMN_TYPES = [
  'WPA_Heyball_Women_WorldChamp',
  'WPA_Heyball_Women_Asian',
  'WPA_Heyball_Women_European',
  'WPA_Heyball_Women_NorthAmerican',
  'WPA_Heyball_Women_Oceania',
  'WPA_Heyball_Women_PanAmerican',
  'WPA_Heyball_Women_Champions',
] as const

/** WPBA Women per-tournament systems (one button per tournament).
 *  Menu rendering is API-driven (wpba-tournament-systems); this list only keeps the
 *  TypeScript union in parity with the backend WPBA_WOMEN_COLUMN_MAPPING. */
const WPBA_WOMEN_COLUMN_TYPES = [
  'WPBA_Women_ClassicBilliards2026',
  'WPBA_Women_IronCityVI',
  'WPBA_Women_Jacoby2025',
  'WPBA_Women_Colorado2025',
  'WPBA_Women_SoaringEagle2025',
  'WPBA_Women_RaxxMezz2025',
  'WPBA_Women_IronCityV',
  'WPBA_Women_Jacoby2024',
  'WPBA_Women_CapitalCity2024',
  'WPBA_Women_NAPA2024',
  'WPBA_Women_Colorado2024',
  'WPBA_Women_Rotating11th',
  'WPBA_Women_Palmetto',
  'WPBA_Women_DRPool2025',
] as const

/** WPA Artistic Pool per-event systems (one button per tournament) */
const WPA_ARTISTIC_COLUMN_TYPES = [
  'WPA_Artistic_2019_CAO',
  'WPA_Artistic_2019_WC',
  'WPA_Artistic_2021_NC',
  'WPA_Artistic_2022_NC',
  'WPA_Artistic_2022_WC',
  'WPA_Artistic_2023_MC',
  'WPA_Artistic_2023_SAO',
] as const

type WpbaWomenColumnType = typeof WPBA_WOMEN_COLUMN_TYPES[number]
type WpaMenColumnType = typeof WPA_MEN_COLUMN_TYPES[number]
type WpaWomenColumnType = typeof WPA_WOMEN_COLUMN_TYPES[number]
type WpaHeyballMenColumnType = typeof WPA_HEYBALL_MEN_COLUMN_TYPES[number]
type WpaHeyballWomenColumnType = typeof WPA_HEYBALL_WOMEN_COLUMN_TYPES[number]
type WpaArtisticColumnType = typeof WPA_ARTISTIC_COLUMN_TYPES[number]

// `WpbaWomenColumnDynamic` is a catch-all: WPBA per-event systems are discovered
// at runtime from the rolling-window PDF header (e.g. a newly published event ->
// `WPBA_Women_<Event>`). Accepting any such id keeps the API-driven menu casts
// honest so a new event needs NO frontend code change. The explicit
// `WpbaWomenColumnType` literals above stay listed only to keep the `.includes()`
// type-guards (and existing RANKING_TYPES entries) precise.
type WpbaWomenColumnDynamic = `WPBA_Women_${string}`
// Inside Spin (insidesp.in) rating systems: per-discipline + cohort overall lists.
// Catch-all template keeps the menu/switch casts simple (InsideSpin_<suffix>).
type InsideSpinType = `InsideSpin_${string}`

// Digital Pool historical pro_world_rankings (2021-2023 snapshots): rank-only.
type DigitalPoolType = `DigitalPool_${string}`

type RankingType = 'WPBA_Women' | 'WPA_Women' | 'WPA_Men' | 'WPA_Heyball_Men' | 'WPA_Heyball_Women' | 'WPA_Artistic' | 'Competitors_Pool_9Ball' | 'Competitors_Pool_10Ball' | 'Competitors_Pool_8Ball' | 'Competitors_Pool_Women_9Ball' | 'Competitors_Pool_Men_9Ball' | InsideSpinType | DigitalPoolType | WpbaWomenColumnType | WpbaWomenColumnDynamic | WpaMenColumnType | WpaWomenColumnType | WpaHeyballMenColumnType | WpaHeyballWomenColumnType | WpaArtisticColumnType

/** Drill-down level: top = WPBA/WPA/Heyball; then category submenus; leaf = specific ranking */
type DrillLevel = 'top' | 'wpba' | 'wpa' | 'wpa_women' | 'wpa_men' | 'wpa_artistic' | 'heyball' | 'heyball_women' | 'heyball_men' | 'insidesp' | 'digitalpool'

/** Menu item: either a submenu (drill) or a leaf ranking */
type DrillItem =
  | { kind: 'drill'; id: DrillLevel; label: string; style: 'wpba' | 'wpa' | 'heyball' }
  | { kind: 'leaf'; type: RankingType; label: string; style: 'wpba' | 'wpa' | 'heyball' }

const WPBA_OVERALL_ITEM: DrillItem = { kind: 'leaf', type: 'WPBA_Women', label: '👑 WPBA Women (overall)', style: 'wpba' }

const DRILL_MENUS: Record<Exclude<DrillLevel, 'top'>, DrillItem[]> = {
  wpba: [WPBA_OVERALL_ITEM],
  wpa: [
    { kind: 'drill', id: 'wpa_women', label: '🌍 WPA Women', style: 'wpa' },
    { kind: 'drill', id: 'wpa_men', label: '🎱 WPA Men', style: 'wpa' },
  ],
  // Placeholders: per-event leaves come from API (wpa-women-tournament-systems / wpa-men-tournament-systems).
  wpa_women: [{ kind: 'leaf', type: 'WPA_Women', label: '🌍 WPA Women (overall)', style: 'wpa' }],
  wpa_men: [{ kind: 'leaf', type: 'WPA_Men', label: '🎱 WPA Men (overall)', style: 'wpa' }],
  wpa_artistic: [
    { kind: 'leaf', type: 'WPA_Artistic', label: '🎨 Artistic Pool (overall)', style: 'wpa' },
    { kind: 'leaf', type: 'WPA_Artistic_2023_SAO', label: '🎨 2023 South African Open', style: 'wpa' },
    { kind: 'leaf', type: 'WPA_Artistic_2023_MC', label: '🎨 2023 Masters Championship', style: 'wpa' },
    { kind: 'leaf', type: 'WPA_Artistic_2022_WC', label: '🎨 2022 World Championship', style: 'wpa' },
    { kind: 'leaf', type: 'WPA_Artistic_2022_NC', label: '🎨 2022 National Championship', style: 'wpa' },
    { kind: 'leaf', type: 'WPA_Artistic_2021_NC', label: '🎨 2021 National Championship', style: 'wpa' },
    { kind: 'leaf', type: 'WPA_Artistic_2019_WC', label: '🎨 2019 World Championship', style: 'wpa' },
    { kind: 'leaf', type: 'WPA_Artistic_2019_CAO', label: '🎨 2019 Coughlin Auto Open', style: 'wpa' },
  ],
  heyball: [
    { kind: 'drill', id: 'heyball_women', label: '🎯 Heyball Women', style: 'heyball' },
    { kind: 'drill', id: 'heyball_men', label: '🎯 Heyball Men', style: 'heyball' },
  ],
  heyball_women: [
    { kind: 'leaf', type: 'WPA_Heyball_Women', label: '🎯 Heyball Women (overall)', style: 'heyball' },
    { kind: 'leaf', type: 'WPA_Heyball_Women_WorldChamp', label: '🎯 World Championship 2025', style: 'heyball' },
    { kind: 'leaf', type: 'WPA_Heyball_Women_Champions', label: '🎯 Champion of Champions 2025', style: 'heyball' },
    { kind: 'leaf', type: 'WPA_Heyball_Women_PanAmerican', label: '🎯 Pan American Open 2025', style: 'heyball' },
    { kind: 'leaf', type: 'WPA_Heyball_Women_Oceania', label: '🎯 Oceania Open 2025', style: 'heyball' },
    { kind: 'leaf', type: 'WPA_Heyball_Women_NorthAmerican', label: '🎯 North American Open 2025', style: 'heyball' },
    { kind: 'leaf', type: 'WPA_Heyball_Women_European', label: '🎯 European Open 2025', style: 'heyball' },
    { kind: 'leaf', type: 'WPA_Heyball_Women_Asian', label: '🎯 Asian Open 2025', style: 'heyball' },
  ],
  heyball_men: [
    { kind: 'leaf', type: 'WPA_Heyball_Men', label: '🎯 Heyball Men (overall)', style: 'heyball' },
    { kind: 'leaf', type: 'WPA_Heyball_Men_WorldChamp', label: '🎯 World Championship 2025', style: 'heyball' },
    { kind: 'leaf', type: 'WPA_Heyball_Men_Champions', label: '🎯 Champion of Champions 2025', style: 'heyball' },
    { kind: 'leaf', type: 'WPA_Heyball_Men_PanAmerican', label: '🎯 Pan American Open 2025', style: 'heyball' },
    { kind: 'leaf', type: 'WPA_Heyball_Men_Oceania', label: '🎯 Oceania Open 2025', style: 'heyball' },
    { kind: 'leaf', type: 'WPA_Heyball_Men_NorthAmerican', label: '🎯 North American Open 2025', style: 'heyball' },
    { kind: 'leaf', type: 'WPA_Heyball_Men_European', label: '🎯 European Open 2025', style: 'heyball' },
    { kind: 'leaf', type: 'WPA_Heyball_Men_Asian', label: '🎯 Asian Open 2025', style: 'heyball' },
    { kind: 'leaf', type: 'WPA_Heyball_Men_10Ball', label: '🎯 10-Ball World Championship 2024', style: 'heyball' },
  ],
  // Inside Spin (insidesp.in) third-party ratings. Styled 'wpa' to avoid a new theme.
  insidesp: [
    { kind: 'leaf', type: 'InsideSpin_Overall', label: '🌐 Overall (all players)', style: 'wpa' },
    { kind: 'leaf', type: 'InsideSpin_Women', label: '🌐 Women', style: 'wpa' },
    { kind: 'leaf', type: 'InsideSpin_Juniors', label: '🌐 Juniors', style: 'wpa' },
    { kind: 'leaf', type: 'InsideSpin_9Ball', label: '🌐 9-Ball', style: 'wpa' },
    { kind: 'leaf', type: 'InsideSpin_10Ball', label: '🌐 10-Ball', style: 'wpa' },
    { kind: 'leaf', type: 'InsideSpin_8Ball', label: '🌐 8-Ball', style: 'wpa' },
    { kind: 'leaf', type: 'InsideSpin_OnePocket', label: '🌐 One Pocket', style: 'wpa' },
  ],
  // Digital Pool historical world rankings (pro_world_rankings, 2021-2023 snapshots).
  // Latest snapshot per system shows; rank-only. Styled 'wpa' to avoid a new theme.
  digitalpool: [
    { kind: 'leaf', type: 'DigitalPool_WPAWorldMen', label: '🗄️ WPA World Men (2021–23)', style: 'wpa' },
    { kind: 'leaf', type: 'DigitalPool_WPAWorldWomen', label: '🗄️ WPA World Women (2021–23)', style: 'wpa' },
    { kind: 'leaf', type: 'DigitalPool_MatchroomWorld9Ball', label: '🗄️ Matchroom World 9-Ball (2021–23)', style: 'wpa' },
    { kind: 'leaf', type: 'DigitalPool_FargoWorld', label: '🗄️ Fargo World (2021–23)', style: 'wpa' },
    { kind: 'leaf', type: 'DigitalPool_FargoWorldMen', label: '🗄️ Fargo World Men (2021–23)', style: 'wpa' },
    { kind: 'leaf', type: 'DigitalPool_FargoWorldWomen', label: '🗄️ Fargo World Women (2021–23)', style: 'wpa' },
    { kind: 'leaf', type: 'DigitalPool_FargoUS', label: '🗄️ Fargo US (2021–23)', style: 'wpa' },
    { kind: 'leaf', type: 'DigitalPool_USProSeries', label: '🗄️ US Pro Series (2021–22)', style: 'wpa' },
  ],
}

const TOP_LEVEL_ITEMS: DrillItem[] = [
  { kind: 'drill', id: 'wpba', label: '👑 WPBA', style: 'wpba' },
  { kind: 'drill', id: 'wpa', label: '🌍 WPA', style: 'wpa' },
  { kind: 'drill', id: 'heyball', label: '🎯 Heyball', style: 'heyball' },
  { kind: 'drill', id: 'wpa_artistic', label: '🎨 Artistic Pool', style: 'wpa' },
  { kind: 'drill', id: 'insidesp', label: '🌐 Inside Spin', style: 'wpa' },
  { kind: 'drill', id: 'digitalpool', label: '🗄️ Digital Pool (history)', style: 'wpa' },
]

interface RankingTypeInfo {
  type: RankingType
  label: string
  association: string
  division: string
  heroTitle: string
  description: string
  color: 'wpba' | 'wpa' | 'heyball'
}

// Partial: the `WPBA_Women_${string}` catch-all in RankingType means not every
// member can have a static entry. Dynamically-discovered per-event systems are
// resolved at runtime in `currentRankingInfo` (API label + WPBA styling), which
// already handles a missing entry. Static entries below cover the fixed systems.
const RANKING_TYPES: Partial<Record<RankingType, RankingTypeInfo>> = {
  'WPBA_Women': {
    type: 'WPBA_Women',
    label: 'WPBA Women',
    association: 'WPBA',
    division: 'Women',
    heroTitle: 'Meet the best players in the world',
    description: "Official WPBA women's tour standings — all events combined.",
    color: 'wpba'
  },
  'WPA_Women': {
    type: 'WPA_Women',
    label: 'WPA Women',
    association: 'WPA',
    division: 'Women',
    heroTitle: 'Welcome to the world of pool',
    description: "Official WPA women's world rankings — all listed events combined.",
    color: 'wpa'
  },
  'WPA_Men': {
    type: 'WPA_Men',
    label: 'WPA Men',
    association: 'WPA',
    division: 'Men',
    heroTitle: 'Welcome to the world of pool',
    description: "Official WPA men's world rankings — all listed events combined.",
    color: 'wpa'
  },
  'WPA_Heyball_Men': {
    type: 'WPA_Heyball_Men',
    label: 'Heyball Men',
    association: 'WPA',
    division: 'Heyball Men',
    heroTitle: 'Heyball Men',
    description: "Official Heyball men's standings from WPA — regional opens and world events combined.",
    color: 'heyball'
  },
  'WPA_Heyball_Women': {
    type: 'WPA_Heyball_Women',
    label: 'Heyball Women',
    association: 'WPA',
    division: 'Heyball Women',
    heroTitle: 'Heyball Women',
    description: "Official Heyball women's standings from WPA — regional opens and world events combined.",
    color: 'heyball'
  },
  'WPA_Artistic': {
    type: 'WPA_Artistic',
    label: 'Artistic Pool',
    association: 'WPA',
    division: 'Artistic Pool',
    heroTitle: 'Artistic Pool',
    description: 'Artistic Pool overall standings. Points from each championship are added together; older events count a little less than recent ones.',
    color: 'wpa'
  },
  // WPA Artistic Pool: one button per event/tournament
  'WPA_Artistic_2019_CAO': { type: 'WPA_Artistic_2019_CAO', label: '2019 Coughlin Auto Open', association: 'WPA', division: 'Artistic Pool', heroTitle: '2019 Coughlin Auto Open', description: 'Standings for this Artistic Pool championship only.', color: 'wpa' },
  'WPA_Artistic_2019_WC': { type: 'WPA_Artistic_2019_WC', label: '2019 World Championship', association: 'WPA', division: 'Artistic Pool', heroTitle: '2019 World Championship', description: 'Standings for this Artistic Pool championship only.', color: 'wpa' },
  'WPA_Artistic_2021_NC': { type: 'WPA_Artistic_2021_NC', label: '2021 National Championship', association: 'WPA', division: 'Artistic Pool', heroTitle: '2021 National Championship', description: 'Standings for this Artistic Pool championship only.', color: 'wpa' },
  'WPA_Artistic_2022_NC': { type: 'WPA_Artistic_2022_NC', label: '2022 National Championship', association: 'WPA', division: 'Artistic Pool', heroTitle: '2022 National Championship', description: 'Standings for this Artistic Pool championship only.', color: 'wpa' },
  'WPA_Artistic_2022_WC': { type: 'WPA_Artistic_2022_WC', label: '2022 World Championship', association: 'WPA', division: 'Artistic Pool', heroTitle: '2022 World Championship', description: 'Standings for this Artistic Pool championship only.', color: 'wpa' },
  'WPA_Artistic_2023_MC': { type: 'WPA_Artistic_2023_MC', label: '2023 Masters Championship', association: 'WPA', division: 'Artistic Pool', heroTitle: '2023 Masters Championship', description: 'Standings for this Artistic Pool championship only.', color: 'wpa' },
  'WPA_Artistic_2023_SAO': { type: 'WPA_Artistic_2023_SAO', label: '2023 South African Open', association: 'WPA', division: 'Artistic Pool', heroTitle: '2023 South African Open', description: 'Standings for this Artistic Pool championship only.', color: 'wpa' },
  'Competitors_Pool_9Ball': {
    type: 'Competitors_Pool_9Ball',
    label: '9-Ball',
    association: 'WPA',
    division: '9-Ball',
    heroTitle: '9-Ball (WPA Men)',
    description: "Men's 9-ball: major WPA events rolled into one list (world championship, China Open, International Open).",
    color: 'wpa'
  },
  'Competitors_Pool_10Ball': {
    type: 'Competitors_Pool_10Ball',
    label: '10-Ball',
    association: 'WPA',
    division: '10-Ball',
    heroTitle: 'Predator 10-Ball (WPA Men)',
    description: "Men's 10-ball: Predator world championship plus Indonesia, Qatar, and Polish opens combined.",
    color: 'wpa'
  },
  'Competitors_Pool_8Ball': {
    type: 'Competitors_Pool_8Ball',
    label: '8-Ball',
    association: 'WPA',
    division: '8-Ball',
    heroTitle: 'Yalin 8-Ball (WPA Men)',
    description: "Men's 8-ball: Yalin WPA 8-Ball World Championship standings.",
    color: 'wpa'
  },
  'Competitors_Pool_Women_9Ball': {
    type: 'Competitors_Pool_Women_9Ball',
    label: '9-Ball Women',
    association: 'WPA',
    division: '9-Ball Women',
    heroTitle: '9-Ball Women',
    description: "Women's 9-ball combined standings (CP tour data).",
    color: 'wpa'
  },
  'Competitors_Pool_Men_9Ball': {
    type: 'Competitors_Pool_Men_9Ball',
    label: '9-Ball Men',
    association: 'WPA',
    division: '9-Ball Men',
    heroTitle: '9-Ball Men',
    description: "Men's 9-ball combined standings (CP tour data).",
    color: 'wpa'
  },
  // Inside Spin (insidesp.in) third-party ratings. These are rank-position lists
  // (no points); Inside Spin's own Display Rating + Matches Rated are in source_data.
  'InsideSpin_Overall': { type: 'InsideSpin_Overall', label: 'Overall', association: 'Inside Spin', division: 'Overall', heroTitle: 'Inside Spin — Overall', description: "Inside Spin's overall player ratings (all players, all disciplines). Third-party aggregator; ranked by Inside Spin Display Rating.", color: 'wpa' },
  'InsideSpin_Women': { type: 'InsideSpin_Women', label: 'Women', association: 'Inside Spin', division: 'Women', heroTitle: 'Inside Spin — Women', description: "Inside Spin's overall ratings for women players. Third-party aggregator.", color: 'wpa' },
  'InsideSpin_Juniors': { type: 'InsideSpin_Juniors', label: 'Juniors', association: 'Inside Spin', division: 'Juniors', heroTitle: 'Inside Spin — Juniors', description: "Inside Spin's overall ratings for junior players. Third-party aggregator.", color: 'wpa' },
  'InsideSpin_9Ball': { type: 'InsideSpin_9Ball', label: '9-Ball', association: 'Inside Spin', division: '9-Ball', heroTitle: 'Inside Spin — 9-Ball', description: "Inside Spin's 9-ball discipline ratings. Third-party aggregator.", color: 'wpa' },
  'InsideSpin_10Ball': { type: 'InsideSpin_10Ball', label: '10-Ball', association: 'Inside Spin', division: '10-Ball', heroTitle: 'Inside Spin — 10-Ball', description: "Inside Spin's 10-ball discipline ratings. Third-party aggregator.", color: 'wpa' },
  'InsideSpin_8Ball': { type: 'InsideSpin_8Ball', label: '8-Ball', association: 'Inside Spin', division: '8-Ball', heroTitle: 'Inside Spin — 8-Ball', description: "Inside Spin's 8-ball discipline ratings. Third-party aggregator.", color: 'wpa' },
  'InsideSpin_OnePocket': { type: 'InsideSpin_OnePocket', label: 'One Pocket', association: 'Inside Spin', division: 'One Pocket', heroTitle: 'Inside Spin — One Pocket', description: "Inside Spin's one-pocket discipline ratings. Third-party aggregator.", color: 'wpa' },
  // Digital Pool historical world rankings (pro_world_rankings). Rank-position
  // snapshots 2021-2023; the UI shows the latest snapshot per system. Not live.
  'DigitalPool_WPAWorldMen': { type: 'DigitalPool_WPAWorldMen', label: 'WPA World Men', association: 'Digital Pool', division: 'WPA World Men', heroTitle: 'Digital Pool — WPA World Men (history)', description: 'Historical WPA World Men ranking snapshots from Digital Pool (2021-09 → 2023-09). Rank-position only; latest snapshot shown.', color: 'wpa' },
  'DigitalPool_WPAWorldWomen': { type: 'DigitalPool_WPAWorldWomen', label: 'WPA World Women', association: 'Digital Pool', division: 'WPA World Women', heroTitle: 'Digital Pool — WPA World Women (history)', description: 'Historical WPA World Women ranking snapshots from Digital Pool (2021-09 → 2023-09). Rank-position only; latest snapshot shown.', color: 'wpa' },
  'DigitalPool_MatchroomWorld9Ball': { type: 'DigitalPool_MatchroomWorld9Ball', label: 'Matchroom World 9-Ball', association: 'Digital Pool', division: 'Matchroom World 9-Ball', heroTitle: 'Digital Pool — Matchroom World 9-Ball (history)', description: 'Historical Matchroom World 9-Ball ranking snapshots from Digital Pool (2021-09 → 2023-09). Rank-position only; latest snapshot shown.', color: 'wpa' },
  'DigitalPool_FargoWorld': { type: 'DigitalPool_FargoWorld', label: 'Fargo World', association: 'Digital Pool', division: 'Fargo World', heroTitle: 'Digital Pool — Fargo World (history)', description: 'Historical Fargo World ranking snapshots from Digital Pool (2021-09 → 2023-09). Rank-position only; latest snapshot shown.', color: 'wpa' },
  'DigitalPool_FargoWorldMen': { type: 'DigitalPool_FargoWorldMen', label: 'Fargo World Men', association: 'Digital Pool', division: 'Fargo World Men', heroTitle: 'Digital Pool — Fargo World Men (history)', description: 'Historical Fargo World Men ranking snapshots from Digital Pool (2021-09 → 2023-09). Rank-position only; latest snapshot shown.', color: 'wpa' },
  'DigitalPool_FargoWorldWomen': { type: 'DigitalPool_FargoWorldWomen', label: 'Fargo World Women', association: 'Digital Pool', division: 'Fargo World Women', heroTitle: 'Digital Pool — Fargo World Women (history)', description: 'Historical Fargo World Women ranking snapshots from Digital Pool (2021-09 → 2023-09). Rank-position only; latest snapshot shown.', color: 'wpa' },
  'DigitalPool_FargoUS': { type: 'DigitalPool_FargoUS', label: 'Fargo US', association: 'Digital Pool', division: 'Fargo US', heroTitle: 'Digital Pool — Fargo US (history)', description: 'Historical Fargo US ranking snapshots from Digital Pool (2021-09 → 2023-09). Rank-position only; latest snapshot shown.', color: 'wpa' },
  'DigitalPool_USProSeries': { type: 'DigitalPool_USProSeries', label: 'US Pro Series', association: 'Digital Pool', division: 'US Pro Series', heroTitle: 'Digital Pool — US Pro Series (history)', description: 'Historical US Pro Series ranking snapshots from Digital Pool (2021-09 → 2022-04). Rank-position only; latest snapshot shown.', color: 'wpa' },
  // WPA Men: one button per event column (no combining)
  'WPA_Men_10B_Polish': { type: 'WPA_Men_10B_Polish', label: "Jax Men's International", association: 'WPA', division: 'Men', heroTitle: "Jax Men's International Open 2025", description: 'Standings for this WPA Men event only.', color: 'wpa' },
  'WPA_Men_Maldives': { type: 'WPA_Men_Maldives', label: 'Little Monster International', association: 'WPA', division: 'Men', heroTitle: 'Little Monster International Open 2025', description: 'Standings for this WPA Men event only.', color: 'wpa' },
  'WPA_Men_HCM': { type: 'WPA_Men_HCM', label: '58th All Japan Open', association: 'WPA', division: 'Men', heroTitle: '58th All Japan Open 2025', description: 'Standings for this WPA Men event only.', color: 'wpa' },
  'WPA_Men_9B_IntlOpen': { type: 'WPA_Men_9B_IntlOpen', label: 'International Open 9-Ball', association: 'WPA', division: 'Men', heroTitle: 'International 9-Ball Open 2025', description: 'Standings for this WPA Men event only.', color: 'wpa' },
  'WPA_Men_10B_Qatar': { type: 'WPA_Men_10B_Qatar', label: 'Qatar World Cup 10-Ball', association: 'WPA', division: 'Men', heroTitle: 'Qatar World Cup 10-Ball 2025', description: 'Standings for this WPA Men event only.', color: 'wpa' },
  'WPA_Men_Yalin_8Ball': { type: 'WPA_Men_Yalin_8Ball', label: 'Yalin 8-Ball', association: 'WPA', division: 'Men', heroTitle: 'Yalin 8-Ball World Championship 2025', description: 'Standings for this WPA Men event only.', color: 'wpa' },
  'WPA_Men_Predator_10B': { type: 'WPA_Men_Predator_10B', label: 'Predator 10-Ball', association: 'WPA', division: 'Men', heroTitle: 'Predator 10-Ball World Championship 2025', description: 'Standings for this WPA Men event only.', color: 'wpa' },
  'WPA_Men_JPBA_JapanOpen': { type: 'WPA_Men_JPBA_JapanOpen', label: '38th JPBA Japan Open', association: 'WPA', division: 'Men', heroTitle: '38th JPBA Japan Open 2025', description: 'Standings for this WPA Men event only.', color: 'wpa' },
  'WPA_Men_9B_ChinaOpen': { type: 'WPA_Men_9B_ChinaOpen', label: '9-Ball China Open', association: 'WPA', division: 'Men', heroTitle: 'Pudong 9-Ball China Open 2025', description: 'Standings for this WPA Men event only.', color: 'wpa' },
  'WPA_Men_9B_WorldChamp': { type: 'WPA_Men_9B_WorldChamp', label: '9-Ball World Champs', association: 'WPA', division: 'Men', heroTitle: '9-Ball World Championship 2025', description: 'Standings for this WPA Men event only.', color: 'wpa' },
  'WPA_Men_10B_Indonesia': { type: 'WPA_Men_10B_Indonesia', label: 'Indonesia 10-Ball', association: 'WPA', division: 'Men', heroTitle: 'Indonesia 10-Ball Open 2025', description: 'Standings for this WPA Men event only.', color: 'wpa' },
  'WPA_Men_Kamui_LasVegas': { type: 'WPA_Men_Kamui_LasVegas', label: 'Kamui Las Vegas', association: 'WPA', division: 'Men', heroTitle: 'Kamui Las Vegas Open 2025', description: 'Standings for this WPA Men event only.', color: 'wpa' },
  // WPA Women: one button per event column (no combining)
  'WPA_Women_9B_WorldChamp': { type: 'WPA_Women_9B_WorldChamp', label: 'WPA 9-Ball World Champs', association: 'WPA', division: 'Women', heroTitle: 'WPA 9-Ball World Championship 2025', description: 'Standings for this WPA Women event only.', color: 'wpa' },
  'WPA_Women_LittleMonster': { type: 'WPA_Women_LittleMonster', label: 'Little Monster International', association: 'WPA', division: 'Women', heroTitle: 'Little Monster International Open 2025', description: 'Standings for this WPA Women event only.', color: 'wpa' },
  'WPA_Women_AllJapan57': { type: 'WPA_Women_AllJapan57', label: '57th All Japan Championship', association: 'WPA', division: 'Women', heroTitle: '57th All Japan Championship 2025', description: 'Standings for this WPA Women event only.', color: 'wpa' },
  'WPA_Women_DRPoolTour': { type: 'WPA_Women_DRPoolTour', label: 'WPBA DR Pool Tour', association: 'WPA', division: 'Women', heroTitle: 'WPBA DR Pool Tour Championship 2025', description: 'Standings for this WPA Women event only.', color: 'wpa' },
  'WPA_Women_10B_Predator': { type: 'WPA_Women_10B_Predator', label: 'Predator 10-Ball', association: 'WPA', division: 'Women', heroTitle: 'Predator WPA 10-Ball World Championship 2025', description: 'Standings for this WPA Women event only.', color: 'wpa' },
  'WPA_Women_9Ball': { type: 'WPA_Women_9Ball', label: 'Poison Saigon 9-Ball', association: 'WPA', division: 'Women', heroTitle: 'Poison Saigon 9-Ball Open 2025', description: 'Standings for this WPA Women event only.', color: 'wpa' },
  'WPA_Women_JapanOpen': { type: 'WPA_Women_JapanOpen', label: 'Japan Open', association: 'WPA', division: 'Women', heroTitle: 'Japan Open 2025', description: 'Standings for this WPA Women event only.', color: 'wpa' },
  'WPA_Women_ChinaOpen': { type: 'WPA_Women_ChinaOpen', label: 'China Open', association: 'WPA', division: 'Women', heroTitle: 'China Open 2025', description: 'Standings for this WPA Women event only.', color: 'wpa' },
  'WPA_Women_WPBA_Colorado': { type: 'WPA_Women_WPBA_Colorado', label: 'WPBA Colorado Classic', association: 'WPA', division: 'Women', heroTitle: 'WPBA Olhausen Colorado Classic 2025', description: 'Standings for this WPA Women event only.', color: 'wpa' },
  'WPA_Women_10B_Indonesia': { type: 'WPA_Women_10B_Indonesia', label: 'Indonesia 10-Ball', association: 'WPA', division: 'Women', heroTitle: 'Indonesia 10-Ball Open 2025', description: 'Standings for this WPA Women event only.', color: 'wpa' },
  'WPA_Women_8Ball': { type: 'WPA_Women_8Ball', label: 'WPA 8-Ball World Champs', association: 'WPA', division: 'Women', heroTitle: 'WPA 8-Ball World Championship 2025', description: 'Standings for this WPA Women event only.', color: 'wpa' },
  'WPA_Women_WPBA_SEMasters': { type: 'WPA_Women_WPBA_SEMasters', label: 'WPBA SE Masters', association: 'WPA', division: 'Women', heroTitle: 'WPBA SE Masters 2025', description: 'Standings for this WPA Women event only.', color: 'wpa' },
  'WPA_Women_WPBA_RaxxMezz': { type: 'WPA_Women_WPBA_RaxxMezz', label: 'WPBA Raxx Mezz', association: 'WPA', division: 'Women', heroTitle: 'WPBA Raxx Mezz 2025', description: 'Standings for this WPA Women event only.', color: 'wpa' },
  'WPA_Women_Kamui_LasVegas': { type: 'WPA_Women_Kamui_LasVegas', label: 'Kamui Las Vegas', association: 'WPA', division: 'Women', heroTitle: 'Kamui Las Vegas Open 2025', description: 'Standings for this WPA Women event only.', color: 'wpa' },
  'WPA_Women_WPBA_IronCity': { type: 'WPA_Women_WPBA_IronCity', label: 'WPBA IronCity', association: 'WPA', division: 'Women', heroTitle: 'WPBA Olhausen IronCity 2025', description: 'Standings for this WPA Women event only.', color: 'wpa' },
  // WPA Heyball Men: one button per event column (no combining)
  'WPA_Heyball_Men_WorldChamp': { type: 'WPA_Heyball_Men_WorldChamp', label: 'World Championship', association: 'WPA', division: 'Heyball Men', heroTitle: 'Heyball World Championship 2025', description: 'Standings for this Heyball Men event only.', color: 'heyball' },
  'WPA_Heyball_Men_10Ball': { type: 'WPA_Heyball_Men_10Ball', label: '10-Ball World Champs', association: 'WPA', division: 'Heyball Men', heroTitle: '10-Ball World Championship 2024', description: 'Standings for this Heyball Men event only.', color: 'heyball' },
  'WPA_Heyball_Men_Asian': { type: 'WPA_Heyball_Men_Asian', label: 'Asian Open', association: 'WPA', division: 'Heyball Men', heroTitle: 'Asian Heyball Open 2025', description: 'Standings for this Heyball Men event only.', color: 'heyball' },
  'WPA_Heyball_Men_European': { type: 'WPA_Heyball_Men_European', label: 'European Open', association: 'WPA', division: 'Heyball Men', heroTitle: 'European Heyball Open 2025', description: 'Standings for this Heyball Men event only.', color: 'heyball' },
  'WPA_Heyball_Men_NorthAmerican': { type: 'WPA_Heyball_Men_NorthAmerican', label: 'North American Open', association: 'WPA', division: 'Heyball Men', heroTitle: 'North American Heyball Open 2025', description: 'Standings for this Heyball Men event only.', color: 'heyball' },
  'WPA_Heyball_Men_Oceania': { type: 'WPA_Heyball_Men_Oceania', label: 'Oceania Open', association: 'WPA', division: 'Heyball Men', heroTitle: 'Oceania Heyball Open 2025', description: 'Standings for this Heyball Men event only.', color: 'heyball' },
  'WPA_Heyball_Men_PanAmerican': { type: 'WPA_Heyball_Men_PanAmerican', label: 'Pan American Open', association: 'WPA', division: 'Heyball Men', heroTitle: 'Pan American Heyball Open 2025', description: 'Standings for this Heyball Men event only.', color: 'heyball' },
  'WPA_Heyball_Men_Champions': { type: 'WPA_Heyball_Men_Champions', label: 'Champion of Champions', association: 'WPA', division: 'Heyball Men', heroTitle: 'Heyball Champion of Champions 2025', description: 'Standings for this Heyball Men event only.', color: 'heyball' },
  // WPA Heyball Women: one button per event column (no combining)
  'WPA_Heyball_Women_WorldChamp': { type: 'WPA_Heyball_Women_WorldChamp', label: 'World Championship', association: 'WPA', division: 'Heyball Women', heroTitle: 'Heyball World Championship 2025', description: 'Standings for this Heyball Women event only.', color: 'heyball' },
  'WPA_Heyball_Women_Asian': { type: 'WPA_Heyball_Women_Asian', label: 'Asian Open', association: 'WPA', division: 'Heyball Women', heroTitle: 'Asian Heyball Open 2025', description: 'Standings for this Heyball Women event only.', color: 'heyball' },
  'WPA_Heyball_Women_European': { type: 'WPA_Heyball_Women_European', label: 'European Open', association: 'WPA', division: 'Heyball Women', heroTitle: 'European Heyball Open 2025', description: 'Standings for this Heyball Women event only.', color: 'heyball' },
  'WPA_Heyball_Women_NorthAmerican': { type: 'WPA_Heyball_Women_NorthAmerican', label: 'North American Open', association: 'WPA', division: 'Heyball Women', heroTitle: 'North American Heyball Open 2025', description: 'Standings for this Heyball Women event only.', color: 'heyball' },
  'WPA_Heyball_Women_Oceania': { type: 'WPA_Heyball_Women_Oceania', label: 'Oceania Open', association: 'WPA', division: 'Heyball Women', heroTitle: 'Oceania Heyball Open 2025', description: 'Standings for this Heyball Women event only.', color: 'heyball' },
  'WPA_Heyball_Women_PanAmerican': { type: 'WPA_Heyball_Women_PanAmerican', label: 'Pan American Open', association: 'WPA', division: 'Heyball Women', heroTitle: 'Pan American Heyball Open 2025', description: 'Standings for this Heyball Women event only.', color: 'heyball' },
  'WPA_Heyball_Women_Champions': { type: 'WPA_Heyball_Women_Champions', label: 'Champion of Champions', association: 'WPA', division: 'Heyball Women', heroTitle: 'Heyball Champion of Champions 2025', description: 'Standings for this Heyball Women event only.', color: 'heyball' },
  // WPBA Women: one button per tournament
  'WPBA_Women_IronCityVI': { type: 'WPBA_Women_IronCityVI', label: 'Iron City Invitational VI', association: 'WPBA', division: 'Women', heroTitle: 'Iron City Invitational VI', description: 'Standings for this WPBA event only.', color: 'wpba' },
  'WPBA_Women_Jacoby2025': { type: 'WPBA_Women_Jacoby2025', label: 'Jacoby Tour Masters 2025', association: 'WPBA', division: 'Women', heroTitle: 'Jacoby Tour Masters 2025', description: 'Standings for this WPBA event only.', color: 'wpba' },
  'WPBA_Women_Colorado2025': { type: 'WPBA_Women_Colorado2025', label: 'Colorado Classic 2025', association: 'WPBA', division: 'Women', heroTitle: 'Colorado Classic 2025', description: 'Standings for this WPBA event only.', color: 'wpba' },
  'WPBA_Women_SoaringEagle2025': { type: 'WPBA_Women_SoaringEagle2025', label: 'Soaring Eagle Invitational 2025', association: 'WPBA', division: 'Women', heroTitle: 'Soaring Eagle Invitational 2025', description: 'Standings for this WPBA event only.', color: 'wpba' },
  'WPBA_Women_RaxxMezz2025': { type: 'WPBA_Women_RaxxMezz2025', label: 'Raxx Mezz Invitational 2025', association: 'WPBA', division: 'Women', heroTitle: 'Raxx Mezz Invitational 2025', description: 'Standings for this WPBA event only.', color: 'wpba' },
  'WPBA_Women_Jacoby2024': { type: 'WPBA_Women_Jacoby2024', label: 'Jacoby Tour Championship 2024', association: 'WPBA', division: 'Women', heroTitle: 'Jacoby Tour Championship 2024', description: 'Standings for this WPBA event only.', color: 'wpba' },
  'WPBA_Women_CapitalCity2024': { type: 'WPBA_Women_CapitalCity2024', label: 'Capital City Invitational 2024', association: 'WPBA', division: 'Women', heroTitle: 'Capital City Invitational 2024', description: 'Standings for this WPBA event only.', color: 'wpba' },
  'WPBA_Women_NAPA2024': { type: 'WPBA_Women_NAPA2024', label: 'Cuespeed NAPA Invitational 2024', association: 'WPBA', division: 'Women', heroTitle: 'Cuespeed NAPA Invitational 2024', description: 'Standings for this WPBA event only.', color: 'wpba' },
  'WPBA_Women_Colorado2024': { type: 'WPBA_Women_Colorado2024', label: 'Colorado Classic 2024', association: 'WPBA', division: 'Women', heroTitle: 'Colorado Classic 2024', description: 'Standings for this WPBA event only.', color: 'wpba' },
  'WPBA_Women_Palmetto': { type: 'WPBA_Women_Palmetto', label: 'Palmetto Billiards Invitational', association: 'WPBA', division: 'Women', heroTitle: 'Palmetto Billiards Invitational', description: 'Standings for this WPBA event only.', color: 'wpba' },
  'WPBA_Women_DRPool2025': { type: 'WPBA_Women_DRPool2025', label: 'DR Pool Championship 2025', association: 'WPBA', division: 'Women', heroTitle: 'DR Pool Championship 2025', description: 'Standings for this WPBA event only.', color: 'wpba' },
}

/** Modal for Admin to edit a ranking row (name, rank, points, country, etc.). */
function EditRankingRowModal({
  row,
  onClose,
  onSave,
  isSaving,
}: {
  row: Ranking
  onClose: () => void
  onSave: (body: { name?: string; rank?: number; points?: number; country?: string; license_number?: string; stops_played?: number }) => void
  isSaving: boolean
}) {
  const [name, setName] = useState(row.name ?? '')
  const [rank, setRank] = useState(String(row.rank ?? ''))
  const [points, setPoints] = useState(String(row.points ?? ''))
  const [country, setCountry] = useState(row.country ?? '')
  const [licenseNumber, setLicenseNumber] = useState(row.license_number ?? '')
  const [stopsPlayed, setStopsPlayed] = useState(row.stops_played != null ? String(row.stops_played) : '')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const rankNum = parseInt(rank, 10)
    const pointsNum = parseFloat(points)
    const stopsNum = stopsPlayed === '' ? undefined : parseInt(stopsPlayed, 10)
    if (Number.isNaN(rankNum) || rankNum < 1 || Number.isNaN(pointsNum) || pointsNum < 0) {
      toast.error('Rank must be ≥ 1 and points must be ≥ 0')
      return
    }
    onSave({
      name: name.trim() || undefined,
      rank: rankNum,
      points: pointsNum,
      country: country.trim() || undefined,
      license_number: licenseNumber.trim() || undefined,
      stops_played: stopsNum,
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div className="bg-card border border-border rounded-xl shadow-xl max-w-md w-full mx-4 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="p-6">
          <h2 className="text-lg font-semibold text-foreground mb-4">Edit ranking row</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Player name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Rank</label>
                <input
                  type="number"
                  min={1}
                  value={rank}
                  onChange={(e) => setRank(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">Points</label>
                <input
                  type="number"
                  min={0}
                  step="any"
                  value={points}
                  onChange={(e) => setPoints(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Country</label>
              <input
                type="text"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground"
                placeholder="e.g. USA"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">License number</label>
              <input
                type="text"
                value={licenseNumber}
                onChange={(e) => setLicenseNumber(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Stops played</label>
              <input
                type="number"
                min={0}
                value={stopsPlayed}
                onChange={(e) => setStopsPlayed(e.target.value)}
                className="w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground"
                placeholder="Optional"
              />
            </div>
            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 rounded-lg border border-border bg-background text-foreground hover:bg-muted"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSaving}
                className="px-4 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {isSaving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

/** Single option in drill-down menu (navigate to submenu or select ranking) */
function MenuOptionButton({
  item,
  onClick,
}: {
  item: DrillItem
  onClick: () => void
}) {
  const style = item.style
  const base = 'rounded-xl py-3 sm:py-4 px-3 sm:px-4 min-h-[48px] sm:min-h-[56px] font-bold text-sm sm:text-base lg:text-lg transition-all shadow-md w-full sm:w-auto'
  const wpba = 'bg-slate-700/50 border-2 border-felt/30 text-white hover:border-felt/60 hover:bg-slate-600/50'
  const wpa = 'bg-slate-700/50 border-2 border-felt/30 text-white hover:border-felt/60 hover:bg-slate-600/50'
  const hey = 'bg-slate-700/50 border-2 border-purple-400/30 text-white hover:border-purple-400/60 hover:bg-slate-600/50'
  const cn = style === 'heyball' ? hey : style === 'wpa' ? wpa : wpba
  return (
    <button type="button" onClick={onClick} className={`${base} ${cn}`}>
      {item.label}
    </button>
  )
}

export default function Rankings({ sidebarOpen: _sidebarOpen, onSidebarToggle }: RankingsPageProps) {
  const rankingsApi = useRankingsApi()
  const { scope: apiScope } = useApiPathPrefixes()
  const queryClient = useQueryClient()
  const { isAdmin, isSuperAdmin } = useAuth()
  const canEditRankings = isAdmin && apiScope === 'production'
  const { getLayout } = useUiCustomization()
  const [viewMode, setViewMode] = useState<'menu' | 'table'>('menu')
  const [navStack, setNavStack] = useState<DrillLevel[]>(['top'])
  const [selectedRankingType, setSelectedRankingType] = useState<RankingType | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [currentPage, setCurrentPage] = useState(0)
  const [playerModalName, setPlayerModalName] = useState<string | null>(null)
  const [editRow, setEditRow] = useState<Ranking | null>(null)
  const itemsPerPage = 100

  const updateRowMutation = useMutation({
    mutationFn: (payload: { rowId: number; body: { name?: string; rank?: number; points?: number; country?: string; license_number?: string; stops_played?: number } }) =>
      rankingsApi.updateRankingRow(payload.rowId, payload.body),
    onSuccess: () => {
      toast.success('Ranking row updated')
      setEditRow(null)
      queryClient.invalidateQueries({ queryKey: ['rankings'] })
    },
    onError: (err: Error) => {
      toast.error(err.message || 'Update failed')
    },
  })

  // WPBA tournament buttons from API (single source of truth; no static fallback)
  const { data: wpbaSystemsData } = useQuery({
    queryKey: ['rankings', 'wpba-tournament-systems'],
    queryFn: rankingsApi.getWpbaTournamentSystems,
    staleTime: 0,
    refetchOnMount: 'always',
    refetchOnWindowFocus: true,
    retry: 2,
  })
  const wpbaMenuItems: DrillItem[] = useMemo(() => {
    const systems = wpbaSystemsData?.systems ?? []
    const tournamentItems: DrillItem[] = systems.map((s) => ({
      kind: 'leaf' as const,
      type: s.ranking_system as RankingType,
      label: `🏆 ${s.label}`,
      style: 'wpba' as const,
    }))
    return [WPBA_OVERALL_ITEM, ...tournamentItems]
  }, [wpbaSystemsData?.systems])

  const { data: wpaMenSystemsData } = useQuery({
    queryKey: ['rankings', 'wpa-men-tournament-systems'],
    queryFn: rankingsApi.getWpaMenTournamentSystems,
    staleTime: 0,
    refetchOnMount: 'always',
    refetchOnWindowFocus: true,
    retry: 2,
  })
  const { data: wpaWomenSystemsData } = useQuery({
    queryKey: ['rankings', 'wpa-women-tournament-systems'],
    queryFn: rankingsApi.getWpaWomenTournamentSystems,
    staleTime: 0,
    refetchOnMount: 'always',
    refetchOnWindowFocus: true,
    retry: 2,
  })

  const wpaMenMenuItems: DrillItem[] = useMemo(() => {
    const overall: DrillItem = { kind: 'leaf', type: 'WPA_Men', label: '🎱 WPA Men (overall)', style: 'wpa' }
    const systems = wpaMenSystemsData?.systems ?? []
    const tournamentItems: DrillItem[] = systems.map((s) => ({
      kind: 'leaf' as const,
      type: s.ranking_system as RankingType,
      label: `🎱 ${s.label}`,
      style: 'wpa' as const,
    }))
    return [overall, ...tournamentItems]
  }, [wpaMenSystemsData?.systems])

  const wpaWomenMenuItems: DrillItem[] = useMemo(() => {
    const overall: DrillItem = { kind: 'leaf', type: 'WPA_Women', label: '🌍 WPA Women (overall)', style: 'wpa' }
    const systems = wpaWomenSystemsData?.systems ?? []
    const tournamentItems: DrillItem[] = systems.map((s) => ({
      kind: 'leaf' as const,
      type: s.ranking_system as RankingType,
      label: `🎱 ${s.label}`,
      style: 'wpa' as const,
    }))
    return [overall, ...tournamentItems]
  }, [wpaWomenSystemsData?.systems])

  const drillMenus = useMemo(
    () => ({
      ...DRILL_MENUS,
      wpba: wpbaMenuItems,
      wpa_men: wpaMenMenuItems,
      wpa_women: wpaWomenMenuItems,
    }),
    [wpbaMenuItems, wpaMenMenuItems, wpaWomenMenuItems]
  )
  const wpbaLabelMap = useMemo(() => {
    const m = new Map<string, string>()
    wpbaSystemsData?.systems?.forEach((s) => m.set(s.ranking_system, s.label))
    return m
  }, [wpbaSystemsData?.systems])

  const wpaMenLabelMap = useMemo(() => {
    const m = new Map<string, string>()
    wpaMenSystemsData?.systems?.forEach((s) => m.set(s.ranking_system, s.label))
    return m
  }, [wpaMenSystemsData?.systems])

  const wpaWomenLabelMap = useMemo(() => {
    const m = new Map<string, string>()
    wpaWomenSystemsData?.systems?.forEach((s) => m.set(s.ranking_system, s.label))
    return m
  }, [wpaWomenSystemsData?.systems])

  const currentRankingInfo = useMemo((): RankingTypeInfo | null => {
    if (selectedRankingType === null) return null
    const t = selectedRankingType
    const fromRecord = RANKING_TYPES[t as keyof typeof RANKING_TYPES]
    if (fromRecord) return fromRecord
    if (t.startsWith('WPBA_Women_')) {
      const lbl =
        wpbaLabelMap.get(t) ?? t.replace('WPBA_Women_', '').replace(/_/g, ' ')
      return {
        type: t,
        label: lbl,
        association: 'WPBA',
        division: 'Women',
        heroTitle: lbl,
        description: 'Standings for this WPBA event only.',
        color: 'wpba',
      }
    }
    if (t.startsWith('WPA_Men_')) {
      const lbl = wpaMenLabelMap.get(t) ?? t.replace('WPA_Men_', '').replace(/_/g, ' ')
      return {
        type: t,
        label: lbl,
        association: 'WPA',
        division: 'Men',
        heroTitle: lbl,
        description: 'Standings for this WPA Men event only.',
        color: 'wpa',
      }
    }
    if (t.startsWith('WPA_Women_')) {
      const lbl = wpaWomenLabelMap.get(t) ?? t.replace('WPA_Women_', '').replace(/_/g, ' ')
      return {
        type: t,
        label: lbl,
        association: 'WPA',
        division: 'Women',
        heroTitle: lbl,
        description: 'Standings for this WPA Women event only.',
        color: 'wpa',
      }
    }
    return {
      type: t,
      label: t.replace(/_/g, ' '),
      association: 'WPA',
      division: 'Men',
      heroTitle: t.replace(/_/g, ' '),
      description: '',
      color: 'wpa',
    }
  }, [selectedRankingType, wpbaLabelMap, wpaMenLabelMap, wpaWomenLabelMap])

  // Fetch rankings only when a ranking is selected (table view)
  const { data: rankingsData, isLoading: rankingsLoading, isError: rankingsError, error } = useQuery({
    queryKey: ['rankings', selectedRankingType ?? 'none', currentPage],
    queryFn: () => {
      const type = selectedRankingType!
      const offset = currentPage * itemsPerPage
      switch (type) {
        case 'WPBA_Women':
          return rankingsApi.getWPBAWomen(itemsPerPage, offset)
        case 'WPA_Women':
          return rankingsApi.getWPAWomen(itemsPerPage, offset)
        case 'WPA_Men':
          return rankingsApi.getWPAMen(itemsPerPage, offset)
        case 'WPA_Heyball_Men':
          return rankingsApi.getWPAHeyballMen(itemsPerPage, offset)
        case 'WPA_Heyball_Women':
          return rankingsApi.getWPAHeyballWomen(itemsPerPage, offset)
        case 'WPA_Artistic':
          return rankingsApi.getWPAArtistic(itemsPerPage, offset)
        case 'Competitors_Pool_9Ball':
          return rankingsApi.getCp9Ball(itemsPerPage, offset)
        case 'Competitors_Pool_10Ball':
          return rankingsApi.getCp10Ball(itemsPerPage, offset)
        case 'Competitors_Pool_8Ball':
          return rankingsApi.getCp8Ball(itemsPerPage, offset)
        case 'Competitors_Pool_Women_9Ball':
          return rankingsApi.getCpWomen9Ball(itemsPerPage, offset)
        case 'Competitors_Pool_Men_9Ball':
          return rankingsApi.getCpMen9Ball(itemsPerPage, offset)
        default:
          if (type.startsWith('InsideSpin_')) {
            return rankingsApi.getBySystem(type, itemsPerPage, offset)
          }
          if (type.startsWith('DigitalPool_')) {
            return rankingsApi.getBySystem(type, itemsPerPage, offset)
          }
          if (type.startsWith('WPBA_Women_')) {
            return rankingsApi.getBySystem(type, itemsPerPage, offset)
          }
          if (type.startsWith('WPA_Men_')) {
            return rankingsApi.getBySystem(type, itemsPerPage, offset)
          }
          if (type.startsWith('WPA_Women_')) {
            return rankingsApi.getBySystem(type, itemsPerPage, offset)
          }
          if (WPBA_WOMEN_COLUMN_TYPES.includes(type as WpbaWomenColumnType)) {
            return rankingsApi.getBySystem(type, itemsPerPage, offset)
          }
          if (WPA_WOMEN_COLUMN_TYPES.includes(type as WpaWomenColumnType)) {
            return rankingsApi.getBySystem(type, itemsPerPage, offset)
          }
          if (WPA_MEN_COLUMN_TYPES.includes(type as WpaMenColumnType)) {
            return rankingsApi.getBySystem(type, itemsPerPage, offset)
          }
          if (WPA_HEYBALL_MEN_COLUMN_TYPES.includes(type as WpaHeyballMenColumnType)) {
            return rankingsApi.getBySystem(type, itemsPerPage, offset)
          }
          if (WPA_HEYBALL_WOMEN_COLUMN_TYPES.includes(type as WpaHeyballWomenColumnType)) {
            return rankingsApi.getBySystem(type, itemsPerPage, offset)
          }
          if (WPA_ARTISTIC_COLUMN_TYPES.includes(type as WpaArtisticColumnType)) {
            return rankingsApi.getBySystem(type, itemsPerPage, offset)
          }
          return rankingsApi.getWPBAWomen(itemsPerPage, offset)
      }
    },
    enabled: selectedRankingType !== null,
    refetchInterval: false, // DISABLED: Auto-refresh disabled to prevent bans
    refetchOnWindowFocus: true,
    retry: 2,
    retryDelay: 1000,
  })

  // Fetch last update timestamp
  const { data: lastUpdateData } = useQuery({
    queryKey: ['rankings-last-update'],
    queryFn: rankingsApi.getLastUpdate,
    refetchInterval: 15_000, // Live-update: last-update timestamp every 15s
    refetchOnWindowFocus: true,
    retry: 2,
  })

  // Filter rankings by search query (client-side)
  const filteredRankings = useMemo(() => {
    if (!rankingsData?.rankings) return []
    
    if (!searchQuery.trim()) {
      return rankingsData.rankings
    }

    const query = searchQuery.toLowerCase()
    return rankingsData.rankings.filter((ranking: Ranking) => {
      return (
        ranking.name.toLowerCase().includes(query) ||
        (ranking.country && ranking.country.toLowerCase().includes(query))
      )
    })
  }, [rankingsData?.rankings, searchQuery])

  // Calculate statistics
  const totalPlayers = rankingsData?.total || 0
  const displayedCount = filteredRankings.length

  // Format last update time
  const formatLastUpdate = (dateString: string | null | undefined) => {
    if (!dateString) return 'Never'
    try {
      const date = new Date(dateString)
      return date.toLocaleString()
    } catch (error) {
      logger.warn('Failed to format rankings last update timestamp', { dateString }, error as Error)
      return 'Unknown'
    }
  }

  const lastUpdate = selectedRankingType === 'WPBA_Women' 
    ? lastUpdateData?.wpba
    : lastUpdateData?.wpa

  // Export to CSV
  const handleExportCSV = () => {
    if (!filteredRankings.length) {
      alert('No data to export')
      return
    }

    const csvContent = [
      ['Rank', 'Player Name', 'Country', 'Points'].join(','),
      ...filteredRankings.map((r: Ranking) => 
        [r.rank, `"${r.name}"`, r.country || '', r.points].join(',')
      )
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${currentRankingInfo.label.replace(/\s+/g, '_')}_rankings_${new Date().toISOString().split('T')[0]}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }

  // Pagination handlers (avoid division by zero when no data)
  const totalPages = Math.max(1, Math.ceil(totalPlayers / itemsPerPage))
  const canGoBack = currentPage > 0
  const canGoForward = currentPage < totalPages - 1

  const handlePrevPage = () => {
    if (canGoBack) {
      setCurrentPage(currentPage - 1)
      setSearchQuery('') // Clear search when changing pages
    }
  }

  const handleNextPage = () => {
    if (canGoForward) {
      setCurrentPage(currentPage + 1)
      setSearchQuery('') // Clear search when changing pages
    }
  }

  // Drill-down: navigate to submenu or select ranking and show table
  const handleMenuAction = (item: DrillItem) => {
    if (item.kind === 'drill') {
      setNavStack((prev) => [...prev, item.id])
    } else {
      setSelectedRankingType(item.type)
      setViewMode('table')
      setCurrentPage(0)
      setSearchQuery('')
    }
  }

  const handleBack = () => {
    if (viewMode === 'table') {
      setViewMode('menu')
      return
    }
    if (navStack.length > 1) {
      setNavStack((prev) => prev.slice(0, -1))
    }
  }

  const currentLevel = navStack[navStack.length - 1]
  const menuItems: DrillItem[] =
    currentLevel === 'top' ? TOP_LEVEL_ITEMS : drillMenus[currentLevel] ?? []
  const showBackButton = viewMode === 'table' || navStack.length > 1

  // Loading state (only when viewing a specific ranking)
  if (viewMode === 'table' && selectedRankingType !== null && rankingsLoading && !rankingsData) {
    return (
      <div className="flex flex-col h-screen bg-slate-950 text-slate-50">
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto">
            <div className="animate-pulse space-y-4">
              <div className="h-8 bg-slate-800 rounded w-1/4"></div>
              <div className="h-64 bg-slate-800 rounded"></div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Error state (only when viewing a specific ranking)
  if (viewMode === 'table' && selectedRankingType !== null && rankingsError && !rankingsData) {
    return (
      <div className="flex flex-col h-screen bg-slate-950 text-slate-50">
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto">
            <div className="bg-red-950/20 border border-red-900/40 rounded-lg p-6">
              <h2 className="text-xl font-semibold text-red-400 mb-2">We couldn&apos;t load rankings</h2>
              <p className="text-slate-400 mb-4">
                {error instanceof Error ? error.message : 'Please check your connection and try again.'}
              </p>
              <button
                onClick={() => queryClient.invalidateQueries({ queryKey: ['rankings'] })}
                className="px-4 py-2 bg-sky-600 text-white rounded-lg hover:bg-sky-500 transition-colors"
              >
                Retry
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-50">
      <div className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="max-w-7xl mx-auto space-y-4 sm:space-y-6">
          {/* Top bar: menu toggle (mobile/tablet) */}
          <div className="flex items-center justify-between gap-2 md:hidden">
            {onSidebarToggle && (
              <button
                type="button"
                onClick={onSidebarToggle}
                className="p-2.5 min-w-[44px] min-h-[44px] flex items-center justify-center rounded-xl hover:bg-accent transition-colors"
                aria-label="Toggle menu"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
            )}
            <span className="text-sm font-medium text-muted-foreground">Rankings</span>
          </div>
          {/* Drill-down: Back + menu (category → division → game) or Back + title when viewing a ranking */}
          <section
            className="rounded-2xl border-2 border-felt/30 backdrop-blur-sm p-4 sm:p-6 md:p-8 shadow-xl bg-gradient-to-br from-slate-900 to-slate-800"
            aria-label={viewMode === 'table' ? 'Current ranking' : 'Choose rankings'}
          >
            <div className="flex items-center gap-3 mb-4">
              {showBackButton && (
                <button
                  type="button"
                  onClick={handleBack}
                  className="flex items-center gap-2 rounded-xl py-2.5 px-3 sm:px-4 min-h-[44px] font-semibold text-sm sm:text-base bg-slate-700/60 hover:bg-slate-600/60 text-white border border-slate-500/50 transition-colors"
                  aria-label="Back"
                >
                  <svg className="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                  </svg>
                  <span className="hidden sm:inline">Back</span>
                </button>
              )}
              {viewMode === 'menu' && (
                <h2 className="text-lg sm:text-2xl font-bold text-white tracking-tight">
                  {currentLevel === 'top' ? '🏆 What would you like to see?' : '🏆 Pick a ranking list'}
                </h2>
              )}
              {viewMode === 'table' && currentRankingInfo && (
                <h2 className="text-lg sm:text-2xl font-bold text-white tracking-tight">
                  🏆 {currentRankingInfo.heroTitle}
                </h2>
              )}
            </div>
            {viewMode === 'menu' && (
              <div className="flex flex-wrap gap-2 sm:gap-3">
                {menuItems.map((item) => (
                  <MenuOptionButton
                    key={item.kind === 'drill' ? item.id : item.type}
                    item={item}
                    onClick={() => handleMenuAction(item)}
                  />
                ))}
              </div>
            )}
            {viewMode === 'table' && currentRankingInfo && (
              <>
                <p className="text-felt font-semibold text-sm sm:text-base">
                  {currentRankingInfo.description}
                </p>
                <p className="text-slate-300 text-sm mt-2">
                  {totalPlayers} players • {currentRankingInfo.label}
                </p>
                <p className="text-slate-400 text-xs mt-1">
                  Last updated: {formatLastUpdate(lastUpdate)}
                </p>
              </>
            )}
          </section>

          {viewMode === 'menu' && currentLevel === 'top' && (
            <p className="text-center text-slate-400 text-sm">
              Tap a category above to open full standings, search players, and export (admins).
            </p>
          )}

          {viewMode === 'table' && currentRankingInfo && (
            <>
          {/* Statistics Cards — Displayed count only (players + association consolidated into Welcome box) */}
          {getLayout('show_rankings_stats_cards', false) && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {getLayout('show_displayed_card', false) && (
                <div className="bg-gradient-to-br from-slate-800 to-slate-900 border border-felt/30 rounded-xl p-4 shadow-lg hover:shadow-xl transition-shadow">
                  <div className="text-xs font-bold uppercase tracking-widest text-felt mb-2 flex items-center gap-2">
                    <span>📊</span> Displayed
                  </div>
                  <div className="text-3xl font-bold text-white tabular-nums">{displayedCount}</div>
                  <p className="text-xs text-slate-400 mt-1">{`${displayedCount === totalPlayers ? 'All' : 'Filtered'} rankings shown`}</p>
                </div>
              )}
            </div>
          )}

          {/* Search and Export */}
          <div className="flex flex-col sm:flex-row gap-3 sm:gap-4">
            <input
              type="text"
              placeholder="Search by player name or country..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex-1 min-w-0 px-4 py-2.5 sm:py-2 bg-card border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <button
              onClick={() => isAdmin && handleExportCSV()}
              disabled={!isAdmin}
              title={isAdmin ? 'Export current rankings to a CSV file' : 'Sign in as Admin to export rankings to CSV'}
              className="min-h-[44px] px-4 py-2.5 bg-card border border-border rounded-lg hover:bg-accent transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 w-full sm:w-auto"
            >
              <span>📥</span>
              Export CSV
            </button>
          </div>

          {/* Rankings Table */}
          <RankingsTable
            rankings={filteredRankings}
            isLoading={rankingsLoading}
            onPlayerClick={(name) => setPlayerModalName(name)}
            emptyReason={totalPlayers === 0 ? 'no-data' : 'search'}
            association={currentRankingInfo.association}
            rankingType={selectedRankingType}
            showEditButton={canEditRankings}
            onEditRow={canEditRankings ? (row) => row.id != null && setEditRow(row) : undefined}
            isAdmin={isAdmin}
            isSuperAdmin={isSuperAdmin}
          />

          {/* Edit ranking row modal (Admin only) */}
          {editRow != null && editRow.id != null && (
            <EditRankingRowModal
              row={editRow}
              onClose={() => setEditRow(null)}
              onSave={(body) => updateRowMutation.mutate({ rowId: editRow.id!, body })}
              isSaving={updateRowMutation.isPending}
            />
          )}

          {/* Player detail modal */}
          <PlayerDetailModal
            isOpen={!!playerModalName}
            onClose={() => setPlayerModalName(null)}
            playerName={playerModalName}
          />

          {/* Pagination Controls */}
          {!searchQuery && (
            <div className="flex flex-wrap items-center justify-between gap-3 bg-card border border-border rounded-lg p-4">
              <button
                onClick={handlePrevPage}
                disabled={!canGoBack || rankingsLoading}
                className="min-h-[44px] px-4 py-2.5 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed order-2 sm:order-1"
              >
                ← Previous
              </button>
              <div className="text-sm text-muted-foreground order-1 sm:order-2 w-full sm:w-auto text-center sm:text-left">
                Page {currentPage + 1} of {totalPages}
              </div>
              <button
                onClick={handleNextPage}
                disabled={!canGoForward || rankingsLoading}
                className="min-h-[44px] px-4 py-2.5 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed order-3"
              >
                Next →
              </button>
            </div>
          )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
