import { apiClient } from '@/api/client'

export async function scraperDiagnose(payload: {
  error_message: string
  html_snippet?: string
  page_url?: string
}): Promise<{ analysis: string }> {
  const { data } = await apiClient.post('/admin/dev-tools/scraper-diagnose', payload)
  return data
}

export async function tournamentQA(notes: string): Promise<{ analysis: string }> {
  const { data } = await apiClient.post('/admin/dev-tools/tournament-qa', { notes })
  return data
}

export async function rankingsAssist(question: string): Promise<{
  filters_applied: Record<string, unknown>
  row_count: number
  rows: Record<string, unknown>[]
}> {
  const { data } = await apiClient.post('/admin/dev-tools/rankings-assist', { question })
  return data
}

export async function docsAssist(question: string): Promise<{ answer: string; docs_excerpt_preview: string }> {
  const { data } = await apiClient.post('/admin/dev-tools/docs-assist', { question })
  return data
}

export async function emailDraft(payload: {
  purpose: string
  audience: string
  key_facts: string
  tone?: string
}): Promise<{ draft: string }> {
  const { data } = await apiClient.post('/admin/dev-tools/email-draft', payload)
  return data
}

export async function mergeHints(player_names: string[], context?: string): Promise<{ hints: string }> {
  const { data } = await apiClient.post('/admin/dev-tools/merge-hints', { player_names, context: context ?? '' })
  return data
}

export async function ciLogTriage(log_excerpt: string, workflow_hint?: string): Promise<{ suggestion: string }> {
  const { data } = await apiClient.post('/admin/dev-tools/ci-log-triage', {
    log_excerpt,
    workflow_hint: workflow_hint ?? '',
  })
  return data
}
