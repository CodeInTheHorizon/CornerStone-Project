/** Dashboard sidebar: brand, section navigation, account footer. */

import { Link, NavLink } from 'react-router-dom'

import { Icon } from '@/components/Icon'
import { Logo } from '@/components/Logo'
import { dashboardNav } from '@/config/dashboard'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/cn'

interface SidebarProps {
  /** Called after navigating, so the mobile drawer can close itself. */
  onNavigate?: () => void
}

export function Sidebar({ onNavigate }: SidebarProps) {
  const { user, logout } = useAuth()

  return (
    <div className="flex h-full flex-col border-r border-border-hair bg-surface">
      <div className="flex h-16 shrink-0 items-center border-b border-border-hair px-5">
        <Link to="/" onClick={onNavigate} aria-label="MarketPulse AI, home">
          <Logo />
        </Link>
      </div>

      <nav aria-label="Dashboard" className="flex-1 overflow-y-auto p-3">
        <ul className="space-y-1">
          {dashboardNav.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.to === '/dashboard'}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    'group flex items-center gap-3 rounded-card px-3 py-2.5 text-sm transition-colors',
                    isActive
                      ? 'bg-accent-soft font-medium text-accent-text'
                      : 'text-muted hover:bg-background-alt hover:text-foreground',
                  )
                }
              >
                <Icon name={item.icon} className="size-[18px] shrink-0" />
                <span className="flex-1 truncate">{item.label}</span>
                {!item.available && (
                  <span
                    className="rounded-full border border-border-hair px-1.5 py-0.5 text-[10px] text-subtle"
                    title="Not built yet"
                  >
                    Soon
                  </span>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="shrink-0 border-t border-border-hair p-3">
        <div className="flex items-center gap-3 rounded-card px-3 py-2.5">
          <span
            className="grid size-8 shrink-0 place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent-text"
            aria-hidden="true"
          >
            {(user?.full_name ?? user?.email ?? '?').charAt(0).toUpperCase()}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">
              {user?.full_name ?? 'Signed in'}
            </span>
            <span className="block truncate text-xs text-subtle">
              {user?.email}
            </span>
          </span>
        </div>

        <button
          type="button"
          onClick={logout}
          className="mt-1 flex w-full items-center gap-3 rounded-card px-3 py-2.5 text-sm text-muted transition-colors hover:bg-signal-down/10 hover:text-signal-down"
        >
          <Icon name="logout" className="size-[18px]" />
          Logout
        </button>
      </div>
    </div>
  )
}
