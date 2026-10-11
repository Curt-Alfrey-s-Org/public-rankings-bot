/**
 * Performance Metrics Tracker for TestCenter API Testing
 * Captures detailed timing metrics, response sizes, and performance data
 */

export interface PerformanceMetrics {
  // Basic timing metrics
  totalTime: number
  dnsTime?: number
  tcpTime?: number
  sslTime?: number
  ttfb: number // Time to First Byte
  responseTime: number

  // Response metrics
  responseSize: number
  responseSizeText: string
  bandwidth: number // bytes per second
  bandwidthText: string

  // Request details
  method: string
  url: string
  statusCode: number
  statusText: string

  // Metadata
  timestamp: number
  userAgent: string
  networkType?: string
  connectionType?: string

  // Error tracking
  error?: string
  isError: boolean
}

export interface NetworkCondition {
  name: string
  description: string
  latency: number // ms
  downloadThroughput: number // kbps
  uploadThroughput: number // kbps
  packetLoss?: number // percentage
}

export interface LoadTestConfig {
  concurrentRequests: number
  totalRequests: number
  rampUpTime: number // seconds
  duration: number // seconds
  networkCondition?: NetworkCondition
}

export interface LoadTestResult {
  config: LoadTestConfig
  startTime: number
  endTime: number
  totalDuration: number
  totalRequests: number
  successfulRequests: number
  failedRequests: number
  averageResponseTime: number
  minResponseTime: number
  maxResponseTime: number
  percentile95: number
  percentile99: number
  requestsPerSecond: number
  errorRate: number
  metrics: PerformanceMetrics[]
}

export interface PerformanceHistory {
  testRuns: PerformanceTestRun[]
  baselines: PerformanceBaseline[]
}

export interface PerformanceTestRun {
  id: string
  name: string
  timestamp: number
  metrics: PerformanceMetrics[]
  loadTestResults?: LoadTestResult[]
  networkCondition?: NetworkCondition
  notes?: string
}

export interface PerformanceBaseline {
  id: string
  name: string
  description: string
  metrics: PerformanceMetrics[]
  createdAt: number
  updatedAt: number
}

export class PerformanceMetricsTracker {
  private performanceObserver: PerformanceObserver | null = null
  private networkConditions: NetworkCondition[] = [
    {
      name: 'No Throttling',
      description: 'Normal network conditions',
      latency: 0,
      downloadThroughput: 0,
      uploadThroughput: 0
    },
    {
      name: 'Slow 3G',
      description: 'Slow 3G network (typical in rural areas)',
      latency: 400,
      downloadThroughput: 400,
      uploadThroughput: 400
    },
    {
      name: 'Fast 3G',
      description: 'Fast 3G network (typical in urban areas)',
      latency: 150,
      downloadThroughput: 1600,
      uploadThroughput: 768
    },
    {
      name: '4G',
      description: '4G LTE network',
      latency: 100,
      downloadThroughput: 10000,
      uploadThroughput: 5000
    },
    {
      name: '5G',
      description: '5G network',
      latency: 20,
      downloadThroughput: 100000,
      uploadThroughput: 50000
    },
    {
      name: 'WiFi',
      description: 'Typical WiFi network',
      latency: 10,
      downloadThroughput: 50000,
      uploadThroughput: 25000
    }
  ]

  constructor() {
    this.initializePerformanceObserver()
  }

  private initializePerformanceObserver() {
    if (typeof PerformanceObserver !== 'undefined') {
      try {
        this.performanceObserver = new PerformanceObserver((list) => {
          const entries = list.getEntries()
          entries.forEach(entry => {
            if (entry.entryType === 'navigation' || entry.entryType === 'resource') {
              this.processPerformanceEntry(entry)
            }
          })
        })

        // Observe navigation and resource timing
        this.performanceObserver.observe({
          entryTypes: ['navigation', 'resource', 'measure']
        })
      } catch (error) {
        console.warn('Performance Observer not supported:', error)
      }
    }
  }

  private processPerformanceEntry(entry: PerformanceEntry) {
    // Process performance entries for detailed timing analysis
    // This will be used by the metrics collection methods
  }

  /**
   * Capture detailed performance metrics for an API request
   */
  async captureMetrics(
    method: string,
    url: string,
    response: Response,
    startTime: number,
    networkCondition?: NetworkCondition
  ): Promise<PerformanceMetrics> {
    const endTime = performance.now()
    const totalTime = endTime - startTime

    // Get response size
    const responseClone = response.clone()
    let responseSize = 0
    try {
      const responseText = await responseClone.text()
      responseSize = new Blob([responseText]).size
    } catch (error) {
      console.warn('Could not calculate response size:', error)
    }

    // Calculate bandwidth (bytes per second)
    const bandwidth = totalTime > 0 ? (responseSize / totalTime) * 1000 : 0

    // Get network information
    const connection = (navigator as any).connection
    const networkType = connection?.effectiveType || 'unknown'
    const connectionType = connection?.type || 'unknown'

    const metrics: PerformanceMetrics = {
      totalTime,
      ttfb: totalTime, // Simplified - in a real implementation, we'd use Resource Timing API
      responseTime: totalTime,
      responseSize,
      responseSizeText: this.formatBytes(responseSize),
      bandwidth,
      bandwidthText: this.formatBandwidth(bandwidth),
      method,
      url,
      statusCode: response.status,
      statusText: response.statusText,
      timestamp: Date.now(),
      userAgent: navigator.userAgent,
      networkType,
      connectionType,
      isError: !response.ok,
      error: response.ok ? undefined : `${response.status} ${response.statusText}`
    }

    return metrics
  }

