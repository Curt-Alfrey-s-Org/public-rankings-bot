/**
 * Settings API functions
 */

import apiClient from './client'

export interface Settings {
  BOT_TOTAL_CAPITAL: number
  BOT_MIN_ALLOCATION: number
  BOT_MAX_ALLOCATION: number
  BOT_RISK_THRESHOLD: number
  BOT_POSITION_SIZE: number
  BOT_MAX_OPEN_POSITIONS: number
  BOT_STOP_LOSS_PERCENT: number
  BOT_TAKE_PROFIT_PERCENT: number
  // Trading mode settings
  MANUAL_TRADE_APPROVAL_MODE?: boolean | string
  PAPER_TRADING_MODE?: boolean | string
  DRY_RUN_MODE?: boolean | string
  BACKTEST_MODE?: boolean | string
  SCHWAB_SANDBOX_MODE?: boolean | string
  SCHWAB_API_ENABLED?: string
  // Advanced settings
  TRADING_FREQUENCY?: number
  LOG_LEVEL?: string
  DEBUG?: boolean | string
  TOP_PERFORMERS_REFRESH_INTERVAL?: number
  ASYNC_REQUEST_TIMEOUT?: number
  BOT_MAX_CPU_PERCENT?: number
  BOT_MAX_MEMORY_PERCENT?: number
  BOT_THROTTLE_DELAY?: number
  BOT_ENABLE_THROTTLING?: boolean | string
  EXIT_REFRESH_PRICE?: boolean | string
  ALERT_EMAIL_ENABLED?: boolean | string
  USE_MARGIN?: boolean | string
  // Discovery / today's best (screener, refresh)
  SYMBOL_REFRESH_INTERVAL_CYCLES?: number
  MAX_STOCK_PRICE?: number
  MIN_STOCK_PRICE?: number
  MAX_DISCOVERED_STOCKS?: number
  // Strategy / yfinance (ML filter, min bars for signals)
  ENABLE_ML_SIGNAL_FILTER?: boolean | string
  ML_SIGNAL_FILTER_MIN_CONFIDENCE?: number
  ML_SIGNAL_FILTER_MIN_WIN_PROB?: number
  STRATEGY_MIN_BARS?: number
  [key: string]: any
}

export const settingsApi = {
  getSettings: async (): Promise<Settings> => {
    const response = await apiClient.get<Settings>('/settings')
    return response.data
  },

  updateSettings: async (settings: Partial<Settings>): Promise<{ message: string; settings: Settings }> => {
    const response = await apiClient.put('/settings', { settings })
    return response.data
  },
}
