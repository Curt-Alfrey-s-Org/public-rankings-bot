/**
 * Splash Screen with embedded login form
 * Displays video/image/slideshow background with LoginForm component.
 * Bot capabilities list moved to Home tab.
 *
 * Live config: config/splash_config.json via GET /api/splash-config. If the API is unreachable or
 * misconfigured, we still show login with a minimal default splash and an inline notice (see docs/SPLASH_CONFIG.md).
 *
 * Layout: lg+ uses the original absolute overlay (PC). Below lg, content stacks in a scrollable column
 * (standard mobile/tablet) so nothing overlaps.
 *
 * Doc refs (AI / maintainers): docs/SPLASH_CONFIG.md; api/routes/splash_config.py
 */

import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { isAxiosError } from 'axios'
import type { SplashType } from '@/lib/appearance'
import { useAuth } from '@/contexts/AuthContext'
import LoginForm from '@/components/LoginForm'
import VeteranFlagsBanner from '@/components/VeteranFlagsBanner'
import CurtisAlfreyMeme from '@/components/CurtisAlfreyMeme'
import { mediaApi } from '@/api/media'
import { assetUrl } from '@/api/assets'
import { splashConfigApi, splashMediaSrc, type SplashConfig } from '@/api/splashConfig'

const SPLASH_SLIDESHOW_INTERVAL_MS = 5000

/** Minimal splash when /api/splash-config cannot be loaded (network down or server 503). */
const SPLASH_OFFLINE_DEFAULT: SplashConfig = {
  splash_url: '',
  splash_type: 'none',
  splash_use_scraped_media: false,
  title: 'Pro Billiards Software',
  splash_media_revision: 0,
}

function splashConfigHttpDetail(error: unknown): string | undefined {
  if (!isAxiosError(error) || !error.response?.data) return undefined
  const data = error.response.data as { detail?: unknown }
  const d = data.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) {
    return d.map((e: { msg?: string }) => e?.msg).filter(Boolean).join('; ') || undefined
  }
  return undefined
}

function SplashHero({ title, compact = false }: { title?: string; compact?: boolean }) {
  return (
    <div className={`flex w-full flex-col items-center ${compact ? 'gap-4' : 'gap-5'}`}>
      <h1
        className={`font-bold text-white drop-shadow-2xl leading-tight ${
          compact ? 'text-2xl sm:text-3xl' : 'text-3xl sm:text-4xl md:text-5xl'
        }`}
      >
        {title}
      </h1>
      <div className="flex justify-center px-1">
        <a
          href="https://example.com"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block max-w-[min(100%,22rem)] sm:max-w-none rounded-full border border-amber-400/60 bg-amber-950/55 px-3 py-2 text-[10px] sm:text-[11px] font-semibold uppercase tracking-[0.08em] text-amber-pool_opt_in shadow-lg underline-offset-2 hover:border-amber-300/70 hover:bg-amber-950/70 hover:text-white focus:outline-none focus:ring-2 focus:ring-sky-400/60 leading-snug"
        >
          Official Software App Engine of the USPBF
        </a>
      </div>
      <p className="text-sm sm:text-base text-white/95 max-w-lg mx-auto leading-relaxed drop-shadow-md">
        The tournament, rankings, and analytics engine behind the{' '}
        <a
          href="https://example.com"
          target="_blank"
          rel="noopener noreferrer"
          className="font-semibold text-amber-200 underline-offset-2 hover:text-amber-pool_opt_in hover:underline focus:outline-none focus:ring-2 focus:ring-sky-400/60 rounded"
        >
          United States Pro Billiards Federation
        </a>
        .
      </p>
    </div>
  )
}

