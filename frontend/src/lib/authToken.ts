/** Bearer token resolution for ALFa chat widget (matches api/client.ts). */

export function getBearerToken(): string | null {
  let token = localStorage.getItem('access_token')
  if (token) return token

  const authData = localStorage.getItem('rankings_bot_auth')
  if (authData) {
    try {
      const parsed = JSON.parse(authData) as { token?: string; access_token?: string }
      token = parsed?.token ?? parsed?.access_token ?? null
      if (token) return token
    } catch {
      /* ignore */
    }
  }

  token = localStorage.getItem('auth_token')
  if (token) return token

  return sessionStorage.getItem('access_token') || sessionStorage.getItem('auth_token')
}

export function getAuthHeaders(): Record<string, string> | undefined {
  const token = getBearerToken()
  return token ? { Authorization: `Bearer ${token}` } : undefined
}
