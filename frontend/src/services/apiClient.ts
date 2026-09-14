/**
 * Minimal typed fetch wrapper shared by every service module.
 */

import { env } from '@/config/env'
import type { ApiError } from '@/types/api'

export class ApiRequestError extends Error implements ApiError {
  readonly status?: number
  readonly detail?: unknown

  constructor(message: string, status?: number, detail?: unknown) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
    this.detail = detail
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
  /** A timeout does not cancel server-side work; mutations are never auto-retried. */
  timeoutMs?: number
}

export async function apiRequest<T>(
  path: string,
  { token, timeoutMs = 30_000, ...init }: RequestOptions = {},
): Promise<T> {
  if (!env.isApiConfigured) {
    throw new ApiRequestError('The API address is not configured. Rebuild the frontend with VITE_API_BASE_URL set to the backend URL.')
  }
  const url = `${env.apiBaseUrl}${path}`

  const headers = new Headers(init.headers)
  if (!(init.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const controller = new AbortController()
  const cancel = () => controller.abort()
  if (init.signal?.aborted) cancel()
  else init.signal?.addEventListener('abort', cancel, { once: true })
  const timer = setTimeout(cancel, timeoutMs)
  try {
    const response = await fetch(url, { ...init, headers, signal: controller.signal })
    if (response.status === 401 && token && typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('marketpulse:unauthorized', { detail: { token } }))
    }
    if (response.status === 204) return undefined as T
    let body: unknown = null
    try { body = await response.json() }
    catch {
      if (controller.signal.aborted) throw new Error('aborted')
    }
    if (!response.ok) {
      const fallbacks: Record<number, string> = {
        401: 'Your session was rejected. Please sign in again.',
        403: 'You do not have permission to perform this action.',
        404: 'The requested resource was not found.',
        422: 'Check the submitted values and try again.',
        500: 'The server could not complete the request. Please retry.',
      }
      throw new ApiRequestError(
        extractMessage(body, fallbacks[response.status] ?? `Request failed with status ${response.status}.`),
        response.status,
        body && typeof body === 'object' ? (body as { detail?: unknown }).detail : undefined,
      )
    }
    if (body === null) throw new ApiRequestError('The API returned an unreadable response. Please retry.', response.status)
    return body as T
  } catch (error) {
    if (error instanceof ApiRequestError) throw error
    if (controller.signal.aborted) {
      throw new ApiRequestError(init.signal?.aborted ? 'Request cancelled.' : 'The request timed out. Server work may still finish; reload status before submitting again.')
    }
    throw new ApiRequestError(`Could not reach the API at ${env.apiBaseUrl}. Is the backend running?`)
  } finally {
    clearTimeout(timer)
    init.signal?.removeEventListener('abort', cancel)
  }
}