function SplashLoginPanel({
  onSubmit,
  onSuccess,
}: {
  onSubmit: ReturnType<typeof useAuth>['login']
  onSuccess: () => void
}) {
  return (
    <div className="space-y-2 pointer-events-auto">
      <LoginForm variant="minimal" onSubmit={onSubmit} onSuccess={onSuccess} />
      <div
        className="rounded-lg border border-slate-600/80 bg-slate-950/80 backdrop-blur px-3 py-2 text-[10px] sm:text-[11px] text-slate-200/95 leading-snug shadow-lg"
        role="note"
      >
        <span className="font-semibold text-amber-200/95">Accounts:</span> Pros are set up from WPA license data by
        admins—use the credentials from your TD to sign in (you&apos;ll set your email and password on first login).{' '}
        <Link
          to="/register"
          className="text-sky-400 hover:text-sky-300 underline-offset-2 hover:underline focus:outline-none focus:ring-2 focus:ring-sky-500/50 rounded"
        >
          Self-service signup for everyone else is coming soon
        </Link>
        .
      </div>
    </div>
  )
}

export default function SplashScreen() {
  const [showSplash, setShowSplash] = useState(true)
  const [mediaError, setMediaError] = useState(false)
  const [slideIndex, setSlideIndex] = useState(0)
  const { login, user, isLoading } = useAuth()

  const {
    data: splashConfigRemote,
    error: splashFetchError,
    isLoading: loadingSplash,
    isError: splashConfigError,
  } = useQuery({
    queryKey: ['splash-config'],
    queryFn: () => splashConfigApi.get(),
    staleTime: 0,
    retry: 1,
  })

  const splashConfig =
    splashConfigRemote ?? (splashConfigError ? SPLASH_OFFLINE_DEFAULT : undefined)
  const apiUnreachable =
    splashConfigError && isAxiosError(splashFetchError) && !splashFetchError.response
  const serverSplashDetail = splashConfigError ? splashConfigHttpDetail(splashFetchError) : undefined
  const splashRev = splashConfig?.splash_media_revision ?? 0
  const splashUrl = splashMediaSrc(splashConfig?.splash_url, splashRev)
  const splashType = splashConfig?.splash_type as SplashType
  const splashUseScrapedMedia = splashConfig?.splash_use_scraped_media ?? false
  const title = splashConfig?.title

  const { data: scrapedUrls } = useQuery({
    queryKey: ['media-slideshow-splash'],
    queryFn: async () => {
      const { data } = await mediaApi.getSlideshow(16)
      return (data?.urls ?? []).map((u) => assetUrl(u))
    },
    enabled: !!splashUseScrapedMedia,
    staleTime: 0,
  })
  const slideshowUrls = (scrapedUrls ?? []).map((u) => splashMediaSrc(u, splashRev) ?? u).filter(Boolean)
  const useSlideshow = splashUseScrapedMedia && slideshowUrls.length > 0

  useEffect(() => {
    if (!useSlideshow || slideshowUrls.length === 0) return
    const t = setInterval(() => setSlideIndex((i) => (i + 1) % slideshowUrls.length), SPLASH_SLIDESHOW_INTERVAL_MS)
    return () => clearInterval(t)
  }, [useSlideshow, slideshowUrls.length])

  useEffect(() => {
    if (!useSlideshow && splashUrl && splashType !== 'none') {
      if (splashType === 'video') {
        const video = document.createElement('video')
        video.src = splashUrl
        video.onerror = () => setMediaError(true)
        video.onloadeddata = () => setMediaError(false)
      } else {
        const img = document.createElement('img')
        img.src = splashUrl
        img.onerror = () => setMediaError(true)
        img.onload = () => setMediaError(false)
      }
    }
  }, [splashUrl, splashType, useSlideshow])

  useEffect(() => {
    if (!isLoading && user) {
      setShowSplash(false)
    }
  }, [isLoading, user])

  const handleLoginSuccess = () => {
    setShowSplash(false)
  }

  if (!showSplash) {
    return null
  }

  if (loadingSplash) {
    return (
      <div className="fixed inset-0 z-50 bg-black flex items-center justify-center">
        <div className="absolute left-3 top-3 z-[60] sm:left-5 sm:top-5">
          <VeteranFlagsBanner />
        </div>
        <p className="text-white/80">Loading…</p>
      </div>
    )
  }

  if (!splashConfig) {
    return null
  }

  const errorBanner = splashConfigError ? (
    <div
      className={`relative z-20 px-4 py-3 text-center text-sm ${
        apiUnreachable
          ? 'border-b border-amber-500/40 bg-amber-950/90 text-amber-pool_opt_in'
          : 'border-b border-red-500/40 bg-red-950/90 text-red-pool_opt_in'
      }`}
      role="alert"
    >
      {apiUnreachable ? (
        <>
          <span className="font-medium">Cannot reach the API.</span>{' '}
          Start the backend and reverse proxy (for example Docker Compose / nginx on the same host as this page).
          The UI will use default splash settings until <code className="rounded bg-black/30 px-1">/api/splash-config</code>{' '}
          succeeds.
        </>
      ) : (
        <>
          <span className="font-medium">Splash configuration could not be loaded from the server.</span>{' '}
          {serverSplashDetail ? (
            <span className="opacity-90">{serverSplashDetail}</span>
          ) : (
            <span className="opacity-90">
              Ensure <code className="rounded bg-black/30 px-1">config/splash_config.json</code> exists in the API
              container (image includes repo defaults; production can override via volume).
            </span>
          )}
        </>
      )}
    </div>
  ) : null

  const backgroundLayer = (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {useSlideshow && slideshowUrls.map((src, i) => (
        <img
          key={src}
          src={src}
          alt=""
          className="absolute inset-0 w-full h-full object-cover transition-opacity duration-1000"
          style={{ opacity: i === slideIndex ? 1 : 0, zIndex: i === slideIndex ? 1 : 0 }}
        />
      ))}
      {!useSlideshow && !mediaError && splashUrl && splashType !== 'none' && (
        splashType === 'image' ? (
          <img
            src={splashUrl}
            alt="Splash"
            className="w-full h-full object-contain"
            style={{ objectPosition: 'center' }}
          />
        ) : (
          <video
            autoPlay
            loop
            muted
            playsInline
            className="w-full h-full object-contain"
            style={{ objectFit: 'contain', objectPosition: 'center' }}
          >
            <source src={splashUrl} type="video/mp4" />
            Your browser does not support the video tag.
          </video>
        )
      )}
      <div className="absolute inset-0 bg-black/35" />
    </div>
  )

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto overflow-x-hidden bg-black">
      {errorBanner}
      {backgroundLayer}

      {/* Desktop (lg+): original absolute overlay layout — scrolls if viewport is short */}
      <div className="relative z-10 hidden lg:block w-full min-h-[100dvh]">
        <div
          className={`absolute left-5 z-[60] pointer-events-auto ${
            splashConfigError ? 'top-[4.5rem]' : 'top-5'
          }`}
        >
          <VeteranFlagsBanner />
        </div>
        <div className="absolute top-6 right-6 z-20 w-[min(100%,20rem)] pointer-events-auto">
          <SplashLoginPanel onSubmit={login} onSuccess={handleLoginSuccess} />
        </div>
        <div className="flex flex-col items-center text-center px-6 w-full max-w-2xl mx-auto pt-10 pb-32 pointer-events-auto">
          <SplashHero title={title} />
        </div>
      </div>

      {/* Mobile / tablet: scrollable — hero at top (like PC/iPad), then login, then meme */}
      <div className="relative z-10 lg:hidden w-full min-h-[100dvh] px-4 pb-10">
        <div
          className={`absolute left-4 z-[60] pointer-events-auto ${
            splashConfigError ? 'top-16' : 'top-4'
          }`}
        >
          <VeteranFlagsBanner />
        </div>
        <div className="mx-auto flex w-full max-w-lg flex-col gap-8 pt-14 sm:pt-12">
          <div className="flex flex-col items-center text-center pointer-events-auto">
            <SplashHero title={title} compact />
          </div>
          <div className="w-full max-w-[20rem] mx-auto pointer-events-auto">
            <SplashLoginPanel onSubmit={login} onSuccess={handleLoginSuccess} />
          </div>
        </div>
      </div>

      <CurtisAlfreyMeme />
    </div>
  )
}
