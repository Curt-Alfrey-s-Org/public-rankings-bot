import { useState, useEffect } from 'react'
import { logger } from '@/lib/logger'

export type ChartStyle = 'line' | 'area' | 'bar' | 'candlestick' | 'hybrid'

interface ChartPreferences {
  performanceChart: ChartStyle
  monthlyReturns: ChartStyle
}

const STORAGE_KEY = 'chart-preferences'

const DEFAULT_PREFERENCES: ChartPreferences = {
  performanceChart: 'area',
  monthlyReturns: 'bar',
}

export function useChartPreferences() {
  const [preferences, setPreferences] = useState<ChartPreferences>(DEFAULT_PREFERENCES)
  const [isLoaded, setIsLoaded] = useState(false)

  // Load from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      try {
        const parsed = JSON.parse(stored)
        setPreferences({ ...DEFAULT_PREFERENCES, ...parsed })
      } catch (error) {
        logger.warn('Failed to parse chart preferences; resetting to defaults', undefined, error as Error)
        setPreferences(DEFAULT_PREFERENCES)
      }
    }
    setIsLoaded(true)
  }, [])

  // Save to localStorage whenever preferences change
  const updateChartStyle = (chartType: keyof ChartPreferences, style: ChartStyle) => {
    setPreferences((prev) => {
      const updated = { ...prev, [chartType]: style }
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated))
      } catch (error) {
        logger.warn('Failed to save chart preferences', { chartType, style }, error as Error)
      }
      return updated
    })
  }

  const resetToDefaults = () => {
    setPreferences(DEFAULT_PREFERENCES)
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch (error) {
      logger.warn('Failed to clear chart preferences', undefined, error as Error)
    }
  }

  return {
    preferences,
    updateChartStyle,
    resetToDefaults,
    isLoaded,
  }
}
