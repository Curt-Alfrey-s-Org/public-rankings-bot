/** PlayerCard - Shows player name, rank, FARGO, stats, sparkline */

import type { PlayerComparison } from '@/features/head-to-head/types/comparison'

interface PlayerCardProps {
  player: PlayerComparison
  side: 'left' | 'right'
  showAlfa?: boolean
}

export function PlayerCard({ player, side, showAlfa = false }: PlayerCardProps) {
  const trend = player.ranking_trend ?? []
  const sparklineData = trend.slice(0, 5).map((t) => t.new ?? t.old ?? 0).filter(Boolean)

  return (
    <div
      className={`rounded-lg border border-slate-700 bg-slate-800/50 p-4 ${
        side === 'left' ? 'border-sky-600/50' : 'border-amber-600/50'
      }`}
    >
      <h3 className="text-lg font-semibold text-white">{player.name}</h3>
      <div className="mt-2 space-y-1 text-sm">
        <p className="text-slate-300">
          Rank: <span className="text-sky-400">#{player.rank}</span>
        </p>
        <p className="text-slate-300">
          FARGO: <span className={player.fargo_rating != null ? 'text-amber-400' : 'text-slate-500'}>{player.fargo_rating != null ? player.fargo_rating.toFixed(0) : 'none'}</span>
        </p>
        {showAlfa && (
          <p className="text-slate-300">
            ALFa Rating <span className="text-[10px] opacity-80">(fargo on steroids)</span>:{' '}
            <span className={player.alfa_rating != null ? 'text-amber-400' : 'text-slate-500'}>{player.alfa_rating != null ? player.alfa_rating.toFixed(0) : '—'}</span>
          </p>
        )}
        {(player.wins != null || player.losses != null) && (
          <p className="text-slate-300">
            Record: {player.wins ?? 0}–{player.losses ?? 0}
            {player.win_pct != null && ` (${(player.win_pct * 100).toFixed(1)}%)`}
          </p>
        )}
      </div>
      {sparklineData.length > 0 && (
        <div className="mt-3 flex h-8 items-end gap-1">
          {sparklineData.map((v, i) => (
            <div
              key={i}
              className="min-w-[4px] flex-1 rounded-t bg-sky-500/60"
              style={{ height: `${Math.max(20, (v / 100) * 100)}%` }}
              title={`Rank: ${v}`}
            />
          ))}
        </div>
      )}
    </div>
  )
}
