/**
 * Minimal typed fetch wrapper shared by every service module.
 *
 * Kept deliberately small in Phase 1; auth headers are added in Phase 3.
 */

import { env } from '@/config/env'
import type { ApiError } from '@/types/api'

export class ApiRequestError extends Error implements ApiError {
  readonly status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
  }
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const url = `${env.apiBaseUrl}${path}`

  let response: Response
  try {
    response = await fetch(url, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init.headers },
    })
  } catch {
    // Network-level failure: backend not running, DNS, CORS rejection.
    throw new ApiRequestError(
      `Could not reach the API at ${env.apiBaseUrl}. Is the backend running?`,
    )
  }

  if (!response.ok) {
    throw new ApiRequestError(
      `Request to ${path} failed with status ${response.status}.`,
      response.status,
    )
  }

  return (await response.json()) as T
}
