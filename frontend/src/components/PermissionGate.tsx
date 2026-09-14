import type { ReactNode } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { can, PERMISSION_DENIED, roleLabel, type Permission } from '@/auth/permissions'

/**
 * Keep context visible; native disabled fieldsets block all nested form controls.
 * While the session is still being restored, actions stay disabled without
 * claiming the user lacks permission. The backend authorizes every request.
 */
export function PermissionGate({ permission, children }: { permission: Permission; children: ReactNode }) {
  const { user, status } = useAuth()
  if (status !== 'restoring' && can(user, permission)) return children
  const note = status === 'restoring'
    ? 'Checking your permissions…'
    : user
      ? `${PERMISSION_DENIED} Your role: ${roleLabel(user.role)}.`
      : `${PERMISSION_DENIED} Sign in to continue.`
  return <div className="min-w-0">
    <p role="note" className="mb-3 text-sm text-muted">{note}</p>
    <fieldset disabled className="min-w-0">{children}</fieldset>
  </div>
}
