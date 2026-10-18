import { Link, NavLink } from 'react-router-dom'
import { motion } from 'framer-motion'
import { LogOut } from 'lucide-react'

import { can, roleLabel } from '@/auth/permissions'
import { Icon } from '@/components/Icon'
import { Logo } from '@/components/Logo'
import { dashboardNav, dashboardNavGroups } from '@/config/dashboard'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/cn'

interface SidebarProps {
  onNavigate?: () => void
}

export function Sidebar({ onNavigate }: SidebarProps) {
  const { user, logout } = useAuth()

  return (
    <div className="flex h-full flex-col border-r border-border-hair bg-surface shadow-card">
      <div className="flex h-16 shrink-0 items-center px-5">
        <Link to="/" onClick={onNavigate} aria-label="MarketPulse AI, home">
          <Logo />
        </Link>
      </div>

      <nav aria-label="Dashboard" className="flex-1 overflow-y-auto px-3 pt-2 pb-4">
        {dashboardNavGroups.map((group) => (
          <div key={group.id} className="mt-5 first:mt-1">
            <p
              id={`nav-group-${group.id}`}
              className="px-3 pb-2.5 text-[11px] font-semibold tracking-[0.12em] text-subtle uppercase"
            >
              {group.label}
            </p>
            <ul aria-labelledby={`nav-group-${group.id}`} className="space-y-1">
              {dashboardNav
                .filter((item) => item.group === group.id)
                .map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.to === '/dashboard'}
                      onClick={onNavigate}
                      className={({ isActive }) =>
                        cn(
                          'group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors duration-200 ease-standard',
                          isActive
                            ? 'font-semibold text-accent-text'
                            : 'text-muted hover:bg-background-alt hover:text-foreground',
                        )
                      }
                    >
                      {({ isActive }) => (
                        <>
                          {isActive && (
                            <motion.span
                              layoutId="sidebar-active"
                              className="absolute inset-0 rounded-xl bg-accent-soft"
                              transition={{ type: 'spring', stiffness: 350, damping: 30 }}
                            />
                          )}
                          <span
                            aria-hidden="true"
                            className={cn(
                              'absolute inset-y-2 -left-3 w-[3px] rounded-r-full bg-accent transition-opacity duration-200',
                              isActive ? 'opacity-100' : 'opacity-0',
                            )}
                          />
                          <Icon name={item.icon} className="relative size-[18px] shrink-0" />
                          <span className="relative flex-1 truncate">
                            {item.to === '/dashboard/train' && !can(user, 'model:train') ? 'Datasets / Model Status' : item.label}
                          </span>
                          {!item.available && (
                            <span
                              className="relative rounded-full border border-border-hair px-1.5 py-0.5 text-[10px] text-subtle"
                              title="Not built yet"
                            >
                              Soon
                            </span>
                          )}
                        </>
                      )}
                    </NavLink>
                  </li>
                ))}
            </ul>
          </div>
        ))}
      </nav>

      <div className="shrink-0 border-t border-border-hair p-3">
        <div className="flex items-center gap-3 rounded-xl bg-background-alt/70 px-3 py-3">
          <span
            className="grid size-9 shrink-0 place-items-center rounded-full bg-linear-to-br from-brand to-brand-deep text-xs font-semibold text-white shadow-accent"
            aria-hidden="true"
          >
            {(user?.full_name ?? user?.email ?? '?').charAt(0).toUpperCase()}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">
              {user?.full_name ?? user?.email ?? 'Signed in'}
            </span>
            <span className="block truncate text-[11px] text-subtle">
              {user?.email ? `${user.email} · ` : ''}{roleLabel(user?.role)}
            </span>
          </span>
        </div>

        <button
          type="button"
          onClick={() => void logout()}
          className="mt-1.5 flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-muted transition-colors duration-200 ease-standard hover:bg-signal-down/10 hover:text-signal-down"
        >
          <LogOut className="size-[18px]" />
          Logout
        </button>
      </div>
    </div>
  )
}
