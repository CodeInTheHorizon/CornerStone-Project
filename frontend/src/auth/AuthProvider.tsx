/**
 * Holds the access token and the authenticated user.
 *
 * The token lives in localStorage so a refresh does not log the user out.
 * That is readable by any script on the origin, so it trades some XSS exposure
 * for a usable session; a httpOnly refresh-token cookie would be the stronger
 * design and is worth revisiting before this handles anything sensitive.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

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
  const sessionToken = useRef(token)
  const [sessionError, setSessionError] = useState<string | null>(null)
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
        if (cancelled || sessionToken.current !== stored) return
        setUser(current)
        setStatus('authenticated')
      })
      .catch((error: unknown) => {
        if (cancelled || sessionToken.current !== stored) return
        // A network failure should not destroy a possibly-valid session, but a
        // rejected token should be cleared.
        if (error instanceof ApiRequestError && !error.isUnauthorized && error.status !== 403) {
          setSessionError(error.message)
          setStatus('anonymous')
          return
        }
        setSessionError('Your session is no longer valid. Please sign in again.')
        sessionToken.current = null
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
    sessionToken.current = accessToken
    setSessionError(null)
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
    sessionToken.current = null
    setSessionError(null)
    writeStoredToken(null)
    setToken(null)
    setUser(null)
    setStatus('anonymous')
  }, [])

  useEffect(() => {
    const rejected = (event: Event) => {
      const rejectedToken = (event as CustomEvent<{ token: string }>).detail.token
      if (rejectedToken !== sessionToken.current) return
      logout()
      setSessionError('Your session expired or was rejected. Please sign in again.')
    }
    const storageChanged = (event: StorageEvent) => {
      if (event.key === TOKEN_STORAGE_KEY && event.newValue === null) logout()
    }
    window.addEventListener('marketpulse:unauthorized', rejected)
    window.addEventListener('storage', storageChanged)
    return () => {
      window.removeEventListener('marketpulse:unauthorized', rejected)
      window.removeEventListener('storage', storageChanged)
    }
  }, [logout])

  const value = useMemo(
    () => ({ user, token, status, sessionError, login, register, logout }),
    [user, token, status, sessionError, login, register, logout],
  )

  return <AuthContext value={value}>{children}</AuthContext>
}
