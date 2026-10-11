/**
 * WebSocket live-updates hook. Connects to /ws/live-updates.
 *
 * Error path: on close/error, exponential backoff reconnect (max 5 attempts).
 * ConnectionStatus uses isConnected to show banner; React Query polling continues when WS is down.
 * See docs/DEBUG_CONSOLE_ERRORS.md for WebSocket 1006, API-not-on-8003, etc.
 */
import { useEffect, useState } from 'react'

export interface LiveUpdateMessage {
  type: 'live_update'
  event: string
  data: any
  timestamp: string
}

export interface TournamentUpdateData {
  tournament_id: string
  [key: string]: any
}

export interface MatchScoreUpdateData {
  match_id: string
  tournament_id: string
  operator_score?: number
  player2_score?: number
  status?: string
  operator_id?: string
  player2_id?: string
  winner_id?: string
}

export interface PlayerRegistrationData {
  tournament_id: string
  player_name: string
}

// Global WebSocket connection state - singleton pattern
let globalWebSocket: WebSocket | null = null
let globalIsConnected = false
let globalLastMessage: LiveUpdateMessage | null = null
const connectionCallbacks = new Set<(isConnected: boolean) => void>()
const messageCallbacks = new Set<(message: LiveUpdateMessage) => void>()
let cleanupTimeout: NodeJS.Timeout | null = null

// Connection management
let reconnectAttempts = 0
const MAX_RECONNECT_ATTEMPTS = 5
const INITIAL_RECONNECT_DELAY = 1000 // 1 second
const MAX_RECONNECT_DELAY = 30000 // 30 seconds
let reconnectTimeout: NodeJS.Timeout | null = null
let isReconnecting = false
const wsDebugEnabled = import.meta.env.DEV || import.meta.env.VITE_DEBUG_WEBSOCKET === 'true'

function logWebSocketDebug(...args: unknown[]) {
  if (wsDebugEnabled) {
    console.log(...args)
  }
}

function notifyConnectionCallbacks(isConnected: boolean) {
  globalIsConnected = isConnected
  connectionCallbacks.forEach(callback => callback(isConnected))
}

function notifyMessageCallbacks(message: LiveUpdateMessage) {
  globalLastMessage = message
  messageCallbacks.forEach(callback => callback(message))
}

function calculateReconnectDelay(attempt: number): number {
  // Exponential backoff with jitter
  const baseDelay = INITIAL_RECONNECT_DELAY * Math.pow(2, attempt)
  const jitter = Math.random() * 1000 // Add up to 1 second of randomness
  return Math.min(baseDelay + jitter, MAX_RECONNECT_DELAY)
}

function cleanupWebSocket() {
  if (globalWebSocket) {
    try {
      globalWebSocket.close(1000, 'Component cleanup')
    } catch (error) {
      console.warn('Error closing WebSocket during cleanup:', error)
    }
    globalWebSocket = null
  }
  globalIsConnected = false
  notifyConnectionCallbacks(false)

  if (reconnectTimeout) {
    clearTimeout(reconnectTimeout)
    reconnectTimeout = null
  }
  isReconnecting = false
  reconnectAttempts = 0
}

function handleWebSocketError(error: Event, context: string) {
  console.error(`WebSocket ${context} error:`, error)

  // Log additional context for debugging
  if (globalWebSocket) {
    console.error('WebSocket readyState:', globalWebSocket.readyState)
    console.error('WebSocket URL:', globalWebSocket.url)
  }

  globalIsConnected = false
  notifyConnectionCallbacks(false)

  // Attempt reconnection if not already reconnecting
  if (!isReconnecting && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
    scheduleReconnect()
  } else if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
    console.error('Max WebSocket reconnection attempts reached. Giving up.')
  }
}

function scheduleReconnect() {
  if (isReconnecting || reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
    return
  }

  isReconnecting = true
  const delay = calculateReconnectDelay(reconnectAttempts)

  logWebSocketDebug(`Scheduling WebSocket reconnection attempt ${reconnectAttempts + 1}/${MAX_RECONNECT_ATTEMPTS} in ${delay}ms`)

  reconnectTimeout = setTimeout(() => {
    reconnectAttempts++
    isReconnecting = false
    logWebSocketDebug(`Attempting WebSocket reconnection ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS}`)
    initializeGlobalWebSocket()
  }, delay)
}

