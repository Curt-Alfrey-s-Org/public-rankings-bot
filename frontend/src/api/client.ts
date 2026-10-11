/**
 * API Client for FastAPI Backend
 */

import axios from 'axios'

/** Opt out of global error toasts (caller handles UX), e.g. public registration form. */
declare module 'axios' {
  export interface InternalAxiosRequestConfig {
    skipGlobalErrorUI?: boolean
  }
}
import { logger } from '@/lib/logger'
import { toast } from '@/lib/toast'

// Use same origin by default so dev proxy and production subdomain both work.
const _raw = import.meta.env.VITE_API_URL
const _normalized = (typeof _raw === 'string' && _raw.trim() !== '')
  ? _raw.replace(/\/+$/, '')
  : ''
export const API_BASE_URL = _normalized ? `${_normalized}/api` : '/api'

const API_KEY =
  typeof import.meta.env.VITE_API_KEY === 'string' && import.meta.env.VITE_API_KEY
    ? import.meta.env.VITE_API_KEY
    : ''

// Throttle connection/5xx toasts for polling endpoints so we don't spam when API is down
const CONNECTION_TOAST_THROTTLE_MS = 60_000
let lastConnectionErrorToastAt = 0

function isPollingEndpoint(url: string): boolean {
  const u = url.replace(/\?.*/, '')
  return (
    u.endsWith('/health') ||
    u.endsWith('/rankings/last-update') ||
    u.endsWith('/system/module-lights') ||
    u.endsWith('/system/health') ||
    u.endsWith('/splash-config')
  )
}

function shouldShowConnectionToast(url: string): boolean {
  if (!isPollingEndpoint(url)) return true
  const now = Date.now()
  if (now - lastConnectionErrorToastAt < CONNECTION_TOAST_THROTTLE_MS) return false
  lastConnectionErrorToastAt = now
  return true
}

function getApiErrorDetail(data: any): string | undefined {
  if (!data) return undefined
  const msg = data.error?.message ?? data.detail
  return typeof msg === 'string' ? msg : Array.isArray(msg) ? msg.map((e: any) => e?.msg ?? e).join(', ') : undefined
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000, // 15s so cold-start / slow API doesn't flood timeouts
})

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    const startTime = Date.now()

    if (API_KEY) {
      config.headers['X-API-Key'] = API_KEY
    }

    // Add JWT token if available - check multiple storage locations
    // 1. Direct access_token key (centralized auth)
    let token = localStorage.getItem('access_token')

    // 2. Legacy auth_token key
    if (!token) {
      token = localStorage.getItem('auth_token')
    }

    // 3. Inside rankings_bot_auth object (current)
    if (!token) {
      try {
        const authData = localStorage.getItem('rankings_bot_auth')
        if (authData) {
          const parsed = JSON.parse(authData)
          token = parsed?.token
        }
      } catch (error) {
        logger.warn('Failed to parse rankings_bot_auth from localStorage', undefined, error as Error)
      }
    }

    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    // Store start time for duration calculation
    config.metadata = { startTime }

    return config
  },
  (error) => {
    logger.error('API request failed before sending', error)
    return Promise.reject(error)
  }
)

