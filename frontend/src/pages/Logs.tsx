import { useState, useMemo, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { logsApi, LogEntry } from '@/api/logs'
import { logger } from '@/lib/logger'

const LOGS_PREFS_KEY = 'logs_preferences'

function loadLogsPrefs(): Partial<{
  activeView: ViewId
  filterLevel: string
  filterLogger: string
  searchText: string
  sortBy: 'timestamp' | 'level' | 'logger'
  sortOrder: 'asc' | 'desc'
  limit: number
  autoRefresh: boolean
}> {
  try {
    const raw = localStorage.getItem(LOGS_PREFS_KEY)
    if (!raw) return {}
    const p = JSON.parse(raw) as Record<string, unknown>
    return {
      activeView: typeof p.activeView === 'string' ? p.activeView as ViewId : undefined,
      filterLevel: typeof p.filterLevel === 'string' ? p.filterLevel : undefined,
      filterLogger: typeof p.filterLogger === 'string' ? p.filterLogger : undefined,
      searchText: typeof p.searchText === 'string' ? p.searchText : undefined,
      sortBy: p.sortBy === 'timestamp' || p.sortBy === 'level' || p.sortBy === 'logger' ? p.sortBy : undefined,
      sortOrder: p.sortOrder === 'asc' || p.sortOrder === 'desc' ? p.sortOrder : undefined,
      limit: typeof p.limit === 'number' && p.limit > 0 ? p.limit : undefined,
      autoRefresh: typeof p.autoRefresh === 'boolean' ? p.autoRefresh : undefined,
    }
  } catch (error) {
    logger.warn('Failed to parse saved log preferences', undefined, error as Error)
    return {}
  }
}

function saveLogsPrefs(prefs: Record<string, unknown>) {
  try {
    localStorage.setItem(LOGS_PREFS_KEY, JSON.stringify(prefs))
  } catch (error) {
    logger.warn('Failed to persist log preferences', undefined, error as Error)
  }
}

interface LogsProps {
  sidebarOpen?: boolean
  onSidebarToggle?: () => void
}

type ViewId = 'all' | 'trade' | 'errors' | 'critical' | 'warnings' | 'info' | 'debug'

const LOG_VIEWS: { id: ViewId; label: string; level: string; search: string; tooltip: string }[] = [
  { id: 'all', label: 'All', level: 'all', search: '', tooltip: 'Show all log entries. No level or search filter. Example: full bot output, startup, and all levels.' },
  { id: 'trade', label: 'Trade', level: 'all', search: 'order', tooltip: 'Logs about orders and trade execution. Search: "order". Example: "Order filled", "Order submitted", "execute_trade", "Cycle #N complete".' },
  { id: 'errors', label: 'Errors', level: 'ERROR', search: '', tooltip: 'Only ERROR level. Failures and exceptions. Example: "Strategy signal failed", "Execution error for AAPL".' },
  { id: 'critical', label: 'Critical', level: 'CRITICAL', search: '', tooltip: 'Only CRITICAL level. Severe failures. Example: unhandled crashes, critical system errors.' },
  { id: 'warnings', label: 'Warnings', level: 'WARNING', search: '', tooltip: 'Only WARNING level. Non-fatal issues. Example: "Symbol timed out", "Resource throttle".' },
  { id: 'info', label: 'Info', level: 'INFO', search: '', tooltip: 'Only INFO level. Normal operation. Example: "Cycle #1 started", "Loaded 16 symbols".' },
  { id: 'debug', label: 'Debug', level: 'DEBUG', search: '', tooltip: 'Only DEBUG level. Verbose details. Enable in Settings or .env (DEBUG=true). Example: timing, internal state.' },
]

export default function LogsPage({ sidebarOpen: _sidebarOpen, onSidebarToggle }: LogsProps) {
  const [activeView, setActiveView] = useState<ViewId>(() => loadLogsPrefs().activeView ?? 'all')
  const [filterLevel, setFilterLevel] = useState<string>(() => loadLogsPrefs().filterLevel ?? 'all')
  const [filterLogger, setFilterLogger] = useState<string>(() => loadLogsPrefs().filterLogger ?? '')
  const [searchText, setSearchText] = useState<string>(() => loadLogsPrefs().searchText ?? '')
  const [sortBy, setSortBy] = useState<'timestamp' | 'level' | 'logger'>(() => loadLogsPrefs().sortBy ?? 'timestamp')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>(() => loadLogsPrefs().sortOrder ?? 'asc')
  const [limit, setLimit] = useState<number>(() => loadLogsPrefs().limit ?? 500)
  const [autoRefresh, setAutoRefresh] = useState<boolean>(() => loadLogsPrefs().autoRefresh ?? true)

  useEffect(() => {
    saveLogsPrefs({
      activeView,
      filterLevel,
      filterLogger,
      searchText,
      sortBy,
      sortOrder,
      limit,
      autoRefresh,
    })
  }, [activeView, filterLevel, filterLogger, searchText, sortBy, sortOrder, limit, autoRefresh])

  const applyView = (view: typeof LOG_VIEWS[0]) => {
    setActiveView(view.id)
    setFilterLevel(view.level)
    setSearchText(view.search)
  }

  const { data, isLoading, error } = useQuery({
    queryKey: ['logs', filterLevel, filterLogger, searchText, sortBy, sortOrder, limit],
    queryFn: () => logsApi.getLogs({
      limit,
      level: filterLevel === 'all' ? undefined : filterLevel,
      logger_name: filterLogger || undefined,
      search: searchText || undefined,
      sort_by: sortBy,
      sort_order: sortOrder,
      tail: true,
    }),
    refetchInterval: autoRefresh ? 5000 : false, // Refresh every 5 seconds if auto-refresh enabled (reduced to prevent glitching)
    retry: 1,
    retryDelay: 1000,
  })

  // Extract unique loggers for filter dropdown
  const uniqueLoggers = useMemo(() => {
    if (!data?.logs) return []
    const loggers = new Set<string>()
    data.logs.forEach(log => {
      if (log.logger) loggers.add(log.logger)
    })
    return Array.from(loggers).sort()
  }, [data])

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'CRITICAL':
        return 'text-red-600 bg-red-500/20 border-red-500/30'
      case 'ERROR':
        return 'text-red-500 bg-red-500/10 border-red-500/20'
      case 'WARNING':
        return 'text-yellow-600 bg-yellow-500/20 border-yellow-500/30'
      case 'INFO':
        return 'text-blue-500 bg-blue-500/10 border-blue-500/20'
      case 'DEBUG':
        return 'text-gray-500 bg-gray-500/10 border-gray-500/20'
      default:
        return 'text-muted-foreground bg-muted'
    }
  }

  const formatTimestamp = (timestamp: string) => {
    if (!timestamp) return ''
    // Try to parse and format timestamp
    try {
      const date = new Date(timestamp)
      if (!isNaN(date.getTime())) {
        return date.toLocaleString()
      }
    } catch (error) {
      logger.warn('Failed to parse log timestamp', { timestamp }, error as Error)
    }
    return timestamp
  }

  return (
    <div className="flex flex-col h-screen bg-black/90 text-foreground overflow-hidden">
      {/* Header */}
      <header className="bg-card/50 backdrop-blur-sm border-b border-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          {onSidebarToggle && (
            <button
              onClick={onSidebarToggle}
              className="p-2 hover:bg-accent rounded-lg transition-colors"
              aria-label="Toggle menu"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          )}
          <div>
            <h1 className="text-2xl font-bold">Logs</h1>
            <p className="text-sm text-muted-foreground">
              Real-time bot execution logs
            </p>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-hidden flex flex-col p-6">
        {/* View buttons: quick presets for log kind */}
        <div className="mb-3 flex items-center gap-3 flex-wrap">
          <span className="text-sm font-medium text-muted-foreground" title="Click a preset to show that kind of log in the box below. Filters and sort still apply.">View:</span>
          <div className="flex flex-wrap gap-2" role="group" aria-label="Log view presets">
          {LOG_VIEWS.map((view) => (
            <button
              key={view.id}
              type="button"
              title={view.tooltip}
              onClick={() => applyView(view)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors border ${
                activeView === view.id
                  ? 'bg-primary text-primary-foreground border-primary'
                  : 'bg-card/80 border-border hover:bg-accent/50'
              }`}
            >
              {view.label}
            </button>
          ))}
        </div>
        </div>

        {/* Controls: filters and sort (apply on top of current view) */}
        <div className="mb-4 space-y-3">
          {/* First Row: Filters */}
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2" title="Filter by log level. Example: choose ERROR to see only error lines; All shows every level.">
              <label className="text-sm font-medium">Level:</label>
              <select
                value={filterLevel}
                onChange={(e) => { setFilterLevel(e.target.value); setActiveView('all') }}
                className="px-3 py-1.5 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="all">All Levels</option>
                <option value="DEBUG">DEBUG</option>
                <option value="INFO">INFO</option>
                <option value="WARNING">WARNING</option>
                <option value="ERROR">ERROR</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
            </div>

            <div className="flex items-center gap-2" title="Filter by logger (module) name. Example: api.bot_manager shows only bot loop logs; leave All for every logger.">
              <label className="text-sm font-medium">Logger:</label>
              <select
                value={filterLogger}
                onChange={(e) => { setFilterLogger(e.target.value); setActiveView('all') }}
                className="px-3 py-1.5 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring min-w-[150px]"
              >
                <option value="">All Loggers</option>
                {uniqueLoggers.map(logger => (
                  <option key={logger} value={logger}>{logger}</option>
                ))}
              </select>
            </div>

            <div className="flex items-center gap-2 flex-1 min-w-[200px]" title="Search inside log messages (case-insensitive). Example: type 'timeout' to see only lines containing 'timeout'.">
              <label className="text-sm font-medium">Search:</label>
              <input
                type="text"
                value={searchText}
                onChange={(e) => { setSearchText(e.target.value); setActiveView('all') }}
                placeholder="Search in messages..."
                className="px-3 py-1.5 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring flex-1"
              />
              {searchText && (
                <button
                  onClick={() => setSearchText('')}
                  className="p-1.5 hover:bg-accent rounded-lg transition-colors"
                  title="Clear search"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
          </div>

          {/* Second Row: Sort & Display Options */}
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2" title="Sort rows by this field. Example: Timestamp = chronological; Level = group by severity; Logger = group by module.">
              <label className="text-sm font-medium">Sort By:</label>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as 'timestamp' | 'level' | 'logger')}
                className="px-3 py-1.5 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="timestamp">Timestamp</option>
                <option value="level">Level</option>
                <option value="logger">Logger</option>
              </select>
            </div>

            <div className="flex items-center gap-2" title="Ascending = oldest/first at top; Descending = newest/last at top. Example: Ascending by timestamp = oldest log first.">
              <label className="text-sm font-medium">Order:</label>
              <select
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value as 'asc' | 'desc')}
                className="px-3 py-1.5 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="asc">Ascending</option>
                <option value="desc">Descending</option>
              </select>
            </div>

            <div className="flex items-center gap-2" title="Maximum number of log lines to fetch and show. Example: 500 = show up to 500 lines (after filters); increase for long sessions.">
              <label className="text-sm font-medium">Lines:</label>
              <select
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="px-3 py-1.5 bg-background border border-input rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value={100}>100</option>
                <option value={250}>250</option>
                <option value={500}>500</option>
                <option value={1000}>1000</option>
                <option value={2000}>2000</option>
              </select>
            </div>

            <div className="flex items-center gap-2" title="When on, logs refresh every 5 seconds so you see new entries without reloading. Turn off to freeze the view for reading.">
              <input
                type="checkbox"
                id="autoRefresh"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="w-4 h-4 rounded border-input"
              />
              <label htmlFor="autoRefresh" className="text-sm font-medium cursor-pointer">
                Auto-refresh
              </label>
            </div>

            {data && (
              <div className="text-sm text-muted-foreground ml-auto" title="Count of log lines returned after filters and limit. Increase Lines if you need more.">
                Showing {data.total} log entries
              </div>
            )}
          </div>

          {/* Active Filters Display */}
          {(filterLevel !== 'all' || filterLogger || searchText) && (
            <div className="flex items-center gap-2 flex-wrap text-sm" title="Current Level, Logger, or Search filter. Click × on a chip to remove it; Clear All resets all three.">
              <span className="text-muted-foreground">Active filters:</span>
              {filterLevel !== 'all' && (
                <span className="px-2 py-1 bg-blue-500/20 text-blue-500 rounded flex items-center gap-1">
                  Level: {filterLevel}
                  <button onClick={() => setFilterLevel('all')} className="hover:text-blue-400">×</button>
                </span>
              )}
              {filterLogger && (
                <span className="px-2 py-1 bg-green-500/20 text-green-500 rounded flex items-center gap-1">
                  Logger: {filterLogger}
                  <button onClick={() => setFilterLogger('')} className="hover:text-green-400">×</button>
                </span>
              )}
              {searchText && (
                <span className="px-2 py-1 bg-purple-500/20 text-purple-500 rounded flex items-center gap-1">
                  Search: "{searchText}"
                  <button onClick={() => setSearchText('')} className="hover:text-purple-400">×</button>
                </span>
              )}
              <button
                onClick={() => {
                  setFilterLevel('all')
                  setFilterLogger('')
                  setSearchText('')
                }}
                className="px-2 py-1 bg-destructive/20 text-destructive rounded hover:bg-destructive/30 transition-colors"
              >
                Clear All
              </button>
            </div>
          )}
        </div>

        {/* Log Display */}
        <div
          className="flex-1 overflow-y-auto bg-card border border-border rounded-lg"
          title="Log entries (filtered by view and filters above). Sort by and Order control how rows are ordered."
        >
          {isLoading && (
            <div className="p-8 text-center text-muted-foreground">
              <div className="animate-pulse">Loading logs...</div>
            </div>
          )}

          {/* Show empty state instead of error messages */}
          {error && !isLoading && (
            <div className="p-8 text-center text-muted-foreground">
              <p>No logs available</p>
              <p className="text-sm mt-2">Logs will appear here when available</p>
            </div>
          )}

          {!error && data && !data.exists && (
            <div className="p-8 text-center text-muted-foreground">
              <p>Log file not found</p>
              <p className="text-sm mt-2">Expected location: {data.file}</p>
            </div>
          )}

          {!error && data && data.exists && data.logs.length === 0 && (
            <div className="p-8 text-center text-muted-foreground">
              <p>No logs found</p>
              {filterLevel !== 'all' && (
                <p className="text-sm mt-2">Try changing the filter level</p>
              )}
            </div>
          )}

          {!error && data && data.exists && data.logs.length > 0 && (
            <div className="p-4 space-y-1 font-mono text-xs">
              {data.logs.map((log: LogEntry, index: number) => (
                <div
                  key={index}
                  className={`p-2 rounded border-l-4 ${getLevelColor(log.level)} hover:bg-opacity-20 transition-colors`}
                >
                  <div className="flex items-start gap-2">
                    {log.timestamp && (
                      <span className="text-muted-foreground flex-shrink-0 min-w-[180px]">
                        {formatTimestamp(log.timestamp)}
                      </span>
                    )}
                    {log.level && (
                      <span className={`px-2 py-0.5 rounded text-xs font-semibold uppercase flex-shrink-0 min-w-[80px] ${getLevelColor(log.level)}`}>
                        {log.level}
                      </span>
                    )}
                    {log.logger && (
                      <span className="text-muted-foreground flex-shrink-0 min-w-[120px]">
                        {log.logger}
                      </span>
                    )}
                    <span className="flex-1 break-words">{log.message}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
