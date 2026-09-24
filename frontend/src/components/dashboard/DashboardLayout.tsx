import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ChevronRight, Search } from 'lucide-react'

import { can } from '@/auth/permissions'
import { Icon } from '@/components/Icon'
import { ThemeToggle } from '@/components/ThemeToggle'
import { AccountMenu } from '@/components/dashboard/AccountMenu'
import { GlobalSearch } from '@/components/dashboard/GlobalSearch'
import { NotificationBell } from '@/components/dashboard/NotificationBell'
import { Sidebar } from '@/components/dashboard/Sidebar'
import { dashboardNav } from '@/config/dashboard'
import { useAuth } from '@/hooks/useAuth'

interface DashboardLayoutProps {
  title: string
  subtitle?: string
  children: React.ReactNode
}

function Breadcrumbs({ pathname }: { pathname: string }) {
  const navItem = dashboardNav.find((item) => item.to === pathname)
  if (pathname === '/dashboard' || !navItem) return null

  return (
    <nav aria-label="Breadcrumb" className="hidden items-center gap-1.5 text-xs text-subtle sm:flex">
      <Link to="/dashboard" className="transition-colors hover:text-accent-text">
        Dashboard
      </Link>
      <ChevronRight className="size-3" />
      <span className="font-medium text-foreground">{navItem.label}</span>
    </nav>
  )
}

export function DashboardLayout({ title, subtitle, children }: DashboardLayoutProps) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const { user } = useAuth()
  const { pathname } = useLocation()
  const context = subtitle ?? dashboardNav.find((item) => item.to === pathname)?.description

  const drawer = useRef<HTMLDivElement>(null)
  const opener = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!drawerOpen) return
    const returnFocus = opener.current
    const oldOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const focusable = () => Array.from(drawer.current?.querySelectorAll<HTMLElement>('a[href], button:not(:disabled)') ?? [])
    focusable()[0]?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setDrawerOpen(false)
      if (event.key !== 'Tab') return
      const items = focusable()
      const first = items[0], last = items.at(-1)
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    const onResize = () => { if (window.innerWidth >= 1024) setDrawerOpen(false) }
    window.addEventListener('keydown', onKey)
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('resize', onResize)
      document.body.style.overflow = oldOverflow
      returnFocus?.focus()
    }
  }, [drawerOpen])

  return (
    <div className="workspace page-canvas min-h-screen text-foreground">
      <aside inert={drawerOpen} className="fixed inset-y-0 left-0 z-40 hidden w-64 lg:block">
        <Sidebar />
      </aside>

      {drawerOpen && (
        <div ref={drawer} id="mobile-navigation" role="dialog" aria-modal="true" aria-label="Dashboard navigation" className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            onClick={() => setDrawerOpen(false)}
            className="absolute inset-0 bg-black/50 backdrop-blur-[2px]"
          />
          <div className="workspace-drawer absolute inset-y-0 left-0 w-72 max-w-[85vw] shadow-pop">
            <Sidebar onNavigate={() => setDrawerOpen(false)} />
          </div>
        </div>
      )}

      <div inert={drawerOpen} className="min-w-0 lg:pl-64">
        <header className="sticky top-0 z-30 border-b border-surface-glass-border glass-card !rounded-none">
          <div className="mx-auto flex h-16 max-w-[1360px] items-center gap-3 px-4 sm:px-8">
            <button
              type="button"
              onClick={() => setDrawerOpen(true)}
              ref={opener}
              aria-label="Open navigation"
              aria-expanded={drawerOpen}
              aria-controls="mobile-navigation"
              className="grid size-9 shrink-0 place-items-center rounded-card border border-border-hair bg-surface text-muted transition-colors duration-200 ease-standard hover:border-accent hover:text-accent-text lg:hidden"
            >
              <Icon name="menu" className="size-[18px]" />
            </button>

            <div className="min-w-0 flex-1">
              <Breadcrumbs pathname={pathname} />
              <h1 className="truncate text-[15px] font-semibold tracking-tight sm:text-base">{title}</h1>
              {context && <p className="hidden truncate text-xs text-subtle sm:block">{context}</p>}
            </div>

            <div className="hidden items-center gap-1.5 rounded-full border border-border-hair bg-background-alt/60 px-3 py-1.5 text-sm text-muted transition-colors hover:border-accent/40 md:flex">
              <Search className="size-3.5" />
              <span className="text-xs">Search...</span>
              <kbd className="ml-2 rounded border border-border-hair bg-surface px-1.5 py-0.5 text-[10px] font-medium text-subtle">
                Ctrl K
              </kbd>
            </div>

            {can(user, 'prediction:run') && pathname !== '/dashboard/predictor' && pathname !== '/dashboard' && (
              <Link
                to="/dashboard/predictor"
                className="inline-flex shrink-0 items-center gap-2 rounded-full bg-accent px-2.5 py-2 text-sm font-medium text-accent-ink shadow-accent transition-colors duration-200 ease-standard hover:bg-accent-hover sm:px-3.5"
              >
                <Icon name="compass" className="size-4" />
                <span className="sr-only sm:not-sr-only">Run prediction</span>
              </Link>
            )}

            <NotificationBell />

            <ThemeToggle className="shrink-0 bg-surface" />
            <AccountMenu />
          </div>
        </header>

        <main className="px-4 py-6 sm:px-8 sm:py-8">
          <div className="mx-auto min-w-0 max-w-[1296px]">{children}</div>
        </main>
      </div>

      <GlobalSearch />
    </div>
  )
}
