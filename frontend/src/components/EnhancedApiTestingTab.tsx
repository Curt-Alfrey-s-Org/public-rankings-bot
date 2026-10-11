/**
 * Enhanced API Testing Tab with Comprehensive Performance Monitoring
 * Features detailed metrics, load testing, network simulation, and visual analytics
 */

import React, { useState, useEffect, useCallback } from 'react'
import { testTournamentsApi } from '@/api/testTournaments'
import { toast } from '@/lib/toast'
import { testCenterLogger, testCenterLog } from '@/lib/testCenterLogger'
import {
  performanceTracker,
  PerformanceMetrics,
  LoadTestResult,
  LoadTestConfig,
  PerformanceBaseline,
  NetworkCondition,
  PerformanceHistory,
  PerformanceTestRun
} from '@/lib/performanceMetricsTracker'
import PerformanceCharts, { PerformanceSummary, LoadTestSummary } from './PerformanceCharts'
import { Download, Upload, Play, Square, Settings, BarChart3, Zap, Globe, Cpu } from 'lucide-react'

interface EnhancedApiTestingTabProps {
  testResults: TestResult[]
  isRunningTests: boolean
  onRunTests: () => void
}

interface TestResult {
  test: string
  status: 'pending' | 'running' | 'passed' | 'failed'
  message: string
  duration?: number
}

