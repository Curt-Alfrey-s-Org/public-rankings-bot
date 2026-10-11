/**
 * Alfa Dashboard Module - Router Integration
 * 
 * Add these routes to your main App.tsx or router configuration:
 */

import { lazy, Suspense } from 'react'
import PageLoader from '@/components/PageLoader'
import AlfaDashboardLayout from '@/layouts/AlfaDashboardLayout'

// Lazy load dashboard pages
const AlfaDashboard = lazy(() => import('@/pages/AlfaDashboard'))
const AlfaPlayerRatings = lazy(() => import('@/pages/AlfaPlayerRatings'))
const AlfaAnomalyAlerts = lazy(() => import('@/pages/AlfaAnomalyAlerts'))
const AlfaPredictionExplain = lazy(() => import('@/pages/AlfaPredictionExplain'))
const AlfaABTestResults = lazy(() => import('@/pages/AlfaABTestResults'))
const AlfaSystemStatus = lazy(() => import('@/pages/AlfaSystemStatus'))
const AlfaRatingAdjustments = lazy(() => import('@/pages/AlfaRatingAdjustments'))

/**
 * Router Configuration Example
 * 
 * Add to your main router (e.g., in App.tsx):
 * 
 * <Routes>
 *   <Route element={<AlfaDashboardLayout />}>
 *     <Route index element={<AlfaDashboard />} />
 *     <Route path="players" element={<AlfaPlayerRatings />} />
 *     <Route path="anomalies" element={<AlfaAnomalyAlerts />} />
 *     <Route path="predictions" element={<AlfaPredictionExplain />} />
 *     <Route path="ab-tests" element={<AlfaABTestResults />} />
 *     <Route path="health" element={<AlfaSystemStatus />} />
 *     <Route path="admin" element={<AlfaRatingAdjustments />} />
 *   </Route>
 * </Routes>
 * 
 * Or with path grouping (recommended):
 * 
 * <Routes>
 *   <Route path="/alfa" element={<AlfaDashboardLayout />}>
 *     <Route index element={<AlfaDashboard />} />
 *     <Route path="dashboard" element={<AlfaDashboard />} />
 *     <Route path="players" element={<AlfaPlayerRatings />} />
 *     <Route path="anomalies" element={<AlfaAnomalyAlerts />} />
 *     <Route path="predictions" element={<AlfaPredictionExplain />} />
 *     <Route path="ab-tests" element={<AlfaABTestResults />} />
 *     <Route path="health" element={<AlfaSystemStatus />} />
 *     <Route path="admin" element={<AlfaRatingAdjustments />} />
 *   </Route>
 * </Routes>
 */

// Suspense wrapper for lazy loading
export const withAlfaSuspense = (Component: React.ComponentType<any>) => (
  <Suspense fallback={<PageLoader />}>
    <Component />
  </Suspense>
)

// Export layout and page components
export {
  AlfaDashboardLayout,
  AlfaDashboard,
  AlfaPlayerRatings,
  AlfaAnomalyAlerts,
  AlfaPredictionExplain,
  AlfaABTestResults,
  AlfaSystemStatus,
  AlfaRatingAdjustments,
}

// Component exports for modular usage
export { AlfaMetricCard } from '@/components/AlfaMetricCard'
export { AlfaRatingChart } from '@/components/AlfaRatingChart'
export { AlfaAnomalyFlag } from '@/components/AlfaAnomalyFlag'
export { AlfaFactorBreakdown } from '@/components/AlfaFactorBreakdown'
export { AlfaComparisonCard } from '@/components/AlfaComparisonCard'
export { AlfaPlayerComparison } from '@/components/AlfaPlayerComparison'

// Hook exports for custom implementations
export {
  useAlfaPlayerRatings,
  useAlfaPlayerDetail,
  useAlfaPlayerHistory,
  useAlfaPlayerComparison,
  useAlfaAnomalies,
  useAlfaReviewAnomaly,
  useAlfaAnomalyStatistics,
  useAlfaPredictionExplain,
  useAlfaPredictMatch,
  useAlfaABTestResults,
  useAlfaSystemStatus,
  useAlfaSystemHealth,
  useAlfaDashboardStats,
  useAlfaRatingAdjustments,
  useAlfaSubmitAdjustment,
  useAlfaApproveAdjustment,
  useAlfaRejectAdjustment,
  useAlfaExportRatings,
  useAlfaImportAdjustments,
  useAlfaSendNotifications,
  useAlfaExportPredictionPDF,
} from '@/hooks/useAlfaRatings'

// Type exports for TypeScript projects
export type {
  AlfaPlayer,
  RatingHistoryPoint,
  AnomalyFlag,
  AnomalyAlert,
  PredictionExplanation,
  ABTestResults,
  SystemStatus,
  PlayerComparison,
  RatingAdjustment,
  DashboardStats,
} from '@/types/alfa.types'

// API client export
export { alfaDashboardApi } from '@/api/alfaDashboard'
