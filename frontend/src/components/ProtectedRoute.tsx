/** Gates a route behind an authenticated session. */

import { Navigate, useLocation } from 'react-router-dom'

import { useAuth } from '@/hooks/useAuth'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()

  // A stored token is still being checked. Bouncing to /login here would sign
  // the user out on every page refresh.
  if (status === 'restoring') {
    return (
      <div
        className="grid min-h-screen place-items-center bg-background"
        role="status"
        aria-live="polite"
      >
        <p className="text-sm text-muted">Restoring your session…</p>
      </div>
    )
  }

  if (status === 'anonymous') {
    // Remember where they were headed so login can return them there.
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }

  return <>{children}</>
}
