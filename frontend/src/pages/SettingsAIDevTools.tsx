/**
 * Settings > Super Admin > AI Dev Tools (Grok)
 * Scraper triage, tournament QA, rankings NL assist, docs Q&A, email drafts, merge hints, CI log triage.
 */

import { useState } from 'react'
import axios from 'axios'
import {
  scraperDiagnose,
  tournamentQA,
  rankingsAssist,
  docsAssist,
  emailDraft,
  mergeHints,
  ciLogTriage,
} from '@/api/adminDevTools'
import { Wrench, Loader2 } from 'lucide-react'

type TabId =
  | 'scraper'
  | 'tournament'
  | 'rankings'
  | 'docs'
  | 'email'
  | 'merge'
  | 'ci'

const TABS: { id: TabId; label: string }[] = [
  { id: 'scraper', label: 'Scraper diagnose' },
  { id: 'tournament', label: 'Tournament QA' },
  { id: 'rankings', label: 'Rankings assist' },
  { id: 'docs', label: 'Docs Q&A' },
  { id: 'email', label: 'Email draft' },
  { id: 'merge', label: 'Merge hints' },
  { id: 'ci', label: 'CI log triage' },
]

export default function SettingsAIDevToolsPage() {
  const [tab, setTab] = useState<TabId>('scraper')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [output, setOutput] = useState<string>('')

  const [errMsg, setErrMsg] = useState('')
  const [htmlSnip, setHtmlSnip] = useState('')
  const [pageUrl, setPageUrl] = useState('')

  const [tournamentNotes, setTournamentNotes] = useState('')

  const [rankQ, setRankQ] = useState('')

  const [docQ, setDocQ] = useState('')

  const [emailPurpose, setEmailPurpose] = useState('')
  const [emailAudience, setEmailAudience] = useState('')
  const [emailFacts, setEmailFacts] = useState('')
  const [emailTone, setEmailTone] = useState('professional')

  const [mergeNames, setMergeNames] = useState('')
  const [mergeCtx, setMergeCtx] = useState('')

  const [ciLog, setCiLog] = useState('')
  const [ciHint, setCiHint] = useState('')

  async function run() {
    setError(null)
    setOutput('')
    setLoading(true)
    try {
      if (tab === 'scraper') {
        const r = await scraperDiagnose({
          error_message: errMsg,
          html_snippet: htmlSnip,
          page_url: pageUrl,
        })
        setOutput(r.analysis)
      } else if (tab === 'tournament') {
        const r = await tournamentQA(tournamentNotes)
        setOutput(r.analysis)
      } else if (tab === 'rankings') {
        const r = await rankingsAssist(rankQ)
        setOutput(
          JSON.stringify(
            { filters_applied: r.filters_applied, row_count: r.row_count, rows: r.rows },
            null,
            2,
          ),
        )
      } else if (tab === 'docs') {
        const r = await docsAssist(docQ)
        setOutput(`${r.answer}\n\n---\nDocs preview:\n${r.docs_excerpt_preview}`)
      } else if (tab === 'email') {
        const r = await emailDraft({
          purpose: emailPurpose,
          audience: emailAudience,
          key_facts: emailFacts,
          tone: emailTone,
        })
        setOutput(r.draft)
      } else if (tab === 'merge') {
        const names = mergeNames
          .split('\n')
          .map((s) => s.trim())
          .filter(Boolean)
        const r = await mergeHints(names, mergeCtx)
        setOutput(r.hints)
      } else if (tab === 'ci') {
        const r = await ciLogTriage(ciLog, ciHint)
        setOutput(r.suggestion)
      }
    } catch (e: unknown) {
      let msg = String(e)
      if (axios.isAxiosError(e)) {
        const d = e.response?.data as { detail?: string | unknown[] } | undefined
        if (typeof d?.detail === 'string') msg = d.detail
        else if (Array.isArray(d?.detail)) msg = d.detail.map((x) => JSON.stringify(x)).join(', ')
        else if (e.message) msg = e.message
      }
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-5xl text-foreground">
      <div className="flex items-center gap-3 mb-2">
        <Wrench className="w-7 h-7 text-sky-500" />
        <div>
          <h2 className="text-xl font-semibold">AI Dev Tools (Grok)</h2>
          <p className="text-sm text-muted-foreground">
            Super admin only. Uses your configured <code className="text-xs">XAI_API_KEY</code>. Advisory only — no auto-merge or deploy.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 mb-4 border-b border-border pb-3">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              tab === t.id ? 'bg-sky-600 text-white' : 'bg-muted/50 hover:bg-muted text-muted-foreground'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="space-y-3 mb-4">
        {tab === 'scraper' && (
          <>
            <label className="block text-sm font-medium">Error / traceback</label>
            <textarea
              className="w-full min-h-[100px] rounded-md border border-border bg-background p-2 text-sm font-mono"
              value={errMsg}
              onChange={(e) => setErrMsg(e.target.value)}
              placeholder="Exception message or log lines"
            />
            <label className="block text-sm font-medium">Page URL (optional)</label>
            <input
              className="w-full rounded-md border border-border bg-background p-2 text-sm"
              value={pageUrl}
              onChange={(e) => setPageUrl(e.target.value)}
            />
            <label className="block text-sm font-medium">HTML snippet (optional)</label>
            <textarea
              className="w-full min-h-[120px] rounded-md border border-border bg-background p-2 text-xs font-mono"
              value={htmlSnip}
              onChange={(e) => setHtmlSnip(e.target.value)}
            />
          </>
        )}
        {tab === 'tournament' && (
          <>
            <label className="block text-sm font-medium">Notes (JSON or free text)</label>
            <textarea
              className="w-full min-h-[200px] rounded-md border border-border bg-background p-2 text-sm font-mono"
              value={tournamentNotes}
              onChange={(e) => setTournamentNotes(e.target.value)}
              placeholder='e.g. duplicate bracket entries, conflicting scores...'
            />
          </>
        )}
        {tab === 'rankings' && (
          <>
            <label className="block text-sm font-medium">Question</label>
            <input
              className="w-full rounded-md border border-border bg-background p-2 text-sm"
              value={rankQ}
              onChange={(e) => setRankQ(e.target.value)}
              placeholder="e.g. WPA Women players named Kim with Fargo over 600"
            />
            <p className="text-xs text-muted-foreground">
              Grok maps your question to safe filters; results are read-only from the latest snapshot per player/system.
            </p>
          </>
        )}
        {tab === 'docs' && (
          <>
            <label className="block text-sm font-medium">Question</label>
            <textarea
              className="w-full min-h-[80px] rounded-md border border-border bg-background p-2 text-sm"
              value={docQ}
              onChange={(e) => setDocQ(e.target.value)}
              placeholder="How do I restart the API in production?"
            />
          </>
        )}
        {tab === 'email' && (
          <>
            <label className="block text-sm font-medium">Purpose</label>
            <input
              className="w-full rounded-md border border-border bg-background p-2 text-sm"
              value={emailPurpose}
              onChange={(e) => setEmailPurpose(e.target.value)}
            />
            <label className="block text-sm font-medium">Audience</label>
            <input
              className="w-full rounded-md border border-border bg-background p-2 text-sm"
              value={emailAudience}
              onChange={(e) => setEmailAudience(e.target.value)}
            />
            <label className="block text-sm font-medium">Key facts</label>
            <textarea
              className="w-full min-h-[100px] rounded-md border border-border bg-background p-2 text-sm"
              value={emailFacts}
              onChange={(e) => setEmailFacts(e.target.value)}
            />
            <label className="block text-sm font-medium">Tone</label>
            <input
              className="w-full rounded-md border border-border bg-background p-2 text-sm"
              value={emailTone}
              onChange={(e) => setEmailTone(e.target.value)}
            />
          </>
        )}
        {tab === 'merge' && (
          <>
            <label className="block text-sm font-medium">Player names (one per line)</label>
            <textarea
              className="w-full min-h-[160px] rounded-md border border-border bg-background p-2 text-sm font-mono"
              value={mergeNames}
              onChange={(e) => setMergeNames(e.target.value)}
            />
            <label className="block text-sm font-medium">Context (optional)</label>
            <textarea
              className="w-full min-h-[80px] rounded-md border border-border bg-background p-2 text-sm"
              value={mergeCtx}
              onChange={(e) => setMergeCtx(e.target.value)}
            />
          </>
        )}
        {tab === 'ci' && (
          <>
            <label className="block text-sm font-medium">Log excerpt</label>
            <textarea
              className="w-full min-h-[220px] rounded-md border border-border bg-background p-2 text-xs font-mono"
              value={ciLog}
              onChange={(e) => setCiLog(e.target.value)}
              placeholder="Paste CI or service failure log"
            />
            <label className="block text-sm font-medium">Workflow hint (optional)</label>
            <input
              className="w-full rounded-md border border-border bg-background p-2 text-sm"
              value={ciHint}
              onChange={(e) => setCiHint(e.target.value)}
              placeholder="e.g. Tests / api-unit-tests"
            />
          </>
        )}
      </div>

      <button
        type="button"
        onClick={() => void run()}
        disabled={loading}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-sm font-medium disabled:opacity-50"
      >
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
        Run
      </button>

      {error && (
        <div className="mt-4 rounded-lg border border-red-500/50 bg-red-950/30 p-3 text-sm text-red-200 whitespace-pre-wrap">
          {error}
        </div>
      )}

      {output && (
        <div className="mt-4 rounded-lg border border-border bg-card/40 p-4">
          <h3 className="text-sm font-semibold mb-2 text-muted-foreground">Result</h3>
          <pre className="text-sm whitespace-pre-wrap break-words max-h-[480px] overflow-y-auto">{output}</pre>
        </div>
      )}
    </div>
  )
}
