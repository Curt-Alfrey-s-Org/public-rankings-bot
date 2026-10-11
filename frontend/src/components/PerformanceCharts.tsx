/**
 * Performance Charts and Visualization Components
 * Provides visual representations of API performance data
 */

import React from 'react'
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts'
import { PerformanceMetrics, LoadTestResult, PerformanceBaseline, NetworkCondition } from '@/lib/performanceMetricsTracker'

interface PerformanceChartsProps {
  metrics: PerformanceMetrics[]
  loadTestResults?: LoadTestResult[]
  baseline?: PerformanceBaseline
  networkCondition?: NetworkCondition
}

export default function PerformanceCharts({
  metrics,
  loadTestResults,
  baseline,
  networkCondition
}: PerformanceChartsProps) {
  // Prepare data for response time chart
  const responseTimeData = metrics.map((metric, index) => ({
    request: index + 1,
    responseTime: metric.responseTime,
    ttfb: metric.ttfb,
    totalTime: metric.totalTime,
    status: metric.statusCode,
    isError: metric.isError
  }))

  // Prepare data for bandwidth chart
  const bandwidthData = metrics.map((metric, index) => ({
    request: index + 1,
    bandwidth: metric.bandwidth / 1024, // Convert to KB/s
    responseSize: metric.responseSize / 1024, // Convert to KB
    status: metric.statusCode
  }))

  // Prepare data for error rate over time
  const errorRateData = metrics.reduce((acc, metric, index) => {
    const existingEntry = acc.find(entry => entry.timestamp === metric.timestamp)
    if (existingEntry) {
      existingEntry.totalRequests++
      if (metric.isError) existingEntry.errors++
    } else {
      acc.push({
        timestamp: metric.timestamp,
        request: index + 1,
        totalRequests: 1,
        errors: metric.isError ? 1 : 0,
        errorRate: 0
      })
    }
    return acc
  }, [] as any[]).map(entry => ({
    ...entry,
    errorRate: (entry.errors / entry.totalRequests) * 100
  }))

  // Prepare data for load test results
  const loadTestData = loadTestResults?.map(result => ({
    test: `Load Test ${loadTestResults.indexOf(result) + 1}`,
    avgResponseTime: result.averageResponseTime,
    requestsPerSecond: result.requestsPerSecond,
    errorRate: result.errorRate,
    percentile95: result.percentile95,
    percentile99: result.percentile99
  })) || []

  // Status code distribution for pie chart
  const statusCodeData = metrics.reduce((acc, metric) => {
    const status = metric.statusCode.toString()
    const existing = acc.find(item => item.status === status)
    if (existing) {
      existing.count++
    } else {
      acc.push({
        status,
        count: 1,
        fill: getStatusColor(metric.statusCode)
      })
    }
    return acc
  }, [] as any[])

  return (
    <div className="performance-charts space-y-6">
      {/* Response Time Trends */}
      <div className="chart-container">
        <h3 className="chart-title">Response Time Trends</h3>
        <ResponsiveContainer width="100%" height={300} minWidth={200} minHeight={300}>
          <LineChart data={responseTimeData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="request" />
            <YAxis label={{ value: 'Time (ms)', angle: -90, position: 'insideLeft' }} />
            <Tooltip
              formatter={(value: any, name: string) => [
                `${value.toFixed(2)} ms`,
                name === 'responseTime' ? 'Response Time' :
                name === 'ttfb' ? 'Time to First Byte' :
                name === 'totalTime' ? 'Total Time' : name
              ]}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="responseTime"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ r: 3 }}
              name="Response Time"
            />
            <Line
              type="monotone"
              dataKey="ttfb"
              stroke="#10b981"
              strokeWidth={2}
              dot={{ r: 3 }}
              name="Time to First Byte"
            />
            {baseline && (
              <Line
                type="monotone"
                dataKey={() => baseline.metrics.reduce((sum, m) => sum + m.responseTime, 0) / baseline.metrics.length}
                stroke="#ef4444"
                strokeWidth={2}
                strokeDasharray="5 5"
                name="Baseline Avg"
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Bandwidth and Response Size */}
      <div className="chart-container">
        <h3 className="chart-title">Bandwidth & Response Size</h3>
        <ResponsiveContainer width="100%" height={300} minWidth={200} minHeight={300}>
          <AreaChart data={bandwidthData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="request" />
            <YAxis yAxisId="bandwidth" orientation="left" label={{ value: 'Bandwidth (KB/s)', angle: -90, position: 'insideLeft' }} />
            <YAxis yAxisId="size" orientation="right" label={{ value: 'Response Size (KB)', angle: 90, position: 'insideRight' }} />
            <Tooltip
              formatter={(value: any, name: string) => [
                name === 'bandwidth' ? `${value.toFixed(2)} KB/s` : `${value.toFixed(2)} KB`,
                name === 'bandwidth' ? 'Bandwidth' : 'Response Size'
              ]}
            />
            <Legend />
            <Area
              yAxisId="bandwidth"
              type="monotone"
              dataKey="bandwidth"
              stackId="1"
              stroke="#8b5cf6"
              fill="#8b5cf6"
              fillOpacity={0.6}
              name="bandwidth"
            />
            <Area
              yAxisId="size"
              type="monotone"
              dataKey="responseSize"
              stackId="2"
              stroke="#f59e0b"
              fill="#f59e0b"
              fillOpacity={0.6}
              name="responseSize"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Error Rate Over Time */}
      <div className="chart-container">
        <h3 className="chart-title">Error Rate Over Time</h3>
        <ResponsiveContainer width="100%" height={300} minWidth={200} minHeight={300}>
          <LineChart data={errorRateData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="request" />
            <YAxis label={{ value: 'Error Rate (%)', angle: -90, position: 'insideLeft' }} />
            <Tooltip formatter={(value: any) => [`${value.toFixed(2)}%`, 'Error Rate']} />
            <Legend />
            <Line
              type="monotone"
              dataKey="errorRate"
              stroke="#ef4444"
              strokeWidth={2}
              dot={{ r: 4 }}
              name="Error Rate"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Load Test Performance (if available) */}
      {loadTestResults && loadTestResults.length > 0 && (
        <div className="chart-container">
          <h3 className="chart-title">Load Test Performance</h3>
          <ResponsiveContainer width="100%" height={300} minWidth={200} minHeight={300}>
            <BarChart data={loadTestData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="test" />
              <YAxis yAxisId="response" orientation="left" label={{ value: 'Response Time (ms)', angle: -90, position: 'insideLeft' }} />
              <YAxis yAxisId="throughput" orientation="right" label={{ value: 'Requests/sec', angle: 90, position: 'insideRight' }} />
              <Tooltip />
              <Legend />
              <Bar yAxisId="response" dataKey="avgResponseTime" fill="#3b82f6" name="Avg Response Time" />
              <Bar yAxisId="response" dataKey="percentile95" fill="#10b981" name="95th Percentile" />
              <Bar yAxisId="throughput" dataKey="requestsPerSecond" fill="#f59e0b" name="Requests/sec" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Status Code Distribution */}
      <div className="chart-container">
        <h3 className="chart-title">Status Code Distribution</h3>
        <ResponsiveContainer width="100%" height={300} minWidth={200} minHeight={300}>
          <PieChart>
            <Pie
              data={statusCodeData}
              cx="50%"
              cy="50%"
              labelLine={false}
              label={({ status, count, percent }) => `${status}: ${count} (${(percent * 100).toFixed(0)}%)`}
              outerRadius={80}
              fill="#8884d8"
              dataKey="count"
            >
              {statusCodeData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.fill} />
              ))}
            </Pie>
            <Tooltip />
            </PieChart>
          </ResponsiveContainer>
      </div>

      {/* Network Condition Info */}
      {networkCondition && (
        <div className="network-condition-info">
          <h4>Network Condition: {networkCondition.name}</h4>
          <div className="condition-details">
            <span>Latency: {networkCondition.latency}ms</span>
            <span>Download: {networkCondition.downloadThroughput} kbps</span>
            <span>Upload: {networkCondition.uploadThroughput} kbps</span>
          </div>
        </div>
      )}
    </div>
  )
}

