/**
 * Splash config API — server-side config for the login splash screen.
 * GET is public; PATCH requires admin.
 * Server is authoritative; the splash page uses a minimal default if the request fails (see SplashLogin).
 */

import apiClient from './client'

export interface SplashConfig {
  splash_url: string
  splash_type: 'video' | 'image' | 'none'
  splash_use_scraped_media: boolean
  title: string
  /** Server-owned; incremented on each PATCH so media at a stable URL is not served stale from cache. */
  splash_media_revision?: number
}

/**
 * Append cache-bust query for splash background media (video/image). Same URL + new bytes after deploy
 * otherwise stays cached; revision bumps when admin saves splash config (see api/routes/splash_config.py).
 */
export function splashMediaSrc(url: string | undefined, revision?: number): string | undefined {
  if (url == null || url === '') return url
  const r = revision ?? 0
  if (r <= 0) return url
  const joiner = url.includes('?') ? '&' : '?'
  return `${url}${joiner}smr=${encodeURIComponent(String(r))}`
}

export const splashConfigApi = {
  /** Get splash config. No auth. */
  get(): Promise<SplashConfig> {
    const cacheBust = Date.now()
    return apiClient
      .get<SplashConfig>(`/splash-config?_=${cacheBust}`, {
        headers: { 'Cache-Control': 'no-cache' },
        skipGlobalErrorUI: true,
      })
      .then((r) => r.data)
  },

  /** Update splash config. Admin only. */
  update(body: Partial<SplashConfig>): Promise<SplashConfig> {
    return apiClient.patch<SplashConfig>('/splash-config', body).then((r) => r.data)
  },
}
