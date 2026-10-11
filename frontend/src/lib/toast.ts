/**
 * Enhanced toast notification utility with user-friendly error messages
 */

import { logger } from './logger'
import { toast as sonnerToast } from 'sonner'

export interface ToastOptions {
  duration?: number
  type?: 'info' | 'success' | 'error' | 'warning'
  showAlert?: boolean // Force alert dialog for critical errors
  logError?: boolean // Log to error monitoring
}

export interface ErrorContext {
  code?: string
  status?: number
  details?: any
  retryable?: boolean
}

// Error message mappings for user-friendly messages
// API error codes (from backend api/utils/error_handling.py) map to user-facing messages
const ERROR_MESSAGES: Record<string, string> = {
  // Network errors
  'ERR_NETWORK': 'Unable to connect to the server. Please check your internet connection.',
  'ECONNABORTED': 'Request timed out. The server may be busy.',
  'ENOTFOUND': 'Server not found. Please check if the service is running.',

  // Authentication errors
  'Invalid token': 'Your session has expired. Please log in again.',
  'Invalid or expired token': 'Your session has expired. Please log in again.',
  'Authentication required': 'Please log in to continue.',
  'Insufficient permissions': 'You don\'t have permission to perform this action.',
  'AUTHENTICATION_ERROR': 'Your session has expired. Please log in again.',
  'AUTHORIZATION_ERROR': 'You don\'t have permission to perform this action.',

  // API error codes (backend)
  'VALIDATION_ERROR': 'Please check your input and try again.',
  'DATABASE_CONNECTION_ERROR': 'The service is temporarily unavailable. Please try again later.',
  'DATABASE_INTEGRITY_ERROR': 'A conflict occurred with the data. Please try again.',
  'DATABASE_ERROR': 'A database error occurred. Please try again later.',
  'INTERNAL_SERVER_ERROR': 'Something went wrong on our end. Please try again later.',
  'HTTP_EXCEPTION': 'A request error occurred. Please try again.',
  'NOT_FOUND': 'The requested resource was not found.',
  'CONFLICT': 'A conflict occurred. Please try again.',

  // API errors (descriptive)
  'Service temporarily unavailable': 'The service is temporarily unavailable. Please try again later.',
  'Database connection error': 'Unable to connect to the database. Please try again later.',
  'Rate limit exceeded': 'Too many requests. Please wait a moment and try again.',

  // Validation errors
  'Validation error': 'Please check your input and try again.',
  'Invalid data': 'The provided data is invalid. Please check and try again.',

  // Generic fallbacks
  'Internal server error': 'Something went wrong on our end. Please try again later.',
  'Bad request': 'Invalid request. Please check your input.',
  'Not found': 'The requested resource was not found.',
  'Forbidden': 'Access denied.',
  'Conflict': 'A conflict occurred. Please try again.',
}

// HTTP status → user message (fallback when error code not in map)
const STATUS_MESSAGES: Record<number, string> = {
  400: 'Invalid request. Please check your input.',
  401: 'Your session has expired. Please log in again.',
  403: 'You don\'t have permission to perform this action.',
  404: 'The requested resource was not found.',
  409: 'A conflict occurred. Please try again.',
  423: 'Account locked. Too many failed attempts. Try again later.',
  429: 'Too many requests. Please wait a moment and try again.',
  500: 'Something went wrong on our end. Please try again later.',
  502: 'The server is temporarily unavailable. Please try again later.',
  503: 'The service is temporarily unavailable. Please try again later.',
}

// Success message mappings
const SUCCESS_MESSAGES: Record<string, string> = {
  'login': 'Successfully logged in!',
  'logout': 'Successfully logged out.',
  'save': 'Changes saved successfully.',
  'delete': 'Item deleted successfully.',
  'update': 'Updated successfully.',
  'create': 'Created successfully.',
  'refresh': 'Data refreshed successfully.',
}