// Utility function to get status code colors
function getStatusColor(statusCode: number): string {
  if (statusCode >= 200 && statusCode < 300) return '#10b981' // Green for success
  if (statusCode >= 300 && statusCode < 400) return '#3b82f6' // Blue for redirects
  if (statusCode >= 400 && statusCode < 500) return '#f59e0b' // Yellow for client errors
  if (statusCode >= 500) return '#ef4444' // Red for server errors
  return '#6b7280' // Gray for unknown
}

// Performance Summary Component
interface PerformanceSummaryProps {
  metrics: PerformanceMetrics[]
  loadTestResults?: LoadTestResult[]
  baseline?: PerformanceBaseline
}

export function PerformanceSummary({ metrics, loadTestResults, baseline }: PerformanceSummaryProps) {
  const avgResponseTime = metrics.reduce((sum, m) => sum + m.responseTime, 0) / metrics.length
  const avgBandwidth = metrics.reduce((sum, m) => sum + m.bandwidth, 0) / metrics.length
  const errorRate = (metrics.filter(m => m.isError).length / metrics.length) * 100
  const totalRequests = metrics.length
  const successfulRequests = metrics.filter(m => !m.isError).length

  return (
    <div className="performance-summary grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <div className="summary-card">
        <div className="summary-value">{avgResponseTime.toFixed(2)}ms</div>
        <div className="summary-label">Avg Response Time</div>
        {baseline && (
          <div className="summary-comparison">
            vs Baseline: {((avgResponseTime - (baseline.metrics.reduce((sum, m) => sum + m.responseTime, 0) / baseline.metrics.length)) /
              ((baseline.metrics.reduce((sum, m) => sum + m.responseTime, 0) / baseline.metrics.length)) * 100).toFixed(1)}%
          </div>
        )}
      </div>

      <div className="summary-card">
        <div className="summary-value">{(avgBandwidth / 1024).toFixed(2)} KB/s</div>
        <div className="summary-label">Avg Bandwidth</div>
      </div>

      <div className="summary-card">
        <div className="summary-value">{errorRate.toFixed(2)}%</div>
        <div className="summary-label">Error Rate</div>
        {baseline && (
          <div className="summary-comparison">
            vs Baseline: {((errorRate - ((baseline.metrics.filter(m => m.isError).length / baseline.metrics.length) * 100)) /
              (((baseline.metrics.filter(m => m.isError).length / baseline.metrics.length) * 100) || 1) * 100).toFixed(1)}%
          </div>
        )}
      </div>

      <div className="summary-card">
        <div className="summary-value">{successfulRequests}/{totalRequests}</div>
        <div className="summary-label">Success Rate</div>
        <div className="summary-comparison">
          {((successfulRequests / totalRequests) * 100).toFixed(1)}% success
        </div>
      </div>
    </div>
  )
}

