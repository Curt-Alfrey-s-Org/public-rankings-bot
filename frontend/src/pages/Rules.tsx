/**
 * Rules, License, & Points: WPA and WPBA rules, license docs, and tour points.
 * Tabbed by organization (WPA / WPBA).
 */

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { rulesApi } from '@/api/rules'

/** Official WPA license/sanctioning PDFs (hosted on wpapool.com). */
const WPA_LICENSE_DOCS = [
  { title: 'WPA Athletes License', url: 'https://wpapool.com/wp-content/uploads/2025/09/2025.07.03-WPA-ATHLETES-LICENSE.pdf' },
  { title: 'WPA Players License', url: 'https://wpapool.com/wp-content/uploads/2025/09/2025.07.03-WPA-ATHLETES-LICENSE.pdf' },
  { title: 'WPA Sanctioning Regulations', url: 'https://wpapool.com/wp-content/uploads/2025/04/2025.02.12-WPA-Sanctioning-Regulations.pdf' },
] as const

/** WPBA rules and points — 9-ball PDF must match official hosted revision (Rev 5.16.25). */
const WPBA_DOCS = [
  {
    title: 'Download 9 Ball Rules',
    url: 'https://static1.squarespace.com/static/5acf990e8ab7220efae54260/t/6827a9221dc42503382149e3/1747429667111/WPBA+9-Ball+Rules+-+%28Rev+5.16.25%29.pdf',
    type: 'pdf' as const,
  },
  { title: 'WPBA Point System', url: 'https://wpba.com/s/WPBA-Point-System-rev-12326jpg.png', type: 'image' as const },
] as const

type TabId = 'wpa' | 'wpba'

function DocCard({
  title,
  url,
  type,
}: { title: string; url: string; type: 'pdf' | 'image' }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-3 p-4 rounded-xl bg-slate-800/60 border border-slate-700 hover:border-slate-500 hover:bg-slate-800/80 transition-colors group"
    >
      <span className="text-2xl flex-shrink-0" aria-hidden>{type === 'pdf' ? '📄' : '📊'}</span>
      <span className="font-medium text-white group-hover:text-sky-300">{title}</span>
      <span className="ml-auto text-slate-500 group-hover:text-slate-400" aria-hidden>
        Open {type === 'pdf' ? 'PDF' : 'image'} ↗
      </span>
    </a>
  )
}

export default function Rules() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get('tab')
  const [activeTab, setActiveTab] = useState<TabId>(tabParam === 'wpba' ? 'wpba' : 'wpa')

  const { data: rules, isLoading, error } = useQuery({
    queryKey: ['wpa-rules'],
    queryFn: () => rulesApi.list(),
    staleTime: 5 * 60 * 1000,
  })

  return (
    <div className="flex flex-col min-h-full bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-50">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-4 md:p-6 space-y-6">
          <header>
            <h1 className="text-2xl md:text-3xl font-bold text-white">Rules, License, & Points</h1>
            <p className="text-slate-400 mt-1">
              Official rulebooks, player licenses, and how tour points work. Use the tabs to switch between WPA and WPBA.
            </p>
          </header>

          {/* Tabs: WPA | WPBA */}
          <div role="tablist" aria-label="Rules by organization" className="flex gap-2 border-b border-slate-700 pb-2">
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'wpa'}
              aria-controls="wpa-panel"
              id="wpa-tab"
              onClick={() => { setActiveTab('wpa'); setSearchParams({}) }}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === 'wpa'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700 hover:text-white'
              }`}
            >
              WPA
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeTab === 'wpba'}
              aria-controls="wpba-panel"
              id="wpba-tab"
              onClick={() => { setActiveTab('wpba'); setSearchParams({ tab: 'wpba' }) }}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === 'wpba'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-slate-800/80 text-slate-300 hover:bg-slate-700 hover:text-white'
              }`}
            >
              WPBA
            </button>
          </div>

          {/* WPA panel */}
          <div
            id="wpa-panel"
            role="tabpanel"
            aria-labelledby="wpa-tab"
            hidden={activeTab !== 'wpa'}
            className="space-y-6"
          >
            <a
              href="https://wpapool.com/rules/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-sky-400 hover:text-sky-300 inline-block"
            >
              wpapool.com/rules ↗
            </a>

            <section aria-labelledby="wpa-license-heading">
              <h2 id="wpa-license-heading" className="text-lg font-semibold text-white mb-2">
                WPA license documents
              </h2>
              <p className="text-slate-400 text-sm mb-3">
                Official WPA athletes/players license and sanctioning regulations (external PDFs).
              </p>
              <ul className="space-y-2">
                {WPA_LICENSE_DOCS.map((doc) => (
                  <li key={doc.title}>
                    <DocCard title={doc.title} url={doc.url} type="pdf" />
                  </li>
                ))}
              </ul>
            </section>

            <section aria-labelledby="wpa-rules-heading">
              <h2 id="wpa-rules-heading" className="text-lg font-semibold text-white mb-2">
                Rule books and regulations
              </h2>
              {isLoading && <div className="text-slate-400 py-8">Loading rules…</div>}
              {error && (
                <div className="rounded-lg bg-red-950/50 border border-red-800 text-red-200 p-4">
                  Failed to load rules. Try again later.
                </div>
              )}
              {rules && rules.length > 0 && (
                <ul className="space-y-2">
                  {rules.map((item) => (
                    <li key={item.filename}>
                      <a
                        href={rulesApi.fileUrl(item.filename)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-3 p-4 rounded-xl bg-slate-800/60 border border-slate-700 hover:border-slate-500 hover:bg-slate-800/80 transition-colors group"
                      >
                        <span className="text-2xl flex-shrink-0" aria-hidden>📄</span>
                        <span className="font-medium text-white group-hover:text-sky-300">{item.title}</span>
                        <span className="ml-auto text-slate-500 group-hover:text-slate-400" aria-hidden>Open PDF ↗</span>
                      </a>
                    </li>
                  ))}
                </ul>
              )}
              {rules && rules.length === 0 && !isLoading && !error && (
                <p className="text-slate-400">No rule documents available.</p>
              )}
            </section>
          </div>

          {/* WPBA panel */}
          <div
            id="wpba-panel"
            role="tabpanel"
            aria-labelledby="wpba-tab"
            hidden={activeTab !== 'wpba'}
            className="space-y-6"
          >
            <a
              href="https://wpba.com/rules"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-sky-400 hover:text-sky-300 inline-block"
            >
              wpba.com/rules ↗
            </a>

            <section aria-labelledby="wpba-docs-heading">
              <h2 id="wpba-docs-heading" className="text-lg font-semibold text-white mb-2">
                Rules & tour points
              </h2>
              <p className="text-slate-400 text-sm mb-3">
                Official WPBA 9 Ball rules and the point system used to calculate tournament rankings. The point system is referenced in <Link to="/tournament-wizard" className="text-sky-400 hover:text-sky-300 underline">New Tournament</Link> (steps 1–4) and is the standard for players and directors to read.
              </p>
              <ul className="space-y-2">
                {WPBA_DOCS.map((doc) => (
                  <li key={doc.title}>
                    <DocCard title={doc.title} url={doc.url} type={doc.type} />
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </div>
      </div>
    </div>
  )
}