  /**
   * Run load test with specified configuration
   */
  async runLoadTest(
    config: LoadTestConfig,
    requestFn: () => Promise<Response>
  ): Promise<LoadTestResult> {
    const startTime = Date.now()
    const metrics: PerformanceMetrics[] = []
    let successfulRequests = 0
    let failedRequests = 0

    // Apply network throttling if specified
    if (config.networkCondition && config.networkCondition.name !== 'No Throttling') {
      await this.applyNetworkThrottling(config.networkCondition)
    }

    try {
      // Run concurrent requests
      const promises = []
      const responseTimes: number[] = []

      for (let i = 0; i < config.totalRequests; i++) {
        const requestStartTime = performance.now()

        const promise = requestFn()
          .then(async (response) => {
            const requestEndTime = performance.now()
            const responseTime = requestEndTime - requestStartTime
            responseTimes.push(responseTime)

            if (response.ok) {
              successfulRequests++
            } else {
              failedRequests++
            }

            // Capture detailed metrics
            const metric = await this.captureMetrics(
              'GET', // Would need to be parameterized
              'test-endpoint', // Would need to be parameterized
              response,
              requestStartTime,
              config.networkCondition
            )
            metrics.push(metric)

            return response
          })
          .catch((error) => {
            failedRequests++
            const requestEndTime = performance.now()
            const responseTime = requestEndTime - requestStartTime
            responseTimes.push(responseTime)

            // Create error metric
            const errorMetric: PerformanceMetrics = {
              totalTime: responseTime,
              ttfb: responseTime,
              responseTime,
              responseSize: 0,
              responseSizeText: '0 B',
              bandwidth: 0,
              bandwidthText: '0 B/s',
              method: 'GET',
              url: 'test-endpoint',
              statusCode: 0,
              statusText: 'Request Failed',
              timestamp: Date.now(),
              userAgent: navigator.userAgent,
              isError: true,
              error: error.message
            }
            metrics.push(errorMetric)

            return null
          })

        promises.push(promise)

        // Ramp up requests gradually if specified
        if (config.rampUpTime > 0 && i > 0) {
          const delay = (config.rampUpTime * 1000) / config.concurrentRequests
          await new Promise(resolve => setTimeout(resolve, delay))
        }
      }

      // Wait for all requests to complete
      await Promise.allSettled(promises)

    } finally {
      // Remove network throttling
      if (config.networkCondition && config.networkCondition.name !== 'No Throttling') {
        await this.removeNetworkThrottling()
      }
    }

    const endTime = Date.now()
    const totalDuration = endTime - startTime

    // Calculate statistics
    const responseTimes = metrics.map(m => m.responseTime).filter(t => !isNaN(t))
    responseTimes.sort((a, b) => a - b)

    const averageResponseTime = responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length
    const minResponseTime = Math.min(...responseTimes)
    const maxResponseTime = Math.max(...responseTimes)
    const percentile95 = this.calculatePercentile(responseTimes, 95)
    const percentile99 = this.calculatePercentile(responseTimes, 99)
    const requestsPerSecond = config.totalRequests / (totalDuration / 1000)
    const errorRate = (failedRequests / config.totalRequests) * 100

    return {
      config,
      startTime,
      endTime,
      totalDuration,
      totalRequests: config.totalRequests,
      successfulRequests,
      failedRequests,
      averageResponseTime: averageResponseTime || 0,
      minResponseTime: minResponseTime || 0,
      maxResponseTime: maxResponseTime || 0,
      percentile95: percentile95 || 0,
      percentile99: percentile99 || 0,
      requestsPerSecond,
      errorRate,
      metrics
    }
  }

  /**
   * Get available network conditions for simulation
   */
  getNetworkConditions(): NetworkCondition[] {
    return this.networkConditions
  }

  /**
   * Apply network throttling (simplified - in practice would use browser dev tools protocol)
   */
  private async applyNetworkThrottling(condition: NetworkCondition): Promise<void> {
    // This is a simplified implementation
    // In a real application, you would use Chrome DevTools Protocol or similar
    // to actually throttle network conditions

    if ('serviceWorker' in navigator && condition.name !== 'No Throttling') {
      // Could implement network throttling via service worker
      console.log(`Applying network throttling: ${condition.name}`)
    }
  }

