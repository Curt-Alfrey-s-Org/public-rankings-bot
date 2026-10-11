import { useState } from 'react'
import axios from 'axios'
import { useAuth } from '@/contexts/AuthContext'
import { askRankingsAssistant } from '@/api/rankingsAssistant'
import { logger } from '@/lib/logger'

const TIER_HELP: Record<string, string> = {
  player:
    'Public leaderboard snapshots and your own linked player stats (if your account is linked to a player).',
  scorekeeper:
    'Tablet or device in scorekeeper mode (assigned by a director): same operational snapshot as directors—recent tournaments, upcoming events sample, clock settings—plus public rankings. Not a personal player role.',
  director:
    'Everything in the player tier, plus recent past tournaments, upcoming events sample, and director clock settings. Directors control which tablets run in scorekeeper mode.',
  admin:
    'Everything above, plus aggregate user counts by role and latest ranking snapshot dates per system.',
  super_admin:
    'Broadest snapshot (including non-secret environment flags). Answers still must follow CONTEXT_JSON only.',
}

function assistantTierForRole(role: string | undefined): keyof typeof TIER_HELP {
  const r = (role || '').toLowerCase()
  if (r === 'super_admin') return 'super_admin'
  if (r === 'admin') return 'admin'
  if (r === 'director') return 'director'
  if (r === 'score_keeper') return 'scorekeeper'
  return 'player'
}

export default function SettingsRankingsAssistant() {
  const { user } = useAuth()
  const expectedTier = user ? assistantTierForRole(user.role) : 'player'
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<string | null>(null)
  const [tier, setTier] = useState<string | null>(null)
  const [keys, setKeys] = useState<string[] | null>(null)
  const [disclaimer, setDisclaimer] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const q = question.trim()
    if (!q || loading) return
    setLoading(true)
    setError(null)
    setAnswer(null)
    setTier(null)
    setKeys(null)
    setDisclaimer(null)
    try {
      const res = await askRankingsAssistant(q)
      setAnswer(res.answer)
      setTier(res.assistant_tier)
      setKeys(res.context_keys)
      setDisclaimer(res.disclaimer)
    } catch (err: unknown) {
      let msg = 'Request failed'
      if (axios.isAxiosError(err)) {
        const d = err.response?.data?.detail
        if (typeof d === 'string') msg = d
        else if (Array.isArray(d)) msg = d.map((x: { msg?: string }) => x?.msg).filter(Boolean).join(', ') || msg
      } else if (err instanceof Error) msg = err.message
      setError(msg)
      logger.warn('Rankings assistant ask failed', undefined, err instanceof Error ? err : undefined)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-3xl space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white">Rankings Assistant</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Ask questions about rankings and tournaments. Answers use only data your role is allowed to see (same idea as
          the rest of the app). Requires Ollama (<code className="text-xs bg-slate-800 px-1 rounded">OLLAMA_ENABLED</code>
          ).
        </p>
        {user && (
          <p className="text-xs text-slate-400 mt-2">
            Signed in as <span className="text-slate-200">{user.user}</span> — role{' '}
            <span className="text-slate-200">{user.role.replace('_', ' ')}</span>
            {' · '}
            Assistant data tier: <span className="text-sky-400">{tier ?? expectedTier}</span>
          </p>
        )}
      </div>

      <div className="rounded-lg border border-slate-700 bg-slate-900/50 p-4 text-sm text-slate-300">
        <p className="font-medium text-slate-200 mb-2">Your data scope</p>
        <p className="text-slate-400">
          <span className="text-slate-200 capitalize">{expectedTier.replace('_', ' ')}:</span>{' '}
          {TIER_HELP[expectedTier]}
        </p>
        <p className="text-xs text-slate-500 mt-2">
          Higher roles include broader context; the server builds the JSON you are allowed to see—same rules as the rest
          of the app.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <label htmlFor="ra-question" className="block text-sm font-medium text-slate-300">
          Your question
        </label>
        <textarea
          id="ra-question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={4}
          maxLength={2000}
          placeholder="e.g. Who is ranked first in WPBA Women in the latest snapshot?"
          className="w-full rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-slate-pool_opt_in placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-sky-600"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="px-4 py-2 rounded-lg bg-sky-600 text-white font-medium hover:bg-sky-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Thinking…' : 'Ask'}
        </button>
      </form>

      {error && (
        <div className="rounded-lg border border-amber-800 bg-amber-950/30 p-4 text-amber-pool_opt_in text-sm">{error}</div>
      )}

      {answer && (
        <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-4 space-y-3">
          <h3 className="text-sm font-semibold text-slate-200">Answer</h3>
          <p className="text-slate-pool_opt_in whitespace-pre-wrap">{answer}</p>
          {keys && keys.length > 0 && (
            <p className="text-xs text-slate-500">
              Data sections used: {keys.join(', ')}
            </p>
          )}
          {disclaimer && <p className="text-xs text-slate-500 border-t border-slate-700 pt-2">{disclaimer}</p>}
        </div>
      )}
    </div>
  )
}
