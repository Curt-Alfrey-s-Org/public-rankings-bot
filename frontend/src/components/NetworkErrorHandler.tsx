/**
 * Backward-compatible wrapper around the unified connection status banner.
 */
import ConnectionStatus from '@/components/ConnectionStatus'

export default function NetworkErrorHandler() {
  return <ConnectionStatus />
}
