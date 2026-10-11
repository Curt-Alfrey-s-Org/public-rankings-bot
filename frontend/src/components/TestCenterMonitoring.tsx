/**
 * Monitoring component for TestCenter showing session statistics and performance metrics
 */

import React, { useState, useEffect } from 'react'
import { testCenterLogger } from '@/lib/testCenterLogger'

interface SessionStats {
  sessionDuration: number
  activeOperations: number
  activeOperationIds: string[]
  isDevelopment: boolean
  consoleLoggingEnabled: boolean
}

interface MonitoringStats {
  totalErrors: number
  errorRate: number
  avgOperationDuration: number
  operationsCompleted: number
  operationsFailed: number
}

export default function TestCenterMonitoring() {
  const [sessionStats, setSessionStats] = useState<SessionStats | null>(null)
  const [monitoringStats, setMonitoringStats] = useState<MonitoringStats>({
    totalErrors: 0,
    errorRate: 0,
    avgOperationDuration: 0,
    operationsCompleted: 0,
    operationsFailed: 0
  })
  const [isExpanded, setIsExpanded] = useState(false)

  // Update stats every 5 seconds
  useEffect(() => {
    const updateStats = () => {
      const stats = testCenterLogger.getSessionStats()
      setSessionStats(stats)

      // Calculate monitoring stats from logger data
      // This is a simplified version - in a real app you'd track these metrics
      setMonitoringStats(prev => ({
        ...prev,
        // These would be calculated from actual logged data
        totalErrors: prev.totalErrors,
        operationsCompleted: prev.operationsCompleted,
        operationsFailed: prev.operationsFailed
      }))
    }

    updateStats()
    const interval = setInterval(updateStats, 5000)
    return () => clearInterval(interval)
  }, [])

  const formatDuration = (ms: number) => {
    const seconds = Math.floor(ms / 1000)
    const minutes = Math.floor(seconds / 60)
    const hours = Math.floor(minutes / 60)

    if (hours > 0) return `${hours}h ${minutes % 60}m`
    if (minutes > 0) return `${minutes}m ${seconds % 60}s`
    return `${seconds}s`
  }

  const formatPercentage = (value: number) => `${value.toFixed(1)}%`

  if (!sessionStats) return null

  return (
    <div className="test-center-monitoring">
      <div className="monitoring-header">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="monitoring-toggle"
        >
          📊 Monitoring {isExpanded ? '▼' : '▶'}
        </button>
        <div className="monitoring-indicators">
          <span className={`indicator ${sessionStats.activeOperations > 0 ? 'active' : 'idle'}`}>
            {sessionStats.activeOperations > 0 ? '🟢' : '⚪'} {sessionStats.activeOperations} active
          </span>
          {sessionStats.isDevelopment && (
            <span className="indicator dev">🔧 DEV</span>
          )}
        </div>
      </div>

      {isExpanded && (
        <div className="monitoring-details">
          <div className="monitoring-section">
            <h4>📈 Session Statistics</h4>
            <div className="stats-grid">
              <div className="stat-item">
                <span className="stat-label">Duration:</span>
                <span className="stat-value">{formatDuration(sessionStats.sessionDuration)}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Active Operations:</span>
                <span className="stat-value">{sessionStats.activeOperations}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Console Logging:</span>
                <span className="stat-value">{sessionStats.consoleLoggingEnabled ? 'Enabled' : 'Disabled'}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Environment:</span>
                <span className="stat-value">{sessionStats.isDevelopment ? 'Development' : 'Production'}</span>
              </div>
            </div>
          </div>

          {sessionStats.activeOperationIds.length > 0 && (
            <div className="monitoring-section">
              <h4>⚙️ Active Operations</h4>
              <div className="active-operations">
                {sessionStats.activeOperationIds.map((id, index) => (
                  <div key={id} className="operation-item">
                    <span className="operation-id">{id}</span>
                    <span className="operation-status">⏳ Running</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="monitoring-section">
            <h4>🔍 Performance Metrics</h4>
            <div className="stats-grid">
              <div className="stat-item">
                <span className="stat-label">Total Errors:</span>
                <span className="stat-value">{monitoringStats.totalErrors}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Error Rate:</span>
                <span className="stat-value">{formatPercentage(monitoringStats.errorRate)}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Avg Operation Time:</span>
                <span className="stat-value">{formatDuration(monitoringStats.avgOperationDuration)}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Success Rate:</span>
                <span className="stat-value">
                  {monitoringStats.operationsCompleted + monitoringStats.operationsFailed > 0
                    ? formatPercentage((monitoringStats.operationsCompleted /
                        (monitoringStats.operationsCompleted + monitoringStats.operationsFailed)) * 100)
                    : 'N/A'
                  }
                </span>
              </div>
            </div>
          </div>

          <div className="monitoring-actions">
            <button
              onClick={() => testCenterLogger.cleanup()}
              className="action-button secondary small"
            >
              🧹 Cleanup
            </button>
            <button
              onClick={() => {
                const logs = testCenterLogger.getSessionStats()
                console.log('TestCenter Session Stats:', logs)
                alert('Session stats logged to console')
              }}
              className="action-button secondary small"
            >
              📋 Log Stats
            </button>
          </div>
        </div>
      )}
    </div>
  )
}