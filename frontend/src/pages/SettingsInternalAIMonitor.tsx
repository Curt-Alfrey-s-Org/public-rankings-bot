/**
 * Settings > Admin > AI Monitor (internal) — super admin only.
 * Ollama activity not tagged as public_web / app_authenticated (batch, extractors, etc.).
 */

import { useState, useEffect, useCallback } from 'react'
import { apiClient } from '@/api/client'
import { Bot, AlertTriangle, Clock, Filter, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react'

interface ActivityEntry {
  id: number
  created_at: string
  feature: string
  model: string
  prompt_summary: string
  request_text: string
  response_text: string
  duration_seconds: number
  eval_tokens: number
  prompt_tokens: number
  status: string
  error_message: string | null
}

interface FeatureSummary {
  feature: string
  count: number
  avg_duration: number
  errors: number
}

interface MonitorData {
  entries: ActivityEntry[]
  total: number
  feature_summary: FeatureSummary[]
  error?: string
}

const FEATURE_LABELS: Record<string, string> = {
  name_resolution: 'Name Matching',
  bracket_extraction: 'Bracket Extraction',
  pdf_extraction: 'PDF Extraction',
  text_coaching: 'Text Coaching',
  player_narrative: 'Player Narrative',
  matchup_narrative: 'Matchup Narrative',
  rankings_assistant: 'Rankings Assistant',
  generate: 'Generate',
  chat: 'Chat',
}

function featureLabel(f: string): string {
  return FEATURE_LABELS[f] || f
}

function formatDuration(s: number): string {
  if (s < 1) return `${(s * 1000).toFixed(0)}ms`
  return `${s.toFixed(1)}s`
}

function timeAgo(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const diff = Math.floor((now.getTime() - d.getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function ExpandableText({ text, maxLen = 300 }: { text: string; maxLen?: number }) {
  const [expanded, setExpanded] = useState(false)
  if (!text) return <span className="text-muted-foreground italic">empty</span>
  if (text.length <= maxLen) return <span className="whitespace-pre-wrap break-words">{text}</span>
  return (
    <div>
      <span className="whitespace-pre-wrap break-words">
        {expanded ? text : text.slice(0, maxLen) + '...'}
      </span>
      <button
        onClick={() => setExpanded(!expanded)}
        className="ml-1 text-sky-500 hover:text-sky-400 text-xs font-medium"
      >
        {expanded ? 'Show less' : 'Show more'}
      </button>
    </div>
  )
}

export default function SettingsInternalAIMonitorPage() {
  const [data, setData] = useState<MonitorData | null>(null)
  const [loading, setLoading] = useState(true)
  const [filterFeature, setFilterFeature] = useState<string>('')
  const [filterStatus, setFilterStatus] = useState<string>('')
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)

  const fetchData = useCallback(async () => {
    try {
      const params: Record<string, string> = { limit: '100' }
      if (filterFeature) params.feature = filterFeature
      if (filterStatus) params.status = filterStatus
      const { data: d } = await apiClient.get<MonitorData>('/admin/ai-monitor/internal', { params })
      setData(d)
    } catch (e: any) {
      setData({ entries: [], total: 0, feature_summary: [], error: e.message || 'Failed to load' })
    } finally {
      setLoading(false)
    }
  }, [filterFeature, filterStatus])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(fetchData, 10_000)
    return () => clearInterval(interval)
  }, [autoRefresh, fetchData])

  const totalCalls = data?.feature_summary?.reduce((s, f) => s + f.count, 0) ?? 0
  const totalErrors = data?.feature_summary?.reduce((s, f) => s + f.errors, 0) ?? 0

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-3">
            <Bot className="h-6 w-6 text-amber-500" />
            <h2 className="text-xl font-semibold">AI Monitor (internal)</h2>
            <span className="text-sm text-muted-foreground">Super admin — batch &amp; untagged LLM</span>
          </div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 text-sm text-muted-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded border-slate-600"
              />
              Auto-refresh
            </label>
            <button
              onClick={() => { setLoading(true); fetchData() }}
              className="p-1.5 rounded-md hover:bg-slate-700 text-muted-foreground"
              title="Refresh now"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
        <p className="text-xs text-muted-foreground max-w-3xl">
          Rows here exclude <strong className="text-slate-300">website / app user</strong> trust zones. May contain
          operational prompts — do not expose this page publicly. For ALFa orchestrator runs, use the{' '}
          <strong className="text-slate-300">operator console</strong> on the ALFa host (see alfa-ai docs).
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="rounded-lg bg-slate-800/50 border border-slate-700 p-3">
          <div className="text-xs text-muted-foreground mb-1">Total Calls</div>
          <div className="text-2xl font-bold">{totalCalls}</div>
        </div>
        <div className="rounded-lg bg-slate-800/50 border border-slate-700 p-3">
          <div className="text-xs text-muted-foreground mb-1">Errors</div>
          <div className={`text-2xl font-bold ${totalErrors > 0 ? 'text-red-400' : 'text-green-400'}`}>
            {totalErrors}
          </div>
        </div>
        <div className="rounded-lg bg-slate-800/50 border border-slate-700 p-3">
          <div className="text-xs text-muted-foreground mb-1">Features Active</div>
          <div className="text-2xl font-bold">{data?.feature_summary?.length ?? 0}</div>
        </div>
        <div className="rounded-lg bg-slate-800/50 border border-slate-700 p-3">
          <div className="text-xs text-muted-foreground mb-1">Showing</div>
          <div className="text-2xl font-bold">{data?.entries?.length ?? 0}<span className="text-sm text-muted-foreground">/{data?.total ?? 0}</span></div>
        </div>
      </div>

      {data?.feature_summary && data.feature_summary.length > 0 && (
        <div className="rounded-lg bg-slate-800/50 border border-slate-700 p-4">
          <h3 className="text-sm font-medium mb-3 text-muted-foreground">Feature Breakdown</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {data.feature_summary.map((f) => (
              <button
                key={f.feature}
                onClick={() => setFilterFeature(filterFeature === f.feature ? '' : f.feature)}
                className={`text-left rounded-md p-2 text-sm border transition-colors ${
                  filterFeature === f.feature
                    ? 'border-amber-500 bg-amber-500/10'
                    : 'border-slate-700 hover:border-slate-600'
                }`}
              >
                <div className="font-medium">{featureLabel(f.feature)}</div>
                <div className="text-xs text-muted-foreground">
                  {f.count} calls, avg {formatDuration(f.avg_duration)}
                  {f.errors > 0 && <span className="text-red-400 ml-1">({f.errors} errors)</span>}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="flex gap-2 items-center">
        <Filter className="h-4 w-4 text-muted-foreground" />
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="bg-slate-800 border border-slate-700 rounded-md px-2 py-1 text-sm"
        >
          <option value="">All statuses</option>
          <option value="success">Success only</option>
          <option value="error">Errors only</option>
        </select>
        {(filterFeature || filterStatus) && (
          <button
            onClick={() => { setFilterFeature(''); setFilterStatus('') }}
            className="text-xs text-sky-500 hover:text-sky-400"
          >
            Clear filters
          </button>
        )}
      </div>

      {data?.error && (
        <div className="rounded-lg bg-red-900/20 border border-red-800 p-4 text-red-300 text-sm">
          <AlertTriangle className="inline h-4 w-4 mr-1" />
          {data.error}
        </div>
      )}

      {!loading && data?.entries?.length === 0 && !data.error && (
        <div className="text-center py-12 text-muted-foreground">
          <Bot className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p>No internal Ollama activity in this view.</p>
          <p className="text-sm mt-1">Untagged or non–website-zone calls will appear here.</p>
        </div>
      )}

      <div className="space-y-2">
        {data?.entries?.map((entry) => {
          const isExpanded = expandedId === entry.id
          const isError = entry.status === 'error'
          return (
            <div
              key={entry.id}
              className={`rounded-lg border p-3 transition-colors cursor-pointer ${
                isError
                  ? 'border-red-800 bg-red-900/10 hover:bg-red-900/20'
                  : 'border-slate-700 bg-slate-800/30 hover:bg-slate-800/60'
              }`}
              onClick={() => setExpandedId(isExpanded ? null : entry.id)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                    isError ? 'bg-red-800 text-red-200' : 'bg-amber-900/80 text-amber-200'
                  }`}>
                    {featureLabel(entry.feature)}
                  </span>
                  <span className="text-xs text-muted-foreground">{entry.model}</span>
                  <span className="text-xs text-muted-foreground flex items-center gap-0.5">
                    <Clock className="h-3 w-3" />
                    {formatDuration(entry.duration_seconds)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">{timeAgo(entry.created_at)}</span>
                  {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </div>
              </div>

              <div className="mt-1.5 text-sm">
                {isError ? (
                  <span className="text-red-300">{entry.error_message || 'Unknown error'}</span>
                ) : (
                  <span className="text-slate-300 line-clamp-2">{entry.prompt_summary}</span>
                )}
              </div>
              {!isError && entry.response_text ? (
                <div className="mt-1 text-xs text-slate-500 line-clamp-2" title="Expand row for full response">
                  <span className="text-slate-600">Response preview:</span> {entry.response_text}
                </div>
              ) : null}

              {isExpanded && (
                <div className="mt-3 space-y-3 border-t border-slate-700 pt-3">
                  <div>
                    <div className="text-xs font-medium text-muted-foreground mb-1">Request</div>
                    <div className="text-sm bg-slate-900 rounded p-2 border border-slate-700 max-h-60 overflow-y-auto">
                      <ExpandableText text={entry.request_text} maxLen={1000} />
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-medium text-muted-foreground mb-1">Response</div>
                    <div className={`text-sm rounded p-2 border max-h-60 overflow-y-auto ${
                      isError ? 'bg-red-900/20 border-red-800' : 'bg-slate-900 border-slate-700'
                    }`}>
                      <ExpandableText text={entry.response_text || entry.error_message || ''} maxLen={1000} />
                    </div>
                  </div>
                  <div className="flex gap-4 text-xs text-muted-foreground">
                    <span>Eval tokens: {entry.eval_tokens}</span>
                    <span>Prompt tokens: {entry.prompt_tokens}</span>
                    <span>Duration: {formatDuration(entry.duration_seconds)}</span>
                    <span>{new Date(entry.created_at).toLocaleString()}</span>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
