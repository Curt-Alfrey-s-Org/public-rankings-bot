/**
 * Featured players section — Tournament Champions Showcase
 * Highlights top WPBA & WPA players with professional styling
 */

export interface FeaturedPlayer {
  name: string
  title: string
  /** Optional role/achievement */
  achievement?: string
  /** Optional image URL; use placeholder if not licensed */
  imageUrl?: string | null
  /** Placeholder initials when no image */
  initials?: string
  /** Ranking/points info */
  ranking?: number
}

const FEATURED: FeaturedPlayer[] = [
  {
    name: 'Tournament Rankings',
    title: 'Professional Billiards',
    achievement: 'WPBA & WPA Champions',
    imageUrl: null,
    initials: '🏆',
  },
  {
    name: 'World Pool Association',
    title: "Women's Rankings",
    achievement: 'WPA Women Champions',
    imageUrl: null,
    initials: '🌍',
  },
  {
    name: "Women's Professional",
    title: 'Billiard Association',
    achievement: 'WPBA Champions',
    imageUrl: null,
    initials: '👑',
  },
]

function ChampionCard({ player, featured = false }: { player: FeaturedPlayer; featured?: boolean }) {
  if (featured) {
    return (
      <div className="rounded-xl border border-felt/40 bg-gradient-to-br from-slate-800 to-slate-900 overflow-hidden shadow-lg hover:shadow-xl transition-shadow p-6">
        <div className="flex items-start justify-between mb-4">
          <div className="text-4xl font-bold text-felt bg-slate-700/50 w-16 h-16 rounded-lg flex items-center justify-center">
            {player.imageUrl ? (
              <img
                src={player.imageUrl}
                alt=""
                className="w-16 h-16 rounded-lg object-cover"
              />
            ) : (
              player.initials ?? '🎱'
            )}
          </div>
          {player.achievement && (
            <div className="bg-felt/20 px-3 py-1 rounded-full">
              <span className="text-xs font-bold text-felt">FEATURED</span>
            </div>
          )}
        </div>
        <h3 className="text-xl font-bold text-white mb-1">{player.name}</h3>
        <p className="text-felt text-sm font-semibold mb-1">{player.title}</p>
        {player.achievement && (
          <p className="text-slate-300 text-xs">{player.achievement}</p>
        )}
        {player.ranking && (
          <div className="mt-3 pt-3 border-t border-felt/20">
            <span className="text-white font-mono font-bold">#{player.ranking}</span>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-felt/30 bg-slate-800/50 overflow-hidden shadow hover:shadow-lg transition-shadow p-3 h-full flex flex-col">
      <div className="text-3xl font-bold text-felt/80 mb-2 text-center">
        {player.imageUrl ? (
          <img
            src={player.imageUrl}
            alt=""
            className="w-12 h-12 rounded-full object-cover mx-auto"
          />
        ) : (
          player.initials ?? '🎱'
        )}
      </div>
      <h3 className="font-semibold text-white text-sm text-center truncate mb-1">{player.name}</h3>
      <p className="text-felt text-xs font-semibold text-center line-clamp-2">{player.title}</p>
      {player.achievement && (
        <p className="text-slate-400 text-xs mt-2 text-center">{player.achievement}</p>
      )}
    </div>
  )
}

export default function FeaturedPlayers() {
  const [featured, ...rest] = FEATURED
  return (
    <section
      className="rounded-lg border border-felt/30 bg-gradient-to-br from-slate-800/50 to-slate-900/30 p-4"
      aria-labelledby="featured-players-heading"
    >
      <h2 id="featured-players-heading" className="text-lg font-bold text-white mb-4 flex items-center gap-2">
        <span className="text-felt text-xl">🏆</span> Championship Rankings
      </h2>
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1 min-w-0">
          <ChampionCard player={featured} featured />
        </div>
        <div className="flex gap-3 overflow-x-auto pb-1 sm:pb-0 sm:flex-1 sm:flex-wrap sm:overflow-visible">
          {rest.map((p) => (
            <div key={p.name} className="flex-shrink-0 w-32 sm:w-40">
              <ChampionCard player={p} />
            </div>
          ))}
        </div>
      </div>
      <p className="text-xs text-slate-400 mt-3 border-t border-felt/20 pt-2 italic">
        World-class professional billiards rankings from WPBA & WPA
      </p>
    </section>
  )
}
