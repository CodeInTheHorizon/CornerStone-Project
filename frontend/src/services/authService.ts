/** Authentication endpoints. */

import { apiRequest } from '@/services/apiClient'
import type {
  AuthToken,
  LoginPayload,
  RegisterPayload,
  User,
} from '@/types/auth'

export function register(payload: RegisterPayload): Promise<AuthToken> {
  return apiRequest<AuthToken>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function login(payload: LoginPayload): Promise<AuthToken> {
  return apiRequest<AuthToken>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function fetchCurrentUser(token: string): Promise<User> {
  return apiRequest<User>('/auth/me', { token })
}
