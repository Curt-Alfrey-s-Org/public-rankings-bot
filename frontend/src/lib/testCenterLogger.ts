/**
 * Specialized logger for TestCenter component
 * Provides comprehensive error handling, debug logging, and performance monitoring
 */

import { logger } from './logger'

// TestCenter specific log contexts
interface TestCenterContext {
  component: 'TestCenter'
  tab?: 'tournament-workflow' | 'api' | 'database' | 'system'
  step?: string
  operation?: string
  duration?: number
  retryCount?: number
  errorType?: string
  recoveryAction?: string
  userAction?: string
  dataSize?: number
  tournamentId?: string
  matchId?: string
}

class TestCenterLogger {
  private isDevelopment = import.meta.env.DEV
  private enableConsoleLogging = import.meta.env.VITE_TESTCENTER_DEBUG_LOGGING !== 'false'
  private sessionStart = Date.now()
  private operationTracker = new Map<string, { start: number; context: Partial<TestCenterContext> }>()

  /**
   * Start tracking an operation
   */
  startOperation(operationId: string, context: Partial<TestCenterContext>) {
    this.operationTracker.set(operationId, {
      start: Date.now(),
      context: { ...context, component: 'TestCenter' }
    })

    if (this.enableConsoleLogging && this.isDevelopment) {
      console.group(`🧪 TestCenter: ${operationId}`)
      console.log('Started:', context)
    }

    logger.debug(`TestCenter operation started: ${operationId}`, context as any)
  }

  /**
   * End tracking an operation
   */
  endOperation(operationId: string, success: boolean = true, additionalContext?: Partial<TestCenterContext>) {
    const operation = this.operationTracker.get(operationId)
    if (!operation) return

    const duration = Date.now() - operation.start
    const finalContext: TestCenterContext = {
      ...operation.context,
      ...additionalContext,
      duration,
      component: 'TestCenter'
    } as TestCenterContext

    this.operationTracker.delete(operationId)

    if (this.enableConsoleLogging && this.isDevelopment) {
      console.log(`Completed ${success ? '✅' : '❌'}:`, finalContext)
      console.groupEnd()
    }

    if (success) {
      logger.performance(`TestCenter operation completed: ${operationId}`, duration, finalContext)
    } else {
      logger.warn(`TestCenter operation failed: ${operationId}`, finalContext)
    }
  }

  /**
   * Log step transitions in the tournament workflow
   */
  stepTransition(fromStep: string, toStep: string, context?: Partial<TestCenterContext>) {
    const logContext: TestCenterContext = {
      component: 'TestCenter',
      tab: 'tournament-workflow',
      operation: 'step_transition',
      userAction: `transition_${fromStep}_to_${toStep}`,
      ...context
    } as TestCenterContext

    if (this.enableConsoleLogging && this.isDevelopment) {
      console.log(`🔄 Step Transition: ${fromStep} → ${toStep}`, context || {})
    }

    logger.userAction(`TestCenter step transition: ${fromStep} → ${toStep}`, logContext)
  }

  /**
   * Log API call results with detailed error information
   */
  apiCall(endpoint: string, method: string, success: boolean, duration: number, context?: Partial<TestCenterContext>, error?: any) {
    const logContext: TestCenterContext = {
      component: 'TestCenter',
      operation: 'api_call',
      duration,
      ...context
    } as TestCenterContext

    if (error) {
      logContext.errorType = error.name || 'UnknownError'
    }

    if (this.enableConsoleLogging && this.isDevelopment) {
      if (success) {
        console.log(`📡 API: ${method} ${endpoint} (${duration}ms)`, context || {})
      } else {
        console.error(`❌ API Failed: ${method} ${endpoint} (${duration}ms)`, error, context || {})
      }
    }

    if (success) {
      logger.apiCall(method, endpoint, 200, duration)
    } else {
      logger.apiCall(method, endpoint, error?.response?.status || 0, duration, error)
    }
  }

  /**
   * Log data flow and transformations
   */
  dataFlow(operation: string, dataSize: number, context?: Partial<TestCenterContext>) {
    const logContext: TestCenterContext = {
      component: 'TestCenter',
      operation: 'data_flow',
      dataSize,
      ...context
    } as TestCenterContext

    if (this.enableConsoleLogging && this.isDevelopment) {
      console.log(`📊 Data Flow: ${operation} (${dataSize} items)`, context || {})
    }

    logger.debug(`TestCenter data flow: ${operation}`, logContext)
  }

