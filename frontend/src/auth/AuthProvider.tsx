/**
 * Holds the access token and the authenticated user.
 *
 * The token lives in localStorage so a refresh does not log the user out.
 * That is readable by any script on the origin, so it trades some XSS exposure
 * for a usable session; a httpOnly refresh-token cookie would be the stronger
 * design and is worth revisiting before this handles anything sensitive.
 */

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import * as authService from '@/services/authService'
import { ApiRequestError } from '@/services/apiClient'
import {
  AuthContext,
  TOKEN_STORAGE_KEY,
  type AuthStatus,
} from '@/auth/authContext'
import type { LoginPayload, RegisterPayload, User } from '@/types/auth'

function readStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY)
  } catch {
    // Private mode or blocked storage: behave as if signed out.
    return null
  }
}

function writeStoredToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_STORAGE_KEY, token)
    else localStorage.removeItem(TOKEN_STORAGE_KEY)
  } catch {
    // The session still works in memory; it just will not survive a refresh.
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(readStoredToken)
  const [user, setUser] = useState<User | null>(null)
  // Only 'restoring' when there is actually a token worth checking.
  const [status, setStatus] = useState<AuthStatus>(() =>
    readStoredToken() ? 'restoring' : 'anonymous',
  )

  // Validate a stored token once on mount. A token that the server rejects is
  // discarded rather than left to fail every subsequent request.
  useEffect(() => {
    const stored = readStoredToken()
    if (!stored) return

    let cancelled = false

    authService
      .fetchCurrentUser(stored)
      .then((current) => {
        if (cancelled) return
        setUser(current)
        setStatus('authenticated')
      })
      .catch((error: unknown) => {
        if (cancelled) return
        // A network failure should not destroy a possibly-valid session, but a
        // rejected token should be cleared.
        if (error instanceof ApiRequestError && !error.isUnauthorized) {
          setStatus('anonymous')
          return
        }
        writeStoredToken(null)
        setToken(null)
        setUser(null)
        setStatus('anonymous')
      })

    return () => {
      cancelled = true
    }
  }, [])

  const applySession = useCallback((accessToken: string, current: User) => {
    writeStoredToken(accessToken)
    setToken(accessToken)
    setUser(current)
    setStatus('authenticated')
  }, [])

  const login = useCallback(
    async (payload: LoginPayload) => {
      const result = await authService.login(payload)
      applySession(result.access_token, result.user)
    },
    [applySession],
  )

  const register = useCallback(
    async (payload: RegisterPayload) => {
      const result = await authService.register(payload)
      applySession(result.access_token, result.user)
    },
    [applySession],
  )

  const logout = useCallback(() => {
    // Tokens are stateless, so signing out is purely a client-side discard.
    // There is no server endpoint that would genuinely revoke this token.
    writeStoredToken(null)
    setToken(null)
    setUser(null)
    setStatus('anonymous')
  }, [])

  const value = useMemo(
    () => ({ user, token, status, login, register, logout }),
    [user, token, status, login, register, logout],
  )

  return <AuthContext value={value}>{children}</AuthContext>
}
