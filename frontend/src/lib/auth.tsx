/* src/lib/auth.tsx
 *
 * The single source of truth for the signed-in user on the client. `AuthProvider`
 * holds the current user + auth status and exposes `login` / `register` /
 * `logout`; `useAuth` reads it. Everything token-related (storage, the Bearer
 * header, the 401 hook) lives in api/client — this file is the React binding
 * around it.
 *
 * Lifecycle:
 *   * On load: if a token is stored, verify it via /auth/me and restore the
 *     session; otherwise go straight to "unauthenticated". A short "loading"
 *     status prevents the login screen from flashing before we know.
 *   * login/register: get a token, store it, then fetch the user.
 *   * A 401 on ANY later request (expired/invalid token) calls the handler the
 *     client fires, dropping the session so the app falls back to login.
 */

import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

import { authApi, getAuthToken, onUnauthorized, setAuthToken } from '../api/client'
import type { AuthCredentials, AuthUser } from '../api/types'

/** loading = restoring session; then authenticated / unauthenticated. */
type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated'

interface AuthContextValue {
  user: AuthUser | null
  status: AuthStatus
  login: (credentials: AuthCredentials) => Promise<void>
  register: (credentials: AuthCredentials) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [status, setStatus] = useState<AuthStatus>('loading')

  // Restore the session on first load: a stored token is only trusted once
  // /auth/me confirms it (an expired token 401s and is cleared by the client).
  useEffect(() => {
    let cancelled = false
    async function restore() {
      if (!getAuthToken()) {
        setStatus('unauthenticated')
        return
      }
      try {
        const me = await authApi.me()
        if (!cancelled) {
          setUser(me)
          setStatus('authenticated')
        }
      } catch {
        // The client already cleared the token on 401; treat as logged out.
        if (!cancelled) {
          setUser(null)
          setStatus('unauthenticated')
        }
      }
    }
    void restore()
    return () => {
      cancelled = true
    }
  }, [])

  // When any request 401s (token expired mid-session), drop the session so the
  // guard shows the login screen. The client has already cleared the token.
  useEffect(() => {
    onUnauthorized(() => {
      setUser(null)
      setStatus('unauthenticated')
    })
  }, [])

  /** Store the token, then load the user it belongs to. */
  async function establishSession(token: string) {
    setAuthToken(token)
    const me = await authApi.me()
    setUser(me)
    setStatus('authenticated')
  }

  async function login(credentials: AuthCredentials) {
    const { access_token } = await authApi.login(credentials)
    await establishSession(access_token)
  }

  async function register(credentials: AuthCredentials) {
    const { access_token } = await authApi.register(credentials)
    await establishSession(access_token)
  }

  function logout() {
    setAuthToken(null)
    setUser(null)
    setStatus('unauthenticated')
  }

  const value: AuthContextValue = { user, status, login, register, logout }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

/** Access the auth context. Throws if used outside <AuthProvider>. */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (context === null) {
    throw new Error('useAuth must be used within <AuthProvider>')
  }
  return context
}