  /**
   * Log error recovery attempts
   */
  errorRecovery(errorType: string, recoveryAction: string, success: boolean, context?: Partial<TestCenterContext>) {
    const logContext: TestCenterContext = {
      component: 'TestCenter',
      operation: 'error_recovery',
      errorType,
      recoveryAction,
      ...context
    } as TestCenterContext

    if (this.enableConsoleLogging && this.isDevelopment) {
      console.log(`${success ? '🔧' : '💥'} Recovery ${success ? 'Success' : 'Failed'}: ${recoveryAction} for ${errorType}`, context || {})
    }

    if (success) {
      logger.info(`TestCenter error recovery successful: ${recoveryAction}`, logContext)
    } else {
      logger.warn(`TestCenter error recovery failed: ${recoveryAction}`, logContext)
    }
  }

  /**
   * Log user interactions with detailed context
   */
  userInteraction(action: string, details?: any, context?: Partial<TestCenterContext>) {
    const logContext: TestCenterContext = {
      component: 'TestCenter',
      operation: 'user_interaction',
      userAction: action,
      ...context
    } as TestCenterContext

    if (this.enableConsoleLogging && this.isDevelopment) {
      console.log(`👤 User Action: ${action}`, details, context || {})
    }

    logger.userAction(`TestCenter: ${action}`, { ...logContext, ...details })
  }

  /**
   * Log retry attempts
   */
  retryAttempt(operationId: string, attemptNumber: number, maxRetries: number, context?: Partial<TestCenterContext>) {
    const logContext: TestCenterContext = {
      component: 'TestCenter',
      operation: 'retry_attempt',
      retryCount: attemptNumber,
      ...context
    } as TestCenterContext

    if (this.enableConsoleLogging && this.isDevelopment) {
      console.warn(`🔄 Retry ${attemptNumber}/${maxRetries}: ${operationId}`, context || {})
    }

    logger.warn(`TestCenter retry attempt ${attemptNumber}/${maxRetries}: ${operationId}`, logContext)
  }

  /**
   * Log critical errors with enhanced context
   */
  criticalError(error: Error, context?: Partial<TestCenterContext>) {
    const logContext: TestCenterContext = {
      component: 'TestCenter',
      operation: 'critical_error',
      errorType: error.name,
      ...context
    } as TestCenterContext

    if (this.enableConsoleLogging && this.isDevelopment) {
      console.error('🚨 CRITICAL ERROR:', error, context || {})
    }

    logger.error(`TestCenter critical error: ${error.message}`, error, logContext)
  }

  /**
   * Log performance metrics
   */
  performance(metric: string, value: number, context?: Partial<TestCenterContext>) {
    const logContext: TestCenterContext = {
      component: 'TestCenter',
      operation: 'performance',
      ...context
    } as TestCenterContext

    if (this.enableConsoleLogging && this.isDevelopment) {
      console.log(`⚡ Performance: ${metric} = ${value}`, context || {})
    }

    logger.performance(`TestCenter: ${metric}`, value, logContext)
  }

  /**
   * Get session statistics
   */
  getSessionStats() {
    const sessionDuration = Date.now() - this.sessionStart
    const activeOperations = Array.from(this.operationTracker.keys())

    return {
      sessionDuration,
      activeOperations: activeOperations.length,
      activeOperationIds: activeOperations,
      isDevelopment: this.isDevelopment,
      consoleLoggingEnabled: this.enableConsoleLogging
    }
  }

  /**
   * Clean up completed operations (call periodically to prevent memory leaks)
   */
  cleanup(maxAge: number = 300000) { // 5 minutes default
    const now = Date.now()
    const toDelete: string[] = []

    for (const [id, operation] of this.operationTracker.entries()) {
      if (now - operation.start > maxAge) {
        toDelete.push(id)
      }
    }

    toDelete.forEach(id => {
      this.operationTracker.delete(id)
      if (this.enableConsoleLogging && this.isDevelopment) {
        console.warn(`🧹 Cleaned up stale operation: ${id}`)
      }
    })

    return toDelete.length
  }
}

// Create singleton instance
export const testCenterLogger = new TestCenterLogger()

// Export convenience functions
export const testCenterLog = {
  startOperation: testCenterLogger.startOperation.bind(testCenterLogger),
  endOperation: testCenterLogger.endOperation.bind(testCenterLogger),
  stepTransition: testCenterLogger.stepTransition.bind(testCenterLogger),
  apiCall: testCenterLogger.apiCall.bind(testCenterLogger),
  dataFlow: testCenterLogger.dataFlow.bind(testCenterLogger),
  errorRecovery: testCenterLogger.errorRecovery.bind(testCenterLogger),
  userInteraction: testCenterLogger.userInteraction.bind(testCenterLogger),
  retryAttempt: testCenterLogger.retryAttempt.bind(testCenterLogger),
  criticalError: testCenterLogger.criticalError.bind(testCenterLogger),
  performance: testCenterLogger.performance.bind(testCenterLogger),
  getSessionStats: testCenterLogger.getSessionStats.bind(testCenterLogger),
  cleanup: testCenterLogger.cleanup.bind(testCenterLogger)
}

export default testCenterLogger