/**
 * Dashboard chrome: fixed sidebar on desktop, slide-over drawer on mobile,
 * sticky top header. Uses the same tokens, radii and hover behaviour as the
 * public site.
 */

import { useEffect, useState } from 'react'

import { Icon } from '@/components/Icon'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Sidebar } from '@/components/dashboard/Sidebar'

interface DashboardLayoutProps {
  title: string
  children: React.ReactNode
}

export function DashboardLayout({ title, children }: DashboardLayoutProps) {
  const [drawerOpen, setDrawerOpen] = useState(false)

  // Close the drawer on Escape.
  useEffect(() => {
    if (!drawerOpen) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setDrawerOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [drawerOpen])

  return (
    <div className="min-h-screen bg-background">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 lg:block">
        <Sidebar />
      </aside>

      {/* Mobile drawer */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            onClick={() => setDrawerOpen(false)}
            className="absolute inset-0 bg-black/50 backdrop-blur-[2px]"
          />
          <div className="absolute inset-y-0 left-0 w-72 max-w-[85vw]">
            <Sidebar onNavigate={() => setDrawerOpen(false)} />
          </div>
        </div>
      )}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 border-b border-border-hair bg-background/85 backdrop-blur-md">
          <div className="flex h-16 items-center gap-3 px-5 sm:px-8">
            <button
              type="button"
              onClick={() => setDrawerOpen(true)}
              aria-label="Open navigation"
              className="grid size-9 shrink-0 place-items-center rounded-card border border-border-hair text-muted transition-colors hover:border-accent hover:text-accent-text lg:hidden"
            >
              <Icon name="menu" className="size-[18px]" />
            </button>

            <h1 className="min-w-0 flex-1 truncate text-sm font-semibold sm:text-base">
              {title}
            </h1>

            <ThemeToggle />
          </div>
        </header>

        <main className="px-5 py-8 sm:px-8 sm:py-10">
          <div className="mx-auto max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  )
}
