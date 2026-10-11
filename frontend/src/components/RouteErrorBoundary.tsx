/**
 * Route-level error boundary.
 * Wraps route content so a crash in one page doesn't take down the whole app.
 * Provides "Try again" and "Go to Dashboard" recovery options.
 */

import { type ReactNode } from 'react'
import ErrorBoundary from '@/components/ErrorBoundary'
import PageErrorFallback from '@/components/PageErrorFallback'
import { useAuth } from '@/contexts/AuthContext'

interface RouteErrorBoundaryProps {
  children: ReactNode
}

export default function RouteErrorBoundary({ children }: RouteErrorBoundaryProps) {
  const { isAdmin } = useAuth()
  return (
    <ErrorBoundary fallback={<PageErrorFallback />} showDetails={isAdmin}>
      {children}
    </ErrorBoundary>
  )
}