// Response interceptor
apiClient.interceptors.response.use(
  (response) => {
    // Log successful API calls; propagate X-Request-ID for end-to-end tracing
    const startTime = response.config.metadata?.startTime
    const duration = startTime ? Date.now() - startTime : undefined
    const requestId = response.headers?.['x-request-id'] ?? response.headers?.['X-Request-ID']

    logger.apiCall(
      response.config.method?.toUpperCase() || 'GET',
      response.config.url || 'unknown',
      response.status,
      duration,
      undefined,
      requestId
    )

    return response
  },
  async (error) => {
    const originalRequest = error.config
    const startTime = originalRequest?.metadata?.startTime
    const duration = startTime ? Date.now() - startTime : undefined
    const method = originalRequest?.method?.toUpperCase() || 'GET'
    const url = originalRequest?.url || 'unknown'

    // Bootstrap / probe calls handle UX themselves (e.g. UpdateRequiredGate when API is down)
    if (originalRequest?.skipGlobalErrorUI) {
      if (!error.response) {
        error.isNetworkError = true
        error.isConnectionError = true
      }
      return Promise.reject(error)
    }

    // Non-fatal: 405 often means proxy/tunnel converts POST to GET; don't flood monitoring
    if (error.response?.status === 405) {
      logger.warn('Method not allowed - request may not reach API (check proxy/tunnel)', {
        url,
        method,
        status: 405
      })
      logger.apiCall(method, url, 405, duration)
      return Promise.reject(error)
    }
    // Handle 401 - local auth doesn't support token refresh
    if (error.response?.status === 401) {
      logger.warn('Authentication failed - token expired or invalid', {
        url,
        method,
        status: 401
      })
      toast.authError('Your session has expired. Please log in again.')

      // Clear all auth storage so next load shows login (and stop sending bad token)
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('auth_token')
      localStorage.removeItem('user_id')
      localStorage.removeItem('organization_id')
      localStorage.removeItem('rankings_bot_auth')
      // Notify AuthContext to clear in-memory user so UI updates without refresh
      try {
        window.dispatchEvent(new CustomEvent('auth:session-expired'))
      } catch (eventError) {
        logger.warn('Failed to dispatch auth:session-expired event', undefined, eventError as Error)
      }
      // Don't retry - let the auth context handle re-login
    } else if (error.response?.status === 503) {
      // Service Unavailable - bot instance not available
      logger.info('Service temporarily unavailable', {
        url,
        method,
        status: 503,
        detail: error.response?.data?.detail || 'Service not available'
      })
      toast.apiError(503, error.response?.data?.error?.code, getApiErrorDetail(error.response?.data))
    } else if (error.response?.status === 423) {
      toast.apiError(423, error.response?.data?.error?.code, getApiErrorDetail(error.response?.data))
    } else if (error.response?.status === 403) {
      toast.apiError(403, error.response?.data?.error?.code, getApiErrorDetail(error.response?.data))
    } else if (error.response?.status >= 500) {
      // Server errors - throttle toast for polling endpoints when API is down
      logger.error('Server error', undefined, {
        url,
        method,
        status: error.response.status,
        statusText: error.response.statusText,
        responseData: error.response.data
      })
      if (shouldShowConnectionToast(url)) {
        toast.apiError(error.response.status, error.response?.data?.error?.code, getApiErrorDetail(error.response?.data))
      }
    } else if (error.response?.status >= 400) {
      // Client errors (400, 404, 409, etc.)
      logger.warn('Client error', {
        url,
        method,
        status: error.response.status,
        statusText: error.response.statusText,
        responseData: error.response.data
      })
      toast.apiError(error.response.status, error.response?.data?.error?.code, getApiErrorDetail(error.response?.data))
    } else if (!error.response) {
      // Network error - API not reachable
      const isTimeout = error.code === 'ECONNABORTED' || error.message?.includes('timeout')

      if (isTimeout) {
        logger.warn('API request timeout', {
          url,
          method,
          timeout: true,
          duration
        })
        if (shouldShowConnectionToast(url)) {
          toast.timeoutError()
        }
      } else {
        logger.error('Network error', error, {
          url,
          method,
          code: error.code,
          isNetworkError: true,
          isConnectionError: true
        })
        if (shouldShowConnectionToast(url)) {
          toast.networkError()
        }
      }
    } else {
      // Other errors
      logger.error('API request failed', error, {
        url,
        method,
        status: error.response?.status,
        hasResponse: !!error.response
      })
    }

    // Log API call with error; propagate X-Request-ID for end-to-end tracing
    const requestId = error.response?.headers?.['x-request-id'] ?? error.response?.headers?.['X-Request-ID']
    logger.apiCall(method, url, error.response?.status, duration, error, requestId)

    // Add error metadata for better handling
    if (!error.response) {
      error.isNetworkError = true
      error.isConnectionError = true
    }

    return Promise.reject(error)
  }
)

export default apiClient