function getUserFriendlyMessage(
  originalMessage: string,
  type: 'error' | 'success' | 'warning' | 'info',
  context?: ErrorContext
): string {
  if (type === 'success') {
    // Try to match success patterns
    const lowerMessage = originalMessage.toLowerCase()
    for (const [key, friendly] of Object.entries(SUCCESS_MESSAGES)) {
      if (lowerMessage.includes(key)) {
        return friendly
      }
    }
  } else if (type === 'error') {
    // Try to match error patterns
    const lowerMessage = originalMessage.toLowerCase()

    // Check for exact matches first
    if (ERROR_MESSAGES[originalMessage]) {
      return ERROR_MESSAGES[originalMessage]
    }

    // Check for partial matches
    for (const [key, friendly] of Object.entries(ERROR_MESSAGES)) {
      if (lowerMessage.includes(key.toLowerCase())) {
        return friendly
      }
    }

    // Handle HTTP status codes (use STATUS_MESSAGES for consistent user-facing text)
    if (context?.status && STATUS_MESSAGES[context.status]) {
      return STATUS_MESSAGES[context.status]
    }

    // Handle specific error codes
    if (context?.code && ERROR_MESSAGES[context.code]) {
      return ERROR_MESSAGES[context.code]
    }
  }

  // Return original message if no friendly version found
  return originalMessage
}

function showToast(
  message: string,
  type: 'info' | 'success' | 'error' | 'warning' = 'info',
  options?: ToastOptions,
  context?: ErrorContext
): void {
  const friendlyMessage = getUserFriendlyMessage(message, type, context)
  const prefix = type === 'error' ? '❌ ' : type === 'success' ? '✅ ' : type === 'warning' ? '⚠️ ' : 'ℹ️ '

  // Log to console with structured logging
  const logMethod = type === 'error' ? 'error' : type === 'warning' ? 'warn' : 'info'
  logger[logMethod](`Toast: ${message}`, { type, friendlyMessage, context })

  // Show visual notification.
  if (type === 'success') {
    sonnerToast.success(friendlyMessage)
  } else if (type === 'error') {
    sonnerToast.error(friendlyMessage)
  } else if (type === 'warning') {
    sonnerToast.warning(friendlyMessage)
  } else {
    sonnerToast.info(friendlyMessage)
  }

  // Show alert for critical errors or when explicitly requested
  const shouldShowAlert = type === 'error' && (
    options?.showAlert ||
    context?.status === 401 || // Auth errors
    context?.status === 403 || // Permission errors
    !context?.retryable // Non-retryable errors
  )

  if (shouldShowAlert) {
    sonnerToast.error(friendlyMessage, {
      duration: options?.duration ?? 7000,
    })
  }

  // Log errors to monitoring if requested
  if (type === 'error' && options?.logError !== false) {
    logger.error('User-facing error displayed', new Error(message), {
      friendlyMessage,
      context,
      toast: true
    })
  }
}

export const toast = Object.assign(
  (message: string, options?: ToastOptions, context?: ErrorContext) =>
    showToast(message, options?.type || 'info', options, context),
  {
    success: (message: string, context?: ErrorContext) =>
      showToast(message, 'success', undefined, context),

    error: (message: string, context?: ErrorContext, options?: ToastOptions) =>
      showToast(message, 'error', { ...options, showAlert: true }, context),

    warning: (message: string, context?: ErrorContext, options?: ToastOptions) =>
      showToast(message, 'warning', options, context),

    info: (message: string, context?: ErrorContext, options?: ToastOptions) =>
      showToast(message, 'info', options, context),

    // Specialized error toasts
    networkError: (message?: string) =>
      showToast(message || 'Network connection error', 'error', undefined, {
        code: 'ERR_NETWORK',
        retryable: true
      }),

    timeoutError: (message?: string) =>
      showToast(message || 'Request timed out', 'error', undefined, {
        code: 'ECONNABORTED',
        retryable: true
      }),

    authError: (message?: string) =>
      showToast(message || 'Authentication required', 'error', undefined, {
        status: 401,
        retryable: false
      }),

    serverError: (message?: string) =>
      showToast(message || 'Server error occurred', 'error', undefined, {
        status: 500,
        retryable: true
      }),

    validationError: (message?: string, details?: any) =>
      showToast(message || 'Please check your input', 'warning', undefined, {
        code: 'VALIDATION_ERROR',
        details,
        retryable: true
      }),

    /** Show user-facing message for API error (status + optional backend error code) */
    apiError: (status: number, code?: string, detail?: string) =>
      showToast(detail || `Request failed (${status})`, 'error', undefined, {
        status,
        code,
        details: detail ? { detail } : undefined,
        retryable: status >= 500 || status === 429
      })
  }
)

export default toast
