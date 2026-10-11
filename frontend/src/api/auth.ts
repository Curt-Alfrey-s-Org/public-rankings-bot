/**
 * Auth API — JWT against the rankings-bot FastAPI backend (`/api/auth/*`).
 */

import apiClient from './client'

export interface TokenResponse {
  access_token: string
  token_type: string
  role: string
  user: string
  must_change_password?: boolean
  requires_email_setup?: boolean
  force_password_reset?: boolean
}

export interface MeResponse {
  role: string
  sub: string
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
  captcha_token: string
  license_key: string
}

/** POST /auth/register — public self-service signup (email verification required). */
export interface PublicRegistrationPayload {
  username: string
  email: string
  password: string
  full_name?: string
  license_number?: string
}

export interface PublicRegistrationResponse {
  message: string
  username: string
}

// Legacy login (for backward compatibility)
export async function login(username: string, password: string): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>('/auth/login', {
    username: username.trim(),
    password,
  })
  return data
}

export async function me(): Promise<MeResponse> {
  const { data } = await apiClient.get<MeResponse>('/auth/me')
  return data
}

export async function resendVerification(): Promise<{ message: string }> {
  const { data } = await apiClient.post<{ message: string }>(
    '/auth/resend-verification',
    {},
    { timeout: 15000 }
  )
  return data
}

export const authApi = {
  // Legacy login (for backward compatibility)
  login,
  me,

  /**
   * Change current user's password (after login with must_change_password=true)
   * Uses apiClient which automatically includes auth headers
   */
  changePassword: async (newPassword: string) => {
    const { data } = await apiClient.post('/users/change-password', { new_password: newPassword })
    return data
  },

  /**
   * Setup email address for Fargo account activation
   * Uses apiClient which automatically includes auth headers
   */
  setupEmail: async (email: string) => {
    const { data } = await apiClient.post<{ message: string; email: string; requires_verification: boolean }>('/auth/setup-email', { email })
    return data
  },

  /**
   * Public registration (local DB + verification email). Rate-limited on the server.
   */
  register: async (body: PublicRegistrationPayload): Promise<PublicRegistrationResponse> => {
    const { data } = await apiClient.post<PublicRegistrationResponse>('/auth/register', body, {
      skipGlobalErrorUI: true,
      timeout: 30_000,
    })
    return data
  },

  /**
   * Logout (clear local tokens)
   */
  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user_id')
    localStorage.removeItem('organization_id')
    localStorage.removeItem('auth_token') // Legacy
  }
}

