/**
 * Doc refs (AI / maintainers): docs/AUTH_DOC_HOOKS.md; docs/AUTH_DESIGN.md;
 *   docs/ROLES_AND_PERMISSIONS.md; docs/ENV_VARS.md (VITE_* if applicable)
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { authApi, login as apiLogin, me as apiMe, type TokenResponse } from '@/api/auth'
import { logger } from '@/lib/logger'
import { toast } from '@/lib/toast'

const AUTH_TOKEN_KEY = 'auth_token'
const AUTH_ROLE_KEY = 'auth_role'
const FORCE_LOGIN_EACH_VISIT = false

const STORAGE_KEY = 'rankings_bot_auth'

export interface AuthUser {
  user: string
  role: 'user' | 'admin' | 'super_admin' | 'director' | 'score_keeper'
  token?: string
  must_change_password?: boolean
  requires_email_setup?: boolean
  force_password_reset?: boolean
}

interface AuthContextValue {
  user: AuthUser | null
  isAdmin: boolean
  isDirector: boolean
  isSuperAdmin: boolean
  isScoreKeeper: boolean
  isLoading: boolean
  must_change_password: boolean
  requires_email_setup: boolean
  force_password_reset: boolean
  login: (username: string, password: string) => Promise<{ success: boolean; message?: string }>
  changePassword: (newPassword: string) => Promise<{ success: boolean; message?: string }>
  setupEmail: (email: string) => Promise<{ success: boolean; message?: string }>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

function loadStoredAuth(): AuthUser | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    const validRoles = ['user', 'admin', 'super_admin', 'director', 'score_keeper']
    if (parsed?.user && parsed?.role && validRoles.includes(parsed.role)) {
      return { user: parsed.user, role: parsed.role, token: parsed.token }
    }
  } catch (error) {
    logger.warn('Invalid auth data in localStorage, clearing stored session', undefined, error as Error)
    localStorage.removeItem(STORAGE_KEY)
  }
  return null
}

function saveAuth(u: AuthUser | null) {
  if (u) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      user: u.user,
      role: u.role,
      token: u.token,
      must_change_password: u.must_change_password,
    }))
  } else {
    localStorage.removeItem(STORAGE_KEY)
  }
}

function clearStored() {
  localStorage.removeItem(STORAGE_KEY)
  localStorage.removeItem(AUTH_TOKEN_KEY)
  localStorage.removeItem(AUTH_ROLE_KEY)
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('user_id')
  localStorage.removeItem('organization_id')
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(loadStoredAuth)
  const [isLoading, setIsLoading] = useState(true)
  const [must_change_password, setMustChangePassword] = useState(false)
  const [requires_email_setup, setRequiresEmailSetup] = useState(false)
  const [force_password_reset, setForcePasswordReset] = useState(false)

  // On 401, api client dispatches 'auth:session-expired'; clear state so UI shows login
  useEffect(() => {
    const handler = () => {
      clearStored()
      setUser(null)
    }
    window.addEventListener('auth:session-expired', handler)
    return () => window.removeEventListener('auth:session-expired', handler)
  }, [])

  useEffect(() => {
    if (FORCE_LOGIN_EACH_VISIT) {
      clearStored()
      setUser(null)
      setIsLoading(false)
      return
    }
    if (!user) {
      setIsLoading(false)
      return
    }
    apiMe()
      .then((me) => {
        setUser((u) => {
          if (!u) return null
          const next = { ...u, role: me.role as AuthUser['role'] }
          saveAuth(next)
          return next
        })
      })
      .catch(() => {
        logger.warn('Session validation failed in apiMe, clearing stored auth')
        clearStored()
        setUser(null)
      })
      .finally(() => setIsLoading(false))
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    try {
      logger.userAction('login_attempt', { username: username.trim() })

      const res = await apiLogin(username.trim(), password)
      const validRoles = ['user', 'admin', 'super_admin', 'director', 'score_keeper']

      if (validRoles.includes(res.role)) {
        const authUser: AuthUser = {
          user: res.user,
          role: res.role as 'user' | 'admin' | 'super_admin' | 'director' | 'score_keeper',
          token: res.access_token,
          must_change_password: res.must_change_password || false,
          requires_email_setup: res.requires_email_setup || false,
          force_password_reset: res.force_password_reset || false,
        }
        setUser(authUser)
        setMustChangePassword(res.must_change_password || false)
        setRequiresEmailSetup(res.requires_email_setup || false)
        setForcePasswordReset(res.force_password_reset || false)
        saveAuth(authUser)

        logger.userAction('login_success', {
          username: username.trim(),
          role: res.role,
          must_change_password: res.must_change_password
        })

        toast.success('Welcome back!', { role: res.role })

        return { success: true }
      } else {
        logger.warn('Login failed: invalid role returned', {
          username: username.trim(),
          returnedRole: res.role,
          validRoles
        })
        throw new Error('Invalid role')
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string; message?: string } }; code?: string; message?: string }
      const msg = err?.response?.data?.detail || err?.response?.data?.message || err?.message

      logger.error('Login failed', e as Error, {
        username: username.trim(),
        errorCode: err?.code,
        statusCode: err?.response?.status,
        errorMessage: msg
      })

      // Show user-friendly error toast
      if (err?.code === 'ECONNABORTED') {
        toast.networkError('Login timed out. Please check your connection and try again.')
        return { success: false, message: 'Connection timed out. Check your network.' }
      }
      if (err?.code === 'ERR_NETWORK' || err?.message?.includes('Network Error')) {
        toast.networkError('Cannot connect to server. Please check if the service is running.')
        return { success: false, message: 'Cannot reach server. Is the API running on the correct port?' }
      }
      if (err?.response?.status === 401 || err?.response?.status === 403) {
        toast.authError(msg || 'Invalid username or password.')
        return { success: false, message: msg || 'Invalid credentials' }
      }

      // Generic error with user-friendly message
      toast.error(msg || 'Login failed. Please try again.', {
        status: err?.response?.status,
        retryable: true
      })

      if (msg) return { success: false, message: msg }
      return { success: false, message: 'Login failed' }
    }
  }, [])

  const changePassword = useCallback(async (newPassword: string) => {
    try {
      await authApi.changePassword(newPassword)
      // Clear the must_change_password and force_password_reset flags so the
      // password-change gate (App.tsx) does not re-render after a successful change.
      setMustChangePassword(false)
      setForcePasswordReset(false)
      if (user) {
        const updated = { ...user, must_change_password: false, force_password_reset: false }
        setUser(updated)
        saveAuth(updated)
      }
      return { success: true }
    } catch (e: unknown) {
      const err = e as { message?: string }
      return { success: false, message: err?.message || 'Password change failed' }
    }
  }, [user])

  const setupEmail = useCallback(async (email: string) => {
    try {
      const { data } = await authApi.setupEmail(email)
      // Do NOT clear requires_email_setup here: the EmailSetup component must stay
      // mounted to show the "check your email" screen. The user verifies via the
      // emailed link, then signs in again (a fresh login picks up
      // force_password_reset=true and triggers the password-change gate).
      toast.success(data.message || 'Email set successfully. Please check your email to verify.')
      return { success: true, message: data.message }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string }
      const msg = err?.response?.data?.detail || err?.message || 'Email setup failed'
      return { success: false, message: msg }
    }
  }, [user])

  const logout = useCallback(() => {
    clearStored()
    authApi.logout()
    setUser(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAdmin: user?.role === 'admin' || user?.role === 'super_admin',
      isDirector: user?.role === 'director',
      isSuperAdmin: user?.role === 'super_admin',
      isScoreKeeper: user?.role === 'score_keeper',
      isLoading,
      must_change_password,
      requires_email_setup: user?.requires_email_setup || false,
      force_password_reset: user?.force_password_reset || false,
      login,
      changePassword,
      setupEmail,
      logout,
    }),
    [user, isLoading, must_change_password, login, changePassword, setupEmail, logout]
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
