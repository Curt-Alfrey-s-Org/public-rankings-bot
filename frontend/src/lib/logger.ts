/**
 * Structured logging utility for the frontend
 * Provides consistent logging across the application with different levels and contexts
 */

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
  FATAL = 4
}

interface LogContext {
  [key: string]: any
}

interface LogEntry {
  timestamp: string
  level: LogLevel
  message: string
  context?: LogContext
  userId?: string
  sessionId?: string
  userAgent?: string
  url?: string
  error?: {
    name: string
    message: string
    stack?: string
  }
}

class Logger {
  private level: LogLevel = LogLevel.INFO
  private sessionId: string
  private logs: LogEntry[] = []
  private maxLogsInMemory = 100

  constructor() {
    // Generate session ID
    this.sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    // Set log level based on environment
    if (import.meta.env.DEV) {
      this.level = LogLevel.DEBUG
    } else if (import.meta.env.PROD) {
      this.level = LogLevel.WARN
    }

    // Override with environment variable if set
    const envLevel = import.meta.env.VITE_LOG_LEVEL
    if (envLevel) {
      const levelMap = {
        'debug': LogLevel.DEBUG,
        'info': LogLevel.INFO,
        'warn': LogLevel.WARN,
        'error': LogLevel.ERROR,
        'fatal': LogLevel.FATAL
      }
      const parsedLevel = levelMap[envLevel.toLowerCase() as keyof typeof levelMap]
      if (parsedLevel !== undefined) {
        this.level = parsedLevel
      }
    }
  }

  private shouldLog(level: LogLevel): boolean {
    return level >= this.level
  }

  private createLogEntry(level: LogLevel, message: string, context?: LogContext, error?: Error): LogEntry {
    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      message,
      sessionId: this.sessionId,
      userAgent: navigator.userAgent,
      url: window.location.href
    }

    // Add user ID if available
    try {
      const authData = localStorage.getItem('rankings_bot_auth')
      if (authData) {
        const parsed = JSON.parse(authData)
        entry.userId = parsed?.user
      }
    } catch {
      // Ignore localStorage errors
    }

    if (context) {
      entry.context = context
    }

    if (error) {
      entry.error = {
        name: error.name,
        message: error.message,
        stack: error.stack
      }
    }

    return entry
  }

  private log(level: LogLevel, message: string, context?: LogContext, error?: Error) {
    if (!this.shouldLog(level)) {
      return
    }

    const entry = this.createLogEntry(level, message, context, error)

    // Store in memory (for debugging and error reporting)
    this.logs.push(entry)
    if (this.logs.length > this.maxLogsInMemory) {
      this.logs.shift() // Remove oldest
    }

    // Console logging with appropriate method
    const logMethod = level >= LogLevel.ERROR ? 'error' :
                     level >= LogLevel.WARN ? 'warn' :
                     level >= LogLevel.INFO ? 'info' : 'debug'

    const prefix = `[${LogLevel[level]}]`

    if (error) {
      console[logMethod](`${prefix} ${message}`, error, context || {})
    } else if (context) {
      console[logMethod](`${prefix} ${message}`, context)
    } else {
      console[logMethod](`${prefix} ${message}`)
    }

    // Send critical errors to monitoring service
    if (level >= LogLevel.ERROR) {
      this.reportToMonitoring(entry)
    }
  }

  private reportToMonitoring(entry: LogEntry) {
    try {
      const sentry = (window as any).Sentry
      if (sentry?.captureMessage) {
        sentry.captureMessage(entry.message, {
          level: 'error',
          extra: entry,
        })
      } else {
        // Best-effort local backend log ingestion endpoint.
        navigator.sendBeacon?.('/api/logs/frontend', JSON.stringify(entry))
      }

      // For now, store critical logs locally for debugging
      const criticalLogs = JSON.parse(localStorage.getItem('critical_logs') || '[]')
      criticalLogs.push(entry)
      // Keep only last 10 critical logs
      if (criticalLogs.length > 10) {
        criticalLogs.splice(0, criticalLogs.length - 10)
      }
      localStorage.setItem('critical_logs', JSON.stringify(criticalLogs))
    } catch (error) {
      // Don't let monitoring failures break the app
      console.warn('Failed to report error to monitoring:', error)
    }
  }

  debug(message: string, context?: LogContext) {
    this.log(LogLevel.DEBUG, message, context)
  }

  info(message: string, context?: LogContext) {
    this.log(LogLevel.INFO, message, context)
  }

  warn(message: string, context?: LogContext, error?: Error) {
    this.log(LogLevel.WARN, message, context, error)
  }

  error(message: string, error?: Error, context?: LogContext) {
    this.log(LogLevel.ERROR, message, context, error)
  }

  fatal(message: string, error?: Error, context?: LogContext) {
    this.log(LogLevel.FATAL, message, context, error)
  }

  // Specialized logging methods
  apiCall(method: string, url: string, status?: number, duration?: number, error?: Error, requestId?: string) {
    const context: LogContext = {
      method,
      url,
      status,
      duration
    }
    if (requestId) {
      context.requestId = requestId
    }

    if (error) {
      this.error(`API call failed: ${method} ${url}`, error, context)
    } else if (status && status >= 400) {
      this.warn(`API call error: ${method} ${url}`, context)
    } else {
      this.debug(`API call: ${method} ${url}`, context)
    }
  }

  userAction(action: string, details?: LogContext) {
    this.info(`User action: ${action}`, details)
  }

  performance(metric: string, value: number, context?: LogContext) {
    this.info(`Performance: ${metric}`, { ...context, value })
  }

  security(event: string, details?: LogContext) {
    this.warn(`Security: ${event}`, details)
  }

  // Get recent logs for debugging
  getRecentLogs(count: number = 50): LogEntry[] {
    return this.logs.slice(-count)
  }

  // Export logs for debugging/support
  exportLogs(): string {
    return JSON.stringify(this.logs, null, 2)
  }

  // Clear logs
  clearLogs() {
    this.logs = []
  }
}

// Create singleton instance
export const logger = new Logger()

// Export convenience functions
export const log = {
  debug: logger.debug.bind(logger),
  info: logger.info.bind(logger),
  warn: logger.warn.bind(logger),
  error: logger.error.bind(logger),
  fatal: logger.fatal.bind(logger),
  apiCall: logger.apiCall.bind(logger),
  userAction: logger.userAction.bind(logger),
  performance: logger.performance.bind(logger),
  security: logger.security.bind(logger)
}

export default logger