  /**
   * Remove network throttling
   */
  private async removeNetworkThrottling(): Promise<void> {
    // Remove any applied throttling
    console.log('Removing network throttling')
  }

  /**
   * Get memory usage information
   */
  getMemoryUsage(): { used: number; total: number; limit: number } | null {
    if ('memory' in performance) {
      const memory = (performance as any).memory
      return {
        used: memory.usedJSHeapSize,
        total: memory.totalJSHeapSize,
        limit: memory.jsHeapSizeLimit
      }
    }
    return null
  }

  /**
   * Format bytes to human readable format
   */
  private formatBytes(bytes: number): string {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  /**
   * Format bandwidth to human readable format
   */
  private formatBandwidth(bytesPerSecond: number): string {
    return this.formatBytes(bytesPerSecond) + '/s'
  }

  /**
   * Calculate percentile from sorted array
   */
  private calculatePercentile(sortedArray: number[], percentile: number): number {
    if (sortedArray.length === 0) return 0
    const index = (percentile / 100) * (sortedArray.length - 1)
    const lower = Math.floor(index)
    const upper = Math.ceil(index)
    const weight = index % 1

    if (upper >= sortedArray.length) return sortedArray[sortedArray.length - 1]
    return sortedArray[lower] * (1 - weight) + sortedArray[upper] * weight
  }

  /**
   * Export performance data
   */
  exportData(data: PerformanceHistory): string {
    return JSON.stringify(data, null, 2)
  }

  /**
   * Import performance data
   */
  importData(jsonData: string): PerformanceHistory {
    return JSON.parse(jsonData)
  }

  /**
   * Create performance baseline from metrics
   */
  createBaseline(name: string, description: string, metrics: PerformanceMetrics[]): PerformanceBaseline {
    return {
      id: `baseline_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      name,
      description,
      metrics: [...metrics],
      createdAt: Date.now(),
      updatedAt: Date.now()
    }
  }

  /**
   * Compare metrics against baseline
   */
  compareAgainstBaseline(metrics: PerformanceMetrics[], baseline: PerformanceBaseline): {
    averageResponseTime: { current: number; baseline: number; difference: number; percentage: number }
    errorRate: { current: number; baseline: number; difference: number; percentage: number }
    bandwidth: { current: number; baseline: number; difference: number; percentage: number }
  } {
    const currentAvgResponseTime = metrics.reduce((sum, m) => sum + m.responseTime, 0) / metrics.length
    const currentErrorRate = (metrics.filter(m => m.isError).length / metrics.length) * 100
    const currentAvgBandwidth = metrics.reduce((sum, m) => sum + m.bandwidth, 0) / metrics.length

    const baselineAvgResponseTime = baseline.metrics.reduce((sum, m) => sum + m.responseTime, 0) / baseline.metrics.length
    const baselineErrorRate = (baseline.metrics.filter(m => m.isError).length / baseline.metrics.length) * 100
    const baselineAvgBandwidth = baseline.metrics.reduce((sum, m) => sum + m.bandwidth, 0) / baseline.metrics.length

    return {
      averageResponseTime: {
        current: currentAvgResponseTime,
        baseline: baselineAvgResponseTime,
        difference: currentAvgResponseTime - baselineAvgResponseTime,
        percentage: ((currentAvgResponseTime - baselineAvgResponseTime) / baselineAvgResponseTime) * 100
      },
      errorRate: {
        current: currentErrorRate,
        baseline: baselineErrorRate,
        difference: currentErrorRate - baselineErrorRate,
        percentage: ((currentErrorRate - baselineErrorRate) / Math.max(baselineErrorRate, 1)) * 100
      },
      bandwidth: {
        current: currentAvgBandwidth,
        baseline: baselineAvgBandwidth,
        difference: currentAvgBandwidth - baselineAvgBandwidth,
        percentage: ((currentAvgBandwidth - baselineAvgBandwidth) / Math.max(baselineAvgBandwidth, 1)) * 100
      }
    }
  }
}

// Create singleton instance
export const performanceMetricsTracker = new PerformanceMetricsTracker()

// Export convenience functions
export const performanceTracker = {
  captureMetrics: performanceMetricsTracker.captureMetrics.bind(performanceMetricsTracker),
  runLoadTest: performanceMetricsTracker.runLoadTest.bind(performanceMetricsTracker),
  getNetworkConditions: performanceMetricsTracker.getNetworkConditions.bind(performanceMetricsTracker),
  getMemoryUsage: performanceMetricsTracker.getMemoryUsage.bind(performanceMetricsTracker),
  exportData: performanceMetricsTracker.exportData.bind(performanceMetricsTracker),
  importData: performanceMetricsTracker.importData.bind(performanceMetricsTracker),
  createBaseline: performanceMetricsTracker.createBaseline.bind(performanceMetricsTracker),
  compareAgainstBaseline: performanceMetricsTracker.compareAgainstBaseline.bind(performanceMetricsTracker)
}