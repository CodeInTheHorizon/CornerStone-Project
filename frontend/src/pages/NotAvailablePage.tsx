/**
 * Honest placeholder for routes the navbar links to but that do not exist yet.
 *
 * The landing page spec requires Login/Register/dashboard entry points, and
 * authentication lands in Phase 3. Rather than silently redirecting away or
 * faking a login screen, these routes say plainly what is not built yet.
 */

import { Link, useLocation } from 'react-router-dom'

import { Button } from '@/components/Button'
import { Footer } from '@/components/Footer'
import { Navbar } from '@/components/Navbar'

const labels: Record<string, string> = {
  '/login': 'Login',
  '/register': 'Register',
  '/dashboard': 'Dashboard',
}

export function NotAvailablePage() {
  const { pathname } = useLocation()
  const label = labels[pathname] ?? 'This page'

  return (
    <>
      <Navbar />

      <main className="mx-auto flex min-h-[70vh] max-w-shell flex-col justify-center px-6 pt-24 pb-16">
        <p className="text-xs font-semibold tracking-[0.18em] text-accent-text uppercase">
          Not built yet
        </p>
        <h1 className="mt-4 max-w-2xl text-4xl font-semibold sm:text-5xl">
          {label} is coming in a later phase
        </h1>
        <p className="mt-4 max-w-xl leading-relaxed text-muted">
          MarketPulse AI is being built in phases. The public landing page is
          complete; accounts and the dashboard arrive with the authentication
          phase.
        </p>

        <div className="mt-9 flex flex-wrap gap-3">
          <Button as="a" href="/">
            Back to home
          </Button>
          <Link
            to="/status"
            className="inline-flex items-center rounded-card border border-border-strong px-5 py-2.5 text-sm font-medium transition-colors hover:border-accent hover:text-accent-text"
          >
            System status
          </Link>
        </div>
      </main>

      <Footer />
    </>
  )
}
