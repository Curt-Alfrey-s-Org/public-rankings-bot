/**
 * Covert Ops — Recon on opponents
 * Player inputs opponent ("victim") name and presses Recon; AI analyzes the opponent's
 * most current YouTube match video and exposes weaknesses. "The battle is won before it's even begun."
 */

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { covertOpsApi, type ReconResponse } from '@/api/covertOps'
import { toast } from '@/lib/toast'

export default function CovertOpsPage() {
  const [victim, setVictim] = useState('')

  const reconMutation = useMutation({
    mutationFn: (name: string) => covertOpsApi.recon(name),
    onSuccess: () => {
      toast.success('Recon complete')
    },
    onError: (err: unknown) => {
      toast.error(err instanceof Error ? err.message : 'Recon failed')
    },
  })

  const handleRecon = () => {
    const name = victim.trim()
    if (!name) {
      toast.error('Enter opponent name')
      return
    }
    reconMutation.mutate(name)
  }

  const result = reconMutation.data as ReconResponse | undefined

  return (
    <div className="mx-auto max-w-3xl space-y-8 p-6">
      <header className="text-center">
        <h1 className="text-3xl font-bold text-white">Covert Ops</h1>
        <p className="mt-2 text-slate-400 italic font-medium">
          The battle is won before it&apos;s even begun.
        </p>
        <p className="mt-2 text-sm text-slate-500">
          Enter your opponent&apos;s name. We&apos;ll find their most current YouTube match video
          and analyze it to expose weaknesses in their game.
        </p>
      </header>

      <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-6">
        <label className="block text-sm font-medium text-slate-300 mb-2">
          Victim (opponent name)
        </label>
        <div className="flex gap-3 flex-wrap">
          <input
            type="text"
            value={victim}
            onChange={(e) => setVictim(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleRecon()}
            placeholder="e.g. Kristina Tkach"
            className="flex-1 min-w-[200px] rounded-lg border border-slate-600 bg-slate-900 px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500"
          />
          <button
            type="button"
            onClick={handleRecon}
            disabled={reconMutation.isPending}
            className="px-6 py-3 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {reconMutation.isPending ? 'Recon…' : 'Recon'}
          </button>
        </div>
      </div>

      {result && (
        <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-white">
            Recon: {result.victim_name}
          </h2>
          {result.video_url && (
            <p className="text-sm text-slate-400">
              Video: {result.video_title && <span>{result.video_title} — </span>}
              <a
                href={result.video_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-amber-400 hover:underline"
              >
                Watch
              </a>
            </p>
          )}
          {result.summary && (
            <p className="text-slate-300">{result.summary}</p>
          )}
          {result.weaknesses.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-slate-400 mb-2">Weaknesses</h3>
              <ul className="list-disc list-inside space-y-1 text-slate-300">
                {result.weaknesses.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
