/**
 * Frontend permission checks. UI gating only: the backend authorizes every
 * request and stays authoritative.
 *
 * Every check fails closed. A missing user, an inactive account, an unknown or
 * absent role, a missing or malformed permissions array, or a role with no
 * mapping all DENY -- they never allow and never throw. Auth payloads reach the
 * UI from the network (and possibly from a backend older than Phase 13, whose
 * user payload had no role or permissions), so nothing here assumes their shape.
 */

export const ROLES = ['viewer', 'analyst', 'operator', 'administrator'] as const
export type Role = (typeof ROLES)[number]

export const PERMISSIONS = [
  'workspace:read',
  'dataset:build',
  'prediction:run',
  'data:collect',
  'data:import',
  'data:demo',
  'model:train',
  'users:manage',
] as const
export type Permission = (typeof PERMISSIONS)[number]

/**
 * Mirror of backend/app/auth/permissions.py (tests/permissions.test.mjs checks
 * they agree). A permission is shown as available only when BOTH the server's
 * permission list for the user and this mapping allow it, so drift or a
 * tampered payload can only hide controls, never reveal them.
 */
export const ROLE_PERMISSIONS: Readonly<Record<Role, readonly Permission[]>> = {
  viewer: ['workspace:read'],
  analyst: ['workspace:read', 'dataset:build', 'prediction:run'],
  operator: ['workspace:read', 'dataset:build', 'prediction:run', 'data:collect', 'data:import', 'data:demo', 'model:train'],
  administrator: [...PERMISSIONS],
}

export const PERMISSION_DENIED = 'You do not have permission to perform this action.'

export function isRole(value: unknown): value is Role {
  return typeof value === 'string' && (ROLES as readonly string[]).includes(value)
}

export function isPermission(value: unknown): value is Permission {
  return typeof value === 'string' && (PERMISSIONS as readonly string[]).includes(value)
}

/** Server-provided permissions, keeping only known permission strings. Never throws. */
export function knownPermissions(value: unknown): Permission[] {
  return Array.isArray(value) ? value.filter(isPermission) : []
}

export function can(
  user: unknown,
  permission: Permission,
  mapping: Partial<Record<string, readonly string[]>> = ROLE_PERMISSIONS,
): boolean {
  if (typeof user !== 'object' || user === null) return false
  const { is_active: isActive, role, permissions } = user as Record<string, unknown>
  if (isActive !== true || !isRole(role) || !isPermission(permission)) return false
  const allowedForRole = mapping[role]
  if (!Array.isArray(allowedForRole) || !allowedForRole.includes(permission)) return false
  return knownPermissions(permissions).includes(permission)
}

/** Human label for a role, including unknown or missing ones. */
export function roleLabel(role: unknown): string {
  return isRole(role) ? role : 'unknown role'
}
