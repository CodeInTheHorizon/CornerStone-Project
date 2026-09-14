/** Authentication endpoints. Account payloads are normalized before use. */

import { normalizeUser } from '@/auth/normalizeUser'
import { ApiRequestError, apiRequest } from '@/services/apiClient'
import type {
  AuthToken,
  LoginPayload,
  RegisterPayload,
  User,
} from '@/types/auth'

const MALFORMED_ACCOUNT = 'The server returned an unrecognised account response. Please retry or contact the operator.'

function requireUser(raw: unknown): User {
  const user = normalizeUser(raw)
  if (!user) throw new ApiRequestError(MALFORMED_ACCOUNT)
  return user
}

function requireToken(raw: AuthToken): AuthToken {
  if (typeof raw?.access_token !== 'string' || !raw.access_token) throw new ApiRequestError(MALFORMED_ACCOUNT)
  return { ...raw, user: requireUser(raw.user) }
}

export async function register(payload: RegisterPayload): Promise<AuthToken> {
  return requireToken(await apiRequest<AuthToken>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  }))
}

export async function login(payload: LoginPayload): Promise<AuthToken> {
  return requireToken(await apiRequest<AuthToken>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  }))
}

export async function fetchCurrentUser(token: string): Promise<User> {
  return requireUser(await apiRequest<unknown>('/auth/me', { token }))
}

export function revokeSessions(token: string): Promise<void> {
  return apiRequest<void>('/auth/logout', { token, method: 'POST' })
}
