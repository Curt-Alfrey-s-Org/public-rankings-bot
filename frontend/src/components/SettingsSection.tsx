import { useState, useEffect, useCallback } from 'react'
import { toast } from '@/lib/toast'
import { Settings } from '@/api/settings'
import { API_BASE_URL } from '@/api/client'
import { getAppearance, setAppearance, resetAppearanceToDefaults, type AppearanceSettings, type BackgroundType, type SplashType, type BackgroundObjectFit } from '@/lib/appearance'
import MediaPicker, { type MediaUse } from '@/components/MediaPicker'

interface SettingsSectionProps {
  category: string
  settings: Settings
  onSave: (category: string, settings: Partial<Settings>) => void
  isSaving: boolean
}

const DEFAULT_AVATAR = '/assets/avatar-default.png'

export default function SettingsSection({
  category,
  settings,
  onSave,
  isSaving,
}: SettingsSectionProps) {
  const [localSettings, setLocalSettings] = useState<Partial<Settings>>({})
  const [hasChanges, setHasChanges] = useState(false)
  const [appearanceState, setAppearanceState] = useState<AppearanceSettings>(getAppearance)

  useEffect(() => {
    if (category === 'appearance') {
      setAppearanceState(getAppearance())
      return
    }
    const categorySettings = getCategorySettings(category, settings)
    setLocalSettings(categorySettings)
    setHasChanges(false)
  }, [category, settings])

  const getCategorySettings = (cat: string, allSettings: Settings): Partial<Settings> => {
    switch (cat) {
      case 'trading':
        return {
          BOT_TOTAL_CAPITAL: allSettings.BOT_TOTAL_CAPITAL,
          BOT_MIN_ALLOCATION: allSettings.BOT_MIN_ALLOCATION,
          BOT_MAX_ALLOCATION: allSettings.BOT_MAX_ALLOCATION,
          BOT_POSITION_SIZE: allSettings.BOT_POSITION_SIZE,
          BOT_MAX_OPEN_POSITIONS: allSettings.BOT_MAX_OPEN_POSITIONS,
          // Trading mode settings (Live/Sandbox/Training set on Dashboard when starting bot)
          MANUAL_TRADE_APPROVAL_MODE: allSettings.MANUAL_TRADE_APPROVAL_MODE,
          PAPER_TRADING_MODE: allSettings.PAPER_TRADING_MODE,
          DRY_RUN_MODE: allSettings.DRY_RUN_MODE,
          BACKTEST_MODE: allSettings.BACKTEST_MODE,
          SCHWAB_SANDBOX_MODE: allSettings.SCHWAB_SANDBOX_MODE,
          USE_MARGIN: allSettings.USE_MARGIN,
        }
      case 'risk':
        return {
          BOT_RISK_THRESHOLD: allSettings.BOT_RISK_THRESHOLD,
          BOT_STOP_LOSS_PERCENT: allSettings.BOT_STOP_LOSS_PERCENT,
          BOT_TAKE_PROFIT_PERCENT: allSettings.BOT_TAKE_PROFIT_PERCENT,
        }
      case 'alerts':
        return {
          ALERT_EMAIL_ENABLED: allSettings.ALERT_EMAIL_ENABLED,
        }
      case 'advanced':
        return {
          TRADING_FREQUENCY: allSettings.TRADING_FREQUENCY,
          LOG_LEVEL: allSettings.LOG_LEVEL,
          DEBUG: allSettings.DEBUG,
          EXIT_REFRESH_PRICE: allSettings.EXIT_REFRESH_PRICE,
        }
      case 'discovery':
        return {
          SYMBOL_REFRESH_INTERVAL_CYCLES: allSettings.SYMBOL_REFRESH_INTERVAL_CYCLES,
          MAX_STOCK_PRICE: allSettings.MAX_STOCK_PRICE,
          MIN_STOCK_PRICE: allSettings.MIN_STOCK_PRICE,
          MAX_DISCOVERED_STOCKS: allSettings.MAX_DISCOVERED_STOCKS,
        }
      case 'strategy':
        return {
          ENABLE_ML_SIGNAL_FILTER: allSettings.ENABLE_ML_SIGNAL_FILTER,
          ML_SIGNAL_FILTER_MIN_CONFIDENCE: allSettings.ML_SIGNAL_FILTER_MIN_CONFIDENCE,
          ML_SIGNAL_FILTER_MIN_WIN_PROB: allSettings.ML_SIGNAL_FILTER_MIN_WIN_PROB,
          STRATEGY_MIN_BARS: allSettings.STRATEGY_MIN_BARS,
        }
      case 'api':
        return {
          SCHWAB_APP_KEY: allSettings.SCHWAB_APP_KEY,
          SCHWAB_SECRET_KEY: allSettings.SCHWAB_SECRET_KEY,
          HUGGING_FACE_API_KEY: allSettings.HUGGING_FACE_API_KEY,
          ALPHA_VANTAGE_API_KEY: allSettings.ALPHA_VANTAGE_API_KEY,
          NEWS_API_KEY: allSettings.NEWS_API_KEY,
          FINNHUB_API_KEY: allSettings.FINNHUB_API_KEY,
          SCHWAB_API_ENABLED: allSettings.SCHWAB_API_ENABLED,
        }
      default:
        return {}
    }
  }

  const handleChange = (key: string, value: any) => {
    setLocalSettings((prev) => ({
      ...prev,
      [key]: value,
    }))
    setHasChanges(true)
  }

  const handleSave = () => {
    onSave(category, localSettings)
    setHasChanges(false)
  }

  const handleReset = () => {
    const categorySettings = getCategorySettings(category, settings)
    setLocalSettings(categorySettings)
    setHasChanges(false)
  }

  const renderTradingSettings = () => (
    <div className="space-y-6">
      <div className="border-b border-border pb-4 mb-4">
        <h3 className="text-lg font-semibold mb-2">Capital & Position Sizing</h3>
        <p className="text-sm text-muted-foreground">Configure capital allocation and position limits</p>
      </div>

      <SettingField
        label="Total Capital"
        value={localSettings.BOT_TOTAL_CAPITAL}
        onChange={(v) => handleChange('BOT_TOTAL_CAPITAL', v)}
        type="number"
        min={0}
        step={100}
        description="Total capital available for trading"
        tooltip="The total amount of money the bot can use for all trading activities. The bot will never risk more than this amount. Set this to your actual account balance for live trading."
        example="$10,000 means the bot can use up to $10k across all positions"
      />
      <SettingField
        label="Min Allocation"
        value={localSettings.BOT_MIN_ALLOCATION}
        onChange={(v) => handleChange('BOT_MIN_ALLOCATION', v)}
        type="number"
        min={0}
        step={10}
        description="Minimum allocation per trade"
        tooltip="The minimum dollar amount the bot will invest in a single position. Trades requiring less than this amount will be skipped. Helps avoid tiny positions with high commission costs."
        example="$50 minimum ensures each position is at least $50"
      />
      <SettingField
        label="Max Allocation"
        value={localSettings.BOT_MAX_ALLOCATION}
        onChange={(v) => handleChange('BOT_MAX_ALLOCATION', v)}
        type="number"
        min={0}
        step={50}
        description="Maximum allocation per trade"
        tooltip="The maximum dollar amount the bot can invest in any single position. This caps position size to prevent over-concentration in one stock, limiting risk per trade."
        example="$500 max means no single position exceeds $500"
      />
      <SettingField
        label="Position Size (%)"
        value={localSettings.BOT_POSITION_SIZE ? localSettings.BOT_POSITION_SIZE * 100 : 0}
        onChange={(v) => handleChange('BOT_POSITION_SIZE', v / 100)}
        type="number"
        min={0}
        max={100}
        step={0.1}
        description="Position size as percentage of capital"
        suffix="%"
        tooltip="What percentage of total capital to allocate per trade. This is calculated dynamically based on available capital. Lower percentages = more diversification."
        example="1% of $10k capital = $100 per position"
      />
      <SettingField
        label="Max Open Positions"
        value={localSettings.BOT_MAX_OPEN_POSITIONS}
        onChange={(v) => handleChange('BOT_MAX_OPEN_POSITIONS', v)}
        type="number"
        min={1}
        max={20}
        step={1}
        description="Maximum number of open positions"
        tooltip="The maximum number of stocks the bot can hold at once. More positions = more diversification but requires more capital. The bot will stop opening new positions when this limit is reached."
        example="5 positions max means hold up to 5 different stocks"
      />

      <div className="flex items-center gap-4 p-4 bg-card/50 rounded-lg border border-border mt-4">
        <div className="flex-1">
          <label className="block text-sm font-medium mb-1">Use margin</label>
          <p className="text-xs text-muted-foreground">
            OFF: trade with settled capital only (T+1). ON: use total capital (margin/capital); unsettled funds count as available.
          </p>
        </div>
        <button
          onClick={() => handleChange('USE_MARGIN', localSettings.USE_MARGIN === true || localSettings.USE_MARGIN === 'true' ? 'false' : 'true')}
          className={`relative w-12 h-6 rounded-full transition-colors flex-shrink-0 ${
            localSettings.USE_MARGIN === true || localSettings.USE_MARGIN === 'true'
              ? 'bg-primary'
              : 'bg-muted'
          }`}
          title={localSettings.USE_MARGIN === true || localSettings.USE_MARGIN === 'true' ? 'Margin ON' : 'Settled only'}
        >
          <div
            className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
              localSettings.USE_MARGIN === true || localSettings.USE_MARGIN === 'true'
                ? 'translate-x-7'
                : 'translate-x-0.5'
            }`}
          />
        </button>
      </div>

      <div className="border-b border-border pb-4 mb-4 mt-6">
        <h3 className="text-lg font-semibold mb-2">Trading Modes</h3>
        <p className="text-sm text-muted-foreground">Control how trades are executed</p>
      </div>

      <div className="space-y-4">
        <div className="flex items-center gap-4 p-4 bg-card/50 rounded-lg border border-border">
          <div className="flex-1">
            <label className="block text-sm font-medium mb-1">Manual Trade Approval</label>
            <p className="text-xs text-muted-foreground">
              Require user approval before executing trades. Trades will appear in Pending Trades for review.
            </p>
          </div>
          <input
            type="checkbox"
            checked={localSettings.MANUAL_TRADE_APPROVAL_MODE === true || localSettings.MANUAL_TRADE_APPROVAL_MODE === 'true' || localSettings.MANUAL_TRADE_APPROVAL_MODE === 'True' || localSettings.MANUAL_TRADE_APPROVAL_MODE === '1'}
            onChange={(e) => handleChange('MANUAL_TRADE_APPROVAL_MODE', e.target.checked ? 'true' : 'false')}
            className="w-5 h-5 rounded border-input"
          />
        </div>

        <div className="flex items-center gap-4 p-4 bg-card/50 rounded-lg border border-border">
          <div className="flex-1">
            <label className="block text-sm font-medium mb-1">Paper Trading Mode</label>
            <p className="text-xs text-muted-foreground">
              Simulate trades without using real money. Safe for testing and learning.
            </p>
          </div>
          <input
            type="checkbox"
            checked={localSettings.PAPER_TRADING_MODE === true || localSettings.PAPER_TRADING_MODE === 'true' || localSettings.PAPER_TRADING_MODE === 'True' || localSettings.PAPER_TRADING_MODE === '1'}
            onChange={(e) => handleChange('PAPER_TRADING_MODE', e.target.checked ? 'true' : 'false')}
            className="w-5 h-5 rounded border-input"
          />
        </div>

        <div className="flex items-center gap-4 p-4 bg-card/50 rounded-lg border border-border">
          <div className="flex-1">
            <label className="block text-sm font-medium mb-1">Dry Run Mode</label>
            <p className="text-xs text-muted-foreground">
              Validate live trading workflow without executing trades. Tests all validations and API connections.
            </p>
          </div>
          <input
            type="checkbox"
            checked={localSettings.DRY_RUN_MODE === true || localSettings.DRY_RUN_MODE === 'true' || localSettings.DRY_RUN_MODE === 'True' || localSettings.DRY_RUN_MODE === '1'}
            onChange={(e) => handleChange('DRY_RUN_MODE', e.target.checked ? 'true' : 'false')}
            className="w-5 h-5 rounded border-input"
          />
        </div>

        <div className="flex items-center gap-4 p-4 bg-card/50 rounded-lg border border-border">
          <div className="flex-1">
            <label className="block text-sm font-medium mb-1">Backtest Mode</label>
            <p className="text-xs text-muted-foreground">
              Run backtesting using historical data. WARNING: Testing-only mode, not for live trading.
            </p>
          </div>
          <input
            type="checkbox"
            checked={localSettings.BACKTEST_MODE === true || localSettings.BACKTEST_MODE === 'true' || localSettings.BACKTEST_MODE === 'True' || localSettings.BACKTEST_MODE === '1'}
            onChange={(e) => handleChange('BACKTEST_MODE', e.target.checked ? 'true' : 'false')}
            className="w-5 h-5 rounded border-input"
          />
        </div>

        <div className="flex items-center gap-4 p-4 bg-card/50 rounded-lg border border-border">
          <div className="flex-1">
            <label className="block text-sm font-medium mb-1">Schwab Sandbox Mode</label>
            <p className="text-xs text-muted-foreground">
              Use Schwab's sandbox environment for testing with real-time API calls (requires sandbox credentials).
            </p>
          </div>
          <input
            type="checkbox"
            checked={localSettings.SCHWAB_SANDBOX_MODE === true || localSettings.SCHWAB_SANDBOX_MODE === 'true' || localSettings.SCHWAB_SANDBOX_MODE === 'True' || localSettings.SCHWAB_SANDBOX_MODE === '1'}
            onChange={(e) => handleChange('SCHWAB_SANDBOX_MODE', e.target.checked ? 'true' : 'false')}
            className="w-5 h-5 rounded border-input"
          />
        </div>

        <p className="text-xs text-muted-foreground p-4 bg-muted/30 rounded-lg border border-border">
          Live, Sandbox, Training, or Dry-run is selected on the <strong>Dashboard</strong> when you start the bot. The bot sets API and mode options automatically from that choice.
        </p>
      </div>
    </div>
  )

  const renderRiskSettings = () => (
    <div className="space-y-6">
      <SettingField
        label="Risk Threshold (%)"
        value={localSettings.BOT_RISK_THRESHOLD ? localSettings.BOT_RISK_THRESHOLD * 100 : 0}
        onChange={(v) => handleChange('BOT_RISK_THRESHOLD', v / 100)}
        type="number"
        min={0}
        max={10}
        step={0.1}
        description="Maximum risk per trade as percentage"
        suffix="%"
        tooltip="Maximum percentage of total capital to risk on any single trade. This is the maximum loss you're willing to accept if the stop loss is hit. Conservative traders use 1-2%."
        example="2% risk on $10k = max $200 loss per trade"
      />
      <SettingField
        label="Stop Loss (%)"
        value={localSettings.BOT_STOP_LOSS_PERCENT ? localSettings.BOT_STOP_LOSS_PERCENT * 100 : 0}
        onChange={(v) => handleChange('BOT_STOP_LOSS_PERCENT', v / 100)}
        type="number"
        min={0}
        max={20}
        step={0.1}
        description="Stop loss percentage"
        suffix="%"
        tooltip="Percentage below entry price where the bot will automatically sell to limit losses. The position is exited when price drops this much from your entry."
        example="5% stop loss on $100 entry = sell at $95"
      />
      <SettingField
        label="Take Profit (%)"
        value={localSettings.BOT_TAKE_PROFIT_PERCENT ? localSettings.BOT_TAKE_PROFIT_PERCENT * 100 : 0}
        onChange={(v) => handleChange('BOT_TAKE_PROFIT_PERCENT', v / 100)}
        type="number"
        min={0}
        max={50}
        step={0.1}
        description="Take profit percentage"
        suffix="%"
        tooltip="Percentage above entry price where the bot will automatically sell to lock in profits. The position is exited when price rises this much from your entry."
        example="10% take profit on $100 entry = sell at $110"
      />
    </div>
  )

  const renderApiSettings = () => (
    <div className="space-y-6">
      <div className="border-b border-border pb-4 mb-4">
        <h3 className="text-lg font-semibold mb-2">API Keys & Credentials</h3>
        <p className="text-sm text-muted-foreground">
          Configure API keys for external services. Keys are stored securely and never exposed in logs.
        </p>
      </div>

      {/* Schwab API */}
      <div className="space-y-4 p-4 bg-card/30 rounded-lg border border-border">
        <div className="flex items-center gap-2 mb-2">
          <h4 className="text-md font-semibold">Schwab Trading API</h4>
          <span className="text-xs px-2 py-0.5 bg-primary/20 text-primary rounded">Required</span>
        </div>
        <p className="text-xs text-muted-foreground mb-3">
          Required for live trading and sandbox testing. Get your API keys from Schwab Developer Portal.
        </p>
        
        <SettingField
          label="App Key"
          value={localSettings.SCHWAB_APP_KEY}
          onChange={(v) => handleChange('SCHWAB_APP_KEY', v)}
          type="password"
          placeholder="Enter your Schwab App Key"
          description="Your Schwab application key from the developer portal"
        />
        <SettingField
          label="Secret Key"
          value={localSettings.SCHWAB_SECRET_KEY}
          onChange={(v) => handleChange('SCHWAB_SECRET_KEY', v)}
          type="password"
          placeholder="Enter your Schwab Secret Key"
          description="Your Schwab secret key (keep this secure)"
        />
        
        <div className="flex items-center gap-4 p-3 bg-card/50 rounded border border-border/50 mt-3">
          <div className="flex-1">
            <label className="block text-sm font-medium">Enable Schwab API</label>
            <p className="text-xs text-muted-foreground">
              Toggle to enable/disable Schwab API integration
            </p>
          </div>
          <button
            onClick={() => handleChange('SCHWAB_API_ENABLED', String(localSettings.SCHWAB_API_ENABLED) === 'true' ? 'false' : 'true')}
            className={`relative w-12 h-6 rounded-full transition-colors flex-shrink-0 ${
              String(localSettings.SCHWAB_API_ENABLED) === 'true'
                ? 'bg-green-500'
                : 'bg-muted'
            }`}
          >
            <div
              className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
                String(localSettings.SCHWAB_API_ENABLED) === 'true'
                  ? 'translate-x-7'
                  : 'translate-x-0.5'
              }`}
            />
          </button>
        </div>
      </div>

      {/* HuggingFace API */}
      <div className="space-y-4 p-4 bg-card/30 rounded-lg border border-border">
        <div className="flex items-center gap-2 mb-2">
          <h4 className="text-md font-semibold">HuggingFace API</h4>
          <span className="text-xs px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded">AI/ML</span>
        </div>
        <p className="text-xs text-muted-foreground mb-3">
          Used for AI-powered strategy optimization and ML signal filtering.
        </p>
        
        <SettingField
          label="API Key"
          value={localSettings.HUGGING_FACE_API_KEY}
          onChange={(v) => handleChange('HUGGING_FACE_API_KEY', v)}
          type="password"
          placeholder="hf_..."
          description="Your HuggingFace API token"
        />
      </div>

      {/* Alpha Vantage */}
      <div className="space-y-4 p-4 bg-card/30 rounded-lg border border-border">
        <div className="flex items-center gap-2 mb-2">
          <h4 className="text-md font-semibold">Alpha Vantage</h4>
          <span className="text-xs px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded">Market Data</span>
        </div>
        <p className="text-xs text-muted-foreground mb-3">
          Fundamental data and additional market analytics.
        </p>
        
        <SettingField
          label="API Key"
          value={localSettings.ALPHA_VANTAGE_API_KEY}
          onChange={(v) => handleChange('ALPHA_VANTAGE_API_KEY', v)}
          type="password"
          placeholder="Enter Alpha Vantage API key"
          description="Free tier available at alphavantage.co"
        />
      </div>

      {/* News API */}
      <div className="space-y-4 p-4 bg-card/30 rounded-lg border border-border">
        <div className="flex items-center gap-2 mb-2">
          <h4 className="text-md font-semibold">News API</h4>
          <span className="text-xs px-2 py-0.5 bg-orange-500/20 text-orange-400 rounded">Sentiment</span>
        </div>
        <p className="text-xs text-muted-foreground mb-3">
          News sentiment analysis for trading signals.
        </p>
        
        <SettingField
          label="API Key"
          value={localSettings.NEWS_API_KEY}
          onChange={(v) => handleChange('NEWS_API_KEY', v)}
          type="password"
          placeholder="Enter News API key"
          description="Get your key from newsapi.org"
        />
      </div>

      {/* Finnhub */}
      <div className="space-y-4 p-4 bg-card/30 rounded-lg border border-border">
        <div className="flex items-center gap-2 mb-2">
          <h4 className="text-md font-semibold">Finnhub</h4>
          <span className="text-xs px-2 py-0.5 bg-teal-500/20 text-teal-400 rounded">Financial Data</span>
        </div>
        <p className="text-xs text-muted-foreground mb-3">
          Real-time financial data and stock fundamentals.
        </p>
        
        <SettingField
          label="API Key"
          value={localSettings.FINNHUB_API_KEY}
          onChange={(v) => handleChange('FINNHUB_API_KEY', v)}
          type="password"
          placeholder="Enter Finnhub API key"
          description="Free tier available at finnhub.io"
        />
      </div>

      <div className="mt-6 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
        <p className="text-sm text-yellow-200 flex items-center gap-2">
          <span className="text-lg">⚠️</span>
          <span>API keys are stored in environment variables and never logged or exposed. Keep them secure.</span>
        </p>
      </div>
    </div>
  )

  const renderAlertsSettings = () => (
    <div className="space-y-6">
      <div className="border-b border-border pb-4 mb-4">
        <h3 className="text-lg font-semibold mb-2">Email Alerts</h3>
        <p className="text-sm text-muted-foreground">
          Control email notifications. Turn on for live mode; turn off for dev/testing.
        </p>
      </div>

      <div className="flex items-center gap-4 p-4 bg-card/50 rounded-lg border border-border">
        <div className="flex-1">
          <label className="block text-sm font-medium mb-1">Email Alerts</label>
          <p className="text-xs text-muted-foreground">
            When ON: send email alerts for trades, errors, PDT warnings, and capital floor (live mode).
            When OFF: no emails sent (dev mode).
          </p>
        </div>
        <button
          onClick={() => handleChange('ALERT_EMAIL_ENABLED', String(localSettings.ALERT_EMAIL_ENABLED) === 'true' ? 'false' : 'true')}
          className={`relative w-12 h-6 rounded-full transition-colors flex-shrink-0 ${
            String(localSettings.ALERT_EMAIL_ENABLED) === 'true'
              ? 'bg-green-500'
              : 'bg-muted'
          }`}
          title={String(localSettings.ALERT_EMAIL_ENABLED) === 'true' ? 'Emails ON (live mode)' : 'Emails OFF (dev mode)'}
        >
          <div
            className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform ${
              String(localSettings.ALERT_EMAIL_ENABLED) === 'true'
                ? 'translate-x-7'
                : 'translate-x-0.5'
            }`}
          />
        </button>
      </div>
      <p className="text-xs text-muted-foreground -mt-2">
        {String(localSettings.ALERT_EMAIL_ENABLED) === 'true'
          ? 'ON — Live mode (sends alerts). Remember to Save Changes.'
          : 'OFF — Dev mode (no emails). Remember to Save Changes.'}
      </p>
      <p className="text-sm text-muted-foreground mt-4">
        Rankings: get notified when a player&apos;s ranking changes — sign up on the Rankings page.{' '}
        <a
          href={`${API_BASE_URL}/docs/notifications-email`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          Learn more about email notifications
        </a>
      </p>
    </div>
  )

  const renderAdvancedSettings = () => (
    <div className="space-y-6">
      <div className="border-b border-border pb-4 mb-4">
        <h3 className="text-lg font-semibold mb-2">Trading Performance</h3>
        <p className="text-sm text-muted-foreground">Control trading frequency and timing</p>
      </div>
      
      <SettingField
        label="Trading Frequency"
        value={localSettings.TRADING_FREQUENCY ?? 2}
        onChange={(v) => handleChange('TRADING_FREQUENCY', v)}
        type="number"
        min={1}
        max={60}
        step={1}
        description="Seconds to wait between trades (lower = more frequent)"
        suffix="seconds"
        tooltip="Time delay between executing trades. Prevents rapid-fire trading and helps avoid pattern day trading violations. Lower values = faster execution but may trigger rate limits or PDT rules."
        example="2 seconds = wait 2 sec between each trade"
      />
      
      <div className="flex items-center gap-4">
        <label className="block text-sm font-medium">Exit Price Refresh</label>
        <input
          type="checkbox"
          checked={localSettings.EXIT_REFRESH_PRICE === true || localSettings.EXIT_REFRESH_PRICE === 'true' || localSettings.EXIT_REFRESH_PRICE === 'True' || localSettings.EXIT_REFRESH_PRICE === '1'}
          onChange={(e) => handleChange('EXIT_REFRESH_PRICE', e.target.checked ? 'true' : 'false')}
          className="w-4 h-4 rounded border-input"
        />
        <span className="text-sm text-muted-foreground">Refresh price immediately before SELL/COVER</span>
      </div>
      <p className="text-xs text-muted-foreground -mt-2">When enabled, fetches latest price right before executing exit trades</p>

      <div className="border-b border-border pb-4 mb-4 mt-6">
        <h3 className="text-lg font-semibold mb-2">Logging & Debug</h3>
        <p className="text-sm text-muted-foreground">Configure logging behavior and debug mode</p>
      </div>

      <div>
        <label className="block text-sm font-medium mb-2">Log Level</label>
        <select
          value={localSettings.LOG_LEVEL ?? 'INFO'}
          onChange={(e) => handleChange('LOG_LEVEL', e.target.value)}
          className="w-full px-3 py-2 bg-background border border-input rounded-lg focus:outline-none focus:ring-2 focus:ring-ring"
        >
          <option value="DEBUG">DEBUG</option>
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
          <option value="CRITICAL">CRITICAL</option>
        </select>
        <p className="text-xs text-muted-foreground mt-1">Minimum log level to display</p>
      </div>

      <div className="flex items-center gap-4">
        <label className="block text-sm font-medium">Debug Mode</label>
        <input
          type="checkbox"
          checked={localSettings.DEBUG === true || localSettings.DEBUG === 'true' || localSettings.DEBUG === 'True' || localSettings.DEBUG === '1'}
          onChange={(e) => handleChange('DEBUG', e.target.checked ? 'true' : 'false')}
          className="w-4 h-4 rounded border-input"
        />
        <span className="text-sm text-muted-foreground">Enable detailed debug logging</span>
      </div>
      <p className="text-xs text-muted-foreground -mt-2">Enables verbose logging for troubleshooting</p>

      <p className="text-xs text-muted-foreground mt-4 p-4 bg-muted/30 rounded-lg border border-border">
        Refresh intervals, timeouts, and resource throttling use built-in defaults. Change them in <code className="bg-muted px-1 rounded">.env</code> only if you need to tune performance.
      </p>
    </div>
  )

  const renderDiscoverySettings = () => (
    <div className="space-y-6">
      <div className="border-b border-border pb-4 mb-4">
        <h3 className="text-lg font-semibold mb-2">Today&apos;s Best (Symbol Refresh)</h3>
        <p className="text-sm text-muted-foreground">Control how often the bot refreshes the symbol list so it can find hot stocks during the run</p>
      </div>

      <SettingField
        label="Symbol refresh every N cycles"
        value={localSettings.SYMBOL_REFRESH_INTERVAL_CYCLES ?? 0}
        onChange={(v) => handleChange('SYMBOL_REFRESH_INTERVAL_CYCLES', v)}
        type="number"
        min={0}
        max={60}
        step={1}
        description="0 = load once at startup; 1 = every cycle; N = every N cycles"
        suffix="cycles"
      />

      <div className="border-b border-border pb-4 mb-4 mt-6">
        <h3 className="text-lg font-semibold mb-2">Screener (Stock Selection)</h3>
        <p className="text-sm text-muted-foreground">Price range and how many stocks to trade from the screener</p>
      </div>

      <SettingField
        label="Max stock price"
        value={localSettings.MAX_STOCK_PRICE ?? 1000}
        onChange={(v) => handleChange('MAX_STOCK_PRICE', v)}
        type="number"
        min={10}
        max={10000}
        step={10}
        description="Stocks above this price are excluded (e.g. 500 or 1000)"
        prefix="$"
      />

      <SettingField
        label="Min stock price"
        value={localSettings.MIN_STOCK_PRICE ?? 5}
        onChange={(v) => handleChange('MIN_STOCK_PRICE', v)}
        type="number"
        min={0.5}
        max={500}
        step={0.5}
        description="Stocks below this price are excluded"
        prefix="$"
      />

      <SettingField
        label="Max discovered stocks"
        value={localSettings.MAX_DISCOVERED_STOCKS ?? 10}
        onChange={(v) => handleChange('MAX_DISCOVERED_STOCKS', v)}
        type="number"
        min={1}
        max={200}
        step={1}
        description="Number of symbols to trade (from Feed or screener)"
      />

      <p className="text-xs text-muted-foreground p-4 bg-muted/30 rounded-lg border border-border">
        Feed → screener priority: the bot uses the Top Performers Feed first (if available), then the screener. Changes apply on next bot start or on the next symbol refresh if refresh is enabled.
      </p>
    </div>
  )

  const renderStrategySettings = () => (
    <div className="space-y-6">
      <div className="border-b border-border pb-4 mb-4">
        <h3 className="text-lg font-semibold mb-2">Strategy &amp; yfinance</h3>
        <p className="text-sm text-muted-foreground">
          ML signal filter and min bars for strategy signals. If the bot shows tickers but no trades in yfinance mode, turn off the ML filter or lower thresholds here.
        </p>
      </div>

      <div className="flex items-center gap-4 p-4 bg-card/50 rounded-lg border border-border">
        <div className="flex-1">
          <label className="block text-sm font-medium mb-1">ML signal filter</label>
          <p className="text-xs text-muted-foreground">
            When ON: BUY/SELL must pass ML confidence and win-prob thresholds. When OFF: all strategy BUY/SELL signals are allowed (use in yfinance to see trades).
          </p>
        </div>
        <input
          type="checkbox"
          checked={localSettings.ENABLE_ML_SIGNAL_FILTER === true || localSettings.ENABLE_ML_SIGNAL_FILTER === 'true' || localSettings.ENABLE_ML_SIGNAL_FILTER === 'True' || localSettings.ENABLE_ML_SIGNAL_FILTER === '1'}
          onChange={(e) => handleChange('ENABLE_ML_SIGNAL_FILTER', e.target.checked ? 'true' : 'false')}
          className="w-5 h-5 rounded border-input"
        />
      </div>

      <SettingField
        label="ML min confidence (0–1)"
        value={localSettings.ML_SIGNAL_FILTER_MIN_CONFIDENCE ?? 0.6}
        onChange={(v) => handleChange('ML_SIGNAL_FILTER_MIN_CONFIDENCE', v)}
        type="number"
        min={0}
        max={1}
        step={0.05}
        description="Signals below this confidence are filtered out (lower = more signals)"
        tooltip="Machine Learning confidence score required for a trade signal to pass. Higher values = only high-confidence trades execute. Lower values = more trades but potentially lower quality."
        example="0.6 means ML must be 60% confident in the signal"
      />

      <SettingField
        label="ML min win prob (0–1)"
        value={localSettings.ML_SIGNAL_FILTER_MIN_WIN_PROB ?? 0.55}
        onChange={(v) => handleChange('ML_SIGNAL_FILTER_MIN_WIN_PROB', v)}
        type="number"
        min={0}
        max={1}
        step={0.05}
        description="Signals below this win probability are filtered out (lower = more signals)"
        tooltip="Minimum win probability predicted by ML model. This is the estimated chance the trade will be profitable. Higher values filter out risky trades."
        example="0.55 means ML predicts 55% chance of profit"
      />

      <SettingField
        label="Min OHLCV bars for signal"
        value={localSettings.STRATEGY_MIN_BARS ?? 50}
        onChange={(v) => handleChange('STRATEGY_MIN_BARS', v)}
        type="number"
        min={10}
        max={100}
        step={5}
        description="Need at least this many price bars to get a strategy signal (lower = more symbols get a signal; 20–30 for testing)"
        tooltip="Minimum historical price bars (days) required before generating trade signals. Technical indicators need enough data to be accurate. Lower values allow trading newer/less liquid stocks."
        example="50 bars = need 50 days of price history"
      />

      <p className="text-xs text-muted-foreground p-4 bg-muted/30 rounded-lg border border-border">
        Manual Trade Approval is under <strong>Trading</strong>. Use <strong>Restart</strong> on the dashboard after changing these for them to take effect.
      </p>
    </div>
  )

  const inferMediaType = (url: string): 'video' | 'image' => {
    const u = url.toLowerCase()
    if (/\.(mp4|webm|ogg|mov|avi|mkv)(\?|$)/.test(u)) return 'video'
    return 'image'
  }

  const handleMediaSelect = useCallback((url: string, use: MediaUse) => {
    setAppearanceState((s) => {
      const next = { ...s }
      if (use === 'avatar') {
        next.avatarUrl = url
        next.avatarNone = false
      } else if (use === 'background') {
        next.backgroundUrl = url
        next.backgroundType = inferMediaType(url)
      } else {
        next.splashUrl = url
        next.splashType = inferMediaType(url)
      }
      return next
    })
  }, [])

  const renderAppearanceSettings = () => (
    <div className="space-y-6">
      <div className="border-b border-border pb-4 mb-4">
        <h3 className="text-lg font-semibold mb-2">Avatar, background & splash</h3>
        <p className="text-sm text-muted-foreground">
          Customize avatar (sidebar), main background, and splash screen. Use the search box to find pics/videos, upload from folder, or paste URLs below.
        </p>
      </div>

      <div>
        <label className="block text-sm font-medium mb-2">Search & upload pics/videos</label>
        <MediaPicker onSelect={handleMediaSelect} />
        <p className="text-xs text-muted-foreground mt-1">Search assets, upload from folder, then use Avatar / BG / Splash on a file.</p>
      </div>

      <div>
        <label className="block text-sm font-medium mb-2">Avatar</label>
        <div className="flex items-center gap-4">
          <input
            type="text"
            value={appearanceState.avatarUrl ?? ''}
            onChange={(e) => setAppearanceState((s) => ({ ...s, avatarUrl: e.target.value || undefined }))}
            placeholder={DEFAULT_AVATAR}
            className="flex-1 px-3 py-2 bg-background border border-input rounded-lg focus:outline-none focus:ring-2 focus:ring-ring"
          />
          {!appearanceState.avatarNone && (
            <img
              src={appearanceState.avatarUrl || DEFAULT_AVATAR}
              alt="Avatar preview"
              className="w-12 h-12 rounded-full object-cover border border-border"
              onError={(e) => {
                (e.target as HTMLImageElement).src = DEFAULT_AVATAR
              }}
            />
          )}
        </div>
        <label className="flex items-center gap-2 text-sm mt-2 cursor-pointer">
          <input
            type="checkbox"
            checked={!!appearanceState.avatarNone}
            onChange={(e) => setAppearanceState((s) => ({ ...s, avatarNone: e.target.checked }))}
            className="rounded border-input"
          />
          <span>None (don&apos;t show avatar)</span>
        </label>
        <p className="text-xs text-muted-foreground mt-1">Shown in the sidebar header</p>
      </div>

      <div>
        <label className="block text-sm font-medium mb-2">Background URL</label>
        <input
          type="text"
          value={appearanceState.backgroundUrl ?? ''}
          onChange={(e) => setAppearanceState((s) => ({ ...s, backgroundUrl: e.target.value || undefined }))}
          placeholder="/assets/video/..."
          className="w-full px-3 py-2 bg-background border border-input rounded-lg focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <div className="mt-2 flex items-center gap-4 flex-wrap">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="backgroundType"
              checked={(appearanceState.backgroundType ?? 'video') === 'video'}
              onChange={() => setAppearanceState((s) => ({ ...s, backgroundType: 'video' as BackgroundType }))}
              className="rounded border-input"
            />
            Video
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="backgroundType"
              checked={(appearanceState.backgroundType ?? 'video') === 'image'}
              onChange={() => setAppearanceState((s) => ({ ...s, backgroundType: 'image' as BackgroundType }))}
              className="rounded border-input"
            />
            Image
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="backgroundType"
              checked={(appearanceState.backgroundType ?? 'video') === 'slideshow'}
              onChange={() => setAppearanceState((s) => ({ ...s, backgroundType: 'slideshow' as BackgroundType }))}
              className="rounded border-input"
            />
            Slideshow
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="backgroundType"
              checked={(appearanceState.backgroundType ?? 'video') === 'none'}
              onChange={() => setAppearanceState((s) => ({ ...s, backgroundType: 'none' as BackgroundType }))}
              className="rounded border-input"
            />
            None
          </label>
        </div>
        <p className="text-xs text-muted-foreground mt-1">Main dashboard background. Slideshow cycles WPBA/WPA billiards pics. None = no pic/video.</p>

        <div className="mt-4 p-4 rounded-lg border border-border bg-card/30 space-y-3">
          <h4 className="text-sm font-medium">Slideshow (WPBA/WPA billiards images)</h4>
          <p className="text-xs text-muted-foreground">One image URL per line. Used when Background = Slideshow.</p>
          <textarea
            rows={4}
            value={(appearanceState.backgroundSlideshowUrls ?? []).join('\n')}
            onChange={(e) => setAppearanceState((s) => ({
              ...s,
              backgroundSlideshowUrls: e.target.value.split(/\n/).map((u) => u.trim()).filter(Boolean),
            }))}
            placeholder="https://example.com/image1.jpg\nhttps://example.com/image2.jpg"
            className="w-full px-3 py-2 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          <div>
            <label className="block text-xs mb-1">Change image every (seconds)</label>
            <input
              type="number"
              min={3}
              max={60}
              value={Math.round((appearanceState.backgroundSlideshowIntervalMs ?? 6000) / 1000)}
              onChange={(e) => setAppearanceState((s) => ({
                ...s,
                backgroundSlideshowIntervalMs: Math.max(3000, Math.min(60000, parseInt(e.target.value, 10) * 1000)),
              }))}
              className="w-24 px-2 py-1 bg-background border border-input rounded text-sm"
            />
          </div>
        </div>

        <div className="mt-4 p-4 rounded-lg border border-border bg-card/30 space-y-4">
          <h4 className="text-sm font-medium">Position & size</h4>
          <p className="text-xs text-muted-foreground">Move and resize the background (dashboard center). Also adjustable via the floating Background Controls.</p>
          <div>
            <label className="block text-xs mb-1">Position X: {(appearanceState.backgroundPositionX ?? 0)}%</label>
            <input
              type="range"
              min="-50"
              max="50"
              step="1"
              value={appearanceState.backgroundPositionX ?? 0}
              onChange={(e) => setAppearanceState((s) => ({ ...s, backgroundPositionX: parseInt(e.target.value, 10) }))}
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-xs mb-1">Position Y: {(appearanceState.backgroundPositionY ?? 0)}%</label>
            <input
              type="range"
              min="-50"
              max="50"
              step="1"
              value={appearanceState.backgroundPositionY ?? 0}
              onChange={(e) => setAppearanceState((s) => ({ ...s, backgroundPositionY: parseInt(e.target.value, 10) }))}
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-xs mb-1">Size: {Math.round((appearanceState.backgroundScale ?? 1) * 100)}%</label>
            <input
              type="range"
              min="0.5"
              max="2"
              step="0.1"
              value={appearanceState.backgroundScale ?? 1}
              onChange={(e) => setAppearanceState((s) => ({ ...s, backgroundScale: parseFloat(e.target.value) }))}
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-xs mb-1">Fit</label>
            <select
              value={appearanceState.backgroundObjectFit ?? 'cover'}
              onChange={(e) => setAppearanceState((s) => ({ ...s, backgroundObjectFit: e.target.value as BackgroundObjectFit }))}
              className="w-full px-3 py-2 bg-background border border-input rounded-lg text-sm"
            >
              <option value="cover">Cover</option>
              <option value="contain">Contain</option>
              <option value="fill">Fill</option>
              <option value="none">None</option>
              <option value="scale-down">Scale down</option>
            </select>
          </div>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium mb-2">Splash screen URL</label>
        <input
          type="text"
          value={appearanceState.splashUrl ?? ''}
          onChange={(e) => setAppearanceState((s) => ({ ...s, splashUrl: e.target.value || undefined }))}
          placeholder="/assets/video/..."
          className="w-full px-3 py-2 bg-background border border-input rounded-lg focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <div className="mt-2 flex items-center gap-4 flex-wrap">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="splashType"
              checked={(appearanceState.splashType ?? 'video') === 'video'}
              onChange={() => setAppearanceState((s) => ({ ...s, splashType: 'video' as SplashType }))}
              className="rounded border-input"
            />
            Video
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="splashType"
              checked={(appearanceState.splashType ?? 'video') === 'image'}
              onChange={() => setAppearanceState((s) => ({ ...s, splashType: 'image' as SplashType }))}
              className="rounded border-input"
            />
            Image
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="splashType"
              checked={(appearanceState.splashType ?? 'video') === 'none'}
              onChange={() => setAppearanceState((s) => ({ ...s, splashType: 'none' as SplashType }))}
              className="rounded border-input"
            />
            None
          </label>
        </div>
        <p className="text-xs text-muted-foreground mt-1">Shown when opening the app. None = no pic/video.</p>
      </div>

      <div className="flex gap-2 pt-4 border-t border-border">
        <button
          onClick={() => {
            resetAppearanceToDefaults()
            setAppearanceState(getAppearance())
          }}
          className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
        >
          Reset to defaults
        </button>
        <button
          onClick={() => {
            setAppearance(appearanceState)
            setAppearanceState(getAppearance())
          }}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
        >
          Save appearance
        </button>
      </div>
    </div>
  )

  const renderContent = () => {
    switch (category) {
      case 'trading':
        return renderTradingSettings()
      case 'risk':
        return renderRiskSettings()
      case 'discovery':
        return renderDiscoverySettings()
      case 'strategy':
        return renderStrategySettings()
      case 'appearance':
        return renderAppearanceSettings()
      case 'api':
        return renderApiSettings()
      case 'alerts':
        return renderAlertsSettings()
      case 'advanced':
        return renderAdvancedSettings()
      default:
        return null
    }
  }

  const applyTestingPreset = () => {
    const preset = {
      ENABLE_ML_SIGNAL_FILTER: 'false',
      ML_SIGNAL_FILTER_MIN_CONFIDENCE: 0.3,
      ML_SIGNAL_FILTER_MIN_WIN_PROB: 0.3,
      STRATEGY_MIN_BARS: 10,
      TRADING_FREQUENCY: 1,
      MAX_DISCOVERED_STOCKS: 200,
      BOT_MAX_OPEN_POSITIONS: 50,
      BOT_MAX_ALLOCATION: 5000,
    }
    // Update local UI state for immediate feedback
    setLocalSettings((prev) => ({ ...prev, ...preset }))
    setHasChanges(true)
    onSave('preset', preset)
    toast.success('Applied Testing Mode preset')
  }

  const applyModerateMlPreset = () => {
    const preset = {
      ENABLE_ML_SIGNAL_FILTER: 'true',
      ML_SIGNAL_FILTER_MIN_CONFIDENCE: 0.5,
      ML_SIGNAL_FILTER_MIN_WIN_PROB: 0.55,
      STRATEGY_MIN_BARS: 30,
      TRADING_FREQUENCY: 3,
    }
    setLocalSettings((prev) => ({ ...prev, ...preset }))
    setHasChanges(true)
    onSave('preset', preset)
    toast.success('Applied Moderate ML preset')
  }

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold capitalize">{category} Settings</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Configure {category} parameters
          </p>
        </div>
        <div className="flex gap-2">
          {category !== 'appearance' && (
            <>
              {hasChanges && (
                <button
                  onClick={handleReset}
                  className="px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                >
                  Reset
                </button>
              )}
              <button
                onClick={handleSave}
                disabled={!hasChanges || isSaving}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isSaving ? 'Saving...' : 'Save Changes'}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Presets Bar */}
      <div className="flex items-center justify-between mb-4 p-3 rounded-lg border border-border bg-card/40">
        <div className="text-sm text-muted-foreground">
          Presets: quickly switch between high-throughput testing and moderate ML settings
        </div>
        <div className="flex gap-2">
          <button
            onClick={applyTestingPreset}
            className="px-3 py-2 text-sm bg-yellow-500/20 text-yellow-300 border border-yellow-500/40 rounded hover:bg-yellow-500/30"
            title="Apply Testing Mode: ML off, freq=1s, min bars=10, max positions=50"
          >
            Apply Testing Mode
          </button>
          <button
            onClick={applyModerateMlPreset}
            className="px-3 py-2 text-sm bg-blue-500/20 text-blue-300 border border-blue-500/40 rounded hover:bg-blue-500/30"
            title="Apply Moderate ML: ML on, confidence≈0.50, win prob≈0.55, min bars=30"
          >
            Apply Moderate ML
          </button>
        </div>
      </div>

      {renderContent()}
    </div>
  )
}

interface SettingFieldProps {
  label: string
  value: any
  onChange: (value: any) => void
  type: string
  min?: number
  max?: number
  step?: number
  description?: string
  suffix?: string
  prefix?: string
  placeholder?: string
  tooltip?: string
  example?: string
}

function SettingField({
  label,
  value,
  onChange,
  type,
  min,
  max,
  step,
  description,
  suffix,
  prefix,
  placeholder,
  tooltip,
  example,
}: SettingFieldProps) {
  const [showTooltip, setShowTooltip] = useState(false)

  return (
    <div>
      <label className="block text-sm font-medium mb-2 flex items-center gap-2">
        {label}
        {(tooltip || example) && (
          <div className="relative inline-block">
            <button
              type="button"
              onMouseEnter={() => setShowTooltip(true)}
              onMouseLeave={() => setShowTooltip(false)}
              onClick={() => setShowTooltip(!showTooltip)}
              className="w-4 h-4 rounded-full bg-muted hover:bg-muted-foreground/20 flex items-center justify-center text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              ?
            </button>
            {showTooltip && (
              <div className="absolute left-6 top-0 z-50 w-80 p-3 bg-popover border border-border rounded-lg shadow-lg text-sm">
                {tooltip && (
                  <div className="mb-2">
                    <p className="text-foreground">{tooltip}</p>
                  </div>
                )}
                {example && (
                  <div className="mt-2 p-2 bg-muted/50 rounded border border-border/50">
                    <p className="text-xs font-semibold text-muted-foreground mb-1">Example:</p>
                    <p className="text-xs text-foreground font-mono">{example}</p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </label>
      <div className="flex items-center gap-2">
        {prefix && <span className="text-muted-foreground">{prefix}</span>}
        <input
          type={type}
          value={value ?? ''}
          onChange={(e) => onChange(type === 'number' ? parseFloat(e.target.value) || 0 : e.target.value)}
          min={min}
          max={max}
          step={step}
          placeholder={placeholder}
          className="flex-1 px-3 py-2 bg-background border border-input rounded-lg focus:outline-none focus:ring-2 focus:ring-ring"
        />
        {suffix && <span className="text-muted-foreground">{suffix}</span>}
      </div>
      {description && (
        <p className="text-xs text-muted-foreground mt-1">{description}</p>
      )}
    </div>
  )
}
