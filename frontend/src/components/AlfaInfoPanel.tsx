import { useState } from 'react'
import { ChevronDown } from 'lucide-react'

interface AlfaInfoPanelProps {
  className?: string
  adminOnly?: boolean
}

export default function AlfaInfoPanel({ className = '', adminOnly = false }: AlfaInfoPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <div className={`bg-purple-900/15 border border-purple-700/40 rounded-lg p-4 ${className}`}>
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between text-left hover:bg-purple-900/25 p-2 rounded transition-colors"
      >
        <div>
          <h3 className="font-semibold text-purple-300 text-sm flex items-center gap-2">
            ℹ️ About ALFa Rating System
            {adminOnly && <span className="text-[10px] px-2 py-0.5 bg-purple-700/50 rounded text-purple-200">Admin Only</span>}
          </h3>
          <p className="text-xs text-purple-300/70 mt-1">Advanced Loss-Free Algorithm — Beyond Fargo's Rating</p>
        </div>
        <ChevronDown
          className={`w-4 h-4 text-purple-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
        />
      </button>

      {isExpanded && (
        <div className="mt-4 space-y-4 text-sm text-slate-300">
          <div>
            <h4 className="font-semibold text-purple-300 mb-2">📊 What is ALFa?</h4>
            <p className="text-slate-400 leading-relaxed">
              ALFa (Advanced Loss-Free Algorithm) is a premium rating system that goes beyond traditional Fargo scores. It combines official tournament standings, accumulated points, Fargo ratings, and recent match history to provide a more comprehensive player evaluation. Think of it as "Fargo on steroids" — capturing more nuances of player skill and consistency.
            </p>
          </div>

          <div>
            <h4 className="font-semibold text-purple-300 mb-2">🔢 What Does the ALFa Rating Number Mean?</h4>
            <p className="text-slate-400 leading-relaxed">
              Higher ALFa numbers = Better/stronger players. The scale is absolute and comparable across all players — an ALFa 650 player is objectively stronger than an ALFa 550 player. The rating represents overall player strength accounting for all sources of data.
            </p>
          </div>

          <div>
            <h4 className="font-semibold text-purple-300 mb-2">⚙️ How is the ALFa Rating Calculated?</h4>
            <p className="text-slate-400 mb-2">ALFa combines four data sources with intelligent weighting:</p>
            <div className="space-y-2 ml-2 border-l-2 border-purple-700/50 pl-3">
              <div>
                <span className="font-semibold text-purple-200">Official Tournament Rank (40%)</span>
                <p className="text-xs text-slate-500">Your current position in the official WPBA/WPA rankings</p>
              </div>
              <div>
                <span className="font-semibold text-purple-200">Tournament Points (60%)</span>
                <p className="text-xs text-slate-500">Points accumulated through official tournament participation</p>
              </div>
              <div>
                <span className="font-semibold text-purple-200">Fargo Rating (35% when available)</span>
                <p className="text-xs text-slate-500">Normalized Fargo score from FairMatch Inc. — adds validated skill metric</p>
              </div>
              <div>
                <span className="font-semibold text-purple-200">Recent Match History (15%)</span>
                <p className="text-xs text-slate-500">Your actual tournament results — recent wins/losses vs other players</p>
              </div>
            </div>
            <p className="text-xs text-purple-400 mt-3 italic">When Fargo is unavailable, tournament data (rank + points) and history carry the full weight.</p>
          </div>

          <div>
            <h4 className="font-semibold text-purple-300 mb-2">📈 ALFa Win Odds % — How Are They Calculated?</h4>
            <p className="text-slate-400 mb-2">When two players match up, ALFa predicts win probability by analyzing:</p>
            <div className="space-y-2 ml-2 border-l-2 border-purple-700/50 pl-3">
              <div>
                <span className="font-semibold text-purple-200">Rating Gap (35% influence)</span>
                <p className="text-xs text-slate-500">The difference in ALFa ratings — larger gaps = more confidence</p>
              </div>
              <div>
                <span className="font-semibold text-purple-200">Table Size Effect (15% influence)</span>
                <p className="text-xs text-slate-500">9ft and 10ft tables may slightly favor higher-ranked players</p>
              </div>
              <div>
                <span className="font-semibold text-purple-200">Game Format (15% influence)</span>
                <p className="text-xs text-slate-500">9-ball, 10-ball, 8-ball, and mixed formats have different skill curves</p>
              </div>
              <div>
                <span className="font-semibold text-purple-200">Race Length (10% influence)</span>
                <p className="text-xs text-slate-500">Longer races (higher race-to) reduce luck/variance — skill matters more</p>
              </div>
            </div>
            <p className="text-xs text-purple-400 mt-3 italic">These factors are combined using advanced logistic regression — the same math used in professional sports analytics.</p>
          </div>

          <div className="bg-purple-900/30 border border-purple-700/30 rounded p-3">
            <h4 className="font-semibold text-purple-300 mb-2">✅ Confidence Score</h4>
            <p className="text-slate-400 text-xs">
              Each ALFa prediction includes a confidence percentage (0-100%). Higher confidence means the system has strong data on both players. Low confidence might indicate newer players or incomplete Fargo data.
            </p>
          </div>

          <div className="bg-amber-900/20 border border-amber-700/30 rounded p-3">
            <h4 className="font-semibold text-amber-300 mb-2">🔍 Status</h4>
            <p className="text-slate-400 text-xs">
              ALFa is currently in <strong>admin-only preview</strong>. We're validating accuracy first before releasing to all players. Once performance is proven across tournaments, it will be available to everyone.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