// Load Test Summary Component
interface LoadTestSummaryProps {
  loadTestResults: LoadTestResult[]
}

export function LoadTestSummary({ loadTestResults }: LoadTestSummaryProps) {
  if (loadTestResults.length === 0) return null

  const latestResult = loadTestResults[loadTestResults.length - 1]

  return (
    <div className="load-test-summary">
      <h3>Load Test Results</h3>
      <div className="summary-grid">
        <div className="summary-item">
          <span className="summary-label">Concurrent Requests:</span>
          <span className="summary-value">{latestResult.config.concurrentRequests}</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Total Requests:</span>
          <span className="summary-value">{latestResult.totalRequests}</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Requests/sec:</span>
          <span className="summary-value">{latestResult.requestsPerSecond.toFixed(2)}</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Avg Response Time:</span>
          <span className="summary-value">{latestResult.averageResponseTime.toFixed(2)}ms</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">95th Percentile:</span>
          <span className="summary-value">{latestResult.percentile95.toFixed(2)}ms</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">99th Percentile:</span>
          <span className="summary-value">{latestResult.percentile99.toFixed(2)}ms</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Error Rate:</span>
          <span className="summary-value">{latestResult.errorRate.toFixed(2)}%</span>
        </div>
        <div className="summary-item">
          <span className="summary-label">Duration:</span>
          <span className="summary-value">{(latestResult.totalDuration / 1000).toFixed(2)}s</span>
        </div>
      </div>
    </div>
  )
}