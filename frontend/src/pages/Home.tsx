/**
 * Home page: news (WPBA Events + Latest WPA News) and quick links.
 */

import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { loginFeaturesApi, type FeatureItem } from '@/api/loginFeatures'
import { useAuth } from '@/contexts/AuthContext'
import { useUiCustomization } from '@/contexts/UiCustomizationContext'
import EditableText from '@/components/EditableText'

/** Two news cards: WPBA Events and Latest WPA News only. */
const NEWS_CARDS = [
  {
    title: 'WPBA Events',
    subtitle: 'Official schedule',
    href: 'https://wpba.com/events-official',
    icon: '📅',
    description: 'See where the WPBA is playing next.',
  },
  {
    title: 'Latest WPA News',
    subtitle: 'World pool',
    href: 'https://wpapool.com/news/',
    icon: '📰',
    description: 'Stories and results from WPA events worldwide.',
  },
]

function NewsCard({
  item,
}: {
  item: { title: string; subtitle: string; href: string; icon: string; description: string }
}) {
  return (
    <a
      href={item.href}
      target="_blank"
      rel="noopener noreferrer"
      className="block p-4 rounded-xl bg-slate-800/60 border border-slate-700 hover:border-slate-500 hover:bg-slate-800/80 transition-colors group"
    >
      <div className="flex items-start gap-3">
        <span className="text-2xl flex-shrink-0">{item.icon}</span>
        <div className="min-w-0">
          <div className="font-semibold text-white group-hover:text-primary">{item.title}</div>
          <div className="text-xs text-slate-500">{item.subtitle}</div>
          <div className="text-sm text-slate-400 mt-1">{item.description}</div>
        </div>
        <span className="text-slate-500 group-hover:text-slate-400 flex-shrink-0" aria-hidden>
          ↗
        </span>
      </div>
    </a>
  )
}

