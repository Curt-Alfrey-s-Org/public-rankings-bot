/**
 * Route-aware Suspense fallback.
 * Shows a skeleton that matches the target page layout for better perceived performance.
 */

import { useLocation } from 'react-router-dom'
import {
  RankingsSkeleton,
  HomeSkeleton,
  DashboardSkeleton,
  PageSkeleton,
} from '@/components/skeletons'

export default function RouteSuspenseFallback() {
  const { pathname } = useLocation()

  if (pathname.includes('/rankings')) return <RankingsSkeleton />
  if (pathname.includes('/home') || pathname === '/') return <HomeSkeleton />
  if (pathname.includes('/dashboard')) return <DashboardSkeleton />

  return <PageSkeleton />
}
