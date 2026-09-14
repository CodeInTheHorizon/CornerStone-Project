/**
 * Auth context, kept separate from the provider component so that the provider
 * file exports components only and Fast Refresh keeps working.
 */

import { createContext } from 'react'

import type { LoginPayload, RegisterPayload, User } from '@/types/auth'

export const TOKEN_STORAGE_KEY = 'marketpulse-token'

/**
 * 'restoring' covers the first paint, while a stored token is being checked
 * against /auth/me. Protected routes must wait rather than bounce the user to
 * the login page on every refresh.
 */
export type AuthStatus = 'restoring' | 'authenticated' | 'anonymous'

export interface AuthContextValue {
  user: User | null
  token: string | null
  status: AuthStatus
  sessionError: string | null
  login: (payload: LoginPayload) => Promise<void>
  register: (payload: RegisterPayload) => Promise<void>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