export default function Home() {
  const { isDirector, isAdmin, isSuperAdmin } = useAuth()
  const { getText, isEditing, setDraftText } = useUiCustomization()

  const { data: featuresData, isError, error, refetch } = useQuery({
    queryKey: ['login-features', 'full'],
    queryFn: () => loginFeaturesApi.get('full'),
    staleTime: 60_000,
    retry: 1,
  })
  const fullList: FeatureItem[] = featuresData?.full?.length ? featuresData.full : []
  const half = Math.ceil(fullList.length / 2)
  const leftCol = fullList.slice(0, half)
  const rightCol = fullList.slice(half)

  const getStartedSuggestions = () => {
    const suggestions = []

    if (isSuperAdmin) {
      suggestions.push({
        icon: '⚙️',
        title: 'Admin tools',
        description: 'Users, appearance, and system options',
        link: '/settings/admin',
      })
    }

    if (isDirector || isAdmin || isSuperAdmin) {
      suggestions.push({
        icon: '📈',
        title: 'Player performance',
        description: 'Charts, history, and how players are doing over time',
        link: '/player-performance',
      })
    }

    suggestions.push(
      {
        icon: '🏆',
        title: 'Rankings',
        description: 'WPBA, WPA, Heyball, and Artistic standings',
        link: '/rankings',
      },
      {
        icon: '🎱',
        title: 'AI Coach',
        description: 'Get tips from your own practice video or a clip',
        link: '/ai-coach',
      },
      {
        icon: '⏳',
        title: 'Future tournaments',
        description: "What's coming up — and how to register",
        link: '/future-tournaments',
      },
      {
        icon: '📅',
        title: 'Tournament history',
        description: 'Past events, finishes, and filters by year or tour',
        link: '/tournament-history',
      }
    )

    return suggestions.slice(0, 6)
  }

  return (
    <div className="flex flex-col min-h-full min-h-[100dvh] bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-50">
      <div className="flex-1 overflow-y-auto overflow-x-hidden min-h-0">
        <div className="max-w-4xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-6 sm:space-y-8 md:space-y-10 lg:space-y-12">
          {/* Hero */}
          <header className="pt-2">
            <h1 className="text-3xl md:text-4xl font-bold text-white mb-2">Welcome</h1>
            <p className="text-slate-400">
              Follow WPBA and WPA rankings, see upcoming events, and explore tools for players and fans — all in one place.
            </p>
            <p className="mt-3 text-xs sm:text-sm">
              <a
                href="https://example.com"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-md border border-amber-500/35 bg-amber-950/30 px-2.5 py-1 text-amber-200/95 hover:border-amber-400/50 hover:bg-amber-950/45 hover:text-amber-pool_opt_in focus:outline-none focus:ring-2 focus:ring-sky-500/50"
              >
                <span className="font-semibold uppercase tracking-wide text-[0.65rem] sm:text-xs text-amber-400/95">
                  Official software of USPBF
                </span>
                <span className="text-slate-500 hidden sm:inline">—</span>
                <span className="text-sky-400/90 hidden sm:inline">United States Pro Billiards Federation</span>
              </a>
            </p>
            {isError && (
              <div className="mt-4 rounded-lg border border-red-500/30 bg-red-900/20 p-3 text-sm text-red-200">
                <div className="mb-2">
                  We couldn&apos;t load the feature list. {error instanceof Error ? error.message : 'Please try again.'}
                </div>
                <button
                  onClick={() => refetch()}
                  className="px-3 py-1.5 rounded bg-red-700/60 hover:bg-red-700 text-white"
                >
                  Retry
                </button>
              </div>
            )}
          </header>

          {/* ALFa AI Getting Started */}
          <section>
            <div className="relative overflow-hidden bg-gradient-to-br from-blue-950/90 via-cyan-900/80 to-blue-950/90 border border-cyan-500/30 rounded-2xl shadow-2xl">
              {/* Holographic Background Effect */}
              <div className="absolute inset-0 opacity-20">
                <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48ZGVmcz48cGF0dGVybiBpZD0iZ3JpZCIgd2lkdGg9IjQwIiBoZWlnaHQ9IjQwIiBwYXR0ZXJuVW5pdHM9InVzZXJTcGFjZU9uVXNlIj48cGF0aCBkPSJNIDQwIDAgTCAwIDAgMCA0MCIgZmlsbD0ibm9uZSIgc3Ryb2tlPSJjeWFuIiBzdHJva2Utd2lkdGg9IjAuNSIgb3BhY2l0eT0iMC4zIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] animate-pulse"></div>
              </div>

              <div className="absolute top-0 right-0 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl"></div>
              <div className="absolute bottom-0 left-0 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl"></div>

              <div className="relative z-10 p-6 md:p-8">
                <div className="flex items-start gap-4 mb-6">
                  <div className="flex-shrink-0">
                    <div className="relative">
                      <div className="absolute inset-0 bg-cyan-400/20 rounded-full blur-xl animate-pulse"></div>
                      {isEditing && isSuperAdmin ? (
                        <div className="relative flex flex-col gap-2">
                          <input
                            type="text"
                            value={getText('home.alfa_image_url', '/branding/alfa-ai-avatar.png')}
                            onChange={(e) => setDraftText('home.alfa_image_url', e.target.value)}
                            placeholder="Image address (URL)"
                            className="w-48 text-xs px-2 py-1 border border-sky-500/40 rounded bg-slate-900/60"
                          />
                          <span className="text-[10px] text-cyan-200">Paste a link to your image</span>
                        </div>
                      ) : (
                        <img
                          src={getText('home.alfa_image_url', '/branding/alfa-ai-avatar.png')}
                          alt="ALFa AI Coach"
                          className="relative block w-16 h-16 md:w-20 md:h-20 rounded-full object-cover border-2 border-cyan-400/50"
                          onError={(e) => {
                            ;(e.currentTarget as HTMLImageElement).src = '/assets/avatar-default.png'
                          }}
                        />
                      )}
                    </div>
                  </div>
                  <div className="flex-1">
                    <h2 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-cyan-300 via-blue-300 to-cyan-300 bg-clip-text text-transparent mb-2 tracking-wide">
                      ALFa AI Coach
                    </h2>
                    <p className="text-sm md:text-base text-cyan-pool_opt_in/90 leading-relaxed">
                      <EditableText
                        textKey="home.alfa_description"
                        defaultText="Your pool coach in the app. Here are popular places to start:"
                        className="block"
                        inputClassName="bg-transparent border border-sky-500/40 rounded px-1 py-0.5 text-inherit w-full"
                      />
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 md:gap-4 w-full min-w-0">
                  {getStartedSuggestions().map((suggestion, idx) => (
                    <Link
                      key={idx}
                      to={suggestion.link}
                      className="group relative overflow-hidden flex items-start gap-3 p-4 min-h-[44px] rounded-xl bg-slate-900/40 backdrop-blur-sm border border-cyan-500/20 hover:border-cyan-400/60 hover:bg-slate-900/60 transition-all duration-300 shadow-lg hover:shadow-cyan-500/20"
                    >
                      <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/5 to-blue-500/5 opacity-0 group-hover:opacity-pool_opt_in transition-opacity"></div>
                      <span className="relative text-2xl md:text-3xl flex-shrink-0 group-hover:scale-rag transition-transform">
                        {suggestion.icon}
                      </span>
                      <div className="relative min-w-0 flex-1">
                        <div className="text-sm md:text-base font-semibold text-cyan-50 group-hover:text-cyan-200 transition-colors mb-1">
                          {suggestion.title}
                        </div>
                        <div className="text-xs md:text-sm text-slate-400 group-hover:text-slate-300 transition-colors leading-snug">
                          {suggestion.description}
                        </div>
                      </div>
                      <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-pool_opt_in transition-opacity">
                        <span className="text-cyan-400 text-xs">→</span>
                      </div>
                    </Link>
                  ))}
                </div>

                <div className="mt-6 pt-4 border-t border-cyan-500/20">
                  <p className="text-xs text-cyan-200/60 italic text-center">
                    💡 Tip:{' '}
                    <EditableText
                      textKey="home.alfa_tip"
                      defaultText="ALFa can offer suggestions as you use other parts of the app too."
                      className="inline"
                      inputClassName="bg-transparent border border-sky-500/40 rounded px-1 py-0.5 text-inherit"
                    />
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* App Capabilities */}
          <section>
            <h2 className="text-xl font-semibold text-white mb-4 sm:mb-5 flex items-center gap-2">
              <span>✨</span> What this app can do
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-5">
              <div>
                <ul className="text-left text-sm text-white/85 space-y-2 sm:space-y-2.5">
                  {leftCol.map((item, i) => (
                    <li key={`${item.title}-${i}`}>
                      <strong className="text-white">{item.title}</strong> — {item.description}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <ul className="text-left text-sm text-white/85 space-y-2 sm:space-y-2.5">
                  {rightCol.map((item, i) => (
                    <li key={`${item.title}-${half + i}`}>
                      <strong className="text-white">{item.title}</strong> — {item.description}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </section>

          {/* Tips */}
          <section>
            <h2 className="text-xl font-semibold text-white mb-4 sm:mb-5 flex items-center gap-2">
              <span>💡</span> Quick tips
            </h2>
            <div className="rounded-xl bg-slate-800/60 border border-slate-700 p-6">
              <ul className="space-y-4 text-slate-300 text-sm">
                <li className="flex gap-3">
                  <span className="text-sky-400 shrink-0" aria-hidden>
                    •
                  </span>
                  <span>
                    <strong className="text-white">Rankings</strong> update on a short schedule; use{' '}
                    <strong className="text-white">Refresh</strong> on the Rankings page (admins) if you need the latest right away.
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className="text-sky-400 shrink-0" aria-hidden>
                    •
                  </span>
                  <span>
                    <strong className="text-white">Tournament history</strong> lets you filter by year, tour, and game type to find past events.
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className="text-sky-400 shrink-0" aria-hidden>
                    •
                  </span>
                  <span>
                    <strong className="text-white">Head-to-head</strong> compares two players’ ranks, Fargo ratings, and record.
                  </span>
                </li>
              </ul>
            </div>
          </section>

          {/* News: WPBA Events + Latest WPA News (2 cards only) */}
          <section>
            <h2 className="text-xl font-semibold text-white mb-4 sm:mb-5 flex items-center gap-2">
              <span>📅</span> Outside the app
            </h2>
            <p className="text-sm text-slate-400 mb-4">Official sites open in a new tab.</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-5">
              {NEWS_CARDS.map((item) => (
                <NewsCard key={item.href + item.title} item={item} />
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
