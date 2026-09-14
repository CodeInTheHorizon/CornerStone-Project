/**
 * Runtime shape check for account payloads at the API boundary.
 *
 * TypeScript types do not validate network data. A backend older than Phase 13
 * returns users without `role` or `permissions`, and a proxy or bug could
 * return anything. Normalizing here means the rest of the UI always receives a
 * well-formed User whose authorization fields fail closed:
 *
 * - unknown or missing role -> `role: null`
 * - missing or malformed permissions -> `permissions: []`
 * - anything but `is_active === true` -> inactive
 *
 * A payload without a usable id or email is not an account at all and returns
 * null so the caller can reject the session instead of rendering with it.
 */

import { isRole, knownPermissions } from '@/auth/permissions'
import type { User } from '@/types/auth'

export function normalizeUser(raw: unknown): User | null {
  if (typeof raw !== 'object' || raw === null) return null
  const value = raw as Record<string, unknown>
  if (typeof value.id !== 'number' || typeof value.email !== 'string' || !value.email) return null
  return {
    id: value.id,
    email: value.email,
    full_name: typeof value.full_name === 'string' ? value.full_name : null,
    role: isRole(value.role) ? value.role : null,
    permissions: knownPermissions(value.permissions),
    is_active: value.is_active === true,
    created_at: typeof value.created_at === 'string' ? value.created_at : '',
  }
}
