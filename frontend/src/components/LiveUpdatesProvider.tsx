import { ReactNode } from 'react'
import { useLiveUpdates } from '@/hooks/useLiveUpdates'

interface LiveUpdatesProviderProps {
  children: ReactNode
}

/**
 * Provider component that enables live updates throughout the application
 * This component doesn't render anything but initializes the live update system
 */
export default function LiveUpdatesProvider({ children }: LiveUpdatesProviderProps) {
  // Initialize live updates for the entire application
  useLiveUpdates()

  return <>{children}</>
}