export default function EnhancedApiTestingTab({
  testResults,
  isRunningTests,
  onRunTests
}: EnhancedApiTestingTabProps) {
  // Performance monitoring state
  const [performanceMetrics, setPerformanceMetrics] = useState<PerformanceMetrics[]>([])
  const [loadTestResults, setLoadTestResults] = useState<LoadTestResult[]>([])
  const [performanceHistory, setPerformanceHistory] = useState<PerformanceHistory>({
    testRuns: [],
    baselines: []
  })
  const [currentBaseline, setCurrentBaseline] = useState<PerformanceBaseline | null>(null)

  // Test configuration state
  const [activeView, setActiveView] = useState<'basic' | 'performance' | 'load-test' | 'analytics'>('basic')
  const [selectedNetworkCondition, setSelectedNetworkCondition] = useState<NetworkCondition | null>(null)
  const [networkConditions] = useState(performanceTracker.getNetworkConditions())

  // Load test configuration
  const [loadTestConfig, setLoadTestConfig] = useState<LoadTestConfig>({
    concurrentRequests: 10,
    totalRequests: 100,
    rampUpTime: 5,
    duration: 30,
    networkCondition: undefined
  })
  const [isLoadTesting, setIsLoadTesting] = useState(false)

  // Memory monitoring
  const [memoryUsage, setMemoryUsage] = useState<{ used: number; total: number; limit: number } | null>(null)
  const [memoryHistory, setMemoryHistory] = useState<Array<{ timestamp: number; used: number; total: number }>>([])

  // Export/Import state
  const [exportFileName, setExportFileName] = useState('performance-test-results')
  const [importData, setImportData] = useState('')

  // Enhanced test runner with performance monitoring
  const runPerformanceTests = useCallback(async () => {
    const testSuiteId = `performance_tests_${Date.now()}`
    testCenterLog.startOperation(testSuiteId, {
      tab: 'api',
      operation: 'run_performance_tests',
      networkCondition: selectedNetworkCondition?.name
    })

    setPerformanceMetrics([])
    const results: PerformanceMetrics[] = []

    try {
      // Test endpoints with performance monitoring
      const endpoints = [
        { name: 'Get Current Tournament', fn: () => testTournamentsApi.getCurrentTournament() },
        { name: 'Get Tournament Players', fn: () => testTournamentsApi.getPlayers() },
        { name: 'Get Tournament Matches', fn: () => testTournamentsApi.getMatches() },
        { name: 'Get Tournament Leaderboard', fn: () => testTournamentsApi.getLeaderboard() }
      ]

      for (const endpoint of endpoints) {
        const startTime = performance.now()

        try {
          const response = await endpoint.fn()

          // Create mock Response object for metrics tracking
          const mockResponse = new Response(JSON.stringify(response), {
            status: 200,
            statusText: 'OK',
            headers: { 'content-type': 'application/json' }
          })

          const metrics = await performanceTracker.captureMetrics(
            'GET',
            endpoint.name.toLowerCase().replace(/\s+/g, '_'),
            mockResponse,
            startTime,
            selectedNetworkCondition || undefined
          )

          results.push(metrics)
          setPerformanceMetrics(prev => [...prev, metrics])

        } catch (error: any) {
          // Create error metrics
          const errorMetrics: PerformanceMetrics = {
            totalTime: performance.now() - startTime,
            ttfb: performance.now() - startTime,
            responseTime: performance.now() - startTime,
            responseSize: 0,
            responseSizeText: '0 B',
            bandwidth: 0,
            bandwidthText: '0 B/s',
            method: 'GET',
            url: endpoint.name.toLowerCase().replace(/\s+/g, '_'),
            statusCode: 0,
            statusText: 'Error',
            timestamp: Date.now(),
            userAgent: navigator.userAgent,
            isError: true,
            error: error.message
          }

          results.push(errorMetrics)
          setPerformanceMetrics(prev => [...prev, errorMetrics])
        }
      }

      // Save test run to history
      const testRun: PerformanceTestRun = {
        id: `test_run_${Date.now()}`,
        name: `API Performance Test ${new Date().toLocaleString()}`,
        timestamp: Date.now(),
        metrics: results,
        networkCondition: selectedNetworkCondition || undefined
      }

      setPerformanceHistory(prev => ({
        ...prev,
        testRuns: [...prev.testRuns, testRun]
      }))

      testCenterLog.endOperation(testSuiteId, true, {
        tab: 'api',
        metricsCount: results.length,
        networkCondition: selectedNetworkCondition?.name
      })

      toast.success('Performance tests completed!')

    } catch (error: any) {
      testCenterLog.endOperation(testSuiteId, false, {
        tab: 'api',
        error: error.message
      })
      toast.error(`Performance tests failed: ${error.message}`)
    }
  }, [selectedNetworkCondition])

  // Load testing functionality
  const runLoadTest = useCallback(async () => {
    if (!loadTestConfig.concurrentRequests || !loadTestConfig.totalRequests) {
      toast.error('Please configure load test parameters')
      return
    }

    setIsLoadTesting(true)
    const testSuiteId = `load_test_${Date.now()}`

    testCenterLog.startOperation(testSuiteId, {
      tab: 'api',
      operation: 'run_load_test',
      config: loadTestConfig
    })

    try {
      // Create a simple request function for load testing
      const requestFn = async () => {
        const startTime = performance.now()
        try {
          const response = await testTournamentsApi.getCurrentTournament()
          const endTime = performance.now()

          return new Response(JSON.stringify(response), {
            status: 200,
            statusText: 'OK',
            headers: { 'content-type': 'application/json' }
          })
        } catch (error) {
          throw error
        }
      }

      const result = await performanceTracker.runLoadTest(loadTestConfig, requestFn)
      setLoadTestResults(prev => [...prev, result])

      // Also add to performance history
      const testRun: PerformanceTestRun = {
        id: `load_test_${Date.now()}`,
        name: `Load Test ${new Date().toLocaleString()}`,
        timestamp: Date.now(),
        metrics: result.metrics,
        loadTestResults: [result],
        networkCondition: loadTestConfig.networkCondition
      }

      setPerformanceHistory(prev => ({
        ...prev,
        testRuns: [...prev.testRuns, testRun]
      }))

      testCenterLog.endOperation(testSuiteId, true, {
        tab: 'api',
        loadTestResult: result
      })

      toast.success(`Load test completed! ${result.successfulRequests}/${result.totalRequests} successful`)

    } catch (error: any) {
      testCenterLog.endOperation(testSuiteId, false, {
        tab: 'api',
        error: error.message
      })
      toast.error(`Load test failed: ${error.message}`)
    } finally {
      setIsLoadTesting(false)
    }
  }, [loadTestConfig])

  // Memory monitoring
  useEffect(() => {
    const interval = setInterval(() => {
      const memory = performanceTracker.getMemoryUsage()
      if (memory) {
        setMemoryUsage(memory)
        setMemoryHistory(prev => [...prev.slice(-19), {
          timestamp: Date.now(),
          used: memory.used,
          total: memory.total
        }])
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [])

  // Export functionality
  const exportPerformanceData = useCallback(() => {
    const dataToExport = {
      performanceHistory,
      currentMetrics: performanceMetrics,
      loadTestResults,
      exportTimestamp: Date.now()
    }

    const dataStr = performanceTracker.exportData(dataToExport as any)
    const dataBlob = new Blob([dataStr], { type: 'application/json' })

    const link = document.createElement('a')
    link.href = URL.createObjectURL(dataBlob)
    link.download = `${exportFileName}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)

    toast.success('Performance data exported successfully!')
  }, [performanceHistory, performanceMetrics, loadTestResults, exportFileName])

  // Import functionality
  const importPerformanceData = useCallback(() => {
    try {
      const importedData = performanceTracker.importData(importData)
      if (importedData.testRuns) {
        setPerformanceHistory(importedData)
        toast.success('Performance data imported successfully!')
        setImportData('')
      } else {
        toast.error('Invalid import data format')
      }
    } catch (error) {
      toast.error('Failed to import data: Invalid JSON format')
    }
  }, [importData])

  // Create baseline from current metrics
  const createBaseline = useCallback(() => {
    if (performanceMetrics.length === 0) {
      toast.error('No performance metrics available to create baseline')
      return
    }

    const baseline = performanceTracker.createBaseline(
      `Baseline ${new Date().toLocaleString()}`,
      'Created from current test run',
      performanceMetrics
    )

    setPerformanceHistory(prev => ({
      ...prev,
      baselines: [...prev.baselines, baseline]
    }))

    setCurrentBaseline(baseline)
    toast.success('Baseline created successfully!')
  }, [performanceMetrics])

  // View tabs
  const renderBasicTests = () => (
    <div className="basic-tests">
      <div className="testing-section">
        <h3>🔌 Basic API Endpoint Tests</h3>
        <p>Test all test tournament API endpoints for functionality.</p>

        <div className="test-controls">
          <button
            className="action-button primary"
            onClick={onRunTests}
            disabled={isRunningTests}
          >
            {isRunningTests ? '🧪 Running Tests...' : '🚀 Run Basic Tests'}
          </button>
        </div>
      </div>

      <div className="testing-section">
        <h3>📊 Basic Test Results</h3>
        {testResults.length === 0 ? (
          <p className="no-results">No tests run yet. Click "Run Basic Tests" to start.</p>
        ) : (
          <div className="test-results">
            {testResults.map((result, index) => (
              <div key={index} className={`test-result ${result.status}`}>
                <div className="test-header">
                  <span className="test-name">{result.test}</span>
                  <span className={`test-status status-${result.status}`}>
                    {result.status.toUpperCase()}
                    {result.duration && ` (${result.duration}ms)`}
                  </span>
                </div>
                <div className="test-message">{result.message}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )

  const renderPerformanceTests = () => (
    <div className="performance-tests">
      <div className="testing-section">
        <h3>⚡ Performance Tests</h3>
        <p>Detailed performance monitoring with timing metrics and analytics.</p>

        <div className="performance-controls">
          <div className="control-group">
            <label className="control-label">Network Condition:</label>
            <select
              value={selectedNetworkCondition?.name || 'No Throttling'}
              onChange={(e) => {
                const condition = networkConditions.find(c => c.name === e.target.value)
                setSelectedNetworkCondition(condition || null)
              }}
              className="form-select"
            >
              {networkConditions.map(condition => (
                <option key={condition.name} value={condition.name}>
                  {condition.name}
                </option>
              ))}
            </select>
          </div>

          <button
            className="action-button primary"
            onClick={runPerformanceTests}
            disabled={isRunningTests}
          >
            {isRunningTests ? '⚡ Testing...' : '⚡ Run Performance Tests'}
          </button>
        </div>
      </div>

      {performanceMetrics.length > 0 && (
        <>
          <PerformanceSummary
            metrics={performanceMetrics}
            loadTestResults={loadTestResults}
            baseline={currentBaseline || undefined}
          />

          <div className="testing-section">
            <h3>📈 Performance Analytics</h3>
            <PerformanceCharts
              metrics={performanceMetrics}
              loadTestResults={loadTestResults}
              baseline={currentBaseline || undefined}
              networkCondition={selectedNetworkCondition || undefined}
            />
          </div>
        </>
      )}

      {/* Memory Usage */}
      {memoryUsage && (
        <div className="testing-section">
          <h3>🧠 Memory Usage</h3>
          <div className="memory-stats">
            <div className="memory-bar">
              <div
                className="memory-fill"
                style={{ width: `${(memoryUsage.used / memoryUsage.limit) * 100}%` }}
              />
            </div>
            <div className="memory-details">
              <span>Used: {(memoryUsage.used / 1024 / 1024).toFixed(2)} MB</span>
              <span>Total: {(memoryUsage.total / 1024 / 1024).toFixed(2)} MB</span>
              <span>Limit: {(memoryUsage.limit / 1024 / 1024).toFixed(2)} MB</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )

  const renderLoadTests = () => (
    <div className="load-tests">
      <div className="testing-section">
        <h3>🔥 Load Testing</h3>
        <p>Stress test API endpoints with concurrent requests.</p>

        <div className="load-test-config">
          <div className="config-grid">
            <div className="config-field">
              <label>Concurrent Requests:</label>
              <input
                type="number"
                value={loadTestConfig.concurrentRequests}
                onChange={(e) => setLoadTestConfig(prev => ({
                  ...prev,
                  concurrentRequests: parseInt(e.target.value) || 1
                }))}
                min="1"
                max="100"
                className="form-input"
              />
            </div>

            <div className="config-field">
              <label>Total Requests:</label>
              <input
                type="number"
                value={loadTestConfig.totalRequests}
                onChange={(e) => setLoadTestConfig(prev => ({
                  ...prev,
                  totalRequests: parseInt(e.target.value) || 10
                }))}
                min="1"
                max="10000"
                className="form-input"
              />
            </div>

            <div className="config-field">
              <label>Ramp Up Time (sec):</label>
              <input
                type="number"
                value={loadTestConfig.rampUpTime}
                onChange={(e) => setLoadTestConfig(prev => ({
                  ...prev,
                  rampUpTime: parseInt(e.target.value) || 0
                }))}
                min="0"
                max="300"
                className="form-input"
              />
            </div>

            <div className="config-field">
              <label>Network Condition:</label>
              <select
                value={loadTestConfig.networkCondition?.name || 'No Throttling'}
                onChange={(e) => {
                  const condition = networkConditions.find(c => c.name === e.target.value)
                  setLoadTestConfig(prev => ({
                    ...prev,
                    networkCondition: condition?.name === 'No Throttling' ? undefined : condition
                  }))
                }}
                className="form-select"
              >
                {networkConditions.map(condition => (
                  <option key={condition.name} value={condition.name}>
                    {condition.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <button
            className="action-button primary"
            onClick={runLoadTest}
            disabled={isLoadTesting}
          >
            {isLoadTesting ? '🔥 Running Load Test...' : '🔥 Start Load Test'}
          </button>
        </div>
      </div>

      {loadTestResults.length > 0 && (
        <LoadTestSummary loadTestResults={loadTestResults} />
      )}
    </div>
  )

  const renderAnalytics = () => (
    <div className="analytics">
      <div className="testing-section">
        <h3>📊 Performance Analytics & History</h3>

        <div className="analytics-controls">
          <button
            className="action-button secondary"
            onClick={createBaseline}
            disabled={performanceMetrics.length === 0}
          >
            📏 Create Baseline
          </button>

          <div className="baseline-selector">
            <label>Compare with Baseline:</label>
            <select
              value={currentBaseline?.id || ''}
              onChange={(e) => {
                const baseline = performanceHistory.baselines.find(b => b.id === e.target.value)
                setCurrentBaseline(baseline || null)
              }}
              className="form-select"
            >
              <option value="">None</option>
              {performanceHistory.baselines.map(baseline => (
                <option key={baseline.id} value={baseline.id}>
                  {baseline.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="testing-section">
        <h3>📈 Historical Performance</h3>
        <div className="history-list">
          {performanceHistory.testRuns.map((run, index) => (
            <div key={run.id} className="history-item">
              <div className="history-header">
                <span className="history-name">{run.name}</span>
                <span className="history-timestamp">
                  {new Date(run.timestamp).toLocaleString()}
                </span>
              </div>
              <div className="history-stats">
                <span>{run.metrics.length} requests</span>
                <span>Avg: {run.metrics.reduce((sum, m) => sum + m.responseTime, 0) / run.metrics.length}ms</span>
                <span>Errors: {run.metrics.filter(m => m.isError).length}</span>
                {run.networkCondition && (
                  <span>Network: {run.networkCondition.name}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="testing-section">
        <h3>💾 Export & Import</h3>
        <div className="export-import-controls">
          <div className="export-section">
            <input
              type="text"
              value={exportFileName}
              onChange={(e) => setExportFileName(e.target.value)}
              placeholder="filename"
              className="form-input"
            />
            <button
              className="action-button secondary"
              onClick={exportPerformanceData}
            >
              <Download size={16} /> Export Data
            </button>
          </div>

          <div className="import-section">
            <textarea
              value={importData}
              onChange={(e) => setImportData(e.target.value)}
              placeholder="Paste JSON data to import..."
              className="form-textarea"
              rows={3}
            />
            <button
              className="action-button secondary"
              onClick={importPerformanceData}
              disabled={!importData.trim()}
            >
              <Upload size={16} /> Import Data
            </button>
          </div>
        </div>
      </div>
    </div>
  )

  return (
    <div className="enhanced-api-testing">
      {/* View Selector */}
      <div className="view-selector">
        <button
          className={`view-tab ${activeView === 'basic' ? 'active' : ''}`}
          onClick={() => setActiveView('basic')}
        >
          <Play size={16} /> Basic Tests
        </button>
        <button
          className={`view-tab ${activeView === 'performance' ? 'active' : ''}`}
          onClick={() => setActiveView('performance')}
        >
          <Zap size={16} /> Performance
        </button>
        <button
          className={`view-tab ${activeView === 'load-test' ? 'active' : ''}`}
          onClick={() => setActiveView('load-test')}
        >
          <BarChart3 size={16} /> Load Testing
        </button>
        <button
          className={`view-tab ${activeView === 'analytics' ? 'active' : ''}`}
          onClick={() => setActiveView('analytics')}
        >
          <Globe size={16} /> Analytics
        </button>
      </div>

      {/* Content */}
      <div className="tab-content">
        {activeView === 'basic' && renderBasicTests()}
        {activeView === 'performance' && renderPerformanceTests()}
        {activeView === 'load-test' && renderLoadTests()}
        {activeView === 'analytics' && renderAnalytics()}
      </div>
    </div>
  )
}