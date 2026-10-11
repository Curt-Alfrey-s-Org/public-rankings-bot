/**
 * Appearance settings management for the app
 */

export type BackgroundType = 'video' | 'image' | 'slideshow' | 'none'
export type SplashType = 'video' | 'image' | 'none'
export type BackgroundObjectFit = 'cover' | 'contain' | 'fill' | 'none' | 'scale-down'

export interface AppearanceSettings {
  backgroundUrl?: string
  backgroundType?: BackgroundType
  /** URLs for slideshow (one per line or comma-separated). When set, background cycles through these images. */
  backgroundSlideshowUrls?: string[]
  /** When true, background slideshow uses scraped WPBA/WPA media (women 2x men, Debbie Teichert 1 in 8). */
  useScrapedMediaSlideshow?: boolean
  backgroundSlideshowIntervalMs?: number
  backgroundPositionX?: number
  backgroundPositionY?: number
  backgroundScale?: number
  backgroundObjectFit?: BackgroundObjectFit
  splashUrl?: string
  splashType?: SplashType
  /** When true, splash shows random slideshow from scraped WPBA/WPA media. */
  splashUseScrapedMedia?: boolean
  avatarUrl?: string
  avatarNone?: boolean
}

const APPEARANCE_KEY = 'appearance-settings'

const DEFAULT_APPEARANCE: AppearanceSettings = {
  backgroundUrl: '',
  backgroundType: 'none',
  backgroundSlideshowUrls: [],
  useScrapedMediaSlideshow: false,
  backgroundSlideshowIntervalMs: 6000,
  backgroundPositionX: 0,
  backgroundPositionY: 0,
  backgroundScale: 1,
  backgroundObjectFit: 'cover',
  splashUrl: '',
  splashType: 'none',
  splashUseScrapedMedia: false,
  avatarUrl: '/assets/avatar-default.png',
  avatarNone: false,
}

export function getAppearance(): AppearanceSettings {
  try {
    const stored = localStorage.getItem(APPEARANCE_KEY)
    if (stored) {
      return { ...DEFAULT_APPEARANCE, ...JSON.parse(stored) }
    }
  } catch (error) {
    console.error('Failed to load appearance settings:', error)
  }
  return DEFAULT_APPEARANCE
}

export function setAppearance(settings: Partial<AppearanceSettings>): void {
  try {
    const current = getAppearance()
    const updated = { ...current, ...settings }
    localStorage.setItem(APPEARANCE_KEY, JSON.stringify(updated))
    
    // Dispatch custom event for other components to listen
    window.dispatchEvent(new CustomEvent('appearance-changed'))
  } catch (error) {
    console.error('Failed to save appearance settings:', error)
  }
}

export function resetAppearanceToDefaults(): void {
  try {
    localStorage.removeItem(APPEARANCE_KEY)
    window.dispatchEvent(new CustomEvent('appearance-changed'))
  } catch (error) {
    console.error('Failed to reset appearance settings:', error)
  }
}
