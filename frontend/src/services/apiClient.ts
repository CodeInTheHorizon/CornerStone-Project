/**
 * Minimal typed fetch wrapper shared by every service module.
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

  /** True when the token is missing, expired or rejected. */
  get isUnauthorized(): boolean {
    return this.status === 401
  }
}

/**
 * Pulls a readable message out of a FastAPI error body.
 *
 * `detail` is a string for our own HTTPExceptions but an array of per-field
 * objects for pydantic validation failures, so both shapes are handled.
 */
function extractMessage(body: unknown, fallback: string): string {
  if (typeof body !== 'object' || body === null) return fallback

  const detail = (body as { detail?: unknown }).detail

  if (typeof detail === 'string') return detail

  // Some endpoints return a structured detail, e.g. the dataset builder's
  // { status: 'insufficient_data', reason: '...' }. Surface the reason rather
  // than discarding it for a generic status-code message.
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    const { reason, message } = detail as {
      reason?: unknown
      message?: unknown
    }
    if (typeof reason === 'string') return reason
    if (typeof message === 'string') return message
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item !== 'object' || item === null) return null
        const { msg, loc } = item as { msg?: unknown; loc?: unknown }
        if (typeof msg !== 'string') return null
        // loc is like ["body", "password"] — the field name is the last entry.
        const field = Array.isArray(loc) ? loc.at(-1) : undefined
        return typeof field === 'string' && field !== 'body'
          ? `${field}: ${msg}`
          : msg
      })
      .filter((message): message is string => Boolean(message))

    if (messages.length > 0) return messages.join(' ')
  }

  return fallback
}

interface RequestOptions extends RequestInit {
  /** Bearer token to attach, when the endpoint requires authentication. */
  token?: string | null
}

export async function apiRequest<T>(
  path: string,
  { token, ...init }: RequestOptions = {},
): Promise<T> {
  const url = `${env.apiBaseUrl}${path}`

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string> | undefined),
  }
  if (token) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(url, { ...init, headers })
  } catch {
    // Network-level failure: backend not running, DNS, CORS rejection.
    throw new ApiRequestError(
      `Could not reach the API at ${env.apiBaseUrl}. Is the backend running?`,
    )
  }

  if (response.status === 204) return undefined as T

  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    body = null
  }

  if (!response.ok) {
    throw new ApiRequestError(
      extractMessage(body, `Request failed with status ${response.status}.`),
      response.status,
    )
  }

  return body as T
}