function initializeGlobalWebSocket() {
  // Cancel any pending cleanup since we have a new subscriber
  if (cleanupTimeout) {
    clearTimeout(cleanupTimeout)
    cleanupTimeout = null
    logWebSocketDebug('Cancelled pending cleanup - new subscriber added')
  }

  if (globalWebSocket) {
    return // Already initialized
  }

  logWebSocketDebug('Initializing global WebSocket connection')

  const connect = () => {
    if (globalWebSocket?.readyState === WebSocket.OPEN) {
      return
    }

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      // Use relative WebSocket URL (proxied by Vite in development)
      const wsUrl = `${protocol}//${window.location.host}/ws`

      // Get JWT token from localStorage (try multiple keys for compatibility)
      let token = localStorage.getItem('auth_token') ||
                  localStorage.getItem('access_token')

      // Try to get from rankings_bot_auth object
      if (!token) {
        try {
          const authData = localStorage.getItem('rankings_bot_auth')
          if (authData) {
            const parsed = JSON.parse(authData)
            token = parsed?.token
          }
        } catch (error) {
          console.warn('Failed to parse rankings_bot_auth from localStorage:', error)
        }
      }

      // Add token as query parameter if available
      const finalUrl = token ? `${wsUrl}?token=${encodeURIComponent(token)}` : wsUrl

      logWebSocketDebug('Connecting to WebSocket:', finalUrl.replace(/token=[^&]*/, 'token=[REDACTED]'))

      globalWebSocket = new WebSocket(finalUrl)

      // Set connection timeout
      const connectionTimeout = setTimeout(() => {
        if (globalWebSocket && globalWebSocket.readyState === WebSocket.CONNECTING) {
          console.warn('WebSocket connection timeout - closing')
          try {
            // Use 1000 (normal) or 4xxx; 1006 is reserved and must not be passed to close()
            globalWebSocket.close(1000, 'Connection timeout')
          } catch (error) {
            console.warn('Error closing timed out connection:', error)
          }
        }
      }, 10000) // 10 second timeout

      globalWebSocket.onopen = (event) => {
        clearTimeout(connectionTimeout)
        reconnectAttempts = 0 // Reset reconnection attempts on successful connection
        isReconnecting = false
        notifyConnectionCallbacks(true)
        logWebSocketDebug('WebSocket connected for live updates')
      }

      globalWebSocket.onmessage = (event) => {
        try {
          const message: LiveUpdateMessage = JSON.parse(event.data)
          if (message.type === 'live_update') {
            notifyMessageCallbacks(message)
          } else if (message.type === 'ping') {
            // Respond to ping with pong to keep connection alive
            if (globalWebSocket.readyState === WebSocket.OPEN) {
              globalWebSocket.send(JSON.stringify({ type: 'pong', timestamp: Date.now() }))
            }
          } else {
            console.warn('Received unknown message type:', message.type, message)
          }
        } catch (parseError) {
          console.error('Failed to parse WebSocket message:', parseError, 'Raw data:', event.data)
          // Don't close connection for parse errors, just log them
        }
      }

      globalWebSocket.onclose = (event) => {
        clearTimeout(connectionTimeout)
        const wasConnected = globalIsConnected
        globalIsConnected = false
        notifyConnectionCallbacks(false)

        // Log close details
        const closeReason = event.reason || 'No reason provided'
        logWebSocketDebug(`WebSocket disconnected (code: ${event.code}, reason: ${closeReason})`)

        // Cancel any pending cleanup since we're handling the close
        if (cleanupTimeout) {
          clearTimeout(cleanupTimeout)
          cleanupTimeout = null
        }

        // Attempt reconnection for unexpected disconnects
        const isCleanClose = event.code === 1000 || event.code === 1001
        if (!isCleanClose && wasConnected && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
          logWebSocketDebug('Unexpected WebSocket disconnection - scheduling reconnection')
          scheduleReconnect()
        } else if (isCleanClose) {
          logWebSocketDebug('WebSocket closed cleanly')
        } else {
          console.warn('WebSocket closed with error code, not attempting reconnection')
        }
      }

      globalWebSocket.onerror = (error) => {
        clearTimeout(connectionTimeout)
        handleWebSocketError(error, 'connection')
      }

    } catch (error) {
      console.error('Failed to create WebSocket connection:', error)
      handleWebSocketError(error as Event, 'creation')
    }
  }

  connect()
}

function cleanupGlobalWebSocket() {
  logWebSocketDebug('Cleaning up global WebSocket')
  cleanupWebSocket()
  globalLastMessage = null
  connectionCallbacks.clear()
  messageCallbacks.clear()
  if (cleanupTimeout) {
    clearTimeout(cleanupTimeout)
    cleanupTimeout = null
  }
}

function scheduleCleanup() {
  // Delay cleanup by 100ms to allow for rapid mount/unmount cycles
  if (cleanupTimeout) {
    clearTimeout(cleanupTimeout)
  }
  logWebSocketDebug('Scheduling WebSocket cleanup in 100ms')
  cleanupTimeout = setTimeout(() => {
    if (connectionCallbacks.size === 0 && messageCallbacks.size === 0) {
      cleanupGlobalWebSocket()
    } else {
      logWebSocketDebug('Cleanup cancelled - subscribers still exist')
    }
  }, 100)
}

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(globalIsConnected)
  const [lastMessage, setLastMessage] = useState<LiveUpdateMessage | null>(globalLastMessage)

  useEffect(() => {
    // Register callbacks
    const handleConnectionChange = (connected: boolean) => setIsConnected(connected)
    const handleMessage = (message: LiveUpdateMessage) => setLastMessage(message)

    connectionCallbacks.add(handleConnectionChange)
    messageCallbacks.add(handleMessage)

    // Initialize global WebSocket if not already done
    initializeGlobalWebSocket()

    // Cleanup function
    return () => {
      connectionCallbacks.delete(handleConnectionChange)
      messageCallbacks.delete(handleMessage)

      // Schedule cleanup with delay to prevent rapid mount/unmount issues
      scheduleCleanup()
    }
  }, [])

  return {
    isConnected,
    lastMessage
  }
}